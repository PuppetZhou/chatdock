import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
import pytest
from textual.widgets import DataTable, Input, Select
from agentdeck.registry import Collector, close_plan, filtered, identity, in_directory, provider, terminate
from agentdeck.store import Store
from agentdeck.tui import AgentDeck, CloseScreen


def row(key='codex:a', **kwargs):
    result = dict(key=key, id=key, title='中文手稿', cwd='/work/paper', agent='Codex', source='VS Code 插件',
                  pid=None, start=None, kind='session', lock='无写锁', status='前端未知', updated_at=0, evidence='测试数据')
    result.update(kwargs)
    return result


class FakeCollector:
    def __init__(self, rows): self.rows = rows; self.home = Path("/unused-test-home")
    def collect(self): return dict(rows=self.rows, warnings=[], time='2026-10-11T12:00:00+08:00')


def test_directory_boundaries():
    assert in_directory('/work/paper/ch1', '/work/paper')
    assert not in_directory('/work/paper-old', '/work/paper')
    assert not in_directory('/work/paper/ch1', '/work/paper', False)


def test_label_persistence_and_filters(tmp_path):
    db = tmp_path / 'labels.sqlite'
    store = Store(db)
    store.save('codex:a', '新版手稿', ['论文', '论文', '待审'])
    labels = Store(db).all()
    assert labels['codex:a']['tags'] == ['论文', '待审']
    assert len(filtered([row()], labels, query='待审')) == 1
    assert not filtered([row()], labels, agent='Claude Code')
    assert not filtered([row()], labels, state='live')


def test_agent_detection_does_not_match_prompts():
    assert provider({'args': ['/bin/bash', '-c', 'claude']}) is None
    assert provider({'args': ['/usr/bin/node', '/x/@anthropic-ai/claude-code/cli.js']}) == 'Claude Code'


def test_own_process_protected():
    r = row(pid=os.getpid(), start=identity(os.getpid()))
    with pytest.raises(ValueError, match='当前管理器'):
        close_plan(r, FakeCollector([r]))


def test_real_child_termination_and_pid_change():
    # Only a disposable test child is signalled; never a user's agent.
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        r = row(pid=p.pid, start=identity(p.pid))
        collector = FakeCollector([r, row('codex:b', pid=p.pid, start=r['start'])])
        plan = close_plan(r, collector)
        assert len(plan['affected']) == 2
        with pytest.raises(ValueError, match='进程已变化'):
            close_plan(dict(r, start='invalid'), collector)
        collector.rows.append(row('codex:c', pid=p.pid, start=r['start']))
        with pytest.raises(ValueError, match='列表已变化'):
            terminate(plan, collector)
        assert p.poll() is None
        collector.rows.pop()
        terminate(plan, collector)
        assert p.wait(timeout=5) == -15
    finally:
        if p.poll() is None: p.terminate(); p.wait()


async def test_tui_mouse_search_edit_and_empty(tmp_path, monkeypatch):
    async def fake_rename(row, name, home):
        return name
    monkeypatch.setattr("agentdeck.tui.rename", fake_rename)
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([
        row(), row('claude:b', title='代码审查', agent='Claude Code', cwd='/work/other')]))
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        assert app.query_one('#sessions', DataTable).row_count == 2
        await pilot.click('#edit')
        await pilot.pause()
        app.screen.query_one('#alias', Input).value = '我的论文'
        app.screen.query_one('#tags', Input).value = '重要, 写作'
        await pilot.click('#save')
        await pilot.pause()
        assert app.store.all()['codex:a']['alias'] == ''
        assert app.current()['title'] == '我的论文'
        assert '我的论文' in str(app.query_one('#detail').render())
        app.query_one('#search', Input).value = '写作'
        await pilot.pause()
        assert app.query_one('#sessions', DataTable).row_count == 1
        app.query_one('#search', Input).value = '不存在'
        await pilot.pause()
        assert app.query_one('#sessions', DataTable).row_count == 0
        app.query_one('#search', Input).value = ''
        await pilot.pause()
        app.query_one('#agent', Select).value = 'Claude Code'
        await pilot.pause()
        assert len(app.filtered_rows) == 1 and app.filtered_rows[0]['agent'] == 'Claude Code'
        await pilot.resize_terminal(100, 32)
        await pilot.pause()


async def test_close_dialog_cancel_never_signals(tmp_path):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]))
    async with app.run_test(size=(140, 45)) as pilot:
        app.push_screen(CloseScreen(dict(pid=1234, affected=[row(), row('codex:b')])))
        await pilot.pause()
        assert app.screen.query_one('#confirm-close').disabled
        app.screen.query_one('#confirm-pid', Input).value = 'wrong'
        await pilot.pause()
        assert app.screen.query_one('#confirm-close').disabled
        await pilot.press('escape')
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def test_selection_folder_filter_and_refresh(tmp_path):
    from textual.widgets import Tree
    rows = [row(), row('codex:b', cwd='/work/paper/ch1'), row('codex:c', cwd='/work/paper-old')]
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector(rows))
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        tree = app.query_one('#folders', Tree)
        target = next(n for n in tree.root.children if n.data == '/work/paper')
        tree.select_node(target)
        await pilot.pause()
        assert len(app.filtered_rows) == 2
        app.query_one('#sessions', DataTable).move_cursor(row=1)
        await pilot.pause()
        assert app.selected == 'codex:b'
        await app.refresh_data()
        await pilot.pause()
        assert app.selected == 'codex:b'
        await pilot.resize_terminal(80, 35)
        await pilot.pause()
        assert app.has_class('narrow')


def test_claude_history_partial_record_and_cache(tmp_path):
    import json
    project = tmp_path / 'projects' / 'project'
    project.mkdir(parents=True)
    path = project / 'session.jsonl'
    path.write_text(json.dumps({'type': 'user', 'cwd': '/work/paper', 'sessionId': 'session'}) + '\n' + '{incomplete')
    collector = Collector(tmp_path/'codex', claude_home=tmp_path)
    warnings = []
    rows = collector.claude(warnings)
    assert rows[0]['cwd'] == '/work/paper'
    assert rows[0]['pid'] is None
    assert collector.claude(warnings) == rows
    assert not warnings


def test_close_confirmation_expires():
    with pytest.raises(ValueError, match='过期'):
        terminate({'created': time.monotonic() - 61}, FakeCollector([]))
