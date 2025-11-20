import json

class ValueLoader:
    """
    Loads and provides access to values from a JSON file for message building.
    Raises clear errors for missing or malformed files.
    """
    def __init__(self, json_file):
        self.values = self._load_json(json_file)

    def _load_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"JSON values file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in {file_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load JSON file {file_path}: {e}")

    def get_value(self, path):
        """
        Navigate JSON structure using a list of keys (path).
        Example: path = ['ports', 0, 'udp', 'connections']
        """
        v = self.values
        for p in path:
            if v is None:
                return None
            if isinstance(v, dict):
                v = v.get(p)
            elif isinstance(v, list):
                try:
                    idx = int(p)
                    v = v[idx]
                except Exception:
                    return None
            else:
                return None
        return v

