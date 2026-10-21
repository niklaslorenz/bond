# Task list tools package

from bond.tools.toolbox import PythonToolset

from .add_tasks import add_tasks
from .clear_completed_tasks import clear_completed_tasks
from .clear_tasks import clear_tasks
from .complete_tasks import complete_tasks
from .delete_tasks import delete_tasks

task_list_toolset = PythonToolset(
    "task-list",
    [add_tasks, complete_tasks, delete_tasks, clear_tasks, clear_completed_tasks],
)

__all__ = [
    "add_tasks",
    "complete_tasks",
    "delete_tasks",
    "clear_tasks",
    "clear_completed_tasks",
    "task_list_toolset",
]
