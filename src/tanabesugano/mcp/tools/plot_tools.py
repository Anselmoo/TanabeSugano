"""Matplotlib raster/vector renderer for non-app MCP clients."""

from __future__ import annotations

import base64
import binascii

from typing import TYPE_CHECKING

from fastmcp.tools import ToolResult
from mcp import types

from tanabesugano import __version__
from tanabesugano.mcp._compute import SpinState
from tanabesugano.mcp._inputs import D_COUNT_LITERAL
from tanabesugano.mcp.plotting import EXPORT_MIME_TYPES
from tanabesugano.mcp.plotting import render_diagram
from tanabesugano.mcp.tools._shared import READONLY
from tanabesugano.mcp.tools._shared import TS_META
from tanabesugano.mcp.tools._shared import resolve_bc
from tanabesugano.script_export import fit_figure_script


if TYPE_CHECKING:
    from fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the ts_plot_png matplotlib PNG fallback tool."""

    @mcp.tool(
        name="ts_plot_png",
        title="Render a Tanabe-Sugano diagram (PNG)",
        version=__version__,
        tags={"tanabesugano", "plot"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_plot_png(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        dq_min: float = 0.0,
        dq_max: float = 1500.0,
        steps: int = 60,
        B: float | None = None,
        C: float | None = None,
        normalize: bool = True,
        dpi: int = 144,
        format: str = "png",  # noqa: A002 - the user-facing name for this concept
    ) -> ToolResult:
        """Render a publication-style matplotlib figure of a Tanabe-Sugano diagram.

        Use this in non-app MCP clients (or when token cost is a concern). In
        app-capable clients prefer `ts_plot_view` / `ts_diagram_app`, which
        render an in-chat Prefab LineChart with per-term legend toggling.

        Args:
            format: ``"png"`` (default) returns an inline image block, which is
                what chat surfaces render. ``"pdf"`` and ``"svg"`` return true
                vector output as an embedded resource the client can save --
                use these for publication figures, where a 144-dpi raster of a
                line diagram will not survive typesetting.

        This is also the *only* export route for vector output. An in-chat
        Chart.js app cannot hand the user a file at all: the MCP Apps sandbox
        strips ``allow-downloads`` from every UI iframe (see ``ts_emit_png``),
        so those tools can only push a rendered PNG back through the
        conversation. Anything vector has to come from here.

        """
        b_val, c_val = resolve_bc(d_count, B, C)
        if b_val <= 0:
            return ToolResult(
                content=[
                    types.TextContent(type="text", text=f"Racah B must be positive, got {b_val}"),
                ],
            )
        if steps < 2:
            return ToolResult(
                content=[types.TextContent(type="text", text=f"steps must be >= 2, got {steps}")],
            )
        if format not in EXPORT_MIME_TYPES:
            # Structured error rather than a raise, per the MCP design notes:
            # an agent that guessed "jpeg" can read the valid set and retry.
            return ToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            f"unsupported format {format!r}; "
                            f"choose one of {sorted(EXPORT_MIME_TYPES)}"
                        ),
                    ),
                ],
            )
        try:
            rendered = render_diagram(
                d_count=d_count,
                dq_min=dq_min,
                dq_max=dq_max,
                steps=steps,
                B=b_val,
                C=c_val,
                normalize=normalize,
                dpi=dpi,
                fmt=format,
            )
        except (ValueError, RuntimeError) as exc:
            return ToolResult(content=[types.TextContent(type="text", text=str(exc))])
        b64 = base64.b64encode(rendered).decode()
        mime = EXPORT_MIME_TYPES[format]
        if format == "png":
            # Image blocks are what chat surfaces actually render inline, so the
            # default stays an image rather than becoming a resource to download.
            return ToolResult(
                content=[types.ImageContent(type="image", data=b64, mimeType=mime)],
            )
        # Vector output is not an image block: ImageContent is for raster
        # previews, and a client handed application/pdf under type="image" has
        # no sensible way to display it. An embedded blob resource carries the
        # MIME type and a filename the client can offer as a save target.
        return ToolResult(
            content=[
                types.EmbeddedResource(
                    type="resource",
                    resource=types.BlobResourceContents(
                        uri=f"file:///tanabesugano_d{d_count}.{format}",
                        mimeType=mime,
                        blob=b64,
                    ),
                ),
            ],
        )

    @mcp.tool(
        name="ts_fit_script",
        title="Export a runnable matplotlib script for an observed-vs-computed fit",
        version=__version__,
        tags={"tanabesugano", "plot", "export", "fit", "reproducibility"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_fit_script(
        d_count: D_COUNT_LITERAL,  # type: ignore[valid-type]
        observed_peaks: list[float],
        C: float | None = None,
        spin_state: SpinState = "high",
        include_spin_forbidden: bool = False,
        title: str | None = None,
    ) -> ToolResult:
        """Return Python source that draws the observed-vs-computed band figure.

        Prefer this over writing matplotlib by hand for a fit. The script
        carries the fitter's own Dq, B, transition energies and residuals as
        literals, so the figure cannot disagree with the fit it came from, and
        its band labels come from the solved manifold's free-ion parentage --
        3A_2g -> 3T_1g(P), the spelling a journal expects.

        Returned as conversation text rather than a file, and that is not a
        limitation to work around: the MCP Apps sandbox strips
        ``allow-downloads`` from every UI iframe (see ``ts_emit_png``), so a
        script offered as a download would be unreachable. Text can be read,
        edited and pasted.

        The generated script imports matplotlib and nothing else -- notably not
        tanabesugano -- so a reviewer can run it without installing this
        package or matching its version.
        """
        try:
            source = fit_figure_script(
                d_count,
                observed_peaks,
                C=C,
                spin_state=spin_state,
                include_spin_forbidden=include_spin_forbidden,
                title=title,
            )
        except (ValueError, KeyError) as exc:
            # Structured error, not a raise: an agent that asked for a figure of
            # an unfittable configuration (high-spin d5 has no spin-allowed d-d
            # bands at all) can read why and retry with different arguments.
            return ToolResult(
                content=[types.TextContent(type="text", text=str(exc))],
                is_error=True,
            )
        return ToolResult(content=[types.TextContent(type="text", text=source)])

    @mcp.tool(
        name="ts_emit_png",
        title="Send a rendered chart PNG to the conversation",
        version=__version__,
        tags={"tanabesugano", "plot", "export"},
        annotations=READONLY,
        meta=TS_META,
    )
    def ts_emit_png(png_base64: str, title: str | None = None) -> ToolResult:
        """Echo a base64-encoded PNG back as an MCP image attachment.

        The Chart.js iframes (ts_diagram_app, ts_overlay_app, …) call this
        from their toolbar "Send PNG to chat" button because the MCP Apps
        sandbox does not permit a server-declared download permission —
        the host strips ``allow-downloads`` from every UI iframe and offers
        no programmatic way to push a file out of one. Routing the PNG
        through the conversation surface is the spec-compliant path: the
        chat renders the image and the user can save / copy / share from
        there. Title becomes the image's alt text.
        """
        cleaned = (png_base64 or "").strip()
        if cleaned.startswith("data:"):
            cleaned = cleaned.split(",", 1)[-1]
        if not cleaned:
            return ToolResult(
                content=[types.TextContent(type="text", text="png_base64 was empty")],
            )
        try:
            base64.b64decode(cleaned, validate=True)
        except (ValueError, binascii.Error):
            return ToolResult(
                content=[types.TextContent(type="text", text="png_base64 is not valid base64")],
            )
        parts: list[types.TextContent | types.ImageContent] = []
        if title:
            parts.append(types.TextContent(type="text", text=str(title)))
        parts.append(types.ImageContent(type="image", data=cleaned, mimeType="image/png"))
        return ToolResult(content=parts)
