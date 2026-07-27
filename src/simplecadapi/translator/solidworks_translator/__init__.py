"""SolidWorks translator backend for SimpleCAD model JSON."""

from .api import (
    export_model_json_to_solidworks_step,
    translate_model_json_to_solidworks_script,
    translate_model_json_to_solidworks_step,
)
from .capabilities import CAPABILITIES
from .compiler import SolidWorksScriptTranslator
from .translator import SolidWorksTranslator

__all__ = [
    "CAPABILITIES",
    "SolidWorksScriptTranslator",
    "SolidWorksTranslator",
    "export_model_json_to_solidworks_step",
    "translate_model_json_to_solidworks_script",
    "translate_model_json_to_solidworks_step",
]
