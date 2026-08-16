from typing import Callable

from . import logger


class BaseRegistry[T]:
    def __init__(self):
        self._entries: dict[str, T] = {}

    def get(self, name: str) -> T | None:
        """
        Get an entry by name

        Args:
            name: Name of the entry to retrieve

        Returns:
            The entry if found, None otherwise
        """
        return self._entries.get(name)

    def get_all(self) -> dict[str, T]:
        return self._entries.copy()

    def get_names(self) -> list[str]:
        return list(self._entries.keys())

    def unregister(self, name: str) -> bool:
        """
        Unregister an entry.

        Args:
            name: The name of the entry to unregister

        Returns:
            True if the entry was registered and removed, False otherwise
        """
        if name in self._entries:
            del self._entries[name]
            logger.debug(f"Unregistered entry: {name}")
            return True
        return False

    def clear(self):
        self._entries = {}


class NamedEntryRegistry[T](BaseRegistry[T]):
    def register(self, name: str, entry: T) -> None:
        """
        Register an entry my name.

        Args:
            name: The name of the entry
            entry: The entry to register

        Raises:
            ValueError: If an entry with the same name is already registered
        """
        if name in self._entries:
            raise ValueError(f"Name '{name}' is already registered")

        self._entries[name] = entry
        logger.debug(f"Registered entry {name}")


class MappedEntryRegistry[T](BaseRegistry[T]):
    def __init__(self, key_fn: Callable[[T], str]):
        super().__init__()
        self._key_fn = key_fn

    def register(self, entry: T):
        """
        Register an entry.

        Args:
            entry: The entry to register

        Raises:
            ValueError: If an entry with the same name is already registered
        """
        name = self._key_fn(entry)
        if name in self._entries:
            raise ValueError(f"Entry '{name}' is already registered")

        self._entries[name] = entry
        logger.debug(f"Registered entry: {name}")
