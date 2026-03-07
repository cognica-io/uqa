#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Columnar batch data structures for vectorized query execution.

A ``Batch`` holds a fixed number of rows in columnar format.  Each column
is a ``ColumnVector`` backed by a NumPy array (numeric/boolean types) or
a Python list (text/bytes).  A boolean null bitmap tracks NULL values.

Selection vectors enable lazy filtering: instead of materializing a new
batch for every filter, the selection vector records which row indices
are "active".  Downstream operators only process active rows.  Call
``compact()`` to physically remove inactive rows when needed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

import numpy as np


DEFAULT_BATCH_SIZE = 1024


class DataType(enum.Enum):
    """Column data types for the execution engine."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    BOOLEAN = "boolean"
    BYTES = "bytes"


# Map SQL type keywords to DataType.
_SQL_TO_DTYPE: dict[str, DataType] = {
    "integer": DataType.INTEGER,
    "int": DataType.INTEGER,
    "int2": DataType.INTEGER,
    "int4": DataType.INTEGER,
    "int8": DataType.INTEGER,
    "bigint": DataType.INTEGER,
    "smallint": DataType.INTEGER,
    "serial": DataType.INTEGER,
    "bigserial": DataType.INTEGER,
    "text": DataType.TEXT,
    "varchar": DataType.TEXT,
    "character varying": DataType.TEXT,
    "char": DataType.TEXT,
    "character": DataType.TEXT,
    "name": DataType.TEXT,
    "real": DataType.FLOAT,
    "float": DataType.FLOAT,
    "float4": DataType.FLOAT,
    "float8": DataType.FLOAT,
    "double precision": DataType.FLOAT,
    "numeric": DataType.FLOAT,
    "decimal": DataType.FLOAT,
    "boolean": DataType.BOOLEAN,
    "bool": DataType.BOOLEAN,
}


@dataclass(slots=True)
class ColumnVector:
    """Typed column with null bitmap.

    Numeric and boolean columns use NumPy arrays for vectorized
    operations.  Text and bytes columns use Python lists.
    """

    data: np.ndarray | list
    nulls: np.ndarray
    dtype: DataType

    def __len__(self) -> int:
        return len(self.nulls)

    def __getitem__(self, idx: int) -> Any:
        if self.nulls[idx]:
            return None
        val = self.data[idx]
        if isinstance(val, np.integer):
            return int(val)
        if isinstance(val, np.floating):
            return float(val)
        if isinstance(val, np.bool_):
            return bool(val)
        return val

    @classmethod
    def from_values(cls, values: list[Any], dtype: DataType) -> ColumnVector:
        """Create a ColumnVector from a list of Python values."""
        nulls = np.array([v is None for v in values], dtype=np.bool_)

        if dtype == DataType.INTEGER:
            data = np.array(
                [v if v is not None else 0 for v in values], dtype=np.int64
            )
        elif dtype == DataType.FLOAT:
            data = np.array(
                [v if v is not None else 0.0 for v in values],
                dtype=np.float64,
            )
        elif dtype == DataType.BOOLEAN:
            data = np.array(
                [v if v is not None else False for v in values],
                dtype=np.bool_,
            )
        else:
            data = [v if v is not None else "" for v in values]

        return cls(data=data, nulls=nulls, dtype=dtype)

    def select(self, indices: np.ndarray | list[int]) -> ColumnVector:
        """Return a new ColumnVector with only the selected rows."""
        if isinstance(self.data, np.ndarray):
            new_data = self.data[indices]
        else:
            new_data = [self.data[i] for i in indices]
        return ColumnVector(
            data=new_data,
            nulls=self.nulls[indices],
            dtype=self.dtype,
        )


@dataclass
class Batch:
    """A batch of rows in columnar format.

    Batches are the unit of data exchange in the Volcano iterator model.
    Each batch contains up to ``DEFAULT_BATCH_SIZE`` rows stored as
    ``ColumnVector`` instances keyed by column name.
    """

    columns: dict[str, ColumnVector] = field(default_factory=dict)
    selection: np.ndarray | None = None
    size: int = 0

    def __len__(self) -> int:
        if self.selection is not None:
            return len(self.selection)
        return self.size

    def column(self, name: str) -> ColumnVector:
        return self.columns[name]

    @property
    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def compact(self) -> Batch:
        """Apply selection vector, producing a dense batch."""
        if self.selection is None:
            return self
        if len(self.selection) == self.size:
            return Batch(columns=self.columns, size=self.size)
        new_cols = {
            name: col.select(self.selection)
            for name, col in self.columns.items()
        }
        return Batch(columns=new_cols, size=len(self.selection))

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert batch to a list of row dicts."""
        if self.selection is not None:
            indices = self.selection
        else:
            indices = range(self.size)
        rows: list[dict[str, Any]] = []
        for i in indices:
            row: dict[str, Any] = {}
            for name, col in self.columns.items():
                row[name] = col[i]
            rows.append(row)
        return rows

    @classmethod
    def from_rows(
        cls,
        rows: list[dict[str, Any]],
        schema: dict[str, DataType] | None = None,
    ) -> Batch:
        """Create a Batch from a list of row dicts.

        If *schema* is ``None``, types are inferred from the first
        non-null value in each column.
        """
        if not rows:
            return cls(columns={}, size=0)

        col_names = list(rows[0].keys())
        n = len(rows)

        if schema is None:
            schema = {}
            for name in col_names:
                for row in rows:
                    val = row.get(name)
                    if val is not None:
                        schema[name] = _infer_dtype(val)
                        break
                if name not in schema:
                    schema[name] = DataType.TEXT

        columns: dict[str, ColumnVector] = {}
        for name in col_names:
            values = [row.get(name) for row in rows]
            dtype = schema.get(name, DataType.TEXT)
            columns[name] = ColumnVector.from_values(values, dtype)

        return cls(columns=columns, size=n)


def _infer_dtype(value: Any) -> DataType:
    """Infer DataType from a Python value."""
    if isinstance(value, bool):
        return DataType.BOOLEAN
    if isinstance(value, int):
        return DataType.INTEGER
    if isinstance(value, float):
        return DataType.FLOAT
    if isinstance(value, bytes):
        return DataType.BYTES
    return DataType.TEXT
