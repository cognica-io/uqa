#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from typing import Any


class TemporalFilter:
    """Time-aware filter for graph edges (Section 10, Paper 2).

    Filters edges based on valid_from/valid_to temporal properties.
    An edge is valid at a timestamp if:
        valid_from <= timestamp <= valid_to

    For range queries, an edge is valid if its validity interval
    overlaps with the query range.
    """

    def __init__(
        self,
        timestamp: float | None = None,
        time_range: tuple[float, float] | None = None,
    ) -> None:
        if timestamp is not None and time_range is not None:
            raise ValueError("Specify either timestamp or time_range, not both")
        self.timestamp = timestamp
        self.time_range = time_range

    def is_valid(self, properties: dict[str, Any]) -> bool:
        """Check whether an edge's temporal properties satisfy this filter."""
        valid_from = properties.get("valid_from")
        valid_to = properties.get("valid_to")

        # If no temporal properties, edge is always valid
        if valid_from is None and valid_to is None:
            return True

        vf = float(valid_from) if valid_from is not None else float("-inf")
        vt = float(valid_to) if valid_to is not None else float("inf")

        if self.timestamp is not None:
            return vf <= self.timestamp <= vt

        if self.time_range is not None:
            range_start, range_end = self.time_range
            # Overlap check: edge interval [vf, vt] overlaps [range_start, range_end]
            return vf <= range_end and vt >= range_start

        # No filter specified -- accept all
        return True
