import subprocess
from pathlib import Path
from textual.widgets import Input, DataTable
from agentdeck.tui import AgentDeck, HelpScreen
from agentdeck.store import Store
from test_deck import FakeCollector, row


def test_cli_help_and_invalid_modes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([str(root/'chatdock'), '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    for text in ('--tui', '--json', 'q 退出', '示例'):
        assert text in result.stdout
    result = subprocess.run([str(root/'chatdock'), '--tui', '--json'], capture_output=True, text=True)
    assert result.returncode == 2


async def test_help_q_and_input(tmp_path):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]))
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        await pilot.press('question_mark')
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press('q')
        await pilot.pause()
        assert len(app.screen_stack) == 1
        await pilot.press('ctrl+f', 'q', 'question_mark')
        await pilot.pause()
        assert app.query_one('#search', Input).value == 'q?'
        assert len(app.screen_stack) == 1
        await pilot.press('escape', 'f1')
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.click('#help-close')
        await pilot.pause()
        await pilot.press('escape', 'q')
        await pilot.pause()
        assert not app.is_running
