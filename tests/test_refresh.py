from textual.widgets import Checkbox, DataTable, Static
from agentdeck.tui import AgentDeck
from agentdeck.store import Store
from test_deck import row, FakeCollector


async def test_refresh_changes_pause_and_manual(tmp_path):
    collector = FakeCollector([row(f'codex:{i}') for i in range(60)])
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=collector)
    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        table = app.query_one('#sessions', DataTable)
        table.move_cursor(row=10)
        table.scroll_to(x=20, y=5, animate=False)
        await pilot.pause()
        before = table.rows[next(iter(table.rows))]
        collector.rows[10] = row('codex:10', title='后台改名', rss_bytes=1048576, threads=4)
        await app.poll_data()
        await pilot.pause()
        assert app.current()['title'] == '后台改名'
        assert table.rows[next(iter(table.rows))] is before
        assert table.scroll_x == 20
        assert 'Δ1' in str(app.query_one('#statusline', Static).render())
        app.query_one('#auto-refresh', Checkbox).value = False
        await pilot.pause()
        revision = app.refresh_revision
        collector.rows.append(row('codex:new'))
        collector.rows = collector.rows[1:]
        await app.poll_data()
        assert app.refresh_revision == revision
        await pilot.click('#refresh')
        await pilot.pause()
        assert app.refresh_revision == revision + 1
        assert app.current()['key'] == 'codex:10'
        assert '+1 / −1' in str(app.query_one('#statusline', Static).render())
        assert table.scroll_x == 20
