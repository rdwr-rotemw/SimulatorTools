"""Fix protocol options from numeric to named values."""

from backend.app.utils.database import get_mongo_db


def fix_protocol_options(obj):
    """Recursively fix protocol _options fields."""
    if not isinstance(obj, dict):
        return obj

    # Fix protocol options - change from ["6", "17", "1"] to named values
    if obj.get('_type') == 'enum' and '_options' in obj:
        if obj['_options'] == ["6", "17", "1"]:
            obj['_options'] = ["tcp", "udp", "icmp", "sftp", "other"]

    # Recurse into nested dicts and lists
    for key, value in obj.items():
        if isinstance(value, dict):
            fix_protocol_options(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    fix_protocol_options(item)

    return obj


def main():
    """Update all polling structures with fixed protocol options."""
    db = get_mongo_db()
    coll = db['polling_structures']

    # Get all structures
    structures = list(coll.find({}))

    print(f"Found {len(structures)} structures to check")

    updated_count = 0
    for structure in structures:
        original = str(structure.get('data_structure'))

        # Fix protocol options in-place
        fix_protocol_options(structure['data_structure'])

        modified = str(structure.get('data_structure'))

        if original != modified:
            # Update in database
            coll.replace_one({'_id': structure['_id']}, structure)
            updated_count += 1
            print(f"  Updated: {structure.get('structure_id')}")

    print(f"Fixed {updated_count} structures")


if __name__ == "__main__":
    main()
