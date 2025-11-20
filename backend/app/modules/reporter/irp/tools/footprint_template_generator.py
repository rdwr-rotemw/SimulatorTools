"""
Footprint Template Generator - Specialized tool for handling complex footprint structures.

This module generates proper JSON templates for footprint structures that use:
- relation enum (0 for "or", 1 for "and")
- footprint-values as lists of [enum_type, value] pairs using var-arrays
"""

import json
from typing import Dict, List, Any, Optional


class FootprintTemplateGenerator:
    """
    Generates templates for footprint structures with proper var-array handling.
    """

    # Footprint types enumeration mapping (from vsecure.footprint-types)
    FOOTPRINT_TYPES = {
        0: "checksum",
        1: "sequence-number",
        2: "id-number",
        3: "dns-id",
        4: "dns-qname",
        5: "dns-subdomain",
        6: "dns-qcount",
        7: "source-port",
        8: "source-ip",
        9: "fragment-offset",
        10: "flow-label",
        11: "tos",
        12: "packet-size",
        13: "destination-port",
        14: "destination-ip",
        15: "fragment",
        19: "message-type",
        20: "ttl",
        28: "context-tag",
        30: "dns-ancount",
        31: "dns-flags"
    }

    # Value examples for each footprint type
    FOOTPRINT_VALUE_EXAMPLES = {
        "checksum": 0,
        "sequence-number": 12345,
        "id-number": 2654,
        "dns-id": 65432,
        "dns-qname": "example.com",
        "dns-subdomain": "subdomain.example.com",
        "dns-qcount": 1,
        "source-port": 80,
        "source-ip": "192.168.1.100",
        "fragment-offset": 0,
        "flow-label": 0,
        "tos": 0,
        "packet-size": 1500,
        "destination-port": 443,
        "destination-ip": "10.0.0.1",
        "fragment": 0,
        "message-type": 1,
        "ttl": 64,
        "context-tag": 12345,
        "dns-ancount": 1,
        "dns-flags": 256
    }

    def generate_footprint_template(self,
                                    relation: int = 0,
                                    footprint_examples: Optional[List[int]] = None,
                                    interactive: bool = False) -> Dict[str, Any]:
        """
        Generate a footprint template structure that properly matches the XML schema.

        The footprint structure requires:
        1. relation enum field
        2. Either "or" or "and" template containing a for-loop with switch inside

        Args:
            relation: Relation enum (0 for "or", 1 for "and")
            footprint_examples: List of footprint type codes to include as examples
            interactive: If True, prompt user for footprint type selection

        Returns:
            Dictionary representing the correct footprint structure for the XML schema
        """
        if footprint_examples is None:
            # Default examples: checksum and id-number
            footprint_examples = [0, 2]

        if interactive:
            footprint_examples = self._interactive_footprint_selection()

        # Create the structure that matches the XML schema exactly:
        # The footprint-values template is a for-loop with switch inside
        footprint_structure = {
            "relation": relation
        }

        # Add the appropriate template based on relation value
        template_name = "or" if relation == 0 else "and"

        # Generate the for-loop structure that the footprint-values template expects
        footprint_entries = []
        for footprint_type_code in footprint_examples:
            if footprint_type_code in self.FOOTPRINT_TYPES:
                footprint_name = self.FOOTPRINT_TYPES[footprint_type_code]
                example_value = self.FOOTPRINT_VALUE_EXAMPLES.get(footprint_name, "example_value")

                # Each entry in the for-loop is a switch case
                # The switch selector will be the footprint type code
                # The case contains a var-array with the values
                footprint_entries.append({
                    footprint_name: [example_value]  # Var-array with one value
                })

        # Always include both 'or' and 'and' sections
        footprint_structure["or"] = {
            "footprint-values": footprint_entries if relation == 0 else []
        }
        footprint_structure["and"] = {
            "footprint-values": footprint_entries if relation == 1 else []
        }

        return footprint_structure

    def generate_or_and_footprint_template(self,
                                           or_footprints: Optional[List[int]] = None,
                                           and_footprints: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Generate a complete footprint template with both "or" and "and" sections.

        Args:
            or_footprints: List of footprint type codes for the "or" section
            and_footprints: List of footprint type codes for the "and" section

        Returns:
            Dictionary with "or" and "and" footprint structures
        """
        if or_footprints is None:
            or_footprints = [0]  # checksum
        if and_footprints is None:
            and_footprints = []  # empty by default

        return {
            "or": {
                "footprint-values": [[code, self.FOOTPRINT_VALUE_EXAMPLES.get(
                    self.FOOTPRINT_TYPES.get(code, "unknown"), "example")]
                                     for code in or_footprints]
            },
            "and": {
                "footprint-values": [[code, self.FOOTPRINT_VALUE_EXAMPLES.get(
                    self.FOOTPRINT_TYPES.get(code, "unknown"), "example")]
                                     for code in and_footprints]
            }
        }

    def _interactive_footprint_selection(self) -> List[int]:
        """
        Interactive selection of footprint types.

        Returns:
            List of selected footprint type codes
        """
        print("\n🔍 Available Footprint Types:")
        print("=" * 50)

        for code, name in sorted(self.FOOTPRINT_TYPES.items()):
            example = self.FOOTPRINT_VALUE_EXAMPLES.get(name, "N/A")
            print(f"  {code:2d}: {name:<20} (example: {example})")

        print("\nEnter footprint type codes separated by commas (e.g., 0,2,7)")
        print("Or press Enter for default (checksum=0, id-number=2):")

        try:
            user_input = input("> ").strip()
            if not user_input:
                return [0, 2]  # Default

            codes = [int(code.strip()) for code in user_input.split(",")]
            valid_codes = [code for code in codes if code in self.FOOTPRINT_TYPES]

            if not valid_codes:
                print("⚠️  No valid codes provided, using defaults")
                return [0, 2]

            print(f"✅ Selected footprint types: {valid_codes}")
            return valid_codes

        except (ValueError, KeyboardInterrupt):
            print("⚠️  Invalid input, using defaults")
            return [0, 2]

    def get_footprint_info(self) -> Dict[str, Any]:
        """
        Get information about available footprint types.

        Returns:
            Dictionary with footprint type information
        """
        return {
            "types": self.FOOTPRINT_TYPES,
            "examples": self.FOOTPRINT_VALUE_EXAMPLES,
            "description": "Footprint types for var-array encoding in IRP messages"
        }


def create_example_footprint_templates():
    """
    Create example footprint templates for testing.
    """
    generator = FootprintTemplateGenerator()

    examples = {
        "simple_or_footprint": {
            "footprint": generator.generate_footprint_template(relation=0, footprint_examples=[0, 2])
        },
        "simple_and_footprint": {
            "footprint": generator.generate_footprint_template(relation=1, footprint_examples=[7, 13])
        },
        "complex_footprint": {
            "footprint": generator.generate_or_and_footprint_template(
                or_footprints=[0, 2, 7],
                and_footprints=[13, 14]
            )
        }
    }

    return examples


if __name__ == "__main__":
    # Demo usage
    generator = FootprintTemplateGenerator()

    print("🎯 Footprint Template Generator Demo")
    print("=" * 40)

    # Show available types
    info = generator.get_footprint_info()
    print(f"\n📋 Available footprint types: {len(info['types'])}")

    # Generate example templates
    examples = create_example_footprint_templates()

    for name, template in examples.items():
        print(f"\n📄 {name}:")
        print(json.dumps(template, indent=2))
