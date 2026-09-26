"""Independent re-check of x01's certified counterexamples (witnesses.jsonl). It is not part of the
registered pipeline, and it shares no code with epmlib: it reads only the exact rationals in each
witness and re-derives, in `fractions.Fraction`, what makes each one a counterexample.

    S1  demand-scarce, nondegenerate: the marginal asset k is strict, so the optimal dual is unique,
        with ν = λ − π_k; asset a with π_a < π_k then needs μ_a = π_k − π_a > 0, not the note's 0.
    S2  generation-scarce, nondegenerate: μ_a ≥ 0, so the note's μ_a = λ − π_a < 0 is infeasible.
    S3  the note's ΣG regime and the G⁺ regime differ.

    python recheck_witnesses.py RUN_DIR [OUT]"""

import json
import sys
from fractions import Fraction
from pathlib import Path


def frac(s: str) -> Fraction:
    p, q = s.split("/")
    return Fraction(int(p), int(q))


def instance(w: dict) -> tuple[Fraction, list[Fraction], list[Fraction], list[Fraction]]:
    i = w["instance"]
    return frac(i["lam"]), [frac(x) for x in i["c"]], [frac(x) for x in i["gen"]], [frac(x) for x in i["premium"]]


def nondegenerate(lam, c, gen, prem) -> bool:
    return (all(x > 0 for x in c) and all(x > 0 for x in gen) and len(set(prem)) == len(prem)
            and all(p != lam for p in prem))


def recheck(w: dict) -> tuple[bool, str]:
    lam, c, gen, prem = instance(w)
    total_c = sum(c)
    order = sorted((a for a in range(len(gen)) if prem[a] < lam), key=lambda a: prem[a])
    g_plus = sum(gen[a] for a in order)
    if w["statement"] == "S3":
        note = "generation-scarce" if sum(gen) < total_c else "demand-scarce" if sum(gen) > total_c else "balanced"
        true = "generation-scarce" if g_plus < total_c else "demand-scarce" if g_plus > total_c else "balanced"
        ok = note != true and note == w["note_regime"] and true == w["true_regime"]
        return ok, f"note {note} vs true {true}"
    if not nondegenerate(lam, c, gen, prem):
        return False, "degenerate instance"
    a = w["asset"]
    if w["statement"] == "S1":
        if not g_plus > total_c:
            return False, "not demand-scarce"
        cum, k, before = Fraction(0), None, Fraction(0)
        for x in order:
            before = cum
            cum += gen[x]
            if cum >= total_c:
                k = x
                break
        strict = before < total_c < cum
        ok = strict and k == w["marginal"] and prem[a] < prem[k] and frac(w["certified_mu"]) == prem[k] - prem[a] > 0
        return ok, f"mu_a = {prem[k] - prem[a]} > 0 (note: 0)"
    if w["statement"] == "S2":
        ok = g_plus < total_c and prem[a] > lam and lam - prem[a] < 0 and frac(w["certified_mu"]) == 0
        return ok, f"note mu_a = {lam - prem[a]} < 0 is infeasible; certified 0"
    return False, "unknown statement"


def main() -> int:
    run = Path(sys.argv[1])
    lines = [json.loads(x) for x in (run / "witnesses.jsonl").read_text().splitlines() if x.strip()]
    counts: dict[str, list[int]] = {}
    failures = []
    for w in lines:
        ok, why = recheck(w)
        counts.setdefault(w["statement"], [0, 0])[0 if ok else 1] += 1
        if not ok:
            failures.append((w["key"], w["statement"], why))
    report = [f"x01 witness re-check (independent; exact rationals) of {run.name}"]
    for st in sorted(counts):
        report.append(f"{st}: {counts[st][0]} verified, {counts[st][1]} not verified")
    report += [f"NOT VERIFIED {k} {st}: {why}" for k, st, why in failures[:50]]
    text = "\n".join(report) + "\n"
    if len(sys.argv) > 2:
        Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[2]).write_text(text)
    print(text, end="")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
