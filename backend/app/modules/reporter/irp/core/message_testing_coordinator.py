"""
Message Testing Coordinator - Orchestrates the complete message validation workflow.

This module coordinates:
1. Template generation with all fields
2. UDP listener setup and packet capture
3. PCAP extraction to text format
4. Java parser validation
5. Error checking and reporting
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from backend.app.modules.reporter.irp.core.udp_listener import UdpPacketListener
from backend.app.modules.reporter.irp.core.pcap_extractor import PcapExtractor
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator


class MessageTestingCoordinator:
    """
    Coordinates the complete message validation workflow.
    """

    def __init__(self, xml_file: str, parser_jar: str = "parser/parser.jar",
                 captures_dir: Optional[Path] = None, results_dir: Optional[Path] = None,
                 templates_dir: Optional[Path] = None):
        """
        Initialize the testing coordinator.

        Args:
            xml_file: Path to XML schema file
            parser_jar: Path to Java parser jar file
            captures_dir: Directory to save PCAP captures (default: core/pcap_captures/)
            results_dir: Directory to save parse results (default: captures_dir/parse_results/)
            templates_dir: Directory to save generated templates (default: core/test_templates/)
        """
        self.xml_file = Path(xml_file)
        self.parser_jar = Path(parser_jar)
        self.template_generator = TemplateGenerator(str(self.xml_file))

        # Set capture and results directories
        if captures_dir is None:
            self.captures_dir = Path(__file__).parent / "pcap_captures"
        else:
            self.captures_dir = Path(captures_dir)

        if results_dir is None:
            self.results_dir = self.captures_dir / "parse_results"
        else:
            self.results_dir = Path(results_dir)

        if templates_dir is None:
            self.templates_dir = Path(__file__).parent / "test_templates"
        else:
            self.templates_dir = Path(templates_dir)

        # Create directories if they don't exist
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Validate parser jar exists
        if not self.parser_jar.exists():
            raise FileNotFoundError(f"Parser JAR not found: {self.parser_jar}")

    def test_message(self,
                    message_id: int,
                    from_ip: str = "127.0.0.1",
                    to_ip: str = "127.0.0.1",
                    irp_tool_path: str = "irp_module.py",
                    timeout: int = 10) -> Dict[str, Any]:
        """
        Complete testing workflow for a single message.

        Args:
            message_id: Message ID to test
            from_ip: Source IP for IRP message
            to_ip: Destination IP for listening
            irp_tool_path: Path to irp_bckp.py
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
            # Step 1: Generate template
            template_path = self._generate_template(message_id)
            test_result["steps"].append({
                "step": "generate_template",
                "status": "completed",
                "template_file": str(template_path)
            })

            # Step 2: Setup listener and send message
            pcap_file = self._capture_message(message_id, template_path, from_ip, to_ip, timeout, irp_tool_path)
            test_result["steps"].append({
                "step": "capture_packet",
                "status": "completed",
                "pcap_file": str(pcap_file)
            })

            # Step 3: Extract packet bytes
            extracted_file = self._extract_bytes(pcap_file)
            test_result["steps"].append({
                "step": "extract_bytes",
                "status": "completed",
                "extracted_file": str(extracted_file)
            })

            # Step 4: Parse with Java parser
            parse_result_file = self._parse_message(message_id, extracted_file)
            test_result["steps"].append({
                "step": "parse_message",
                "status": "completed",
                "parse_result_file": str(parse_result_file)
            })

            # Step 5: Check for errors
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

    def _generate_template(self, message_id: int) -> Path:
        """Generate complete template for message."""
        template_file = self.templates_dir / f"message_{message_id}_full.json"

        try:
            template = self.template_generator.generate_template(message_id, template_file, interactive=False)

            print(f"[OK] Template generated: {template_file}")
            return template_file

        except Exception as e:
            print(f"[ERROR] Failed to generate template: {e}")
            raise

    def _capture_message(self,
                        message_id: int,
                        template_file: Path,
                        from_ip: str,
                        to_ip: str,
                        timeout: int,
                        irp_tool_path: str = "irp_module.py") -> Path:
        """
        Capture message using listener - AUTOMATED.

        Starts listener and automatically sends message in background thread.
        """
        import threading

        # Validate inputs
        print(f"[DEBUG] Template file exists: {template_file.exists()}")
        if not template_file.exists():
            raise FileNotFoundError(f"Template file not found: {template_file}")

        print(f"[DEBUG] XML file exists: {self.xml_file.exists()}")
        if not self.xml_file.exists():
            raise FileNotFoundError(f"XML file not found: {self.xml_file}")

        # For localhost on Windows, use 127.0.0.1 for both listener and sender
        listen_ip = "127.0.0.1" if to_ip in ["127.0.0.1", "localhost"] else "0.0.0.0"

        listener = UdpPacketListener(listen_ip=listen_ip, listen_port=2088, output_dir=self.captures_dir)

        print(f"[LISTENER] Starting listener on {listen_ip}:2088...")
        print(f"[LISTENER] Listener timeout: {timeout} seconds")
        print(f"[DEBUG] Captures directory: {self.captures_dir}")

        sender_output = {"stdout": "", "stderr": "", "returncode": None}

        # Function to send message after delay
        def send_message_delayed():
            print(f"[SEND] Sender thread started, waiting 2 seconds for listener to bind...")
            time.sleep(2)  # Give listener time to start and bind socket
            try:
                cmd = [
                    "python", irp_tool_path,
                    "-m", str(message_id),
                    "-src", from_ip,
                    "-dst", to_ip,
                    "-v", str(template_file),
                    "-x", str(self.xml_file)
                ]
                print(f"[SEND] Executing command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                sender_output["stdout"] = result.stdout
                sender_output["stderr"] = result.stderr
                sender_output["returncode"] = result.returncode

                print(f"[SEND] Process returncode: {result.returncode}")
                print(f"[SEND] Process stdout: {result.stdout[:200] if result.stdout else '(empty)'}")

                if result.stderr:
                    print(f"[SEND] Process stderr: {result.stderr[:200]}")

                if "Successfully sent" in result.stdout or result.returncode == 0:
                    print(f"[SEND] OK Message {message_id} sent successfully")
                else:
                    print(f"[SEND] WARNING Message {message_id} may not have sent properly")
                    print(f"[SEND] Full stderr: {result.stderr}")
            except subprocess.TimeoutExpired:
                print(f"[SEND] ERROR Process timeout after 10 seconds")
                sender_output["stderr"] = "Process timeout"
            except FileNotFoundError:
                print(f"[SEND] ERROR irp_bckp.py not found at: {irp_tool_path}")
                sender_output["stderr"] = f"irp_module.py not found at {irp_tool_path}"
            except Exception as e:
                print(f"[SEND] ERROR Exception: {e}")
                sender_output["stderr"] = str(e)

        # Start sender in background thread (NOT daemon so it completes)
        sender_thread = threading.Thread(target=send_message_delayed, daemon=False)
        sender_thread.start()
        print(f"[DEBUG] Sender thread started")

        # Start listening (this also runs in a background thread internally)
        print(f"[DEBUG] Starting listener.start(timeout={timeout}, max_packets=1)")
        pcap_file = listener.start(timeout=timeout, max_packets=1)
        print(f"[DEBUG] Listener finished, PCAP file: {pcap_file}")

        # Wait for sender to complete
        print(f"[DEBUG] Waiting for sender thread to complete (max 15 seconds)...")
        sender_thread.join(timeout=15)
        print(f"[DEBUG] Sender thread alive: {sender_thread.is_alive()}")

        packet_count = listener.get_packet_count()
        print(f"[DEBUG] Packet count: {packet_count}")
        print(f"[DEBUG] Sender output - returncode: {sender_output['returncode']}, stderr: {sender_output['stderr'][:100] if sender_output['stderr'] else '(empty)'}")

        if packet_count == 0:
            error_msg = f"No packets captured after {timeout}s timeout"
            if sender_output["stderr"]:
                error_msg += f"\nSender error: {sender_output['stderr']}"
            if sender_output["stdout"]:
                error_msg += f"\nSender output: {sender_output['stdout']}"
            raise RuntimeError(error_msg)

        return Path(pcap_file)

    def _extract_bytes(self, pcap_file: Path) -> Path:
        """Extract bytes from PCAP."""
        print(f"[DEBUG] Extracting bytes from PCAP: {pcap_file}")
        print(f"[DEBUG] PCAP file exists: {pcap_file.exists()}")
        print(f"[DEBUG] PCAP file size: {pcap_file.stat().st_size if pcap_file.exists() else 'N/A'} bytes")

        extractor = PcapExtractor(pcap_file)
        extracted_file = extractor.extract_bytes_to_text()

        print(f"[DEBUG] Extracted file: {extracted_file}")
        print(f"[DEBUG] Extracted file exists: {Path(extracted_file).exists()}")
        if Path(extracted_file).exists():
            print(f"[DEBUG] Extracted file size: {Path(extracted_file).stat().st_size} bytes")

        print(f"[OK] Bytes extracted: {extracted_file}")
        return extracted_file

    def _parse_message(self, message_id: int, extracted_file: Path) -> Path:
        """Parse message with Java parser using absolute paths."""
        result_file = self.results_dir / f"message_{message_id}_parsed.xml"

        # Get absolute paths
        project_root = Path(__file__).parent.parent
        xml_file_abs = (project_root / self.xml_file).resolve()
        extracted_file_abs = extracted_file.resolve()
        parser_jar_abs = (project_root / self.parser_jar).resolve()
        parser_dir = parser_jar_abs.parent

        print(f"[DEBUG] Parser paths:")
        print(f"[DEBUG]   XML file: {xml_file_abs} (exists: {xml_file_abs.exists()})")
        print(f"[DEBUG]   Extracted: {extracted_file_abs} (exists: {extracted_file_abs.exists()})")
        print(f"[DEBUG]   Parser JAR: {parser_jar_abs} (exists: {parser_jar_abs.exists()})")
        print(f"[DEBUG]   Parser dir: {parser_dir}")
        print(f"[DEBUG]   Result file: {result_file}")

        try:
            cmd = [
                "java",
                "-jar",
                str(parser_jar_abs),
                str(xml_file_abs),
                str(extracted_file_abs),
                str(result_file),
                "--dump"
            ]

            print(f"[PARSER] Parsing message {message_id}...")
            print(f"[PARSER] XML: {xml_file_abs}")
            print(f"[PARSER] Input: {extracted_file_abs}")
            print(f"[PARSER] Output: {result_file}")
            print(f"[DEBUG] Command: {' '.join(cmd)}")
            print(f"[DEBUG] Working directory: {parser_dir}")

            result = subprocess.run(cmd, cwd=str(parser_dir), capture_output=True, text=True, timeout=30)

            print(f"[DEBUG] Parser returncode: {result.returncode}")
            if result.stdout:
                print(f"[DEBUG] Parser stdout: {result.stdout[:300]}")
            if result.stderr:
                print(f"[DEBUG] Parser stderr: {result.stderr[:300]}")

            if result.returncode != 0:
                print(f"[ERROR] Parser error: {result.stderr}")
                raise RuntimeError(f"Parser failed: {result.stderr}")

            print(f"[DEBUG] Result file exists: {result_file.exists()}")
            if result_file.exists():
                print(f"[DEBUG] Result file size: {result_file.stat().st_size} bytes")

            print(f"[OK] Parse complete: {result_file}")
            return result_file

        except subprocess.TimeoutExpired:
            print(f"[ERROR] Parser timeout after 30 seconds")
            raise RuntimeError("Parser timeout")
        except Exception as e:
            print(f"[ERROR] Parser exception: {e}")
            raise RuntimeError(f"Parser execution failed: {e}")


    def _check_parse_errors(self, result_file: Path) -> Tuple[list, list]:
        """
        Check parser output for errors and warnings.

        Returns:
            (errors, warnings) tuple
        """
        errors = []
        warnings = []

        if not result_file.exists():
            return ["Parse result file not found"], []

        with open(result_file, 'r') as f:
            content = f.read()

        # Check for common error indicators
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

    def test_messages_batch(self, message_ids: list, **kwargs) -> Dict[int, Dict]:
        """
        Test multiple messages.

        Args:
            message_ids: List of message IDs to test
            **kwargs: Additional arguments for test_message

        Returns:
            Dictionary mapping message IDs to test results
        """
        results = {}

        for msg_id in message_ids:
            print(f"\n{'=' * 60}")
            print(f"Testing Message {msg_id}")
            print(f"{'=' * 60}")

            result = self.test_message(msg_id, **kwargs)
            results[msg_id] = result

            if result["status"] == "failed":
                print(f"[FAILED] Message {msg_id} test FAILED")
                if "errors" in result:
                    for error in result["errors"]:
                        print(f"  [ERROR] {error}")
            else:
                print(f"[OK] Message {msg_id} test PASSED")
                if "warnings" in result:
                    for warning in result["warnings"]:
                        print(f"  [WARNING] {warning}")

        return results

    def print_test_summary(self) -> None:
        """Print testing session summary."""
        self.session_logger.print_session_summary()


def test_message(xml_file: str,
                message_id: int,
                from_ip: str = "127.0.0.1",
                to_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Convenience function to test a single message.

    Args:
        xml_file: XML schema file
        message_id: Message ID to test
        from_ip: Source IP
        to_ip: Destination IP

    Returns:
        Test result
    """
    coordinator = MessageTestingCoordinator(xml_file)
    return coordinator.test_message(message_id, from_ip, to_ip)


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        xml_file = sys.argv[1]
        message_id = int(sys.argv[2])
        from_ip = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
        to_ip = sys.argv[4] if len(sys.argv) > 4 else "127.0.0.1"

        coordinator = MessageTestingCoordinator(xml_file)
        result = coordinator.test_message(message_id, from_ip, to_ip)

        print("\n" + "=" * 60)
        print("TEST RESULT")
        print("=" * 60)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python message_testing_coordinator.py <xml_file> <message_id> [from_ip] [to_ip]")

