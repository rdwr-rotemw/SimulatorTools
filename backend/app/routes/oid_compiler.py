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
from backend.app.utils.device_driver import DEVICE_DRIVER_STORAGE_PATH, list_existing_drivers, save_uploaded_driver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oid-compiler", tags=["OID Compiler"])


def _get_output_dirs(workspace: str) -> tuple[str, str]:
    """Return (cmf_dir, var_dir) based on workspace."""
    if workspace == "default":
        return "/opt/sapro/cmf", "/opt/sapro/var"
    return f"/opt/sapro/projects/{workspace}/cmf", f"/opt/sapro/projects/{workspace}/var"


@router.post("/compile", response_model=CompilationResult)
async def compile_mibs(
    mib_zip: UploadFile = File(..., description="MIB archive file (.rar or .zip) from Radware portal"),
    oids_pdf: UploadFile = File(..., description="OIDs PDF document"),
    output_name: str = Form(None, description="Output filename base (auto-detected if empty)"),
    device_driver_name: str = Form(None, description="Existing device driver filename"),
    device_driver_file: Optional[UploadFile] = File(None, description="New device driver JAR to upload"),
    device_name: str = Form("DefensePro_$$MYIPADDRESS$$", description="Device name (sysName)"),
    platform: str = Form("Virtual DefensePro X", description="Device platform type"),
    data_ports: int = Form(2, description="Number of data/network ports"),
    mgmt_ports: int = Form(1, description="Number of management ports"),
    current_user: User = Depends(require_sapro_access),
):
    """
    Compile MIB files and OIDs PDF into SAPRO .cmf and .var files.

    Optionally accepts a device driver (existing name or new upload) to set
    the rndVisionDriverActiveName scalar in the .var file.
    """
    workspace = current_user.workspace if (current_user.workspace and current_user.workspace != "*") else "default"
    cmf_output_dir, var_output_dir = _get_output_dirs(workspace)

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

        # Resolve JAR path for CC column parsing
        jar_path = None
        if driver_filename:
            jar_path = os.path.join(DEVICE_DRIVER_STORAGE_PATH, driver_filename)
            if not os.path.exists(jar_path):
                jar_path = None

        custom_settings = {
            "device_name": device_name,
            "platform": platform,
            "data_ports": data_ports,
            "mgmt_ports": mgmt_ports,
        }

        compiler = MibCompiler(
            mib_zip_path=zip_path,
            oids_pdf_path=pdf_path,
            output_dir=cmf_output_dir,
            var_output_dir=var_output_dir,
            output_name=output_name or None,
            device_driver=driver_filename,
            device_driver_jar_path=jar_path,
            custom_settings=custom_settings,
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
