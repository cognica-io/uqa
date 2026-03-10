#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Foreign Data Wrapper (FDW) support for querying external data sources."""

from uqa.fdw.foreign_table import ForeignServer, ForeignTable
from uqa.fdw.handler import FDWHandler

__all__ = ["FDWHandler", "ForeignServer", "ForeignTable"]
