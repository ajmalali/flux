"""A JSON file that is never left half-written.

Every save goes to a sibling temp file and is renamed over the target, so a
crash mid-write loses the new state rather than corrupting the old.
"""

import json
import os
import tempfile

EMPTY = {"spaces": [], "members": [], "bookings": []}


class JsonStore(object):
    def __init__(self, path):
        self.path = str(path)
        self._data = None

    def load(self):
        if self._data is None:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            else:
                self._data = {k: list(v) for k, v in EMPTY.items()}
            for key, default in EMPTY.items():
                self._data.setdefault(key, list(default))
        return self._data

    def save(self):
        if self._data is None:
            return
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        if not os.path.isdir(directory):
            os.makedirs(directory)
        handle, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def table(self, name):
        return self.load().setdefault(name, [])
