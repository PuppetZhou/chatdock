from textual._xterm_parser import XTermParser
from textual import events
from textual.widgets import DataTable
from agentdeck.tui import AgentDeck
from agentdeck.store import Store
from test_deck import row, FakeCollector


async def test_horizontal_terminal_wheel_scrolls_table(tmp_path):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]))
    async with app.run_test(size=(130, 42)) as pilot:
        await pilot.pause()
        table = app.query_one('#sessions', DataTable)
        assert table.max_scroll_x > 0
        parser = XTermParser()
        # SGR 67 is a rightward wheel event (e.g. xterm.js / VS Code).
        event = parser.parse_mouse_code('\x1b[<67;50;15M')
        table.post_message(event)
        await pilot.pause()
        assert table.scroll_x > 0
        assert table.scroll_y == 0
        event = parser.parse_mouse_code('\x1b[<66;50;15M')
        table.post_message(event)
        await pilot.pause()
        assert table.scroll_x == 0


def test_wheel_adapter_preserves_other_events_and_modifiers():
    from agentdeck.terminal import install_horizontal_wheel_support
    install_horizontal_wheel_support()
    installed = XTermParser.parse_mouse_code
    install_horizontal_wheel_support()
    assert XTermParser.parse_mouse_code is installed
    parser = XTermParser()
    for code, event_type in [(64, events.MouseScrollUp), (65, events.MouseScrollDown)]:
        event = parser.parse_mouse_code(f'\x1b[<{code};50;15M')
        assert isinstance(event, event_type)
        assert not event.shift
    event = parser.parse_mouse_code('\x1b[<91;50;15M')
    assert isinstance(event, events.MouseScrollDown)
    assert event.shift and event.ctrl and event.meta
    assert (event.x, event.y) == (49, 14)
    assert isinstance(parser.parse_mouse_code('\x1b[<0;50;15M'), events.MouseDown)


async def test_scroll_controls_and_refresh_preserve_view(tmp_path):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'),
                    collector=FakeCollector([row(f'codex:{i}') for i in range(80)]))
    async with app.run_test(size=(130, 42)) as pilot:
        await pilot.pause()
        table = app.query_one('#sessions', DataTable)
        parser = XTermParser()
        table.post_message(parser.parse_mouse_code('\x1b[<65;50;15M'))
        await pilot.pause()
        assert table.scroll_y > 0 and table.scroll_x == 0
        table.post_message(parser.parse_mouse_code('\x1b[<69;50;15M'))
        await pilot.pause()
        assert table.scroll_x > 0
        x, y = table.scroll_x, table.scroll_y
        await app.refresh_data()
        await pilot.pause()
        assert (table.scroll_x, table.scroll_y) == (x, y)
        await pilot.click('#table-right')
        await pilot.pause()
        assert table.scroll_x > x
        await pilot.click('#table-left')
        await pilot.pause()
        assert table.scroll_x == x
