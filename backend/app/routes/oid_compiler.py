import logging
import os
import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.modules.sapro.oid_compiler.compiler import MibCompiler
from backend.app.modules.sapro.oid_compiler.models import CompilationResult
from backend.app.models.user import User
from backend.app.utils.auth import require_sapro_access
from backend.app.utils.database import get_db
from backend.app.utils.device_driver import list_existing_drivers, save_uploaded_driver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oid-compiler", tags=["OID Compiler"])


def _get_output_dirs(workspace: str) -> tuple[str, str, str]:
    """Return (cmf_dir, var_dir, tcl_dir) based on workspace."""
    if workspace == "default":
        return "/opt/sapro/cmf", "/opt/sapro/var", "/opt/sapro/tcl"
    base = f"/opt/sapro/projects/{workspace}"
    return f"{base}/cmf", f"{base}/var", f"{base}/tcl"


@router.post("/compile", response_model=CompilationResult)
async def compile_mibs(
    mib_zip: UploadFile = File(..., description="MIB archive file (.rar or .zip) from Radware portal"),
    oids_pdf: UploadFile = File(..., description="OIDs PDF document"),
    output_name: str = Form(None, description="Output filename base (auto-detected if empty)"),
    device_driver_name: str = Form(None, description="Existing device driver filename"),
    device_driver_file: Optional[UploadFile] = File(None, description="New device driver JAR to upload"),
    soap_metadata_file: Optional[UploadFile] = File(None, description="soap_metadata.c file for modeling file generation"),
    current_user: User = Depends(require_sapro_access),
):
    """
    Compile MIB files and OIDs PDF into SAPRO .cmf, .var, and .tcl files.

    Optionally accepts a device driver (existing name or new upload) to set
    the rndVisionDriverActiveName scalar in the .var file.

    Optionally accepts soap_metadata.c to generate a TCL modeling file that
    simulates firmware behavior for tables with hidden columns.
    """
    workspace = current_user.workspace if (current_user.workspace and current_user.workspace != "*") else "default"
    cmf_output_dir, var_output_dir, modeling_output_dir = _get_output_dirs(workspace)

    # Resolve device driver filename
    driver_filename = None
    if device_driver_file and device_driver_file.filename:
        # Upload new driver to database storage
        success, message, metadata = await save_uploaded_driver(device_driver_file)
        if not success:
            raise HTTPException(status_code=400, detail=f"Driver upload failed: {message}")
        driver_filename = device_driver_file.filename
    elif device_driver_name:
        driver_filename = device_driver_name

    tmp_dir = tempfile.mkdtemp(prefix="mib_compiler_")
    try:
        zip_path = os.path.join(tmp_dir, mib_zip.filename)
        pdf_path = os.path.join(tmp_dir, oids_pdf.filename)

        with open(zip_path, "wb") as f:
            shutil.copyfileobj(mib_zip.file, f)
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(oids_pdf.file, f)

        # Save soap_metadata.c if provided
        soap_metadata_path = None
        if soap_metadata_file and soap_metadata_file.filename:
            soap_metadata_path = os.path.join(tmp_dir, soap_metadata_file.filename)
            with open(soap_metadata_path, "wb") as f:
                shutil.copyfileobj(soap_metadata_file.file, f)

        compiler = MibCompiler(
            mib_zip_path=zip_path,
            oids_pdf_path=pdf_path,
            output_dir=cmf_output_dir,
            var_output_dir=var_output_dir,
            modeling_output_dir=modeling_output_dir,
            output_name=output_name or None,
            device_driver=driver_filename,
            soap_metadata_path=soap_metadata_path,
        )
        result = compiler.compile()
        return result

    except Exception as e:
        logger.exception("MIB compilation endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/device-drivers")
async def list_drivers(
    _current_user: User = Depends(require_sapro_access),
):
    """List available device drivers from database storage."""
    drivers = list_existing_drivers()
    return {"drivers": drivers}


@router.get("/health")
async def health_check():
    """Check if the compiler module is available."""
    return {"status": "ok", "module": "oid_compiler"}
