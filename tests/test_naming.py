import json
import shutil
import sqlite3
from pathlib import Path
import pytest
from textual.widgets import Input
from agentdeck.core import metadata
from agentdeck.naming import CodexRPC, can_rename, rename
from agentdeck.registry import Collector
from agentdeck.store import Store
from agentdeck.tui import AgentDeck
from test_deck import row, FakeCollector


def test_native_name_precedes_title(tmp_path):
    with sqlite3.connect(tmp_path / 'state_5.sqlite') as db:
        db.execute('create table threads (id text, title text, name text)')
        db.executemany('insert into threads values (?,?,?)', [('a','first prompt','APP 已命名'),('b','automatic title',None)])
    rows = metadata(tmp_path, [])
    assert rows['a']['title'] == 'APP 已命名'
    assert rows['a']['original_title'] == 'first prompt'
    assert rows['b']['title'] == 'automatic title'


def test_old_database_schema(tmp_path):
    with sqlite3.connect(tmp_path/'state_1.sqlite') as db:
        db.execute('create table threads (id text, title text)')
        db.execute("insert into threads values ('a','old title')")
    assert metadata(tmp_path, [])['a']['title'] == 'old title'


def test_latest_claude_custom_title(tmp_path):
    p = tmp_path/'projects'/'project'/'session.jsonl'
    p.parent.mkdir(parents=True)
    p.write_text('\n'.join(json.dumps(d) for d in [
        {'type':'user','cwd':'/work'}, {'type':'summary','summary':'summary'},
        {'type':'custom-title','customTitle':'旧名称'}, {'type':'custom-title','customTitle':'最新名称'}]))
    assert Collector(tmp_path, tmp_path).claude([])[0]['title'] == '最新名称'


async def test_native_rpc_persists_in_isolated_home(tmp_path):
    if not shutil.which('codex'):
        pytest.skip('Codex CLI required for native integration test')
    async with CodexRPC(tmp_path) as client:
        created = await client.request('thread/start', {'cwd':str(tmp_path),'persistExtendedHistory':True})
        tid = created['thread']['id']
        await client.request('thread/name/set', {'threadId':tid,'name':'旧名字'})
        await rename(dict(agent='Codex',kind='session',id=tid), 'APP 原生新名字', tmp_path)
        live = await client.request('thread/read', {'threadId':tid,'includeTurns':False})
        assert live['thread']['name'] == 'APP 原生新名字'
    assert metadata(tmp_path, [])[tid]['title'] == 'APP 原生新名字'


async def test_rename_failure_does_not_create_local_alias(tmp_path, monkeypatch):
    async def failed(*args): raise ValueError('模拟接口失败')
    monkeypatch.setattr('agentdeck.tui.rename', failed)
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row()]))
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        await pilot.click('#edit')
        await pilot.pause()
        app.screen.query_one('#alias', Input).value = '不会假装保存成功'
        await pilot.click('#save')
        await pilot.pause()
        assert app.current()['title'] == '中文手稿'
        assert not app.store.all()


async def test_other_agent_name_is_readonly(tmp_path):
    app = AgentDeck(store=Store(tmp_path/'labels.sqlite'), collector=FakeCollector([row(agent='Claude Code')]))
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        await pilot.click('#edit')
        await pilot.pause()
        assert app.screen.query_one('#alias', Input).disabled
        assert not app.screen.query_one('#tags', Input).disabled
