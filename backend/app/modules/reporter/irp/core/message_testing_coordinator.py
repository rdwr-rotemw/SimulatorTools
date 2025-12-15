"""
Message Testing Coordinator - Orchestrates the complete message validation workflow.

Coordinates:
1. User-provided template data
2. UDP listener setup and packet capture
3. PCAP extraction to text format
4. Java parser validation
5. Error checking and reporting
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from backend.app.modules.reporter.irp.core.udp_listener import UdpPacketListener
from backend.app.modules.reporter.irp.core.pcap_extractor import PcapExtractor


class MessageTestingCoordinator:
    """Coordinates the complete message validation workflow."""

    def __init__(self, parser_jar: Optional[str] = None,
                 captures_dir: Optional[Path] = None, results_dir: Optional[Path] = None):
        """
        Initialize the testing coordinator.

        Args:
            parser_jar: Path to Java parser jar file (default: backend/app/modules/reporter/irp/parser/parser.jar)
            captures_dir: Directory to save PCAP captures
            results_dir: Directory to save parse results
        """
        # Use absolute path for parser jar
        if parser_jar is None:
            irp_base = Path(__file__).parent.parent
            self.parser_jar = irp_base / "parser" / "parser.jar"
        else:
            self.parser_jar = Path(parser_jar)

        # Set capture and results directories
        if captures_dir is None:
            self.captures_dir = Path(__file__).parent / "pcap_captures"
        else:
            self.captures_dir = Path(captures_dir)

        if results_dir is None:
            self.results_dir = self.captures_dir / "parse_results"
        else:
            self.results_dir = Path(results_dir)

        # Create directories if they don't exist
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Validate parser jar exists
        if not self.parser_jar.exists():
            raise FileNotFoundError(f"Parser JAR not found: {self.parser_jar}")

    def test_message(self,
                    message_id: int,
                    message_data: Dict[str, Any],
                    schema_obj,
                    xml_file_for_parser: str,
                    from_ip: str = "127.0.0.1",
                    to_ip: str = "127.0.0.1",
                    timeout: int = 10) -> Dict[str, Any]:
        """
        Complete testing workflow for a single message with user-provided template.

        Args:
            message_id: Message ID to test
            message_data: Template data provided by user
            schema_obj: ConvertXml schema object (loaded from MongoDB)
            xml_file_for_parser: Path to DataFormat XML file for Java parser
            from_ip: Source IP for IRP message
            to_ip: Destination IP for listening
            timeout: Timeout for listening

        Returns:
            Test result dictionary with status and details
        """
        test_result = {
            "message_id": message_id,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }

        try:
            # Step 1: Send message and capture packet
            pcap_file = self._capture_message(message_id, message_data, from_ip, to_ip, timeout, schema_obj)
            test_result["steps"].append({
                "step": "capture_packet",
                "status": "completed",
                "pcap_file": str(pcap_file)
            })

            # Step 2: Extract packet bytes
            extracted_file = self._extract_bytes(pcap_file)
            test_result["steps"].append({
                "step": "extract_bytes",
                "status": "completed",
                "extracted_file": str(extracted_file)
            })

            # Step 3: Parse with Java parser
            parse_result_file = self._parse_message(message_id, extracted_file, xml_file_for_parser)
            test_result["steps"].append({
                "step": "parse_message",
                "status": "completed",
                "parse_result_file": str(parse_result_file)
            })

            # Step 4: Check for errors
            errors, warnings = self._check_parse_errors(parse_result_file)

            if errors:
                test_result["status"] = "failed"
                test_result["errors"] = errors
            else:
                test_result["status"] = "completed"
                test_result["warnings"] = warnings if warnings else []

        except Exception as e:
            test_result["status"] = "failed"
            test_result["error"] = str(e)

        return test_result

    def _capture_message(self,
                        message_id: int,
                        message_data: Dict[str, Any],
                        from_ip: str,
                        to_ip: str,
                        timeout: int,
                        schema_obj) -> Path:
        """
        Capture message using UDP listener.

        Starts listener and sends message in background thread using irp_module.

        Args:
            message_id: Message ID to send
            message_data: Template data dict provided by user
            from_ip: Source IP address
            to_ip: Destination IP address
            timeout: Listener timeout in seconds
            schema_obj: ConvertXml schema object

        Returns:
            Path to captured PCAP file
        """
        import threading
        from backend.app.modules.reporter.irp.irp_module import send_irp_message

        listen_ip = "127.0.0.1" if to_ip in ["127.0.0.1", "localhost"] else "0.0.0.0"
        listener = UdpPacketListener(listen_ip=listen_ip, listen_port=2088, output_dir=self.captures_dir)

        sender_output = {"success": False, "error": None}

        def send_message_delayed():
            time.sleep(2)  # Give listener time to bind
            try:
                success, result = send_irp_message(schema_obj, message_id, message_data, from_ip, to_ip)
                sender_output["success"] = success
                if not success:
                    sender_output["error"] = result
            except Exception as e:
                sender_output["error"] = str(e)
                sender_output["success"] = False

        sender_thread = threading.Thread(target=send_message_delayed, daemon=False)
        sender_thread.start()

        pcap_file = listener.start(timeout=timeout, max_packets=1)
        sender_thread.join(timeout=15)

        packet_count = listener.get_packet_count()
        if packet_count == 0:
            error_msg = f"No packets captured after {timeout}s timeout"
            if sender_output["error"]:
                error_msg += f"\nSender error: {sender_output['error']}"
            elif not sender_output["success"]:
                error_msg += "\nSender reported failure"
            raise RuntimeError(error_msg)

        return Path(pcap_file)

    def _extract_bytes(self, pcap_file: Path) -> Path:
        """
        Extract bytes from PCAP file.

        Args:
            pcap_file: Path to PCAP file

        Returns:
            Path to extracted bytes text file
        """
        extractor = PcapExtractor(pcap_file)
        extracted_file = extractor.extract_bytes_to_text()
        return extracted_file

    def _parse_message(self, message_id: int, extracted_file: Path, xml_file: str) -> Path:
        """
        Parse message with Java parser.

        Args:
            message_id: Message ID
            extracted_file: Path to extracted packet bytes file
            xml_file: Path to DataFormat XML file for parser input

        Returns:
            Path to parsed XML result file
        """
        result_file = self.results_dir / f"message_{message_id}_parsed.xml"

        xml_file_abs = Path(xml_file).resolve()
        extracted_file_abs = extracted_file.resolve()
        parser_jar_abs = self.parser_jar.resolve()
        parser_dir = parser_jar_abs.parent

        cmd = [
            "java",
            "-jar",
            str(parser_jar_abs),
            str(xml_file_abs),
            str(extracted_file_abs),
            str(result_file),
            "--dump"
        ]

        try:
            result = subprocess.run(cmd, cwd=str(parser_dir), capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise RuntimeError(f"Parser failed: {result.stderr}")

            return result_file

        except subprocess.TimeoutExpired:
            raise RuntimeError("Parser timeout after 30 seconds")
        except Exception as e:
            raise RuntimeError(f"Parser execution failed: {e}")

    def _check_parse_errors(self, result_file: Path) -> Tuple[list, list]:
        """
        Check parser output for errors and warnings.

        Args:
            result_file: Path to parser result XML file

        Returns:
            Tuple of (errors, warnings) lists
        """
        errors = []
        warnings = []

        if not result_file.exists():
            return ["Parse result file not found"], []

        with open(result_file, 'r') as f:
            content = f.read()

        error_keywords = ['error', 'failed', 'invalid', 'exception']
        warning_keywords = ['warning', 'deprecated', 'note']

        for line in content.split('\n'):
            line_lower = line.lower()

            for keyword in error_keywords:
                if keyword in line_lower:
                    errors.append(line)
                    break

            for keyword in warning_keywords:
                if keyword in line_lower:
                    warnings.append(line)
                    break

        return errors, warnings

