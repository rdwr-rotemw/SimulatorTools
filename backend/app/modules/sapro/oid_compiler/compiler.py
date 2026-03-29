import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from backend.app.modules.sapro.oid_compiler.cmf_generator import CmfGenerator
from backend.app.modules.sapro.oid_compiler.dynamic_row_detector import DynamicRowDetector
from backend.app.modules.sapro.oid_compiler.mib_parser import MibParser
from backend.app.modules.sapro.oid_compiler.models import CompilationResult
from backend.app.modules.sapro.oid_compiler.pdf_parser import PdfParser
from backend.app.modules.sapro.oid_compiler.var_generator import VarGenerator

logger = logging.getLogger(__name__)


class MibCompiler:
    """Main orchestrator for the MIB compilation pipeline."""

    def __init__(
        self,
        mib_zip_path: str,
        oids_pdf_path: str,
        output_dir: str = "/opt/sapro/cmf",
        var_output_dir: str = "/opt/sapro/var",
        output_name: Optional[str] = None,
        num_rows: int = 2,
    ):
        self.mib_zip_path = mib_zip_path
        self.oids_pdf_path = oids_pdf_path
        self.output_dir = Path(output_dir)
        self.var_output_dir = Path(var_output_dir)
        self.output_name = output_name
        self.num_rows = num_rows
        self.warnings: list[str] = []

    def compile(self) -> CompilationResult:
        work_dir = tempfile.mkdtemp(prefix="mib_work_")

        try:
            # Step 1: Parse MIB files
            logger.info("Parsing MIB files...")
            mib_parser = MibParser(self.mib_zip_path, work_dir)
            oid_entries = mib_parser.parse()

            if not oid_entries:
                return CompilationResult(
                    success=False,
                    errors=["No OID entries were parsed from the MIB files."],
                )

            # Step 2: Parse OIDs PDF
            logger.info("Parsing OIDs PDF...")
            pdf_parser = PdfParser(self.oids_pdf_path)
            pdf_tables = pdf_parser.parse()
            version = pdf_parser.get_version()

            if not pdf_tables:
                self.warnings.append(
                    "No table structures extracted from PDF. "
                    "Dynamic row creation blocks will not be generated."
                )

            # Step 3: Auto-detect version and output name
            if not version:
                version = self._auto_detect_version(mib_parser)

            if not self.output_name:
                self.output_name = self._generate_output_name(version)

            # Step 4: Detect dynamic rows
            logger.info("Detecting dynamic row creation tables...")
            detector = DynamicRowDetector(oid_entries, pdf_tables)
            dynamic_rows = detector.detect_all()

            for dr in dynamic_rows:
                if not dr.is_fully_detected:
                    self.warnings.append(dr.detection_warning or f"Undetected table: {dr.entry_name}")

            # Step 5: Generate CMF
            logger.info("Generating CMF file...")
            cmf_path = str(self.output_dir / f"{self.output_name}.cmf")
            cmf_gen = CmfGenerator(oid_entries)
            cmf_path = cmf_gen.generate(cmf_path)

            # Step 6: Generate VAR
            logger.info("Generating VAR file...")
            var_path = str(self.var_output_dir / f"{self.output_name}.var")
            var_gen = VarGenerator(oid_entries, dynamic_rows, version, self.num_rows)
            var_path = var_gen.generate(var_path)

            # Step 7: Collect stats
            stats = {
                "total_oids": len(oid_entries),
                "scalar_oids": sum(1 for e in oid_entries if e.index_type == "S" and not e.is_table_entry),
                "table_columns": sum(1 for e in oid_entries if e.is_table_column),
                "tables": len(set(e.table_name for e in oid_entries if e.table_name)),
                "enum_oids": sum(1 for e in oid_entries if e.has_enum),
                "dynamic_row_tables": len(dynamic_rows),
                "rowstatus_tables": sum(1 for d in dynamic_rows if d.row_type.value == "rowstatus"),
                "rmonstatus_tables": sum(1 for d in dynamic_rows if d.row_type.value == "rmonstatus"),
                "newinstance_tables": sum(1 for d in dynamic_rows if d.row_type.value == "newinstance"),
                "commented_out_tables": sum(1 for d in dynamic_rows if not d.is_fully_detected),
            }

            logger.info(f"Compilation complete: {stats}")

            return CompilationResult(
                success=True,
                cmf_path=cmf_path,
                var_path=var_path,
                version=version,
                stats=stats,
                warnings=self.warnings,
            )

        except Exception as e:
            logger.exception("Compilation failed")
            return CompilationResult(
                success=False,
                errors=[str(e)],
                warnings=self.warnings,
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _auto_detect_version(self, mib_parser: MibParser) -> str:
        # Try from ZIP filename
        zip_name = Path(self.mib_zip_path).stem
        version_match = re.search(r"(\d+[._]\d+(?:[._]\d+)*)", zip_name)
        if version_match:
            return version_match.group(1).replace("_", ".")

        # Try from MIB module names
        modules = mib_parser.get_mib_modules()
        for filename, _ in modules:
            version_match = re.search(r"(\d+[._]\d+(?:[._]\d+)*)", filename)
            if version_match:
                return version_match.group(1).replace("_", ".")

        self.warnings.append("Could not auto-detect DefensePro version.")
        return "unknown"

    def _generate_output_name(self, version: str) -> str:
        if version == "unknown":
            return "DP_unknown"
        # "10.12.0.0" -> "DP_10_12"
        parts = version.split(".")
        if len(parts) >= 2:
            return f"DP_{parts[0]}_{parts[1]}"
        return f"DP_{version.replace('.', '_')}"
