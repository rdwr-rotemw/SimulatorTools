import json
import os
import threading


class ConfigManager:
    """JSON config loader with mtime-based hot-reload."""

    def __init__(self):
        self._cache = {}
        self._mtimes = {}
        self._lock = threading.Lock()

    def get(self, filepath):
        """Read a JSON config file. Returns cached version if file hasn't changed."""
        with self._lock:
            try:
                current_mtime = os.stat(filepath).st_mtime
            except FileNotFoundError:
                return {}

            cached_mtime = self._mtimes.get(filepath)
            if cached_mtime == current_mtime and filepath in self._cache:
                return self._cache[filepath]

            with open(filepath, "r") as f:
                data = json.load(f)

            self._cache[filepath] = data
            self._mtimes[filepath] = current_mtime
            return data

    def reload(self):
        """Force re-read of all cached configs on next access."""
        with self._lock:
            self._mtimes.clear()
