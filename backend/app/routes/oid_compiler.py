import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.modules.sapro.oid_compiler.compiler import MibCompiler
from backend.app.modules.sapro.oid_compiler.models import CompilationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oid-compiler", tags=["OID Compiler"])


@router.post("/compile", response_model=CompilationResult)
async def compile_mibs(
    mib_zip: UploadFile = File(..., description="MIB ZIP file from Radware portal"),
    oids_pdf: UploadFile = File(..., description="OIDs PDF document"),
    output_name: str = Form(None, description="Output filename base (auto-detected if empty)"),
    num_rows: int = Form(2, description="Number of static rows per table"),
    cmf_output_dir: str = Form("/opt/sapro/cmf", description="CMF output directory"),
    var_output_dir: str = Form("/opt/sapro/var", description="VAR output directory"),
):
    """
    Compile MIB files and OIDs PDF into SAPRO .cmf and .var files.

    Upload both a MIB ZIP file and an OIDs PDF document for the same
    DefensePro version. The compiler will:
    1. Parse MIB files to extract OID definitions with full metadata
    2. Parse the PDF to extract table structure information
    3. Generate a .cmf file with all OIDs, types, ranges, and enums
    4. Generate a .var file with scalars, static tables, and dynamic
       row creation blocks
    """
    tmp_dir = tempfile.mkdtemp(prefix="mib_compiler_")
    try:
        zip_path = os.path.join(tmp_dir, mib_zip.filename)
        pdf_path = os.path.join(tmp_dir, oids_pdf.filename)

        with open(zip_path, "wb") as f:
            shutil.copyfileobj(mib_zip.file, f)
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(oids_pdf.file, f)

        compiler = MibCompiler(
            mib_zip_path=zip_path,
            oids_pdf_path=pdf_path,
            output_dir=cmf_output_dir,
            var_output_dir=var_output_dir,
            output_name=output_name or None,
            num_rows=num_rows,
        )
        result = compiler.compile()
        return result

    except Exception as e:
        logger.exception("MIB compilation endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/health")
async def health_check():
    """Check if the compiler module is available."""
    return {"status": "ok", "module": "oid_compiler"}
