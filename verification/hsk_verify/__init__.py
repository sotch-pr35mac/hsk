"""Independent, non-canonical HSK dataset verification tools."""

from .compare import compare_records
from .model import ComparisonReport, Record

__all__ = ["ComparisonReport", "Record", "compare_records"]
__version__ = "1.0.0"
