# x06a-neso-ews — pre-registration (DRAFT, not registered)

> **DRAFT, not registered.** This is an option for the user's decision at gate G1. It becomes a
> registration only if the user chooses it, in which case it is moved to
> `experiments/x06a-neso-ews/PREREG.md` and committed on its own before any code for it exists.

- **Plan:** stage B gate G1, option C.
- **Theory / Inputs:** the x06 run `20260926T135115Z` (6a588c4). There, neso-ews was `inconclusive`:
  - one session reached the dataset's CKAN metadata;
  - it then reached a resource download that curl stopped at the registered 50 MB limit.

## Why this design
The companion note says NESO publishes embedded wind and solar forecasts half-hourly, "from within
day up to 14 days ahead", with yearly archives. x06 could not verify that within its budget: the
agents spent their searches elsewhere, and the one download was an annual archive above the size
limit. This option asks only that question, with an instrument sized for it.

## Hypotheses (proposed)
- **`neso-ews-keyless` (primary).**
  - H1: a keyless GET returns half-hourly embedded wind or solar forecasts covering 2026-03-10: at
    least 46 distinct half-hours on that date.
  - H0: a keyless request is refused, or no such data exists at the stated location.

## Method (proposed)
- The x06 harness as amended by its deviation 1, with the same controls C1–C4.
- The prompt is x06's, restricted to neso-ews, feed-a and feed-b.
- It adds a hint that is allowed under the no-look-up rule: prefer a date-filtered query, for example
  CKAN `datastore_search` with a filter on the date, over whole-file downloads.
- `--max-filesize` rises to 200 MB, for this dataset only.
- 4 sessions, 2 at a time. Caps per session: 900 s, $0.10, and 6 searches.
- The verdict rules are x06's.

## Outcome classes (proposed)
| Class | Condition | Action |
|---|---|---|
| `invalid` | C1 or C2 fails, or fewer than 3 sessions pass C3 and C4 | debug, re-run |
| `confirmed` | at least 1 witness | G2 |
| `refuted` | no witness, and refutations in at least 2 valid sessions | G2 |
| `inconclusive` | otherwise | G2 |

## Deviations
(not registered)
