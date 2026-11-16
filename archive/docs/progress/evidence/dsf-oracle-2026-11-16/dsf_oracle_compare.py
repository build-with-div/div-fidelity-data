#!/usr/bin/env python3
"""Compare pinned Chromium 147 frames under two device-scale methods.

Method `cdp` is the census oracle: tools/accountability/run_all_pixel_comparisons.py
render_chrome, i.e. headless Chromium whose page DSF and viewport come from CDP
Emulation.setDeviceMetricsOverride (host window DPR 1).

Method `forced` launches the same binary with the same font environment and
flags, but sets the DSF with --force-device-scale-factor=<scale>. Its CDP
override sets only the viewport size, with deviceScaleFactor 0, which keeps
the browser's own (forced) DSF: headless window sizing snaps to device pixels
and cannot give an exact 1280x720 viewport at 1.25x (a 1278 or 1279 DIP window
gives 1279.2 or 1281.6 CSS px). If innerWidth/innerHeight/devicePixelRatio do
not match the profile, the row is reported as a viewport mismatch.

For each page and method the script records the RGBA frame (PNG decoded),
devicePixelRatio, innerWidth/innerHeight and the layout geometry of every
element (getBoundingClientRect and getClientRects, in CSS px, unrounded). A pair
is `identical` when the RGBA bytes match; otherwise it is `layout` when any
geometry differs and `paint` when the geometry is equal.

Usage (Linux, from a Div checkout whose fonts and fidelity data are restored):
    python3 dsf_oracle_compare.py --root <div checkout> --chrome <chrome> \
        --rows rows.json --out <dir> [--window-extra-height N]
rows.json: [{"key", "html", "width", "height", "scale", "font_profile",
             "freetype", "sp18", "census_png"?}]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import ExitStack
from pathlib import Path

GEOMETRY_JS = r"""
(() => {
  const out = [];
  const all = document.querySelectorAll('*');
  for (let i = 0; i < all.length; i++) {
    const e = all[i];
    const b = e.getBoundingClientRect();
    const rects = Array.from(e.getClientRects()).map(r => [r.x, r.y, r.width, r.height]);
    out.push([i, e.tagName, [b.x, b.y, b.width, b.height], rects,
              e.offsetWidth ?? null, e.offsetHeight ?? null,
              e.scrollWidth, e.scrollHeight, e.clientWidth, e.clientHeight]);
  }
  return JSON.stringify(out);
})()
"""

READY_JS = (
    "new Promise(resolve => {"
    "const done = () => document.fonts.ready.then(() => "
    "requestAnimationFrame(() => requestAnimationFrame(resolve)));"
    "if (document.readyState === 'complete') done();"
    "else addEventListener('load', done, {once:true});"
    "}).then(() => ({width:innerWidth,height:innerHeight,dpr:devicePixelRatio}))"
)


def load_harness(root: Path):
    path = root / "tools/accountability/run_all_pixel_comparisons.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("run_all_pixel_comparisons", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(client, expression, await_promise=False):
    result = client.command(
        "Runtime.evaluate",
        {"expression": expression, "awaitPromise": await_promise, "returnByValue": True},
    )
    return result.get("result", {}).get("value")


def screenshot(client) -> bytes:
    options = {"format": "png", "fromSurface": True, "captureBeyondViewport": False}
    frames = []
    for _ in range(5):
        frames.append(client.command("Page.captureScreenshot", options).get("data"))
        if len(frames) >= 2 and frames[-1] == frames[-2]:
            return base64.b64decode(frames[-1])
        time.sleep(0.5)
    raise RuntimeError("no two consecutive identical screenshots")


def capture(h, row, method, chrome: Path, extra_height: int):
    width, height, scale = int(row["width"]), int(row["height"]), float(row["scale"])
    use_real_font = row["font_profile"] == "registered-real-font"
    use_ahem = row["font_profile"] == "registered-ahem"
    env = h.chrome_environment(str(chrome.parent), use_ahem, use_real_font)
    with tempfile.TemporaryDirectory(prefix="dsf-oracle-") as profile_dir, ExitStack() as runtime:
        cmd = [str(chrome), "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run",
               "--no-default-browser-check", "--remote-debugging-port=0",
               f"--user-data-dir={profile_dir}"]
        if method == "cdp":
            cmd.append(f"--window-size={int(width * scale + 0.5)},{int(height * scale + 0.5) + 87}")
        else:
            cmd += [f"--force-device-scale-factor={row['scale']}",
                    f"--window-size={max(width, 500) + 16},{max(height, 300) + 160 + extra_height}"]
        if row.get("sp18"):
            cmd.append(f"--enable-blink-features={h.SP18_BLINK_FEATURES}")
        if use_real_font or row.get("freetype"):
            cmd.append("--enable-features=FontDataServiceLinux:typeface/Freetype")
        cmd.append("about:blank")
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        runtime.callback(h._stop_chromium_process, process)
        port = h._wait_for_devtools_endpoint(profile_dir, process)
        client = h._CdpWebSocket(h._page_websocket_url(port))
        runtime.callback(h._close_chromium_client, client)
        client.command("Page.enable")
        if method == "cdp":
            client.command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": scale,
                "mobile": False, "screenWidth": width, "screenHeight": height})
        else:
            # Viewport size only: deviceScaleFactor 0 keeps the browser's own
            # (forced) DSF. Headless window sizing snaps to device pixels and
            # cannot give an exact 1280x720 viewport at 1.25x.
            client.command("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 0,
                "mobile": False, "screenWidth": width, "screenHeight": height})
        url = "file:" + urllib.request.pathname2url(os.path.abspath(row["html"]))
        client.command("Page.navigate", {"url": url})
        metrics = evaluate(client, READY_JS, await_promise=True)
        geometry = json.loads(evaluate(client, GEOMETRY_JS))
        png = screenshot(client)
    return metrics, geometry, png


def rgba(png: bytes):
    from PIL import Image
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    return image.size, image.tobytes()


def geometry_diff(a, b):
    if len(a) != len(b):
        return f"element count {len(a)} vs {len(b)}"
    for x, y in zip(a, b):
        if x != y:
            return f"{x[1]}#{x[0]}: cdp {x[2:]} forced {y[2:]}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--window-extra-height", type=int, default=0)
    parser.add_argument("--keep-pngs", action="store_true")
    args = parser.parse_args()
    h = load_harness(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for row in json.loads(args.rows.read_text()):
        entry = {"key": row["key"], "scale": row["scale"]}
        try:
            m_cdp, g_cdp, p_cdp = capture(h, row, "cdp", args.chrome, args.window_extra_height)
            m_forced, g_forced, p_forced = capture(
                h, row, "forced", args.chrome, args.window_extra_height)
        except Exception as error:  # noqa: BLE001 - report and continue
            entry["status"] = f"error: {error}"
            results.append(entry)
            print(json.dumps(entry), flush=True)
            continue
        safe = row["key"].replace("/", "_")
        if args.keep_pngs:
            (args.out / f"{safe}-cdp.png").write_bytes(p_cdp)
            (args.out / f"{safe}-forced.png").write_bytes(p_forced)
        entry["metrics"] = {"cdp": m_cdp, "forced": m_forced}
        size_c, px_c = rgba(p_cdp)
        size_f, px_f = rgba(p_forced)
        if row.get("census_png") and os.path.isfile(row["census_png"]):
            entry["cdp_matches_census"] = rgba(Path(row["census_png"]).read_bytes()) == (size_c, px_c)
        entry["size"] = {"cdp": size_c, "forced": size_f}
        geometry = geometry_diff(g_cdp, g_forced)
        entry["geometry_equal"] = geometry is None
        if geometry:
            entry["first_geometry_difference"] = geometry[:400]
            entry["geometry_differences"] = sum(1 for x, y in zip(g_cdp, g_forced) if x != y)
        if any((m or {}).get("width") != int(row["width"])
               or (m or {}).get("height") != int(row["height"])
               or abs((m or {}).get("dpr", 0) - float(row["scale"])) > 1e-6
               for m in (m_cdp, m_forced)):
            entry["status"] = "viewport-mismatch"
        elif size_c == size_f and px_c == px_f:
            entry["status"] = "identical"
        else:
            entry["status"] = "layout" if geometry else "paint"
            if size_c == size_f:
                entry["differing_pixels"] = sum(
                    1 for i in range(0, len(px_c), 4) if px_c[i:i + 4] != px_f[i:i + 4])
        entry["png_sha256"] = {"cdp": hashlib.sha256(p_cdp).hexdigest(),
                               "forced": hashlib.sha256(p_forced).hexdigest()}
        results.append(entry)
        print(json.dumps(entry), flush=True)
    (args.out / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    counts: dict[str, int] = {}
    for entry in results:
        status = entry["status"].split(":")[0]
        counts[status] = counts.get(status, 0) + 1
    print("summary", json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
