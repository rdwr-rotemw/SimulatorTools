"""Fix timestamp offset fields from 'int' string to numeric values."""

from backend.app.utils.database import get_mongo_db


def fix_timestamps(obj, field_name=None):
    """Recursively fix timestamp _offset fields."""
    if not isinstance(obj, dict):
        return obj

    # Fix timestamp offsets - change 120/60 to 60/0
    if obj.get('_type') == 'timestamp':
        if obj.get('_offset') == 120:
            obj['_offset'] = 60  # time_from: 120 → 60
        elif obj.get('_offset') == 60:
            obj['_offset'] = 0   # time_to: 60 → 0
        elif obj.get('_offset') == 'int':
            # Old string placeholder - default to 60
            obj['_offset'] = 60

    # Recurse into nested dicts and lists
    for key, value in obj.items():
        if isinstance(value, dict):
            fix_timestamps(value, key)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    fix_timestamps(item, key)

    return obj


def main():
    """Update all polling structures with fixed timestamp offsets."""
    db = get_mongo_db()
    coll = db['polling_structures']

    # Get all structures
    structures = list(coll.find({}))

    print(f"Found {len(structures)} structures to check")

    updated_count = 0
    for structure in structures:
        original = str(structure.get('data_structure'))

        # Fix timestamps in-place
        fix_timestamps(structure['data_structure'])

        modified = str(structure.get('data_structure'))

        if original != modified:
            # Update in database
            coll.replace_one({'_id': structure['_id']}, structure)
            updated_count += 1
            print(f"  Updated: {structure.get('structure_id')}")

    print(f"Fixed {updated_count} structures")


if __name__ == "__main__":
    main()
