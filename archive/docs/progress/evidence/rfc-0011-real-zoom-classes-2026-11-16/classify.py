"""Classify real-zoom census rows for RFC 0011 sizing.

For every non-1x census row that differs at the real-zoom oracle, load
Chromium's and Div's PNGs from the shared cache and split the differing
pixels:

- geometry: the pixel is flat (its 3x3 neighbourhood is one colour) in both
  images, so both engines paint a solid area there, in different colours:
  a box is in a different place or has a different size by at least a
  device pixel.
- edge: every other differing pixel, within a pixel of an edge in at least
  one image: anti-aliasing, edge placement within a pixel, or glyphs.

Edge pixels are split again by what each engine paints there:

- div_blend: Chromium's pixel is an endpoint colour (it equals a flat
  neighbour) and Div's is not: Div anti-aliases an edge that Chromium
  snapped to the device pixel grid.
- chromium_blend: the reverse.
- both_blend / both_crisp: the rest.

A row is "geometry" when at least half its differing pixels are geometry
pixels, as in the fidelity lane's routing heuristic, else "edge".

usage: classify.py <base-summary> <head-summary> <cache-dir> <out.json>
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

CACHE: Path


def load(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.int16)


def neighbours(img: np.ndarray):
    padded = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = img.shape[:2]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                yield padded[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]


def flat(img: np.ndarray) -> np.ndarray:
    out = np.ones(img.shape[:2], dtype=bool)
    for n in neighbours(img):
        out &= (n == img).all(axis=2)
    return out


def endpoint(img: np.ndarray, flat_mask: np.ndarray) -> np.ndarray:
    """The pixel equals some neighbour that is itself flat."""
    padded = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="edge")
    padded_flat = np.pad(flat_mask, 1, mode="edge")
    h, w = img.shape[:2]
    out = flat_mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                n = padded[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]
                nf = padded_flat[1 + dy : 1 + dy + h, 1 + dx : 1 + dx + w]
                out |= nf & (n == img).all(axis=2)
    return out


def classify(job):
    key, chromium_rel, div_rel = job
    try:
        c = load(CACHE / chromium_rel)
        d = load(CACHE / div_rel)
    except Exception as error:  # noqa: BLE001
        return key, {"error": str(error)}
    if c.shape != d.shape:
        return key, {"error": f"shape {c.shape} vs {d.shape}"}
    diff = (c != d).any(axis=2)
    total = int(diff.sum())
    fc, fd = flat(c), flat(d)
    geometry = diff & fc & fd
    edge = diff & ~geometry
    ec, ed = endpoint(c, fc), endpoint(d, fd)
    result = {
        "diff": total,
        "geometry": int(geometry.sum()),
        "edge": int(edge.sum()),
        "div_blend": int((edge & ec & ~ed).sum()),
        "chromium_blend": int((edge & ~ec & ed).sum()),
        "both_blend": int((edge & ~ec & ~ed).sum()),
        "both_crisp": int((edge & ec & ed).sum()),
        "max_delta": int(np.abs(c - d).max()) if total else 0,
    }
    return key, result


def rows(summary: Path):
    data = json.loads(summary.read_text(encoding="utf-8"))
    return {
        (profile["profile"], test["id"]): test
        for profile in data["profiles"]
        for test in profile["tests"]
    }


def main() -> int:
    global CACHE
    base_path, head_path, cache, out = map(Path, sys.argv[1:5])
    CACHE = cache
    base, head = rows(base_path), rows(head_path)
    jobs = []
    meta = {}
    for key, test in head.items():
        profile, test_id = key
        if profile == "legacy-800x600@1" or test["status"] == "exact":
            continue
        old = base.get(key, {}).get("status")
        meta[f"{profile}|{test_id}"] = {"old": old, "new": test["status"]}
        if test["status"] != "different":
            continue
        jobs.append(
            (f"{profile}|{test_id}", test["chromium_png_cache_path"], test["openui_png_cache_path"])
        )
    results = {}
    with ProcessPoolExecutor(max_workers=8, initializer=_init, initargs=(cache,)) as pool:
        for key, result in pool.map(classify, jobs, chunksize=8):
            results[key] = {**meta[key], **result}
    for key, value in meta.items():
        results.setdefault(key, value)
    Path(out).write_text(json.dumps(results, indent=0, sort_keys=True), encoding="utf-8")
    print(f"{len(jobs)} rows classified, {len(results)} rows written")
    return 0


def _init(cache):
    global CACHE
    CACHE = Path(cache)


if __name__ == "__main__":
    raise SystemExit(main())
