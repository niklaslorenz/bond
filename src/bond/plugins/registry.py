import logging
from importlib.metadata import entry_points

from .bond_plugin import BondPlugin

logger = logging.getLogger(__name__)

plugins: list[BondPlugin] | None = None


def get_plugins() -> list[BondPlugin]:
    return plugins or load_plugins()


def load_plugins() -> list[BondPlugin]:
    global plugins
    plugins = []
    for entry_point in entry_points(group="bond.plugins"):
        plugin_class = entry_point.load()
        if issubclass(plugin_class, BondPlugin):
            plugins.append(plugin_class())
        else:
            logger.error(
                f"Invalid plugin: {entry_point.name}. Not a subclass of BondPlugin."
            )
    return plugins
