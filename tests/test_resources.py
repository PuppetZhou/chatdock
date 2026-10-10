import os
from agentdeck.registry import process_resources, identity
from agentdeck.tui import AgentDeck
from agentdeck.store import Store
from textual.widgets import DataTable, Static
from test_deck import FakeCollector, row


def test_live_resources_and_reused_pid():
    pid = os.getpid()
    result = process_resources(pid, identity(pid))
    assert result['rss_bytes'] > 0 and result['threads'] >= 1
    assert process_resources(pid, 'wrong') == dict(rss_bytes=None, threads=None)
    assert process_resources(None, None) == dict(rss_bytes=None, threads=None)


async def test_full_directory_and_resources(tmp_path):
    path = '/workspace/' + 'long-project-name/' * 9 + 'manuscript'
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row(cwd=path, rss_bytes=1048576, threads=3)]))
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        table = app.query_one('#sessions', DataTable)
        directory = table.ordered_columns[5]
        assert directory.content_width >= len(path)
        assert path in str(app.query_one('#detail', Static).render())
        assert '1.0 MiB RSS' in str(app.query_one('#detail', Static).render())
        assert '3 线程' in str(app.query_one('#detail', Static).render())
