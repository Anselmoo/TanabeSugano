"""Regression tests for defects found during the fitting-layer review.

Each test here was written BEFORE its fix and observed to fail, so the assertion
records real behaviour rather than an assumption about it.
"""

from __future__ import annotations

import numpy as np
import pytest

from tanabesugano import matrices
from tanabesugano import tools
from tanabesugano.batch import Batch
from tanabesugano.cmd import CMDmain


class TestBatchSlaterCondon:
    """Batch(slater=True) was dead on arrival."""

    def test_batch_accepts_slater_condon_input(self) -> None:
        """It raised TypeError: list / float, on every call.

        Three compounding faults at batch.py:107: it passed the raw 3-element
        [start, stop, steps] constructor lists instead of the linspace grids,
        used the local `B` rather than `self.B`, and would have clobbered the
        already-built grids with 3-element arrays even if it had run.
        """
        batch = Batch(d_count=3, slater=True)
        assert batch.B is not None
        assert batch.C is not None

    def test_slater_grids_keep_their_length(self) -> None:
        """The transform must map the grid, not replace it with a 3-element array."""
        steps = 4
        batch = Batch(
            d_count=3,
            Dq=[1000.0, 2000.0, steps],
            B=[0.1, 0.2, steps],
            C=[0.4, 0.5, steps],
            slater=True,
        )
        assert len(batch.B) == steps
        assert len(batch.C) == steps

    def test_slater_transform_matches_tools_racah(self) -> None:
        """Batch must apply the same transform CMDmain does, in the same direction."""
        f2, f4 = 0.15, 0.05
        batch = Batch(d_count=3, B=[f2, f2, 1], C=[f4, f4, 1], slater=True)
        expected_b, expected_c = tools.racah(f2, f4)
        assert float(np.asarray(batch.B).flatten()[0]) == pytest.approx(expected_b)
        assert float(np.asarray(batch.C).flatten()[0]) == pytest.approx(expected_c)

    def test_slater_batch_actually_computes(self) -> None:
        """End-to-end: a slater=True batch must produce results, not just construct."""
        batch = Batch(
            d_count=3,
            Dq=[1000.0, 2000.0, 2],
            B=[0.12, 0.13, 2],
            C=[0.45, 0.46, 2],
            slater=True,
        )
        batch.calculation()
        assert batch.result


class TestPublicNumpyTypingImport:
    """matrices.py reached into a private numpy path."""

    def test_no_private_numpy_imports(self) -> None:
        """`numpy._typing._array_like` is private; a reorg breaks package import.

        matrices.py is imported by every other module, so this would take the
        CLI and the MCP server down with it.
        """
        source = __import__("pathlib").Path(matrices.__file__).read_text(encoding="utf-8")
        assert "numpy._typing" not in source, "matrices.py imports a private numpy path"


class TestInvalidDCountRaisesValueError:
    """The intended ValueError guard was unreachable."""

    @pytest.mark.parametrize("d_count", [1, 9, 0, -3])
    def test_cmdmain_rejects_unsupported_d_count(self, d_count: int) -> None:
        """It raised AttributeError: no attribute '_size' from __init__ instead.

        Three unguarded `if` blocks assign self._size with no else, so an
        unsupported d_count fell through and the careful ValueError in
        calculation() was never reached.
        """
        with pytest.raises(ValueError, match="(?i)d.?count|d electrons"):
            CMDmain(d_count=d_count)

    @pytest.mark.parametrize("d_count", [1, 9, 0, -3])
    def test_batch_rejects_unsupported_d_count(self, d_count: int) -> None:
        """Batch constructed fine and only failed later, inconsistently with CMDmain."""
        with pytest.raises(ValueError, match="(?i)d.?count|d electrons"):
            Batch(d_count=d_count)


class TestCLIAxisConvention:
    """The TS abscissa was labelled Delta/B but held Dq/B."""

    def test_delta_b_column_is_ten_dq_over_b(self) -> None:
        """Delta_o == 10Dq by definition, so a column named delta_B must be 10Dq/B.

        cmd.py built `energy / self.B` where energy is Dq -- proven by the
        sibling column "10Dq": energy * 10.0 -- then plotted and exported it
        under the label $\\Delta/B$. The axis was off by exactly 10x.
        """
        dq, b = 1000.0, 500.0
        cmd = CMDmain(Dq=dq, B=b, C=4000.0, d_count=3, nroots=5)
        row = cmd.df.iloc[-1]
        assert row["delta_B"] == pytest.approx(row["10Dq"] / b)


class TestEnergyConversionFactor:
    """cmd.py used a different cm^-1 -> eV factor from the rest of the package."""

    def test_single_conversion_factor(self) -> None:
        """0.00012 (~1/8333) vs 1/8065.54 elsewhere -- a 3.3% discrepancy."""
        source = (__import__("pathlib").Path(matrices.__file__).parent / "cmd.py").read_text(
            encoding="utf-8",
        )
        assert "0.00012" not in source, "cmd.py uses an inconsistent eV conversion"


class TestTsPrintActuallyPrints:
    """ts_print built a PrettyTable and never printed it."""

    def test_ts_print_writes_to_stdout(self, capsys: pytest.CaptureFixture[str], tmp_path) -> None:
        """The docstring promises output "on the screen"; only a CSV was written."""
        import os

        cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cmd = CMDmain(Dq=1000.0, B=860.0, C=3850.0, d_count=3, nroots=10)
            cmd.ci_cut(dq_ci=1000.0)  # the real CLI path; calls ts_print
        finally:
            os.chdir(cwd)
        captured = capsys.readouterr()
        assert captured.out.strip(), "ts_print produced no stdout"
        assert "State" in captured.out


class TestRacahDefaultProvenance:
    """Pin the per-configuration Racah defaults so they cannot drift silently.

    C/B is a modelling *choice*, not a constant -- Adachi (ECS J. Solid State
    Sci. Technol. 2025, 14, 056002, doi:10.1149/2162-8777/add0e2) argues 3.7,
    4.7 and 8.0 for d3 alone. These values are therefore pinned, not derived,
    and any change to them is a deliberate physics decision that should show up
    as a failing test rather than a silent shift in every diagram.
    """

    EXPECTED_C_OVER_B = {
        2: 4.420,
        3: 4.502,
        4: 4.610,
        5: 4.477,
        6: 4.808,
        7: 4.633,
        8: 4.709,
    }

    @pytest.mark.parametrize("d_count", sorted(EXPECTED_C_OVER_B))
    def test_c_over_b_ratio(self, d_count: int) -> None:
        from tanabesugano.mcp._defaults import DEFAULTS

        cfg = DEFAULTS[d_count]
        ratio = float(cfg["default_C"]) / float(cfg["default_B"])
        assert ratio == pytest.approx(self.EXPECTED_C_OVER_B[d_count], abs=1e-3)

    def test_cli_default_is_the_d5_pair(self) -> None:
        """The CLI's single (B, C) default is the d5 pair, not a universal one.

        README documented `C = 4.477*860` with no d-count qualifier, which reads
        as "the C/B for every configuration". It is specifically d5's.
        """
        from tanabesugano.mcp._defaults import DEFAULTS

        assert float(DEFAULTS[5]["default_B"]) == pytest.approx(860.0)
        assert float(DEFAULTS[5]["default_C"]) == pytest.approx(4.477 * 860.0, abs=1.0)

    def test_free_ion_b_is_self_consistent_for_d5(self) -> None:
        """Beta = B/B0 must be 1.0 when a d5 fit returns the free-ion B.

        Note: sources disagree on the Mn2+ free-ion B by ~10% (860 here, ~960
        elsewhere); the same split affects Cr3+ (918 vs 1030) and Ni2+ (1041 vs
        1080). The values here are internally consistent, but any beta reported
        by ts_nephelauxetic inherits that source ambiguity.
        """
        from tanabesugano.mcp._defaults import DEFAULTS
        from tanabesugano.mcp._defaults import FREE_ION_RACAH_B

        assert float(FREE_ION_RACAH_B["Mn2+"]) == pytest.approx(
            float(DEFAULTS[5]["default_B"]),
        )


class TestCiCutRequiresItsArgument:
    """`ci_cut` advertised an optional cut it cannot actually handle.

    Found by `ty`: the signature was `dq_ci: float | None = None`, but the body
    does `dq_ci / 10.0` and `int(dq_ci)`, so calling it with the advertised
    default raised `TypeError: unsupported operand type(s) for /: 'NoneType'
    and 'float'`. The one CLI call site guards with `if args.cut is not None`,
    which is why it never surfaced in practice -- the signature was a footgun
    for every other caller.
    """

    def test_the_signature_no_longer_advertises_none(self) -> None:
        import inspect

        sig = inspect.signature(CMDmain.ci_cut)
        param = sig.parameters["dq_ci"]
        assert param.default is inspect.Parameter.empty, (
            "dq_ci still has a default it cannot honour"
        )
        assert "None" not in str(param.annotation), (
            f"dq_ci still advertises None: {param.annotation}"
        )
