# RFC 0011 measurement targets: ink rows at real zoom, 17 November 2026

Fidelity lane, for build-with-div/div RFC 0011 (layout in device pixels),
stage 2.

## Source

- **Selection:** the 65 "ink" rows of the fidelity lane's routing list
  (border, shadow, background, image, radius, svg and box-decoration
  tests). That list was built under the emulated oracle (main `8871c13`).
  Every row in it was exact at 1x and different only above 1x.
- **Census:** these rows re-measured on the real-zoom census
  `div-fidelity-expanded-opacity-929a`. Div is `929ae81`, the fidelity data
  is `c82502d`, and the oracle is Chromium with
  `--force-device-scale-factor` (RFC 0010).
- **Classifier:** `rfc-0011-real-zoom-classes-2026-11-16/classify.py`,
  from this repository at `ae10ca8`, unchanged.

## File

`ink-targets.json` holds one entry per row that still differs: 64 of 65.
The one exact row is `css_overflow/paint-containment-svg` at 1.25x.

Each entry carries:
- the classifier's pixel classes (`diff`, `geometry`, `edge`, `div_blend`,
  `chromium_blend`, `both_blend`, `both_crisp`, `max_delta`);
- the row class:
  - `edge-only` (no geometry pixel);
  - `geometry<50%`;
  - `geometry>=50%`;
- the 1x status of the same test (exact for every row);
- the emulated status from `ae10ca8` (different for every row);
- a routing field.

| Class | Rows | Routing |
| --- | --- | --- |
| edge-only | 45 | RFC 0011 target. Within a device pixel of an edge in both frames, so device-pixel paint snapping could fix it alone. |
| geometry<50% | 17 | RFC 0011 target. `background-clip_clip-border-area-ref` at 1.25x is 48% geometry. 16 rows are 4–11% geometry, mostly Div-blends: 12 `box-decoration-break-clone`, 2 `ttwf-css3background-border-style`, `background-334`, `box-shadow-041`. These are likely snapping plus device-pixel border widths. |
| geometry>=50% | 2 | `border-image-repeat-005` at 1.25x (69%) and 1.5x (93%). Routing is pending a fidelity read of the test source: border-image tiling (paint) or device-pixel lengths (engine). |

The fidelity lane does not claim these rows. Separately, 13 ink rows
differ at 1x in other tests. Those are fidelity work and are tracked in
the fidelity lane.
