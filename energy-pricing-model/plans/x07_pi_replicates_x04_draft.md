# x07-pi-replicates-x04 — pre-registration (DRAFT, not registered)

> **DRAFT, not registered.** This is an option for the user's decision at gate G1 (stage C): the "pi
> under test" track the user considered when planning stage B. It becomes a registration only if the
> user chooses it.

- **Plan:** stage C, option B.
- **Theory / Inputs:**
  - x04 run `20260926T124644Z`, the reference;
  - the note, §5–§7.5;
  - the x06 harness and its controls, as amended by x06 deviation 1 (run `20260926T135115Z` at 6a588c4).

## Why this design
x04's audit is deterministic and fully specified by the note's §7.4 inputs, which makes it the
cleanest reference for grading an agent.

The question is whether the pi agent (deepseek-v4-flash, with notebooks and web search only),
given §5–§7.5 verbatim, finds what x04 found:
- the §7.5 losses belong to the pass-through price;
- at p*, jitter costs about 1.7% at £1.

## Hypotheses (proposed)
- **`pi-finds-misattribution` (primary).**
  - H1: in at least 6 of 10 sessions, pi's saved `findings.json` puts the σ = £1 jitter loss at p*
    in [1.6, 1.85]%. It must also state that §7.5's 1.0% does not hold at p*.
  - H0: fewer sessions do.
- **Descriptive:**
  - pi reproduces p* to within ±0.01, in how many sessions;
  - it computes the §7.4 table;
  - whether it notices that symmetric jitter breaks the cap;
  - cost and tool use.

## Method (proposed)
- The x06 launch: the same flags, environment allowlist, controls C1 and C2, and redaction.
- The prompt quotes §5–§7.5 verbatim and asks pi to verify the numbers in a notebook, then write
  `findings.json` in a fixed schema.
- No web search is needed. Searches are allowed but capped at 3, with x06's cap follow-up.
  In x06 the pinned model overran every stated search budget, so the hard cap and the cap
  follow-up are needed from the start.
- 10 sessions, 3 at a time, each capped at 900 s and $0.20; $2.00 in all.
- Grading uses `findings.json` and the saved notebook only, against x04's summary, by a registered
  rubric.

## Outcome classes (proposed)
| Class | Condition | Action |
|---|---|---|
| `invalid` | C1 or C2 fails, or fewer than 8 sessions produce a valid `findings.json` | debug, re-run |
| `pi-replicates` | H1 holds | G2 |
| `pi-partial` | 3–5 sessions meet H1 | G2 |
| `pi-fails` | ≤ 2 sessions | G2 |

## Deviations
(not registered)
