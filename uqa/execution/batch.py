#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Columnar batch data structures backed by Apache Arrow.

A ``Batch`` wraps a ``pyarrow.RecordBatch`` and provides the data exchange
interface for the Volcano iterator engine.  An optional selection vector
enables lazy filtering: downstream operators only process selected row
indices, and ``compact()`` materializes the selection via Arrow's
``take()`` kernel.

``ColumnVector`` wraps a single ``pyarrow.Array`` and provides per-element
access with automatic null handling and Python type conversion.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

import pyarrow as pa

if TYPE_CHECKING:
    import numpy as np
import pyarrow.compute as pc

DEFAULT_BATCH_SIZE = 1024


class DataType(enum.Enum):
    """Column data types for the execution engine."""

    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    BOOLEAN = "boolean"
    BYTES = "bytes"


# DataType -> Arrow type mapping.
_DTYPE_TO_ARROW: dict[DataType, pa.DataType] = {
    DataType.INTEGER: pa.int64(),
    DataType.FLOAT: pa.float64(),
    DataType.TEXT: pa.utf8(),
    DataType.BOOLEAN: pa.bool_(),
    DataType.BYTES: pa.binary(),
}


def _arrow_type_to_dtype(arrow_type: pa.DataType) -> DataType:
    """Convert an Arrow data type to the engine DataType enum."""
    if pa.types.is_boolean(arrow_type):
        return DataType.BOOLEAN
    if pa.types.is_integer(arrow_type):
        return DataType.INTEGER
    if pa.types.is_floating(arrow_type):
        return DataType.FLOAT
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
        return DataType.TEXT
    if pa.types.is_binary(arrow_type) or pa.types.is_large_binary(arrow_type):
        return DataType.BYTES
    return DataType.TEXT


# SQL type name -> DataType (used by scan operators and the SQL compiler).
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


class ColumnVector:
    """Typed column backed by a PyArrow Array.

    Numeric, text, and boolean data are stored natively in Arrow's columnar
    format with built-in null handling via validity bitmaps.
    """

    __slots__ = ("_array", "dtype")

    def __init__(self, array: pa.Array, dtype: DataType) -> None:
        self._array = array
        self.dtype = dtype

    def __len__(self) -> int:
        return len(self._array)

    def __getitem__(self, idx: int) -> Any:
        return self._array[idx].as_py()

    @property
    def array(self) -> pa.Array:
        """The underlying PyArrow Array."""
        return self._array

    @classmethod
    def from_values(cls, values: list[Any], dtype: DataType) -> ColumnVector:
        """Create a ColumnVector from a list of Python values."""
        arrow_type = _DTYPE_TO_ARROW[dtype]
        if dtype == DataType.BOOLEAN:
            values = [bool(v) if v is not None else None for v in values]
        arr = pa.array(values, type=arrow_type)
        return cls(arr, dtype)

    def select(self, indices: np.ndarray | list[int]) -> ColumnVector:
        """Return a new ColumnVector with only the selected rows."""
        idx = pa.array(indices, type=pa.int64())
        return ColumnVector(pc.take(self._array, idx), self.dtype)


class Batch:
    """A batch of rows in columnar format backed by a PyArrow RecordBatch.

    Batches are the unit of data exchange in the Volcano iterator model.
    Each batch wraps a ``pyarrow.RecordBatch`` and optionally carries a
    selection vector of active row indices for lazy filtering.
    """

    __slots__ = ("_rb", "selection")

    def __init__(
        self,
        record_batch: pa.RecordBatch,
        selection: list[int] | np.ndarray | None = None,
    ) -> None:
        self._rb = record_batch
        self.selection = selection

    @property
    def record_batch(self) -> pa.RecordBatch:
        """The underlying PyArrow RecordBatch."""
        return self._rb

    @property
    def size(self) -> int:
        """Total number of rows in the underlying RecordBatch."""
        return self._rb.num_rows

    def __len__(self) -> int:
        if self.selection is not None:
            return len(self.selection)
        return self.size

    def column(self, name: str) -> ColumnVector:
        """Look up a column by name.  Raises ``KeyError`` if absent."""
        arr = self._rb.column(name)
        return ColumnVector(arr, _arrow_type_to_dtype(arr.type))

    def get_column(self, name: str) -> ColumnVector | None:
        """Look up a column by name, returning ``None`` if absent."""
        try:
            arr = self._rb.column(name)
        except KeyError:
            return None
        return ColumnVector(arr, _arrow_type_to_dtype(arr.type))

    @property
    def column_names(self) -> list[str]:
        return self._rb.schema.names

    def with_selection(self, sel: list[int] | np.ndarray) -> Batch:
        """Return a new Batch sharing the same data with a selection vector."""
        return Batch(self._rb, sel)

    def compact(self) -> Batch:
        """Apply the selection vector, producing a dense batch."""
        if self.selection is None:
            return self
        if len(self.selection) == self.size:
            return Batch(self._rb)
        idx = pa.array(self.selection, type=pa.int64())
        return Batch(self._rb.take(idx))

    def take(self, indices: list[int] | np.ndarray) -> Batch:
        """Return a new Batch with only the rows at *indices*."""
        idx = pa.array(indices, type=pa.int64())
        return Batch(self._rb.take(idx))

    def slice(self, offset: int, length: int) -> Batch:
        """Zero-copy slice of the batch."""
        return Batch(self._rb.slice(offset, length))

    def select_columns(
        self,
        columns: list[str],
        aliases: dict[str, str] | None = None,
    ) -> Batch:
        """Return a new Batch with only the specified columns.

        Columns not present in the batch are silently skipped.
        If *aliases* is provided, columns are renamed accordingly.

        For qualified column names (``table.col``), falls back to the
        unqualified name (``col``) when the qualified name is not
        found.  This supports both JOIN contexts (where fields are
        qualified) and non-JOIN contexts (unqualified fields).
        """
        aliases = aliases or {}
        schema_names = self._rb.schema.names
        arrays: list[pa.Array] = []
        names: list[str] = []
        for col_name in columns:
            resolved = col_name
            if col_name not in schema_names and "." in col_name:
                # Qualified name not found; try unqualified fallback
                unqualified = col_name.rsplit(".", 1)[-1]
                if unqualified in schema_names:
                    resolved = unqualified
            if resolved in schema_names:
                arrays.append(self._rb.column(resolved))
                names.append(aliases.get(col_name, col_name))
        return Batch(pa.RecordBatch.from_arrays(arrays, names=names))

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert batch to a list of row dicts."""
        if self.selection is not None:
            return self.compact().to_rows()

        n = self.size
        if n == 0:
            return []

        return self._rb.to_pylist()

    @classmethod
    def from_rows(
        cls,
        rows: list[dict[str, Any]],
        schema: dict[str, DataType] | None = None,
    ) -> Batch:
        """Create a Batch from a list of row dicts.

        If *schema* is ``None``, types are inferred from the first
        non-null value in each column.  Complex values (lists, dicts) are
        stored using Arrow's native nested types (list, struct) via
        automatic type inference.
        """
        if not rows:
            return cls(pa.RecordBatch.from_pylist([]))

        col_names = list(rows[0].keys())

        if schema is None:
            schema = {}

        # Include schema columns that may be absent from rows (e.g.
        # NULL-only columns stripped by the document store).
        seen = set(col_names)
        for name in schema:
            if name not in seen:
                col_names.append(name)
                seen.add(name)

        # Infer types for columns not covered by the explicit schema.
        for name in col_names:
            if name not in schema:
                for row in rows:
                    val = row.get(name)
                    if val is not None:
                        schema[name] = _infer_dtype(val)
                        break
                if name not in schema:
                    schema[name] = DataType.TEXT

        arrays: list[pa.Array] = []
        fields: list[pa.Field] = []
        for name in col_names:
            values = [row.get(name) for row in rows]
            dtype = schema.get(name, DataType.TEXT)
            if _has_complex_values(values):
                # Normalize mixed-type lists to homogeneous strings
                # (matches PostgreSQL's type promotion to text).
                values = _normalize_complex_values(values)
                # Let Arrow infer nested types (list, struct) natively
                arr = pa.array(values, from_pandas=True)
                arrays.append(arr)
                fields.append(pa.field(name, arr.type))
            else:
                arrow_type = _DTYPE_TO_ARROW[dtype]
                if dtype == DataType.BOOLEAN:
                    values = [bool(v) if v is not None else None for v in values]
                arrays.append(pa.array(values, type=arrow_type))
                fields.append(pa.field(name, arrow_type))

        return cls(pa.RecordBatch.from_arrays(arrays, schema=pa.schema(fields)))


def _has_complex_values(values: list[Any]) -> bool:
    """Check if any non-null value is a list or dict."""
    return any(isinstance(v, list | dict) for v in values)


def _normalize_complex_values(values: list[Any]) -> list[Any]:
    """Normalize mixed-type lists for Arrow compatibility.

    When a list contains elements of different types (e.g. ``[1, 2, 'four']``),
    all elements are converted to strings.  This matches PostgreSQL's behavior
    of promoting mixed-type arrays to ``text[]``.
    """
    result: list[Any] = []
    for v in values:
        if isinstance(v, list):
            result.append(_normalize_list(v))
        else:
            result.append(v)
    return result


def _normalize_list(lst: list[Any]) -> list[Any]:
    """Convert a mixed-type list to all-strings."""
    if not lst:
        return lst
    types = {type(x) for x in lst if x is not None}
    if len(types) <= 1:
        return lst
    return [str(x) if x is not None else None for x in lst]


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
