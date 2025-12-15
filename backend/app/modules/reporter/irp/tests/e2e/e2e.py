"""
End-to-End IRP Message Testing Tool

This script runs the complete E2E workflow:
1. Capture UDP packet and save as pcap
2. Extract packet bytes
3. Parse with Java parser
4. Validate and log results

Directory structure:
- captures/: Contains pcap files and extracted packet bytes
- results/: Contains parsed XML results from Java parser
- templates/: Contains generated JSON templates for messages

Usage:
    python tests/e2e/e2e.py                      # Interactive menu
    python tests/e2e/e2e.py test 3               # Test message 3
    python tests/e2e/e2e.py test 3 IdsDataFormat100600.xml  # Test with specific XML
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.modules.reporter.irp.core.message_testing_coordinator import MessageTestingCoordinator
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator

# E2E directories
E2E_DIR = Path(__file__).parent
CAPTURES_DIR = E2E_DIR / "captures"
RESULTS_DIR = E2E_DIR / "results"
TEMPLATES_DIR = E2E_DIR / "templates"


def show_menu():
    """Display main menu."""
    print("\n" + "=" * 60)
    print("IRP Message E2E Testing Tool")
    print("=" * 60)
    print("1. Generate template for a message")
    print("2. Test a single message (full workflow)")
    print("3. Test multiple messages")
    print("4. View session summary")
    print("5. Check message status")
    print("6. Exit")
    print("=" * 60)


def select_xml_file():
    """Let user select an XML format file."""
    data_formats_dir = Path(__file__).parent.parent.parent / "data_formats"
    xml_files = sorted(data_formats_dir.glob("*.xml"))

    if not xml_files:
        print("[ERROR] No XML files found in data_formats/")
        return None

    print("\nAvailable XML Format Files:")
    for i, xml_file in enumerate(xml_files, 1):
        print(f"  {i}. {xml_file.name}")

    while True:
        try:
            choice = input("\nSelect XML file (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(xml_files):
                return str(xml_files[idx])
            else:
                print("[ERROR] Invalid selection")
        except ValueError:
            print("[ERROR] Please enter a number")


def generate_template():
    """Generate template for a message."""
    print("\n--- Generate Template ---")
    xml_file = select_xml_file()
    if not xml_file:
        return

    try:
        message_id = int(input("Enter message ID: ").strip())
    except ValueError:
        print("[ERROR] Invalid message ID")
        return

    try:
        generator = TemplateGenerator(xml_file)
        output_file = TEMPLATES_DIR / f"message_{message_id}_full.json"
        template = generator.generate_template(message_id, output_file, interactive=False)

        print(f"✅ Template generated: {output_file}")
        print(f"📋 Template preview:")
        print(json.dumps(template, indent=2)[:500] + "...")

    except Exception as e:
        print(f"❌ Error: {e}")


def test_single_message():
    """Test a single message with full E2E workflow."""
    print("\n--- Test Single Message E2E ---")
    xml_file = select_xml_file()
    if not xml_file:
        return

    try:
        message_id = int(input("Enter message ID: ").strip())
        from_ip = input("Enter source IP (default 127.0.0.1): ").strip() or "127.0.0.1"
        to_ip = input("Enter destination IP (default 127.0.0.1): ").strip() or "127.0.0.1"
    except ValueError:
        print("[ERROR] Invalid input")
        return

    try:
        coordinator = MessageTestingCoordinator(xml_file,
                                               captures_dir=CAPTURES_DIR,
                                               results_dir=RESULTS_DIR,
                                               templates_dir=TEMPLATES_DIR)
        result = coordinator.test_message(message_id, from_ip, to_ip, timeout=30)

        print("\n" + "=" * 60)
        print("TEST RESULT")
        print("=" * 60)
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


def test_multiple_messages():
    """Test multiple messages in E2E workflow."""
    print("\n--- Test Multiple Messages E2E ---")
    xml_file = select_xml_file()
    if not xml_file:
        return

    try:
        message_ids_str = input("Enter message IDs (comma-separated, e.g., 1,2,3): ").strip()
        message_ids = [int(x.strip()) for x in message_ids_str.split(",")]
    except ValueError:
        print("[ERROR] Invalid input")
        return

    from_ip = input("Enter source IP (default 127.0.0.1): ").strip() or "127.0.0.1"
    to_ip = input("Enter destination IP (default 127.0.0.1): ").strip() or "127.0.0.1"

    try:
        coordinator = MessageTestingCoordinator(xml_file,
                                               captures_dir=CAPTURES_DIR,
                                               results_dir=RESULTS_DIR,
                                               templates_dir=TEMPLATES_DIR)
        results = coordinator.test_messages_batch(message_ids, from_ip=from_ip, to_ip=to_ip)

        # Summary
        passed = sum(1 for r in results.values() if r.get("status") == "completed")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")

        print("\n" + "=" * 60)
        print("BATCH TEST SUMMARY")
        print("=" * 60)
        print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")

        for msg_id, result in results.items():
            status = "[OK]" if result.get("status") == "completed" else "[ERROR]"
            print(f"  {status} Message {msg_id}")

        coordinator.print_test_summary()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


def view_session_summary():
    """View current session summary."""
    print("\n--- Session Summary ---")
    try:
        logger = SessionLogger()
        logger.print_session_summary()
    except Exception as e:
        print(f"[ERROR] {e}")


def check_message_status():
    """Check status of a specific message."""
    print("\n--- Check Message Status ---")

    try:
        message_id = int(input("Enter message ID: ").strip())
    except ValueError:
        print("[ERROR] Invalid message ID")
        return

    try:
        logger = SessionLogger()
        status = logger.get_message_status(message_id)

        print(f"\nMessage {message_id} Status:")
        print(f"  Overall Status: {status['status']}")
        print(f"  Operations: {', '.join(status['operations'])}")

        if status['history']:
            print(f"\n  History:")
            for op in status['history']:
                print(f"    - {op['operation']}: {op['status']} ({op['timestamp']})")

    except Exception as e:
        print(f"[ERROR] {e}")


def main():
    """Main menu loop."""
    print("\nIRP Message E2E Testing Tool")
    print("Starting session logger...")

    try:
        logger = SessionLogger()
        print(f"Session ID: {logger.session_id}")

        # Check for previous session
        last_session = logger.get_last_session()
        if last_session and last_session.get("operations"):
            print(f"\nPrevious session with {len(last_session['operations'])} operations")
            print("Completed messages:", last_session.get("completed_messages", []))
            print("Failed messages:", last_session.get("failed_messages", []))
    except Exception as e:
        print(f"Warning: Could not initialize session logger: {e}")

    while True:
        try:
            show_menu()
            choice = input("Select option (1-6): ").strip()

            if choice == "1":
                generate_template()
            elif choice == "2":
                test_single_message()
            elif choice == "3":
                test_multiple_messages()
            elif choice == "4":
                view_session_summary()
            elif choice == "5":
                check_message_status()
            elif choice == "6":
                print("\n👋 Goodbye!")
                break
            else:
                print("[ERROR] Invalid option")

        except KeyboardInterrupt:
            print("\n\n🚫 Interrupted by user")
            break
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    # Command-line support
    if len(sys.argv) > 1:
        if sys.argv[1] == "test" and len(sys.argv) > 2:
            # Direct test: python e2e.py test <message_id> [xml_file]
            try:
                message_id = int(sys.argv[2])
                xml_file = sys.argv[3] if len(sys.argv) > 3 else "data_formats/IdsDataFormat100600.xml"

                print(f"\nTesting Message {message_id} with {xml_file}")
                print("=" * 80)

                coordinator = MessageTestingCoordinator(xml_file,
                                                       captures_dir=CAPTURES_DIR,
                                                       results_dir=RESULTS_DIR,
                                                       templates_dir=TEMPLATES_DIR)
                result = coordinator.test_message(message_id, "127.0.0.1", "127.0.0.1", timeout=30)

                # Print result
                print("\n" + "=" * 80)
                print("TEST RESULT")
                print("=" * 80)
                status_text = "PASSED" if result.get("status") == "completed" else "FAILED"
                print(f"Message {message_id}: {status_text}")
                print(f"Status: {result.get('status')}")

                if result.get("error"):
                    print(f"Error: {result.get('error')}")
                if result.get("warnings"):
                    print(f"Warnings: {result.get('warnings')}")

                # Show steps
                print("\nSteps:")
                for step in result.get("steps", []):
                    step_status = "[OK]" if step.get("status") == "completed" else "[ERROR]"
                    print(f"  {step_status} {step.get('step')}")

            except ValueError as e:
                # Check if it's actually a message ID parsing error
                if "invalid literal" in str(e).lower():
                    print("[ERROR] Invalid message ID. Usage: python e2e.py test <message_id> [xml_file]")
                else:
                    # It's a ValueError from somewhere else, show the actual error
                    print(f"[ERROR] {e}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[ERROR] Unknown command. Usage: python e2e.py test <message_id> [xml_file]")
    else:
        # Interactive menu
        main()

