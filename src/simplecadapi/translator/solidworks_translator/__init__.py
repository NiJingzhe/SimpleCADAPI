"""SolidWorks translator backend for SimpleCAD model JSON."""

from .api import (
    SUPPORTED_SOLIDWORKS_VERSIONS,
    export_model_json_to_solidworks_step,
    translate_model_json_to_solidworks_script,
    translate_model_json_to_solidworks_step,
    translate_product_package_to_solidworks_script,
)
from .capabilities import CAPABILITIES
from .compiler_compat import SolidWorksScriptTranslator  # noqa: F401
from .translator import SolidWorksTranslator

__all__ = [
    "CAPABILITIES",
    "SUPPORTED_SOLIDWORKS_VERSIONS",
    "SolidWorksTranslator",
    "export_model_json_to_solidworks_step",
    "translate_model_json_to_solidworks_script",
    "translate_model_json_to_solidworks_step",
    "translate_product_package_to_solidworks_script",
]
