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
    from uqa.execution.batch import Batch


class PhysicalOperator(ABC):
    """Abstract base for Volcano-model physical operators."""

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
