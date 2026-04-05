#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Volcano-model physical operator interface.

Every physical operator implements the ``open / next / close`` iterator
protocol.  ``next()`` returns the next :class:`Batch` of rows, or
``None`` when the operator is exhausted.

Operators form a tree: each operator pulls from its children on demand,
enabling pipelined (streaming) execution.  Blocking operators (sort,
hash-aggregate) materialize their input before producing output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.cancel import CancellationToken
    from uqa.execution.batch import Batch


class PhysicalOperator(ABC):
    """Abstract base for Volcano-model physical operators."""

    cancel_token: CancellationToken | None = None

    def check_cancelled(self) -> None:
        """Raise :class:`~uqa.cancel.QueryCancelled` if cancelled."""
        if self.cancel_token is not None:
            self.cancel_token.check()

    def propagate_cancel_token(self, token: CancellationToken) -> None:
        """Set the cancel token on this operator and all children."""
        self.cancel_token = token
        if hasattr(self, "_child") and isinstance(self._child, PhysicalOperator):
            self._child.propagate_cancel_token(token)

    @abstractmethod
    def open(self) -> None:
        """Initialize operator state and open children."""
        ...

    @abstractmethod
    def next(self) -> Batch | None:
        """Return the next batch of rows, or None if exhausted."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources and close children."""
        ...
