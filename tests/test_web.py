import http.client
import json
import threading
from unittest.mock import patch, AsyncMock
import pytest
from agentdeck.web import DashboardServer
from agentdeck.store import Store
from test_deck import FakeCollector, row


@pytest.fixture
def server(tmp_path):
    store = Store(tmp_path/'labels.sqlite')
    collector = FakeCollector([row(title='<script>alert(1)</script>', pid=98765, start='123', rss_bytes=1048576, threads=4)])
    server = DashboardServer(tmp_path, 0, collector=collector, store=store)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield server
    server.shutdown()
    server.server_close()
    worker.join()


def request(server, path, body=None, *, auth=True, headers=None):
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
    combined = {'Authorization': 'Bearer '+server.token} if auth else {}
    if body is not None:
        combined['Content-Type'] = 'application/json'
    combined.update(headers or {})
    connection.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, combined)
    response = connection.getresponse()
    result = response.status, response.read(), response.getheaders()
    connection.close()
    return result


def test_http_auth_origin_host_and_assets(server):
    assert request(server, '/api/sessions', auth=False)[0] == 401
    assert request(server, '/api/sessions', headers={'Origin':'https://evil.example'})[0] == 403
    assert request(server, '/api/sessions', headers={'Host':'evil.example'})[0] == 403
    assert request(server, '/api/edit', {'key':'codex:a'}, auth=False)[0] == 401
    status, data, headers = request(server, '/', auth=False)
    assert status == 200 and b'ChatDock' in data
    assert 'frame-ancestors' in dict(headers)['Content-Security-Policy']
    assert request(server, '/../../README.md')[0] == 404
    for asset in ('app.js', 'style.css'):
        assert request(server, '/'+asset)[0] == 200
    status, data, _ = request(server, '/api/sessions')
    result = json.loads(data)
    assert status == 200
    assert result['rows'][0]['threads'] == 4
    assert result['rows'][0]['tags'] == []


def test_edit_and_native_rename(server):
    with patch('agentdeck.web.rename', new_callable=AsyncMock) as rename:
        status, _, _ = request(server, '/api/edit', {'key':'codex:a', 'name':'New name', 'tags':['work']})
        assert status == 200
        rename.assert_awaited_once()
        assert server.store.all()['codex:a']['tags'] == ['work']
        assert request(server, '/api/edit', {'key':'codex:a','tags':['x'*41]})[0] == 400
        assert rename.await_count == 1
        assert request(server, '/api/edit', {'key':'missing','tags':[]})[0] == 400


def test_close_requires_plan_pid_and_is_single_use(server):
    import time
    plan = dict(pid=98765, start='123', key='codex:a', affected=server.collector.rows, created=time.monotonic())
    with patch('agentdeck.web.close_plan', return_value=plan), patch('agentdeck.web.terminate') as terminate:
        assert request(server, '/api/close', {'plan':'fake','pid':98765})[0] == 400
        status, body, _ = request(server, '/api/close-plan', {'key':'codex:a'})
        assert status == 200
        handle = json.loads(body)['plan']
        assert request(server, '/api/close', {'plan':handle,'pid':1})[0] == 400
        terminate.assert_not_called()
        assert request(server, '/api/close', {'plan':handle,'pid':98765})[0] == 200
        terminate.assert_called_once_with(plan, server.collector)
        assert request(server, '/api/close', {'plan':handle,'pid':98765})[0] == 400
