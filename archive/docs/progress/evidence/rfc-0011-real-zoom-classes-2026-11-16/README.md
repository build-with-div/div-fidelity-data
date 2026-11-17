# RFC 0011 sizing: real-zoom census and coverage rows by difference class, 16 November 2026

Evidence for RFC 0011 (layout in device pixels at scales other than 1),
build-with-div/div. Files: `classify.py` (the classifier), `census-classes.json`
and `coverage-classes.json` (one entry per non-exact non-1x row: old and new
status and, for differing rows, the pixel classes), `sample0.png` to
`sample2.png` (crops). Run as
`python classify.py <base-summary> <head-summary> <oracle-cache-dir> <out.json>`.

Base: emulated run `fidelity-expanded-main-da4f` (Div a9e9a46e). Head: real-zoom run
`fidelity-expanded-zoom` (Div 19269a7f, Chromium forced DSF). Div's frames are
byte-identical in the two runs, so every newly different row is the oracle
moving. Classifier: `classify.py` (this folder). It reads the cached PNGs and
splits each row's differing pixels into:
- geometry: pixels flat in both images;
- edge, split by which engine blends:
  - Div blends where Chromium paints an endpoint colour;
  - Chromium blends where Div does;
  - mixed.

A row takes the class of at least half its differing pixels.

## Newly different at real zoom (exact under emulation): 6,277 rows

| Profile | Div blends, Chromium crisp | Mixed (incl. both crisp, offset) | Chromium blends | Geometry |
| --- | --- | --- | --- | --- |
| 1.25x | 2,765 | 382 | 12 | 12 |
| 1.5x | 1,642 | 823 | 9 | 13 |
| 2x | 21 | 520 | 67 | 11 |
| Total | 4,428 | 1,725 | 88 | 36 |

Medians of differing pixels per row:
- Div-blends: 750 at 1.25x, 2,044 at 1.5x;
- mixed: 3,824 at 1.25x, 2,216 at 1.5x, 1,334 at 2x;
- geometry: 20,000 to 62,000.

Areas, by row count:
- **Div-blends:** css_flexbox, css_break, css_backgrounds, css_multicol, css_sizing, css_overflow.
- **2x mixed:** css_flexbox 177, css_multicol 97, css_break 67, css_sizing 61.

## Samples (crops in this folder)

- **`sample2.png`:** 1.25x, `css2_floats/crashtests_float-rewind-parallel-flow-2-crash`. A horizontal line: Chromium's edge is crisp on a device pixel, Div blends the bottom edge (fractional device y). This is paint snapping.
- **`sample1.png`:** 2x, `css2_floats/floats-wrap-bfc-outside-001`. Both engines are crisp, but the border and background edges are offset by one device pixel (0.5 CSS px). Div snaps at CSS-pixel granularity, which at 2x is every other device pixel. Chromium snaps per device pixel. This is snapping granularity, so it is likely the bulk of the 2x mixed rows.
- **`sample0.png`:** 2x, the same crash test. The line is 3 device px in Chromium and 6 in Div. This is a thickness difference, not a position difference: a width rule that is device-pixel-dependent (border width, or a length rounded at device scale). It needs the test source.

## Reading for the staged plan

1. Snap painted box edges to device pixels, not CSS pixels. Paint only, no layout change. Candidates: most of the 4,428 Div-blends rows and the 2x crisp-offset rows. Census it alone: its result is the split between paint and layout.
2. Lengths that Chromium resolves in device pixels: border widths (a 1px border is one device pixel, 0.8 CSS px at 1.25x), scrollbar thickness (15.2px at 1.25x), and rounding to the 1/64-device-pixel `LayoutUnit`. Candidates: the geometry rows, and the rows stage 1 leaves.
3. Text at device scale, if the remaining rows are glyphs.

Not yet done:
- the coverage suite;
- reading the BSD-licensed Blink snapping sources (check headers first);
- the test source of `sample0`'s line.

## Text baselines (build-with-div/div#62)

The fidelity lane recaptured the web-font fixtures at real zoom (#62). In 11
of 14 non-exact rows the glyph raster is identical and the baseline is one
device pixel off: real-zoom Blink places baselines in device pixels. Cite #62
in the RFC. This probably also explains the Inter 400 line-box item (baseline
1–2 device px lower at 1.25x, 1.5x and 2x).

## Paint versus layout bound (rows exact under emulation, different at real zoom)

A row with no geometry pixel differs only within about one device pixel of
an edge in both frames. Device-pixel paint snapping could fix it alone; a
sub-device-pixel layout change or a glyph change also looks like this. A row
with geometry pixels has an area displaced by more than about one device
pixel, which snapping (a move of under one device pixel) cannot produce:
that needs layout (lengths resolved in device pixels) or text.

| Profile | No geometry pixel | Geometry < 1% | Geometry 1–50% | Geometry ≥ 50% |
| --- | --- | --- | --- | --- |
| 1.25x | 2,938 | 17 | 204 | 12 |
| 1.5x | 2,165 | 52 | 257 | 13 |
| 2x | 529 | 1 | 78 | 11 |
| Total | 5,632 | 70 | 539 | 36 |

So paint snapping can explain at most 5,632 of 6,277 rows (90%); at least
645 (10%) need layout or text. Stage 1's census gives the exact split.
Rows already different under emulation (1,120) are not counted here.

## CSS Grid coverage (same method; base `coverage-fidelity-main-da4f`, head `coverage-fidelity-zoom`)

771 comparisons exact under emulation differ at real zoom.

| Profile | No geometry pixel | Geometry < 1% | Geometry 1–50% | Geometry ≥ 50% | Div blends | Mixed | Chromium blends |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.25x | 291 | 6 | 49 | 2 | 318 | 26 | 2 |
| 1.5x | 287 | 3 | 53 | 0 | 214 | 128 | 1 |
| 2x | 76 | 0 | 4 | 0 | 0 | 80 | 0 |
| Total | 654 | 9 | 106 | 2 | 532 | 234 | 3 |

Paint snapping bound: at most 654 of 771 (85%); at least 117 need layout or text.

## Blink sources read (local checkout `out/chromium-src` at 09d377d9; BSD headers checked first)

- `core/css/resolver/style_builder_converter.cc` (BSD, Google 2013), `ConvertBorderWidth`: the width is
  `ComputeLength` through `CssToLengthConversionData`, which includes zoom, so under zoom-for-DSF
  it is in device px. A width in (0, 1) becomes 1; otherwise it is floored to an integer. So a border
  is a whole number of device px, at least one: 1px is 1 device px (0.8 CSS px) at 1.25x and
  1 device px (0.667 CSS px) at 1.5x. `ConvertOutlineOffset` does the same for outline offsets.
- `platform/geometry/layout_unit.h` (BSD, Google 2012), `SnapSizeToPixel(size, location)`:
  `round(fraction(location) + size) - round(fraction(location))`, at least 1 for a non-tiny size.
  Applied to `LayoutUnit`s in zoomed (device-px) space, it snaps to device pixels.
- `core/layout/geometry/physical_rect.h` (BSD, Chromium 2017), `ToPixelSnappedRect`: snapped offset
  plus `PixelSnappedSize`, i.e. the rule above for both axes.
- `core/paint/box_border_painter.cc` (BSD, Chromium 2015): header checked; not yet read.

## sample0 explained

`css/CSS2/floats/crashtests/float-rewind-parallel-flow-2-crash.html`: a floated `span` with
`border-style: solid` (width `medium`, 3px) under two nested `zoom: 0.1`. Its used border is
3 × 0.01 = 0.03 CSS px. Div raises it to 1 CSS px (2 device px at 2x); Chromium raises it to
1 device px, since `ConvertBorderWidth` works in zoomed px. The line is three stacked border edges:
6 device px in Div and 3 in Chromium. This is the minimum-one-pixel border rule applied in device px:
stage 2 (layout), not paint.
