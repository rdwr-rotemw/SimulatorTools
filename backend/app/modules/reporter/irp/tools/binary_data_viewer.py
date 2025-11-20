def view_binary_file(file_path):
    """
    Display the contents of a binary file in hexadecimal format.

    Args:
        file_path (str): Path to the binary file.

    Returns:
        None
    """
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        # Print data in hexadecimal format
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            hex_values = " ".join(f"{byte:02x}" for byte in chunk)
            ascii_values = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
            print(f"{i:08x}  {hex_values:<48}  {ascii_values}")

    except FileNotFoundError:
        print(f"Error: File not found - {file_path}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View binary file in hexadecimal format.")
    parser.add_argument("file", type=str, help="Path to the binary file.")

    args = parser.parse_args()
    view_binary_file(args.file)
