import subprocess
from pathlib import Path
import pytest
from textual.widgets import Select, Input, DataTable, Static
from agentdeck.appearance import PALETTES, colors
from agentdeck.tui import AgentDeck, AppearanceScreen, HelpScreen
from agentdeck.store import Store
from test_deck import row, FakeCollector


@pytest.mark.parametrize('theme', list(PALETTES))
async def test_themes_render_in_english(tmp_path, theme):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]), language='en', theme_name=theme)
    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        assert app.theme == theme
        assert 'Session name (native)' in str(app.query_one('#detail', Static).render())
        assert '中文手稿' in str(app.query_one('#detail', Static).render())
        assert str(app.query_one('#edit').label) == 'Edit name / tags'
        await pilot.press('f1')
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        assert 'NAVIGATION' in str(app.screen.query_one('#help-content Static').render())


async def test_live_switch_preserves_search_and_persists(tmp_path):
    store = Store(tmp_path/'labels.sqlite')
    app = AgentDeck(store=store, collector=FakeCollector([row(), row('codex:b',title='Other')]))
    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        app.query_one('#search', Input).value = '中文'
        await pilot.pause()
        await pilot.press('f2')
        await pilot.pause()
        assert isinstance(app.screen, AppearanceScreen)
        app.screen.query_one('#ui-theme', Select).value = 'github-light'
        app.screen.query_one('#ui-language', Select).value = 'en'
        await pilot.pause()
        assert app.theme == 'github-light'
        await pilot.click('#appearance-apply')
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert app.language == 'en'
        assert app.query_one('#search', Input).value == '中文'
        assert app.query_one('#sessions', DataTable).row_count == 1
        assert str(app.query_one('#edit').label) == 'Edit name / tags'
    assert store.preferences() == {'language':'en', 'theme':'github-light'}
    reopened = AgentDeck(store=store, collector=FakeCollector([row()]))
    assert reopened.language == 'en' and reopened.palette_name == 'github-light'


async def test_cancel_restores_theme(tmp_path):
    store = Store(tmp_path/'labels.sqlite')
    app = AgentDeck(store=store, collector=FakeCollector([row()]))
    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        await pilot.click('#appearance')
        await pilot.pause()
        app.screen.query_one('#ui-theme', Select).value = 'dracula'
        await pilot.pause()
        assert app.theme == 'dracula'
        await pilot.press('escape')
        await pilot.pause()
        assert app.theme == 'vscode'
        assert not store.preferences()


def test_english_cli_help():
    executable=Path(__file__).resolve().parents[1]/'chatdock'
    result=subprocess.run([str(executable),'--lang','en','--help'],capture_output=True,text=True)
    assert result.returncode == 0
    assert 'Start:' in result.stdout
    assert 'tokyo-night' not in result.stdout
    assert 'F2' not in result.stdout


async def test_footer_and_confirmation_use_english(tmp_path):
    from agentdeck.tui import CloseScreen
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]), language='en')
    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        assert app._bindings.key_to_bindings['q'][0].description == 'Quit'
        assert len(app._bindings.key_to_bindings['q']) == 1
        app.push_screen(CloseScreen({'pid':12345,'affected':[row()]}))
        await pilot.pause()
        assert 'Type the PID' in str(app.screen.query('Label').last().render())
        assert str(app.screen.query_one('#confirm-close').label) == 'Stop backend'
