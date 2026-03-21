import logging
import sys
from pathlib import Path

from bond.behaviours.single_turn import SingleTurn
from bond.bond_environment import DynamicBondEnvironment
from bond.tools import tool
from bond.tools.global_toolbox import build_global_toolsets

logger = logging.getLogger("bond")
tool.set_interactive(True)


env = DynamicBondEnvironment(Path("~/.config/bond"), build_global_toolsets())
turn = SingleTurn(env, "executor")

logging.basicConfig(
    stream=sys.stdout,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger.setLevel(logging.DEBUG)
