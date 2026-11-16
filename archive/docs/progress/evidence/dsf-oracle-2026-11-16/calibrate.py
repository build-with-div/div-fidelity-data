import sys, json, tempfile, subprocess, urllib.request, os
from contextlib import ExitStack
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import dsf_oracle_compare as d
h = d.load_harness(Path(sys.argv[1])); chrome = Path(sys.argv[2])
page = sys.argv[3]
for scale, ws in [(sc,(w,hh)) for sc,ws_,hh in [("1.25",[1277,1278,1279,1281],861),("1.5",[1917,1918,1919,1921],1223)] for w in ws_]:
    env = h.chrome_environment(str(chrome.parent))
    with tempfile.TemporaryDirectory() as pd, ExitStack() as rt:
        cmd = [str(chrome), "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run", "--no-default-browser-check",
               "--remote-debugging-port=0", f"--user-data-dir={pd}", f"--force-device-scale-factor={scale}", f"--window-size={ws[0]},{ws[1]}", "about:blank"]
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        rt.callback(h._stop_chromium_process, p)
        port = h._wait_for_devtools_endpoint(pd, p)
        c = h._CdpWebSocket(h._page_websocket_url(port)); rt.callback(h._close_chromium_client, c)
        c.command("Page.enable")
        c.command("Page.navigate", {"url": "file:" + urllib.request.pathname2url(page)})
        m = d.evaluate(c, d.READY_JS, True)
        o = d.evaluate(c, "JSON.stringify([outerWidth, outerHeight, visualViewport.width, visualViewport.height, screen.width, screen.height])")
        print(scale, ws, m, o, flush=True)
