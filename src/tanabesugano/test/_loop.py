"""Run a coroutine from a synchronous test, whatever the main thread is doing.

``asyncio.run()`` raises ``RuntimeError: asyncio.run() cannot be called from a
running event loop`` if a loop is already running on the calling thread, and
anyio's pytest plugin starts one on the main thread for the whole session as
soon as any test needs it. A pool worker always starts loop-free, so dispatching
through one makes the call independent of what else the session has run.

Why this is a module and not four copies. The failure is ordering-dependent, and
the ordering hid it almost perfectly: pytest collects files alphabetically, and
``test_screenshots`` -- the file whose fixtures start the loop -- sorts after
every other module that used a bare ``asyncio.run`` except one,
``test_script_export``. So exactly one file failed, which read like a defect in
that file rather than a property of the suite. Worse, ``poe test`` and CI pass
``--ignore=.../test_screenshots.py``, so under the project's own gate the
collision never happens at all and the whole thing is invisible.

The remaining modules were one alphabetically-later filename, one
``-p randomly``, or one xdist run away from the same failure.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Coroutine


def run_loop_free[T](make_coro: Callable[[], Coroutine[object, object, T]]) -> T:
    """Run ``make_coro()`` to completion on a thread that owns no event loop.

    Takes a factory rather than a coroutine so that nothing is created until it
    is inside the worker: a coroutine built on the calling thread and then
    dropped -- if submission failed -- would surface as a bare
    "coroutine was never awaited" warning far from its cause.

    Usage mirrors the ``asyncio.run`` it replaces::

        async def go():
            server = create_server()
            return await server.list_tools()

        tools = run_loop_free(go)
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make_coro())).result()
