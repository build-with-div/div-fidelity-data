"""Probe pages under --force-device-scale-factor with no CDP override at all,
cropped to the probe's 120x80 CSS frame, against the forced+viewport-override
frame and the census (CDP) fixture."""
import io, sys, os, tempfile, subprocess, urllib.request
from contextlib import ExitStack
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsf_oracle_compare as d
from PIL import Image
h = d.load_harness(Path(sys.argv[1])); chrome = Path(sys.argv[2]); here = Path(__file__).resolve().parent
windows = {"1.25": (1278, 861), "1.5": (1919, 1223)}
for page in sorted((here / "probe").glob("*.html")):
    for scale, ws in windows.items():
        env = h.chrome_environment(str(chrome.parent))
        with tempfile.TemporaryDirectory() as pd, ExitStack() as rt:
            cmd = [str(chrome), "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run", "--no-default-browser-check",
                   "--remote-debugging-port=0", f"--user-data-dir={pd}", f"--force-device-scale-factor={scale}",
                   f"--window-size={ws[0]},{ws[1]}", "about:blank"]
            p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            rt.callback(h._stop_chromium_process, p)
            c = h._CdpWebSocket(h._page_websocket_url(h._wait_for_devtools_endpoint(pd, p))); rt.callback(h._close_chromium_client, c)
            c.command("Page.enable"); c.command("Page.navigate", {"url": "file:" + urllib.request.pathname2url(str(page))})
            m = d.evaluate(c, d.READY_JS, True); png = d.screenshot(c)
        s = float(scale); box = (0, 0, round(120 * s), round(80 * s))
        crop = Image.open(io.BytesIO(png)).convert("RGB").crop(box)
        key = f"probe_{page.stem}@{scale}"
        forced = Image.open(here / "run1" / f"{key}-forced.png").convert("RGB")
        cdp = Image.open(here / "run1" / f"{key}-cdp.png").convert("RGB")
        def diff(a, b): return sum(1 for x, y in zip(a.getdata(), b.getdata()) if x != y)
        print(page.stem, scale, m, "vs forced+viewport:", diff(crop, forced), "vs cdp:", diff(crop, cdp), flush=True)
