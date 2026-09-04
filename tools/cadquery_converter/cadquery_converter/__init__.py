"""CadQuery → SimpleCAD SFTC conversion toolkit."""

from .convert import ConversionReport, convert_cadquery_file, convert_cadquery_source
from .validate import ValidationResult, validate_conversion

__all__ = [
    "ConversionReport",
    "ValidationResult",
    "convert_cadquery_source",
    "convert_cadquery_file",
    "validate_conversion",
]

__version__ = "0.1.0"
