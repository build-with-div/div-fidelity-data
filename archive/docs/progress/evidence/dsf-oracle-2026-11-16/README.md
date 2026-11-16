# CDP-emulated DSF vs --force-device-scale-factor (16 November 2026)

The measurement behind RFC 0010 (`docs/alpha/rfcs/0010-real-zoom-oracle.md`
in build-with-div/div). It was taken on Linux (WSL), with pinned Chrome
147.0.7727.50 run through the census harness's launcher, font environment
and CDP client (`tools/accountability/run_all_pixel_comparisons.py` at
main da4f1e6).

- `cdp`: the census oracle. `Emulation.setDeviceMetricsOverride` with
  `deviceScaleFactor` set to the scale, and the window sized to the
  physical frame.
- `forced`: the same launch plus `--force-device-scale-factor=<scale>`, with
  the viewport size set by `Emulation.setDeviceMetricsOverride`
  `{width, height, deviceScaleFactor: 0}`. A `deviceScaleFactor` of 0 keeps
  the forced DSF.

A pair is `identical` when the RGBA frames match. Otherwise it is
`layout` when any element's `getBoundingClientRect`, `getClientRects`,
offset, scroll or client size differs, and `paint` when they are equal.

| File | Content |
| --- | --- |
| `rows-fractional.json`, `results-fractional.json` | 49 frames at 1.25x and 1.5x: the 5 fractional-edges probe pages and 30 census ids that are exact at 1x and 2x but differ at 1.25x and/or 1.5x (10 split boxes, 10 tables, 10 from `offgrid-rows.csv`). Result: 1 identical, 27 paint, 21 layout. `cdp_matches_census` is true for all 49. |
| `rows-integer.json`, `results-integer.json` | The same ids at 1x and 2x. Result: 1x all 35 identical; 2x 29 identical, 4 paint, 2 layout. |
| `no-override.txt` | `forced` with no CDP override at all (window sized in DIPs) against `forced` with the size override, for the 10 probe frames: 0 differing pixels in each. |
| `calibrate.py` | Why the window alone can't size the viewport: at 1.25x, 1278 and 1279 DIP windows give 1279.2 and 1281.6 CSS px. |
| `dsf_oracle_compare.py`, `build_rows.py`, `no_override_check.py` | The scripts. |

In the row files, `census:<profile>/<id>/test.html` is the census's own page
for that row. `probe/<name>.html` is written by `build_rows.py` from
`tests/fidelity/fixtures/fractional-edges-v1/pages.txt`.
