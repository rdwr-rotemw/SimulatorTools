#!/usr/bin/env python3

import argparse
import json
import time
from pathlib import Path
from core.irp_formatter import IrpFormatter
from tools.template_generator import TemplateGenerator
from tools.message_resolver import MessageResolver


def send_irp_message(message_identifier, from_ip, to_ip, values_file, xml_file, timeout=0):
    """
    Send a single IRP message using the specified parameters.

    Args:
        message_identifier (str or int): The message ID (numeric) or message name to send
        from_ip (str): Source IP address
        to_ip (str): Destination IP address
        values_file (str): Path to the JSON values file
        xml_file (str): Path to the XML schema file
        timeout (int): Timeout in seconds for looped sending (default: 0)
    """
    try:
        # Initialize the IRP formatter with XML file and IP addresses
        irp = IrpFormatter(xml_file, from_ip, to_ip)

        # Send the message using values from the JSON file
        irp.send_message(message_identifier, values_file, timeout=timeout)

        print(f"Successfully sent message {message_identifier} to {to_ip}")
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
    except ValueError as e:
        print(f"Error: Invalid value - {e}")
    except RuntimeError as e:
        print(f"Error: Runtime error - {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def send_multiple_messages(from_ip, to_ip, messages_file, xml_file, timeout=0):
    """
    Send multiple IRP messages from a JSON file containing message definitions.

    Args:
        from_ip (str): Source IP address
        to_ip (str): Destination IP address
        messages_file (str): Path to the JSON file containing multiple message definitions
        xml_file (str): Path to the XML schema file
        timeout (int): Timeout in seconds for continuous sending (default: 0)
    """
    try:
        # Load the messages file
        with open(messages_file, 'r') as f:
            messages_data = json.load(f)

        if 'messages' not in messages_data:
            raise ValueError("JSON file must contain a 'messages' array")

        messages = messages_data['messages']
        if not isinstance(messages, list):
            raise ValueError("'messages' must be an array")

        if not messages:
            print("No messages found in the JSON file")
            return

        print(f"📦 Loading {len(messages)} message(s) from {messages_file}")

        # Initialize the IRP formatter with XML file and IP addresses
        irp = IrpFormatter(xml_file, from_ip, to_ip)

        # Process messages in continuous loop if timeout is specified
        if timeout > 0:
            print(f"🔄 Starting continuous sending for {timeout} seconds...")
            start_time = time.time()
            message_count = 0

            while time.time() - start_time < timeout:
                for i, message in enumerate(messages):
                    # Check if timeout has been reached
                    if time.time() - start_time >= timeout:
                        break

                    if 'id' not in message and 'message' not in message:
                        print(f"⚠️  Skipping message {i+1}: Missing 'id' and 'message' fields")
                        continue

                    # Determine message ID or name
                    message_id = message.get('id') or message.get('message')

                    # Extract message data (everything except 'id' and 'message')
                    message_data = {k: v for k, v in message.items() if k not in ['id', 'message']}

                    try:
                        # Send the message using the extracted data
                        irp.send_message_from_data(message_id, message_data)
                        message_count += 1
                        print(f"✅ Sent message {message_id} to {to_ip} (#{message_count})")

                        # Brief pause between messages to avoid overwhelming the receiver
                        time.sleep(0.1)

                    except Exception as e:
                        print(f"❌ Failed to send message {message_id}: {e}")

                # Wait 15 seconds before next batch (matching existing behavior)
                if time.time() - start_time < timeout:
                    print(f"⏳ Waiting 15 seconds before next batch...")
                    time.sleep(15)

            print(f"🏁 Completed continuous sending. Total messages sent: {message_count}")
        else:
            # Send each message once
            success_count = 0
            for i, message in enumerate(messages):
                if 'id' not in message and 'message' not in message:
                    print(f"⚠️  Skipping message {i+1}: Missing 'id' and 'message' fields")
                    continue

                # Determine message ID or name
                message_id = message.get('id') or message.get('message')

                # Extract message data (everything except 'id' and 'message')
                message_data = {k: v for k, v in message.items() if k not in ['id', 'message']}

                try:
                    # Send the message using the extracted data
                    irp.send_message_from_data(message_id, message_data)
                    success_count += 1
                    print(f"✅ Sent message {message_id} to {to_ip}")

                    # Brief pause between messages
                    time.sleep(0.1)

                except Exception as e:
                    print(f"❌ Failed to send message {message_id}: {e}")

            print(f"🏁 Completed sending {success_count}/{len(messages)} messages successfully")

    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format - {e}")
    except ValueError as e:
        print(f"❌ Error: Invalid value - {e}")
    except RuntimeError as e:
        print(f"❌ Error: Runtime error - {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def create_template(message_id, xml_file, output_file=None, interactive=False):
    """
    Create a JSON template for the specified message ID using the XML schema.

    Args:
        message_id (int): The message ID to create template for
        xml_file (str): Path to the XML schema file
        output_file (str): Optional output file path
        interactive (bool): Enable interactive array size selection
    """
    try:
        # Initialize template generator with XML schema
        generator = TemplateGenerator(xml_file)

        # Generate default output filename if not provided
        if not output_file:
            xml_path = Path(xml_file)
            xml_name = xml_path.stem  # Get filename without extension
            suffix = "_interactive" if interactive else ""
            output_file = f"templates/message_{message_id}_template_{xml_name}{suffix}.json"

        if interactive:
            print(f"🎯 Creating interactive template for message {message_id}")
            print("You'll be prompted to configure array sizes for optimal template generation.\n")

        # Generate and save template
        output_path = generator.generate_template(message_id, output_file, interactive=interactive)

        print(f"\n✅ Successfully created template for message {message_id}")
        print(f"📁 Template saved to: {output_path}")

        # Show available messages for reference
        messages = generator.list_available_messages()
        print(f"\n📋 Available messages in {Path(xml_file).name}:")
        for msg in messages[:10]:  # Show first 10 messages
            print(f"  ID {msg['id']}: {msg['name']}")
        if len(messages) > 10:
            print(f"  ... and {len(messages) - 10} more messages")

    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
    except ValueError as e:
        print(f"❌ Error: Invalid value - {e}")
    except KeyboardInterrupt:
        print(f"\n🚫 Template generation cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='IRP Message Tool - Send UDP messages or create JSON templates using XML schemas.\n\n'
                    'This tool can either format and send IRP messages as UDP packets '
                    'by converting XML schema definitions and JSON value files into binary data, '
                    'or create JSON templates for messages based on XML schema definitions. '
                    'It supports various IDS data formats and can send messages in single-shot mode '
                    'or continuously with timeout-based looping. It also supports sending multiple '
                    'messages from a single JSON file containing an array of message definitions.',
        epilog='Examples:\n'
               '  # Send a single message:\n'
               '  python irp_bckp.py -m 7 -src 10.218.101.38 -dst 172.17.40.1 -v values/message_7.json -x data_formats/IdsDataFormat100600.xml\n\n'
               '  # Send messages continuously for 60 seconds:\n'
               '  python irp_bckp.py -m 38 -src 192.168.1.100 -dst 192.168.1.200 -v values/message_38.json -x data_formats/IdsDataFormat82200.xml -t 60\n\n'
               '  # Send multiple messages from a JSON file:\n'
               '  python irp_bckp.py -f messages/multiple_messages.json -src 10.0.0.1 -dst 10.0.0.2 -x data_formats/IdsDataFormat100600.xml\n\n'
               '  # Send multiple messages continuously for 120 seconds:\n'
               '  python irp_bckp.py -f messages/batch_messages.json -src 192.168.1.100 -dst 192.168.1.200 -x data_formats/IdsDataFormat100600.xml -t 120\n\n'
               '  # Create a JSON template for message ID 7:\n'
               '  python irp_bckp.py -c 7 -x data_formats/IdsDataFormat100600.xml\n\n'
               '  # Create an interactive template (choose array sizes):\n'
               '  python irp_bckp.py -c 7 -i -x data_formats/IdsDataFormat100600.xml\n\n'
               '  # Create a template with custom output file:\n'
               '  python irp_bckp.py -c 38 -x data_formats/IdsDataFormat82200.xml -o templates/my_message_38.json\n\n'
               'Multiple Messages JSON Format:\n'
               '  {\n'
               '    "messages": [\n'
               '      {\n'
               '        "id": 20,\n'
               '        "policy-name": "pol1",\n'
               '        "policy-type": "policy-based",\n'
               '        "ipv4": {\n'
               '          "controllers": [\n'
               '            {\n'
               '              "protection-type": {\n'
               '                "protection": "udp",\n'
               '                "direction": "in"\n'
               '              },\n'
               '              "all-controllers-data": {\n'
               '                "state": "blocking",\n'
               '                "degree-of-attack": 2\n'
               '              }\n'
               '            }\n'
               '          ]\n'
               '        },\n'
               '        "ipv6": false\n'
               '      },\n'
               '      {\n'
               '        "id": 7,\n'
               '        "concur-tcp-connections": 100,\n'
               '        "concur-udp-connections": 50,\n'
               '        "global-data": [\n'
               '          {\n'
               '            "port": 80,\n'
               '            "protocols": {\n'
               '              "tcp": {\n'
               '                "connections": 10\n'
               '              }\n'
               '            }\n'
               '          }\n'
               '        ]\n'
               '      }\n'
               '    ]\n'
               '  }\n\n'
               'Supported Features:\n'
               '  • XML schema parsing and validation\n'
               '  • JSON value loading and processing\n'
               '  • Binary message construction\n'
               '  • UDP packet transmission with proper headers\n'
               '  • Multiple message sending from single JSON file\n'
               '  • Timeout-based continuous sending (15-second intervals)\n'
               '  • JSON template generation from XML schemas\n'
               '  • Interactive array size configuration for templates\n'
               '  • Comprehensive error handling and validation',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Create mutually exclusive groups for send vs create-template modes
    mode_group = parser.add_mutually_exclusive_group(required=True)

    # Send mode arguments
    mode_group.add_argument('--message-id', '-m', type=str,
                        help='Message ID (numeric) or message name to send. Must match a message ID or name defined in the XML schema file.')

    # Multiple messages mode arguments
    mode_group.add_argument('--file', '-f', type=str, metavar='MESSAGES_FILE',
                        help='Path to JSON file containing multiple messages to send. File must contain a "messages" array with message objects.')

    # Create template mode arguments
    mode_group.add_argument('--create-template', '-c', type=int, metavar='MESSAGE_ID',
                        help='Create a JSON template for the specified message ID.')

    # Common arguments
    parser.add_argument('--xml-file', '-x', type=str, required=True,
                        help='Path to XML schema file. Defines the message structure and data types (e.g., IdsDataFormat*.xml).')

    # Send-mode specific arguments
    parser.add_argument('--from-ip', '-src', type=str,
                        help='Source IP address for UDP binding. Required for send mode.')
    parser.add_argument('--to-ip', '-dst', type=str,
                        help='Destination IP address. Required for send mode.')
    parser.add_argument('--values-file', '-v', type=str,
                        help='Path to JSON values file. Required for send mode.')
    parser.add_argument('--timeout', '-t', type=int, default=0,
                        help='Timeout in seconds for continuous sending mode (default: 0 = single send).')

    # Create-template mode specific arguments
    parser.add_argument('--output', '-o', type=str,
                        help='Output file path for template (default: templates/message_<ID>_template_<schema>.json).')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Enable interactive mode to configure array sizes for better templates.')

    args = parser.parse_args()

    # Determine mode and validate required arguments
    if args.message_id is not None:
        # Send mode
        if not all([args.from_ip, args.to_ip, args.values_file]):
            parser.error("Send mode requires --from-ip, --to-ip, and --values-file arguments")

        send_irp_message(
            args.message_id,
            args.from_ip,
            args.to_ip,
            args.values_file,
            args.xml_file,
            args.timeout
        )
    elif args.file is not None:
        # Multiple messages mode
        if not all([args.from_ip, args.to_ip]):
            parser.error("Multiple messages mode requires --from-ip and --to-ip arguments")

        send_multiple_messages(
            args.from_ip,
            args.to_ip,
            args.file,
            args.xml_file,
            args.timeout
        )
    elif args.create_template is not None:
        # Create template mode
        create_template(
            args.create_template,
            args.xml_file,
            args.output,
            args.interactive
        )
    else:
        parser.error("Must specify either --message-id for send mode, --file for multiple messages mode, or --create-template for template creation")
