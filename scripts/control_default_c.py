"""Default-C false-alarm control for the held-C check (plan F look-back; plan G fix pass).

Each unique synthetic point of the fit-path audit is re-generated from the determinant
oracle with C equal to the d-count's default C, then fitted unlabelled at the default
C. The held C is then the true C, so a held-C warning ("C is not determined", the tie
branch, or "the default C ... is inconsistent") on a fit that recovers the truth
(|dDq| <= 2 %, |dB| <= 5 %, the audit's grade) is a false alarm. A warning on a fit
that misses is not, and is counted separately.

Measured before the tie threshold (look-back, 2026-11-25): the tie branch fired on 52
of 130 fits, all of them correct. After ``9f75cdc``: 0 of 130. The script exits 1 on
any false alarm.

Run: ``uv run poe audit-default-c-control`` (about 4 minutes).
"""

from __future__ import annotations

import collections
import sys

from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_fit_paths as audit

from tanabesugano.mcp._compute import fit_spectrum


TIE = "C is not determined"
INCONSISTENT = "the default C"


def main() -> int:
    """Fit every unique synthetic point at C = default; return 1 on any false alarm."""
    seen: set[tuple[object, ...]] = set()
    counts: collections.Counter[str] = collections.Counter()
    fired: list[str] = []
    missed_fired: list[str] = []
    for case in audit.synthetic_cases()[0]:
        if case.expect_raise or case.truth_b is None:
            continue
        key = (case.d, case.spin, case.sf, case.truth_dq, case.truth_b)
        if key in seen:
            continue
        seen.add(key)
        c_default = audit.DEFAULTS[case.d]["default_C"]
        ground, bands, _ = audit.synthetic_bands(
            case.d, case.truth_dq, case.truth_b, c_default, sf=case.sf
        )
        if not bands or audit.multiplicity(ground) != audit.expected_ground_mult(case.d, case.spin):
            counts["skipped (no bands, or the other spin regime at the default C)"] += 1
            continue
        try:
            fit = fit_spectrum(
                case.d,
                [band.energy for band in bands],
                spin_state=case.spin,
                include_spin_forbidden=case.sf,
            )
        except ValueError:
            counts["raised"] += 1
            continue
        counts["fitted"] += 1
        d_dq = audit.pct(fit.Dq, case.truth_dq)
        d_b = audit.pct(fit.B, case.truth_b)
        correct = (
            d_dq is not None
            and d_b is not None
            and abs(d_dq) <= audit.DQ_TOL_PCT
            and abs(d_b) <= audit.B_TOL_PCT
        )
        counts["fitted, correct" if correct else "fitted, missed"] += 1
        kinds = [k for k in (TIE, INCONSISTENT) if any(k in w for w in fit.warnings)]
        if kinds:
            where = f"{case.system} sf={case.sf} Dq={case.truth_dq} B={case.truth_b}: {kinds}"
            (fired if correct else missed_fired).append(where)
    for label, n in counts.items():
        print(f"{label}: {n}")
    print(f"false alarms (fired on a correct fit): {len(fired)} of {counts['fitted']}")
    for line in fired:
        print(f"  {line}")
    print(f"fired on a missed fit (not a false alarm): {len(missed_fired)}")
    for line in missed_fired:
        print(f"  {line}")
    return 1 if fired else 0


if __name__ == "__main__":
    raise SystemExit(main())
