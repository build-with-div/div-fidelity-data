#!/usr/bin/env python3
"""Build rows.json for dsf_oracle_compare.py.

Probe pages: the fractional-edges spec, written with the capture tool's own
document() at 120x80. Census rows: ids that are exact at 1x and 2x but
differ at 1.25x and/or 1.5x in the base census summary, using the census's
own test.html and font profile, with flags taken from the matrix's manifests.

    python3 build_rows.py <div checkout> <expanded-summary.json>         <offgrid rows csv> <out dir> [all|probe|one] [<census oracle cache dir>]

The off-grid CSV (id,profile,off_grid_values,values) is the engine's list
of 205 layout-zoom candidates; its ids are recorded in rows-fractional.json.
"""

import csv
import importlib.util
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])          # Div checkout (census clone)
summary = Path(sys.argv[2])       # base expanded-summary.json
results_dir = summary.parent      # holds <profile>/<id>/test.html
offgrid_csv = Path(sys.argv[3])   # engine's 205 layout-zoom candidates
out = Path(sys.argv[4])           # directory for rows and probe pages
mode = sys.argv[5] if len(sys.argv) > 5 else "all"
oracle_cache = Path(sys.argv[6]) if len(sys.argv) > 6 else None  # census --cache-dir

spec = importlib.util.spec_from_file_location(
    "cap", root / "tools/qualification/capture_fractional_edges_oracle.py")
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)
h_spec = importlib.util.spec_from_file_location(
    "h", root / "tools/accountability/run_all_pixel_comparisons.py")
sys.path.insert(0, str(root / "tools/accountability"))
h = importlib.util.module_from_spec(h_spec)
h_spec.loader.exec_module(h)


def ids(path):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    text = path.read_text()
    try:
        data = json.loads(text)
        return set(data if isinstance(data, list) else data.get("ids", data.get("tests", [])))
    except json.JSONDecodeError:
        return {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}


freetype = ids(h.FREETYPE_TEXT_LIST)
sp18 = ids(h.SP18_TARGET_LIST)

rows = []
probe_dir = out / "probe"
probe_dir.mkdir(parents=True, exist_ok=True)
for name, boxes in cap.pages().items():
    page = probe_dir / f"{name}.html"
    page.write_text(cap.document(boxes), encoding="utf-8")
    for scale in ["1.25", "1.5"]:
        rows.append({"key": f"probe/{name}@{scale}", "html": str(page), "width": 120,
                     "height": 80, "scale": scale, "font_profile": "deterministic-test-collection",
                     "census_png": str(cap.EVIDENCE / f"{name}-{scale}.png")})

data = json.loads(summary.read_text())
by_id = {}
profiles = {}
for prof in data["profiles"]:
    name = prof["profile"]
    profiles[name] = prof
    for t in prof["tests"]:
        by_id.setdefault(t.get("test_id") or t.get("id"), {})[name] = t
fractional = ["desktop-1280x720@1.25", "desktop-1920x1080@1.5"]
integer = ["legacy-800x600@1", "mobile-375x667@2"]
only_fractional = sorted(
    i for i, p in by_id.items()
    if all(p.get(n, {}).get("status") == "exact" for n in integer)
    and any(p.get(n, {}).get("status") == "different" for n in fractional))
print("ids failing only at 1.25/1.5:", len(only_fractional), file=sys.stderr)

offgrid = []
with offgrid_csv.open() as f:
    for r in csv.DictReader(f):
        offgrid.append((r["id"], r["profile"]))


def pick(predicate, count):
    chosen = [i for i in only_fractional if predicate(i)]
    step = max(1, len(chosen) // count)
    return chosen[::step][:count]


split = pick(lambda i: i.startswith("wpt/css_break/") and "table" not in i, 10)
tables = pick(lambda i: "table" in i, 10)
offgrid_ids = []
seen = set(split) | set(tables)
for i, _ in offgrid[:: max(1, len(offgrid) // 14)]:
    if i not in seen and i in only_fractional:
        offgrid_ids.append(i)
        seen.add(i)
    if len(offgrid_ids) == 10:
        break

profile_size = {"desktop-1280x720@1.25": (1280, 720, "1.25"),
                "desktop-1920x1080@1.5": (1920, 1080, "1.5")}
for group, chosen in [("split", split), ("table", tables), ("offgrid", offgrid_ids)]:
    for test_id in chosen:
        for name in fractional:
            t = by_id[test_id].get(name)
            if not t or t["status"] != "different":
                continue
            w, hgt, scale = profile_size[name]
            rows.append({"key": f"{group}/{test_id}@{scale}",
                         "html": str(results_dir / name / test_id / "test.html"),
                         "width": w, "height": hgt, "scale": scale,
                         "font_profile": t["font_profile"],
                         "freetype": test_id in freetype, "sp18": test_id in sp18,
                         "census_png": str(oracle_cache / t["chromium_png_cache_path"])
                         if oracle_cache and t.get("chromium_png_cache_path") else None})

if mode == "probe":
    rows = [r for r in rows if r["key"].startswith("probe/")]
elif mode == "one":
    rows = rows[:1] + [r for r in rows if not r["key"].startswith("probe/")][:1]
(out / f"rows-{mode}.json").write_text(json.dumps(rows, indent=1))
print(len(rows), "rows;", sum(1 for r in rows if r["key"].startswith("probe/")), "probe",
      file=sys.stderr)
