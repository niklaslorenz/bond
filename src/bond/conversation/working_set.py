from pydantic import BaseModel, Field

from bond.conversation.working_set_item import WorkingSetItem


class WorkingSet(BaseModel):
    items: list[WorkingSetItem] = Field(default_factory=list)
