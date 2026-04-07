import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from backend.app.modules.sapro.oid_compiler.cmf_generator import CmfGenerator
from backend.app.modules.sapro.oid_compiler.dynamic_row_detector import DynamicRowDetector
from backend.app.modules.sapro.oid_compiler.jar_parser import parse_cc_columns_from_jar
from backend.app.modules.sapro.oid_compiler.mib_parser import MibParser
from backend.app.modules.sapro.oid_compiler.models import CompilationResult
from backend.app.modules.sapro.oid_compiler.var_generator import VarGenerator
from backend.app.utils.sapro_ssh import get_sapro_ssh_client

logger = logging.getLogger(__name__)


class MibCompiler:
    """Main orchestrator for the MIB compilation pipeline."""

    def __init__(
        self,
        mib_zip_path: str,
        output_dir: str = "/opt/sapro/cmf",
        var_output_dir: str = "/opt/sapro/var",
        output_name: Optional[str] = None,
        device_driver: Optional[str] = None,
        device_driver_jar_path: Optional[str] = None,
        custom_settings: Optional[dict] = None,
    ):
        self.mib_zip_path = mib_zip_path
        self.output_dir = output_dir
        self.var_output_dir = var_output_dir
        self.output_name = output_name
        self.device_driver = device_driver
        self.device_driver_jar_path = device_driver_jar_path
        self.custom_settings = custom_settings
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

            # Step 2: Auto-detect version and output name
            version = self._auto_detect_version(mib_parser)

            if not self.output_name:
                self.output_name = self._generate_output_name(version)

            # Step 3: Parse device driver JAR for CC column mappings (if available)
            cc_columns: dict[str, set[str]] = {}
            if self.device_driver_jar_path:
                logger.info("Parsing device driver JAR for CC column mappings...")
                cc_columns = parse_cc_columns_from_jar(self.device_driver_jar_path)

            # Step 4: Detect dynamic rows (MIB-only, no PDF dependency)
            logger.info("Detecting dynamic row creation tables...")
            detector = DynamicRowDetector(oid_entries, cc_columns)
            dynamic_rows = detector.detect_all()

            for dr in dynamic_rows:
                if not dr.is_fully_detected:
                    self.warnings.append(dr.detection_warning or f"Undetected table: {dr.entry_name}")

            # Step 5: Generate CMF content
            logger.info("Generating CMF file...")
            cmf_gen = CmfGenerator(oid_entries)
            cmf_content = cmf_gen.generate()

            # Step 6: Generate VAR content
            logger.info("Generating VAR file...")
            var_gen = VarGenerator(
                oid_entries, dynamic_rows, version, self.device_driver,
                custom_settings=self.custom_settings,
            )
            var_content = var_gen.generate()

            # Step 7: Write files to SAPRO via SSH
            cmf_remote_path = f"{self.output_dir}/{self.output_name}.cmf"
            var_remote_path = f"{self.var_output_dir}/{self.output_name}.var"

            logger.info(f"Writing files to SAPRO: {cmf_remote_path}, {var_remote_path}")
            self._write_remote_file(cmf_remote_path, cmf_content, work_dir)
            self._write_remote_file(var_remote_path, var_content, work_dir)

            # Step 8: Collect stats
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
                cmf_path=cmf_remote_path,
                var_path=var_remote_path,
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

    def _write_remote_file(self, remote_path: str, content: str, work_dir: str) -> None:
        """Write file content to SAPRO server via SCP."""
        ssh_client = get_sapro_ssh_client()

        # Ensure parent directory exists on SAPRO
        parent_dir = str(Path(remote_path).parent)
        ssh_client.execute_command(f"mkdir -p {parent_dir}", check_stderr=False)

        # Write to local temp file with Unix line endings, then upload via SCP
        local_path = str(Path(work_dir) / Path(remote_path).name)
        with open(local_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        success, output = ssh_client.upload_file(local_path, remote_path)
        if not success:
            raise RuntimeError(f"Failed to upload {remote_path} to SAPRO: {output}")

        logger.info(f"Uploaded {len(content)} bytes to SAPRO: {remote_path}")

    def _auto_detect_version(self, mib_parser: MibParser) -> str:
        zip_name = Path(self.mib_zip_path).stem
        version_match = re.search(r"(\d+[._\-]\d+(?:[._\-]\d+)*)", zip_name)
        if version_match:
            return version_match.group(1).replace("_", ".").replace("-", ".")

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
        # "10.12.0.1" -> "DP_10_12_01" (major_minor_patch with leading zero)
        parts = version.split(".")
        if len(parts) >= 4:
            return f"DP_{parts[0]}_{parts[1]}_{parts[3].zfill(2)}"
        if len(parts) >= 3:
            return f"DP_{parts[0]}_{parts[1]}_{parts[2].zfill(2)}"
        if len(parts) >= 2:
            return f"DP_{parts[0]}_{parts[1]}"
        return f"DP_{version.replace('.', '_')}"
