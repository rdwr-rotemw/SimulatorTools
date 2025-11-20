"""IRP helper utilities for IdsDataFormat conversion.

This module contains a placeholder conversion function that will be implemented
by the user to transform IdsDataFormat XML files into JSON-like Python dicts.
"""
from typing import Dict, Any

from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml


def convert_xml(xml_file_path: str) -> Dict[str, Any]:
    """Convert IdsDataFormat XML file to JSON dict.

    Args:
        xml_file_path: Path to downloaded XML file

    Returns:
        Dict containing parsed IdsDataFormat data
    """
    return ConvertXml(xml_file_path).convert_xml()


