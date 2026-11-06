"""Tests for the skills popup widget (draft logic and key handling)."""

import asyncio

from returns.result import Success
from textual.app import App

from bond.tui.widgets.skills_popup import SkillInfo, SkillsPopup, SkillsPopupResult

SKILLS = [
    SkillInfo(name="pdf", description="PDF tools"),
    SkillInfo(name="git", description="Git helpers"),
    SkillInfo(name="web", description="Web search"),
]


def make_popup(**kwargs) -> SkillsPopup:
    defaults = dict(
        skills=SKILLS,
        persona_name="assistant",
        persona_available_skills=["pdf", "git"],
        conversation_available_skills=None,  # inherit mode
        active_skills=["pdf"],
    )
    defaults.update(kwargs)
    return SkillsPopup(**defaults)


class PopupHost(App):
    """Minimal app that pushes the popup as its screen."""

    def __init__(self, popup: SkillsPopup):
        super().__init__()
        self._popup = popup

    def on_mount(self):
        self.push_screen(self._popup)


def run(coro) -> None:
    asyncio.run(coro)


class TestSkillsPopupDraftLogic:
    def test_initial_state_inherit_mode(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                assert popup._available is None
                # active is pruned against the effective available list on open
                assert popup._active == {"pdf"}
                assert [s.name for s in popup._visible_skills] == ["git", "pdf", "web"]
                assert "inheriting" in popup._mode_text()
                assert "assistant" in popup._mode_text()

        run(main())

    def test_toggle_available_materializes_inherited_list(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await popup._toggle_available("web")
                assert popup._available == {"pdf", "git", "web"}
                assert "custom" in popup._mode_text()

        run(main())

    def test_uncheck_available_also_removes_active(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                assert "pdf" in popup._active
                await popup._toggle_available("pdf")
                assert popup._available == {"git"}
                assert popup._active == set()

        run(main())

    def test_toggle_active_requires_available(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await popup._toggle_active("web")  # not available -> no-op
                assert popup._active == {"pdf"}
                await popup._toggle_available("web")
                await popup._toggle_active("web")
                assert popup._active == {"pdf", "web"}
                await popup._toggle_active("web")  # toggle off again
                assert popup._active == {"pdf"}

        run(main())

    def test_apply_without_changes_keeps_inherit_mode(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                popup._apply()
                result = popup.result
                assert result is not None
                assert result.available_skills is None
                assert result.active_skills == ["pdf"]

        run(main())

    def test_apply_returns_explicit_list_and_pruned_active(self):
        async def main():
            popup = make_popup(
                conversation_available_skills=["pdf", "git"],
                active_skills=["pdf", "git"],
            )
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                assert popup._available == {"pdf", "git"}
                await popup._toggle_available("git")  # also prunes active
                popup._apply()
                result = popup.result
                assert result.available_skills == ["pdf"]
                assert result.active_skills == ["pdf"]

        run(main())

    def test_reset_returns_to_inherit(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await popup._toggle_available("web")
                assert popup._available is not None
                await popup._reset_to_persona()
                assert popup._available is None
                assert popup._active == {"pdf"}
                assert "inheriting" in popup._mode_text()

        run(main())

    def test_clear_empties_available_and_active(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await popup._clear_all()
                assert popup._available == set()
                assert popup._active == set()
                popup._apply()
                assert popup.result.available_skills == []
                assert popup.result.active_skills == []

        run(main())

    def test_select_all_and_none_respect_search_filter(self):
        async def main():
            popup = make_popup(conversation_available_skills=[])
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                assert popup._available == set()
                popup._search_value = "pdf"
                await popup._select_all_visible()
                assert popup._available == {"pdf"}
                popup._search_value = ""
                await popup._select_all_visible()
                assert popup._available == {"git", "pdf", "web"}
                popup._search_value = "pdf"
                await popup._select_none_visible()
                assert popup._available == {"git", "web"}

        run(main())

    def test_missing_referenced_skill_is_shown(self):
        async def main():
            popup = make_popup(
                conversation_available_skills=["pdf", "ghost"],
                active_skills=["ghost"],
            )
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                names = [s.name for s in popup._all_skills]
                assert "ghost" in names
                ghost = next(s for s in popup._all_skills if s.name == "ghost")
                assert ghost.missing is True
                # ghost is in the available list, so it stays active
                assert popup._active == {"ghost"}
                label = popup._row_label(ghost)
                assert "(missing)" in label

        run(main())

    def test_row_label_states(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                pdf = next(s for s in popup._all_skills if s.name == "pdf")
                git = next(s for s in popup._all_skills if s.name == "git")
                web = next(s for s in popup._all_skills if s.name == "web")
                assert popup._row_label(pdf) == "● [x] pdf — PDF tools"
                assert popup._row_label(git) == "○ [x] git — Git helpers"
                assert popup._row_label(web) == "○ [ ] web — Web search"

        run(main())


class TestSkillsPopupKeys:
    def test_enter_toggles_available_of_selected_row(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                # first row (sorted) is "git"; enter removes it from available
                await pilot.press("enter")
                await pilot.pause()
                assert popup._available == {"pdf"}
                assert popup._active == {"pdf"}

        run(main())

    def test_shift_enter_toggles_active_of_selected_row(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                # selected row is "git" (available, not active)
                await pilot.press("shift+enter")
                await pilot.pause()
                assert popup._active == {"pdf", "git"}
                # "web" is not available: move to it and try to activate
                await pilot.press("down", "down")
                await pilot.press("shift+enter")
                await pilot.pause()
                assert popup._active == {"pdf", "git"}

        run(main())

    def test_escape_cancels_with_none_result(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                result = await popup.wait_for()
                assert isinstance(result, Success)
                assert result.unwrap() is None

        run(main())

    def test_apply_button_finishes_with_result(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            # Larger virtual terminal: at the default 80x24 the docked button
            # bar can fall outside the visible region and clicks fail with
            # OutOfBounds.
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.click("#skills-popup-apply")
                await pilot.pause()
                result = await popup.wait_for()
                assert isinstance(result, Success)
                value = result.unwrap()
                assert isinstance(value, SkillsPopupResult)
                assert value.available_skills is None  # untouched inherit mode
                assert value.active_skills == ["pdf"]

        run(main())

    def test_cancel_button_finishes_with_none(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.click("#skills-popup-cancel")
                await pilot.pause()
                result = await popup.wait_for()
                assert isinstance(result, Success)
                assert result.unwrap() is None

        run(main())

    def test_enter_on_empty_filter_is_noop(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                popup._search_value = "zzz-no-match"
                await popup._refresh()
                await pilot.pause()
                assert popup._visible_skills == []
                await pilot.press("enter")
                await pilot.pause()
                assert popup._available is None

        run(main())

    def test_search_filter_narrows_rows(self):
        async def main():
            popup = make_popup()
            app = PopupHost(popup)
            async with app.run_test() as pilot:
                await pilot.pause()
                popup._search_value = "git"
                await popup._refresh()
                await pilot.pause()
                assert [s.name for s in popup._visible_skills] == ["git"]

        run(main())
