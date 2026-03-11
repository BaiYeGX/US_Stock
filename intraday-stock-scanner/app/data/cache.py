from __future__ import annotations

from collections.abc import MutableMapping


class DictCache(MutableMapping):
    def __init__(self) -> None:
        self._store: dict = {}

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)
