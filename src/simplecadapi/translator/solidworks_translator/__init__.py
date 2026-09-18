"""SolidWorks translator backend for SimpleCAD product packages."""

from .api import (
    SUPPORTED_SOLIDWORKS_VERSIONS,
    translate_product_package_to_solidworks_script,
)
from .capabilities import CAPABILITIES
from .translator import SolidWorksTranslator

__all__ = [
    "CAPABILITIES",
    "SUPPORTED_SOLIDWORKS_VERSIONS",
    "SolidWorksTranslator",
    "translate_product_package_to_solidworks_script",
]
