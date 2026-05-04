# Audit Fixes Applied — 2026-05-04

This document tracks fixes applied in response to the external Codex audit (88 findings).

## P0 — Tax Correctness

| ID | Finding | Status | Fix |
|----|---------|--------|-----|
| C1 | `ita2025_comprehensive_knowledge_base.json` invalid JSON (duplicate trailing block) | ✅ Fixed | Removed garbage after root `}`, added `_meta` block |
| T5 | Old regime rebate has no marginal relief | ✅ Already fixed (verified) | `rebateOld` returns `t - ex` when tax > excess (line 538-545) |
| T6 / R2 | `surchargeWithCGCap` defined but never called | ✅ Already fixed (verified) | Wired in `recompute()` for both regimes (lines 1044, 1061) |
| T8 | `getOldSlabs` not used correctly for seniors | ✅ Already fixed (verified) | `slabsForAge = getOldSlabs(ageKey)` (line 1007) |
| T9 | `rebateOld` / `rebateNew` no resident check | ✅ Already fixed (verified) | Both gate on `isResident === false` |
| T11 | Surcharge no marginal relief at 50L/1Cr/2Cr/5Cr thresholds | ✅ Fixed | Added `surchargeWithMarginalRelief()` per Sec 156 proviso. `surcharge()` and `surchargeWithCGCap()` now use it. |
| T12 | 234A/B/C interest never displayed in result panel | ✅ Fixed | Added `interestBannerHtml()` shown after the regime comparison cards. Cites Sec 423/424/425. |
| R7 | ITR JSON uses `AssessmentYear` (1961-Act terminology) | ✅ Fixed | Now `TaxYear: "2026-27"` per ITA 2025 Sec 3, with legacy field for compat. Renamed `CommencementDate` → `ActAppliesFrom`. |

## P0 — Security

| ID | Finding | Status | Fix |
|----|---------|--------|-----|
| R3 | `extractedCardHtml` injects PDF text without escaping | ✅ Fixed | `esc(data.employer)`, `esc(data.pan)` |
| R4 | File names from upload XSS | ✅ Already fixed | `esc(f.name)` in 3 interpolations |
| R5 / S1 | Workflow has `contents: write` at top level on push | ✅ Fixed | Default to `contents: read`; escalate only on commit step. Added `if:` guard against PR triggers. |
| R11 | Live KB fetch has no timeout | ✅ Fixed | Wrapped in `Promise.race` with 5s timeout |
| S7 | `yaml.load` vs `yaml.safe_load` | ✅ Already in use (audit was wrong) | `yaml.safe_load` confirmed in scrape_updates.py:271 |

## P0 — Marketing / UX / Trust

| ID | Finding | Status | Fix |
|----|---------|--------|-----|
| M1 | "Fully DPDP compliant" overclaim | ✅ Fixed | Softened to "Built with DPDP Act, 2023 in mind from day one. Formal DPDP audit pending." |
| M2 | No ITR-1-only disclaimer | ✅ Fixed | Amber notice in hero: *"Currently supports ITR-1 (Sahaj). Capital gains, business income — coming soon."* |
| CII | Provisional 2025-26 / 2026-27 CII values not flagged | ✅ Fixed | `_provisional_years` + warning note + `_official_source` URL added to operational_reference_data.json |
| Q&A | "Click §pill — original text appears" overclaim | ✅ Fixed | Changed to "Hover any §pill — section number, title, principle appear" (which is what actually happens) |

## P1 — Build items still open

These need fresh feature builds, not patches. Engine math exists; chat flow does not.

| ID | Finding | Status | What's needed |
|----|---------|--------|---------------|
| T1 | House Property head not invoked from chat | 🟡 Engine done, chat flow missing | Build `askHouseProperty()` chat flow asking SOP/LOP, rent, loan interest, municipal taxes |
| T2 | Capital gains chat flow missing | 🟡 Engine done (`specialRateTax`), chat flow missing | Build `askCapitalGains()` flow asking STCG/LTCG amounts, asset class |
| T3 | PGBP detection missing | 🔴 Not built | Add detection question + presumptive Sec 58/61 + ITR-3/4 routing |
| T4 | Horse race / card games not in `specialRateTax` | 🟡 Lottery covered (Sec 188), horse race missing | Extend `specialRateTax` to add `horseRaceWinnings` + `cardGameWinnings` (also flat 30%) |

## ACT object additions

Added 3 new section entries so §pills resolve in the new interest banner:

- `s423` — Section 423 (old 234A) — Late filing interest, 1%/month
- `s424` — Section 424 (old 234B) — Default in advance tax, 1%/month
- `s425` — Section 425 (old 234C) — Deferment of advance tax instalments, 1%/month

## Files changed this round

- `app/app.html` — surcharge marginal relief, interest banner, XSS guard on PDF data, ACT additions, JSON field rename
- `app/index.html` — ITR-1-only disclaimer, softened DPDP claim
- `.github/workflows/daily-update.yml` — least-privilege workflow permissions
- `ita2025_comprehensive_knowledge_base.json` — removed JSON syntax error
- `operational_reference_data.json` — flagged provisional CII years
- `app/README.md` — clarified "DRAFT JSON shape" not "CBDT-compliant"

## Remaining audit items deferred

P2/P3 items intentionally deferred (low practical risk or premature optimization):

- **DOMPurify for all innerHTML** — current `esc()` covers user-controllable inputs; broader sweep needs library add
- **CSP header** — needs server-side configuration, not just `<meta>` (would break all inline styles)
- **localStorage encryption** (S8/R10) — sessionStorage swap is 1 line; full WebCrypto plumbing is a project
- **parseUserMessage ReDoS (R6)** — current regexes are simple, low practical risk
- **UA rotation in scraper (R12)** — current single UA works fine for TaxGuru
- **CBDT scraper selectors (C8)** — known-fragile, documented in backend/README.md

These are tracked but not blocking for the current prototype stage.
