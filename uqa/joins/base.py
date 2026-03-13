#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uqa.core.posting_list import GeneralizedPostingList


@dataclass(frozen=True, slots=True)
class JoinCondition:
    """Equijoin condition: left_field = right_field."""

    left_field: str
    right_field: str


class JoinOperator(ABC):
    """Abstract base for join operators (Section 4, Paper 1)."""

    def __init__(
        self,
        left: object,
        right: object,
        condition: JoinCondition,
    ) -> None:
        self.left = left
        self.right = right
        self.condition = condition

    @abstractmethod
    def execute(self, context: object) -> GeneralizedPostingList: ...
