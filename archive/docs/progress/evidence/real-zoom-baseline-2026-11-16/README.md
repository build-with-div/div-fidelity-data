# First real-zoom Div census and CSS Grid coverage

RFC 0010 (build-with-div/div#55) moves every Chromium oracle above scale 1
from CDP device emulation to real zoom (`--force-device-scale-factor`).
These files are the first census and CSS Grid coverage run at the new
oracle, and the baseline from which "no regressions" (D4) is measured
from now on.

- Head: the launcher change, Div `19269a7fee7da3e958471f7c73f094282962e058`
  on main `154d0a7`, with `device_scale_method` `none` at scale 1 and
  `forced` at 1.25, 1.5 and 2.
- Base: `a9e9a46eab36cba553e594e529161fa3744900ac` (the fractional-edges
  probe on main `da4f1e6`), measured on 16 November 2026 against the
  emulated oracle. Div's frames are byte-identical in the two runs (all
  23,728 census rows and all 4,048 coverage rows that render), so the
  base is the emulated measurement of the same Div output.
- Both runs are on Linux (WSL), 16 jobs, under the census lock, with pinned
  Chromium 147.0.7727.50. Comparisons are exact; the tolerance is 0.

| File | Contents |
| --- | --- |
| `summary.json` | Exact counts per profile (old and new), status transitions, per-area exact counts at the new oracle, and the two checks below |
| `census-rows.json` | Every census comparison at the new oracle: id, profile, status, mismatched pixels, Chromium and Div PNG SHA-256 |
| `coverage-rows.json` | The same for the CSS Grid coverage suite |

Checks:

- Scale 1 is unchanged: every census Chromium frame (5,932) and every
  coverage frame that renders (1,012; 39 error in both runs) is
  byte-identical to the base run.
- The non-1x census frames that the earlier forced-scale measurement
  (`dsf-oracle-2026-11-16/`) also captured all match it: 69 of 69.

| Profile | Census exact, emulated → real zoom | Coverage exact, emulated → real zoom |
| --- | --- | --- |
| legacy-800x600@1 | 5,888 → 5,888 | 572 → 572 |
| mobile-375x667@2 | 5,767 → 5,153 | 567 → 487 |
| desktop-1280x720@1.25 | 5,344 → 2,183 | 529 → 183 |
| desktop-1920x1080@1.5 | 5,540 → 3,063 | 559 → 217 |
| Total | 22,539 → 16,287 of 23,728 | 2,227 → 1,459 of 4,204 |

The drop is a new oracle, not a change in Div: Div's frames are the same in
both runs. Div lays out in CSS px and replays paint at the scale, which
matches emulation; closing the gap is layout in device pixels and
device-pixel edge snapping.
