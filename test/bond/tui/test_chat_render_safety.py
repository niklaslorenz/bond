"""Regression tests: arbitrary text (square brackets etc.) must never crash
the TUI while rendering.

Textual's `Static`/`Button` parse plain strings as console markup by default
and raise `MarkupError` on inputs like `"[/"`, which crashes the whole app
during reflow. Chat content, author names, tool arguments, conversation and
skill names are all arbitrary text and must be rendered with markup parsing
disabled (or as `Text`/`Content` objects).
"""

import asyncio

from textual.app import App
from textual.widgets import Static

from bond.tui.widgets.chat_log import ChatLog, ChatMessage
from bond.tui.widgets.confirmation_popup import ConfirmationPopup
from bond.tui.widgets.conversation_selector_popup import ConversationSelectorPopup
from bond.tui.widgets.skills_popup import SkillInfo, SkillsPopup

# Strings that look like (broken) markup or markdown but are plain text.
ADVERSARIAL = [
    "[",
    "[]",
    "[/",
    "[b]",
    "[b",
    "foo [bar] baz",
    "[/b]",
    "[#ff0000]x",
    "a [/ b",
    "[link=https://x]y[/link]",
    "rm -rf [abc]*",
    'echo \'{"a": [1, 2]}\'',
    "apply patch:\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE",
    "| a | b |\n|---|---|\n| 1 | 2 | 3 |",
    "```nonexistentlexer\nx\n```",
    "```\nunclosed fence with [brackets] and | pipes |",
    "[ref]: https://example.com\n[ref]",
    "line with \x00 null",
]


class ChatHost(App):
    def __init__(self):
        super().__init__()
        self.chat_log = ChatLog()

    def compose(self):
        yield self.chat_log


def run(coro) -> None:
    asyncio.run(coro)


class TestChatMessageRendering:
    def test_adversarial_message_content_does_not_crash(self):
        async def main():
            app = ChatHost()
            async with app.run_test() as pilot:
                for s in ADVERSARIAL:
                    msg = ChatMessage("tester", "assistant")
                    app.chat_log.add_message(msg)
                    msg.append_text(s)
                    await pilot.pause()
                    msg.elements[-1].refresh(layout=True)
                    await pilot.pause()
                # think + tool blocks too
                msg = ChatMessage("tester", "assistant")
                app.chat_log.add_message(msg)
                msg.append_thinking("[/ thinking [b]")
                msg.add_tool_result_block("result [/] [b]", name="tool[1]")
                await pilot.pause()
                await pilot.pause()

        run(main())  # run_test re-raises any app exception -> test fails

    def test_author_with_brackets_does_not_crash(self):
        async def main():
            app = ChatHost()
            async with app.run_test() as pilot:
                for author in ["[weird]name", "[b]evil", "[/", "a[b", "C4"]:
                    msg = ChatMessage(author, "assistant")
                    app.chat_log.add_message(msg)
                    msg.append_text("hello")
                    await pilot.pause()
                    await pilot.pause()
                    # the raw author string must be shown verbatim
                    assert author in str(msg.header.content)

        run(main())


class PopupHost(App):
    def __init__(self, popup):
        super().__init__()
        self._popup = popup

    def on_mount(self):
        self.push_screen(self._popup)


class TestPopups:
    def test_confirmation_popup_with_bracketed_request(self):
        async def main():
            for s in ADVERSARIAL:
                app = PopupHost(ConfirmationPopup(s))
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.pause()

        run(main())

    def test_conversation_selector_with_bracketed_names(self):
        async def main():
            names = ["conv [1]", "[/broken", "a[b", "normal"] + ADVERSARIAL[:5]
            app = PopupHost(ConversationSelectorPopup(names))
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()

        run(main())

    def test_skills_popup_with_bracketed_names(self):
        async def main():
            skills = [
                SkillInfo(name="skill[1]", description="[/bad [b]"),
                SkillInfo(name="[/broken"),
                SkillInfo(name="normal", description="fine"),
            ]
            popup = SkillsPopup(
                skills=skills,
                persona_name="persona [x]",
                persona_available_skills=["skill[1]", "[/broken", "normal"],
                conversation_available_skills=None,
                active_skills=["skill[1]"],
            )
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                # toggling re-renders the mode label with the bracketed names
                await popup._toggle_available("normal")
                await pilot.pause()

        run(main())


class TestPlainStatic:
    def test_bracketed_static_content(self):
        """Sanity check for the underlying Textual behavior we guard against."""
        async def main():
            app = ChatHost()
            async with app.run_test() as pilot:
                for s in ADVERSARIAL:
                    await app.mount(Static(s, markup=False))
                await pilot.pause()
                await pilot.pause()

        run(main())
