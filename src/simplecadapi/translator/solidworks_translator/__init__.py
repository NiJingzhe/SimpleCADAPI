"""SolidWorks translator backend for SimpleCAD product packages."""

from .api import translate_product_package_to_solidworks_script
from .capabilities import CAPABILITIES
from .translator import SolidWorksTranslator

__all__ = [
    "CAPABILITIES",
    "SolidWorksTranslator",
    "translate_product_package_to_solidworks_script",
]
