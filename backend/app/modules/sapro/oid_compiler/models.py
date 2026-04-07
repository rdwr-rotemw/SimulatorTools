from typing import Optional
from enum import Enum

from pydantic import BaseModel


class AccessLevel(str, Enum):
    RO = "RO"
    RW = "RW"
    WO = "WO"
    NA = "NA"
    CREATE = "Create"


class DynamicRowType(str, Enum):
    ROWSTATUS = "rowstatus"
    RMONSTATUS = "rmonstatus"
    NEWINSTANCE = "newinstance"


class OidEntry(BaseModel):
    """A single OID as parsed from MIB files."""
    oid: str
    label: str
    syntax: str
    original_syntax: str = ""
    access: AccessLevel
    is_table_entry: bool = False
    is_table_node: bool = False
    is_structural_node: bool = False
    is_table_column: bool = False
    table_name: Optional[str] = None
    entry_name: Optional[str] = None
    index_columns: list[str] = []
    implied_indexes: set[str] = set()
    min_range: Optional[int] = None
    max_range: Optional[int] = None
    has_enum: bool = False
    enum_values: dict[str, int] = {}
    default_value: Optional[str] = None
    description: str = ""
    mib_module: str = ""
    display_hint: Optional[str] = None
    index_type: str = "S"
    range_str: str = ""
    enum_flag: str = "d"


class PdfColumnInfo(BaseModel):
    """A single column within a table, as extracted from the OIDs PDF."""
    oid: str
    label: str
    syntax: str
    table_name: str
    index_name: str
    access: str
    description: str


class PdfTableInfo(BaseModel):
    """Table structure info extracted from the OIDs PDF."""
    table_name: str
    entry_name: str
    columns: list[PdfColumnInfo]
    index_columns: list[str]


class DynamicColumnConfig(BaseModel):
    """A single %dcol line's configuration."""
    label: str
    required: str
    syntax: str
    access: str
    value_info: str


class DynamicRowConfig(BaseModel):
    """Configuration for a single dynamic row creation block."""
    entry_name: str
    row_type: DynamicRowType
    columns: list[DynamicColumnConfig]
    setaction_column: Optional[str] = None
    setaction_type: Optional[str] = None
    setaction_value: Optional[str] = None
    is_fully_detected: bool = True
    detection_warning: Optional[str] = None


class SoapColumnInfo(BaseModel):
    """A single column from a soap_metadata.c attrList array."""
    position: int  # 1-based column position (maps to C1, C2, ... in CMF)
    soap_name: Optional[str] = None  # SOAP attribute name, None if hidden
    is_hidden: bool = False
    is_key: bool = False


class SoapTableInfo(BaseModel):
    """Parsed table metadata from soap_metadata.c."""
    entry_name: str  # e.g., "rsBWMNetworkEntry"
    columns: list[SoapColumnInfo]
    soap_namespace: Optional[str] = None  # e.g., "radware.Classes.Networks"
    has_create: bool = False  # Whether CC can create rows via SOAP
    hidden_count: int = 0
    visible_count: int = 0


class CompilationResult(BaseModel):
    """Result returned to the frontend after compilation."""
    success: bool
    cmf_path: Optional[str] = None
    var_path: Optional[str] = None
    version: str = ""
    stats: dict = {}
    warnings: list[str] = []
    errors: list[str] = []
