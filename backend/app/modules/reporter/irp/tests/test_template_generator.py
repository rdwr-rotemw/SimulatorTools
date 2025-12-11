#!/usr/bin/env python3
"""
Comprehensive IRP Template Generator Test Suite

This script tests template generation for all messages in the IRP data format.
It validates:
1. Bitmap fields are correctly detected and have options
2. Overlap/switch patterns are properly merged (no field duplication)
3. All messages can generate templates without errors
4. Schema metadata is properly structured

Usage:
    python -m backend.app.modules.reporter.irp.tests.test_template_generator

    # Test specific message
    python -m backend.app.modules.reporter.irp.tests.test_template_generator --message 12

    # Verbose output
    python -m backend.app.modules.reporter.irp.tests.test_template_generator -v

    # Test only bitmap detection
    python -m backend.app.modules.reporter.irp.tests.test_template_generator --test-bitmaps
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Determine project root and add to path
# When run as module: backend.app.modules.reporter.irp.tests.test_template_generator
# When run as script: backend/app/modules/reporter/irp/tests/test_template_generator.py
current_file = Path(__file__).resolve()

# Find project root by looking for backend directory
project_root = current_file
while project_root.name != 'SimulatorTools' and project_root.parent != project_root:
    project_root = project_root.parent

if project_root.name != 'SimulatorTools':
    # Fallback: go up 6 levels from test file
    project_root = current_file.parent.parent.parent.parent.parent.parent

# Add to path if not already there
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator


class IRPTemplateTests:
    """Test suite for IRP template generation."""

    def __init__(self, xml_file: Path, verbose: bool = False):
        """Initialize test suite with XML schema file."""
        self.xml_file = xml_file
        self.verbose = verbose
        self.converter = ConvertXml(xml_file)
        self.converter.convert_xml()
        self.schema = self.converter.schema
        self.generator = TemplateGenerator(self.schema)

        # Track test results
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'warnings': 0
        }
        self.failed_tests = []
        self.error_details = []

    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose or if it's an error/warning."""
        if self.verbose or level in ['ERROR', 'WARN', 'FAIL']:
            prefix = {
                'INFO': '  ',
                'WARN': '⚠️ ',
                'ERROR': '❌ ',
                'PASS': '✓ ',
                'FAIL': '✗ '
            }.get(level, '  ')
            print(f"{prefix}{message}")

    def test_bitmap_detection(self) -> bool:
        """Test that all bitmap types are properly detected."""
        print("\n" + "=" * 70)
        print("TEST: BITMAP FIELD DETECTION")
        print("=" * 70)

        # Known bitmaps in IdsDataFormat100600.xml
        known_bitmaps = ['tcp-flags']

        all_passed = True
        for bitmap_name in known_bitmaps:
            is_bitmap = self.generator._is_bitmap(bitmap_name)

            if not is_bitmap:
                self.log(f"FAILED: {bitmap_name} not detected as bitmap", 'FAIL')
                all_passed = False
                self.results['failed'] += 1
                continue

            # Get metadata
            metadata = self.generator._get_field_metadata('test', bitmap_name)

            if metadata.get('fieldType') != 'bitmap':
                self.log(f"FAILED: {bitmap_name} fieldType is '{metadata.get('fieldType')}', expected 'bitmap'", 'FAIL')
                all_passed = False
                self.results['failed'] += 1
                continue

            if not metadata.get('options'):
                self.log(f"FAILED: {bitmap_name} has no options", 'FAIL')
                all_passed = False
                self.results['failed'] += 1
                continue

            self.log(f"PASSED: {bitmap_name} - {len(metadata.get('options', []))} options", 'PASS')
            self.results['passed'] += 1

        return all_passed

    def test_overlap_switch_pattern(self, message_id: int) -> Tuple[bool, str]:
        """
        Test overlap/switch pattern for a specific message.
        Returns (success, details).
        """
        try:
            result = self.generator.generate_template_with_metadata(message_id)
        except Exception as e:
            return False, f"Template generation failed: {e}"

        # Recursively search for overlap patterns
        overlaps_found = []
        issues_found = []

        def check_for_overlap(obj: Any, path: str = "root"):
            """Recursively check for overlap patterns."""
            if isinstance(obj, dict):
                if 'overlap' in obj:
                    overlap_data = obj['overlap']
                    overlaps_found.append(path)

                    # Check if overlap has both 'fields' and a direct field (should be inside fields!)
                    has_fields_dict = 'fields' in overlap_data
                    direct_fields = [k for k in overlap_data.keys() if k not in ['type', 'fieldType', 'fields']]

                    if direct_fields:
                        # Fields should be INSIDE 'fields', not as siblings!
                        for field_name in direct_fields:
                            field_data = overlap_data[field_name]
                            if isinstance(field_data, dict) and field_data.get('type') == 'switch':
                                issues_found.append(
                                    f"Field '{field_name}' placed outside 'fields' at {path}"
                                )

                    # Check fields inside 'fields' object (correct placement)
                    if has_fields_dict:
                        overlap_fields = overlap_data.get('fields', {})
                        for field_name, field_data in overlap_fields.items():
                            if isinstance(field_data, dict) and field_data.get('type') == 'switch':
                                self.log(f"Found merged selector/switch: '{field_name}' at {path}.fields", 'INFO')

                                # Check for duplication
                                if field_name + 's' in overlap_fields:
                                    issues_found.append(
                                        f"Duplication: '{field_name}' and '{field_name}s' at {path}"
                                    )

                # Recurse into nested structures
                for key, value in obj.items():
                    check_for_overlap(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    check_for_overlap(item, f"{path}[{idx}]")

        check_for_overlap(result['schema'])

        if issues_found:
            return False, "; ".join(issues_found)

        if overlaps_found:
            return True, f"Found {len(overlaps_found)} overlap(s), no duplication issues"

        return True, "No overlap patterns found"

    def test_message_template_generation(self, message_id: int) -> Tuple[bool, str]:
        """
        Test that a message can generate a template without errors.
        Returns (success, details).
        """
        try:
            result = self.generator.generate_template_with_metadata(message_id)

            if not result or 'template' not in result or 'schema' not in result:
                return False, "Result missing template or schema"

            # Basic validation
            template = result['template']
            schema = result['schema']

            if not isinstance(template, dict):
                return False, "Template is not a dict"

            if not isinstance(schema, dict):
                return False, "Schema is not a dict"

            # Count fields
            def count_fields(obj):
                count = 0
                if isinstance(obj, dict):
                    count += len(obj)
                    for v in obj.values():
                        if isinstance(v, (dict, list)):
                            count += count_fields(v)
                elif isinstance(obj, list):
                    for item in obj:
                        count += count_fields(item)
                return count

            field_count = count_fields(schema)
            return True, f"{field_count} fields"

        except KeyError as e:
            return False, f"KeyError: {e}"
        except Exception as e:
            return False, f"Exception: {type(e).__name__}: {e}"

    def test_bitmap_fields_in_messages(self, message_id: int) -> Tuple[bool, List[str]]:
        """
        Test that bitmap fields in a message are properly configured.
        Returns (success, list of bitmap fields found).
        """
        try:
            result = self.generator.generate_template_with_metadata(message_id)
            bitmap_fields = []

            def find_bitmaps(obj: Any, path: str = "root"):
                """Recursively find bitmap fields."""
                if isinstance(obj, dict):
                    if obj.get('fieldType') == 'bitmap':
                        field_name = path.split('.')[-1]
                        has_options = bool(obj.get('options'))
                        bitmap_fields.append({
                            'path': path,
                            'name': field_name,
                            'has_options': has_options,
                            'option_count': len(obj.get('options', []))
                        })

                    for key, value in obj.items():
                        find_bitmaps(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        find_bitmaps(item, f"{path}[{idx}]")

            find_bitmaps(result['schema'])

            # Check all bitmaps have options
            invalid_bitmaps = [b for b in bitmap_fields if not b['has_options']]

            if invalid_bitmaps:
                return False, bitmap_fields

            return True, bitmap_fields

        except Exception as e:
            return False, []

    def run_all_message_tests(self, specific_message: int = None):
        """Run tests on all messages or a specific message."""
        print("\n" + "=" * 70)
        print("TEST: ALL MESSAGE TEMPLATE GENERATION")
        print("=" * 70)

        if not self.schema or not hasattr(self.schema, 'messages'):
            self.log("ERROR: No messages found in schema", 'ERROR')
            return

        messages = self.schema.messages
        message_ids = [specific_message] if specific_message else sorted([int(k) for k in messages.keys()])

        print(f"\nTesting {len(message_ids)} message(s)...\n")

        for msg_id in message_ids:
            msg_id_str = str(msg_id)
            if msg_id_str not in messages:
                self.log(f"Message {msg_id} not found in schema", 'WARN')
                self.results['warnings'] += 1
                continue

            message = messages[msg_id_str]
            msg_name = getattr(message, 'name', 'Unknown')

            print(f"Message {msg_id}: {msg_name}")

            # Test 1: Template generation
            success, details = self.test_message_template_generation(msg_id)
            if success:
                self.log(f"✓ Template generation: {details}", 'INFO')
                self.results['passed'] += 1
            else:
                self.log(f"✗ Template generation failed: {details}", 'FAIL')
                self.results['failed'] += 1
                self.failed_tests.append(f"Message {msg_id} ({msg_name}): {details}")
                continue

            # Test 2: Overlap/switch patterns
            success, details = self.test_overlap_switch_pattern(msg_id)
            if success:
                self.log(f"✓ Overlap/switch: {details}", 'INFO')
                self.results['passed'] += 1
            else:
                self.log(f"✗ Overlap/switch issues: {details}", 'FAIL')
                self.results['failed'] += 1
                self.failed_tests.append(f"Message {msg_id} ({msg_name}) overlap: {details}")

            # Test 3: Bitmap fields
            success, bitmap_fields = self.test_bitmap_fields_in_messages(msg_id)
            if bitmap_fields:
                if success:
                    self.log(f"✓ Bitmap fields: {len(bitmap_fields)} found, all valid", 'INFO')
                    self.results['passed'] += 1
                else:
                    invalid = [b['name'] for b in bitmap_fields if not b['has_options']]
                    self.log(f"✗ Bitmap fields: {len(invalid)} missing options: {invalid}", 'FAIL')
                    self.results['failed'] += 1
                    self.failed_tests.append(f"Message {msg_id} ({msg_name}) bitmaps: {invalid}")
            else:
                self.log(f"  No bitmap fields", 'INFO')

            print()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"✓ Passed:   {self.results['passed']}")
        print(f"✗ Failed:   {self.results['failed']}")
        print(f"❌ Errors:   {self.results['errors']}")
        print(f"⚠️  Warnings: {self.results['warnings']}")

        total = self.results['passed'] + self.results['failed']
        if total > 0:
            success_rate = (self.results['passed'] / total) * 100
            print(f"\nSuccess Rate: {success_rate:.1f}%")

        if self.failed_tests:
            print(f"\n{len(self.failed_tests)} Failed Test(s):")
            for fail in self.failed_tests:
                print(f"  • {fail}")

        print("=" * 70)

        # Return exit code
        return 0 if self.results['failed'] == 0 and self.results['errors'] == 0 else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test IRP template generator for all messages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--message', '-m',
        type=int,
        help='Test specific message ID only'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--test-bitmaps',
        action='store_true',
        help='Test only bitmap detection'
    )
    parser.add_argument(
        '--xml-file',
        type=Path,
        default=None,
        help='Path to XML data format file (default: IdsDataFormat100600.xml)'
    )

    args = parser.parse_args()

    # Determine XML file path
    if args.xml_file:
        xml_file = args.xml_file
    else:
        xml_file = project_root / 'backend/app/modules/reporter/irp/data_formats/IdsDataFormat100600.xml'

    if not xml_file.exists():
        print(f"❌ ERROR: XML file not found: {xml_file}")
        return 1

    print("=" * 70)
    print("IRP TEMPLATE GENERATOR TEST SUITE")
    print("=" * 70)
    print(f"XML File: {xml_file.name}")
    print(f"Verbose: {args.verbose}")

    # Initialize test suite
    tests = IRPTemplateTests(xml_file, verbose=args.verbose)

    # Run tests based on arguments
    if args.test_bitmaps:
        tests.test_bitmap_detection()
    elif args.message:
        tests.run_all_message_tests(specific_message=args.message)
    else:
        # Run all tests
        tests.test_bitmap_detection()
        tests.run_all_message_tests()

    # Print summary and return exit code
    return tests.print_summary()


if __name__ == '__main__':
    sys.exit(main())

