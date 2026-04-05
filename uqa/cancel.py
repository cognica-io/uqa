#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Query cancellation support.

Provides :class:`CancellationToken` -- a thread-safe mechanism for
cancelling in-flight queries.  The token is stored on
:class:`~uqa.engine.Engine` and propagated to physical operators and
join operators so they can check it in their hot loops.

Usage::

    engine = Engine()

    # In another thread:
    engine.cancel()

    # Inside an operator hot loop:
    self.check_cancelled()  # raises QueryCancelled
"""

from __future__ import annotations

import threading


class QueryCancelled(Exception):
    """Raised when a query is cancelled by user request.

    Matches PostgreSQL SQLSTATE 57014 (query_canceled).
    """


class CancellationToken:
    """Thread-safe cancellation token for query execution.

    Uses :class:`threading.Event` internally so that ``cancel()``
    called from one thread is immediately visible to operator hot
    loops running in another thread.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation."""
        self._event.set()

    def reset(self) -> None:
        """Clear the cancellation signal for the next query."""
        self._event.clear()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise :class:`QueryCancelled` if cancellation was signalled."""
        if self._event.is_set():
            raise QueryCancelled("canceling statement due to user request")
