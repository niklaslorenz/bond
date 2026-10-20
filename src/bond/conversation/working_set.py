import textwrap

from pydantic import BaseModel, Field

from bond.conversation.working_set_item import WorkingSetItem


class WorkingSet(BaseModel):
    items: list[WorkingSetItem] = Field(default_factory=list)

    def render(self) -> str:
        return "".join(textwrap.dedent(f"""
            <item index={idx}>
            {item.render()}
            </item>
            """) for idx, item in enumerate(self.items))
