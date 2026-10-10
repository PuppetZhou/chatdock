"""Loopback-only HTTP dashboard, using the same collector and operation guards as TUI."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit

from .registry import Collector, close_plan, terminate
from .store import Store
from .naming import can_rename, rename


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, home, port=8765, *, collector=None, store=None):
        self.collector = collector if collector is not None else Collector(home)
        self.store = store if store is not None else Store()
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.plans = {}
        super().__init__(('127.0.0.1', port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Session metadata and credentials never go to access logs.

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, api=False):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:
            self.respond(403, {'error': 'Invalid host'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://{h}' for h in hosts}:
            self.respond(403, {'error': 'Invalid origin'})
            return False
        if api and not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            self.respond(401, {'error': '请使用终端中完整的启动链接打开 / Open the full launch URL from your terminal.'})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.authorized(path.startswith('/api/')):
            return
        if path == '/api/sessions':
            try:
                with self.server.lock:
                    data = self.server.collector.collect()
                    labels = self.server.store.all()
                    for row in data['rows']:
                        row['tags'] = labels.get(row['key'], {}).get('tags', [])
                        row['can_rename'] = can_rename(row)
                self.respond(200, data)
            except Exception as exc:
                self.respond(500, {'error': str(exc)})
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in assets:
            self.respond(404, {'error': 'Not found'})
            return
        filename, mime = assets[path]
        self.respond(200, (Path(__file__).parent / 'static' / filename).read_bytes(), mime)

    def do_POST(self):
        if not self.authorized(True):
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                raise ValueError('Invalid request size')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Expected JSON')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('Expected an object')
            with self.server.lock:
                result = self.action(urlsplit(self.path).path, body)
            self.respond(200, result)
        except (ValueError, KeyError, TypeError) as exc:
            self.respond(400, {'error': str(exc)})
        except Exception as exc:
            self.respond(500, {'error': str(exc)})

    def action(self, path, body):
        self.server.plans = {k: p for k, p in self.server.plans.items() if time.monotonic() - p['created'] <= 60}
        if path == '/api/close':
            plan = self.server.plans.get(body.get('plan'))
            if not plan or str(body.get('pid')) != str(plan['pid']):
                raise ValueError('确认已过期或 PID 不一致，请重新检查。')
            del self.server.plans[body['plan']]
            terminate(plan, self.server.collector)
            return {'ok': True}
        if path not in ('/api/edit', '/api/close-plan'):
            raise ValueError('Unknown action')
        rows = self.server.collector.collect()['rows']
        row = next((r for r in rows if r['key'] == body.get('key')), None)
        if row is None:
            raise ValueError('会话已变化，请刷新。')
        if path == '/api/close-plan':
            if len(self.server.plans) >= 100:
                raise ValueError('请稍后重试。')
            plan = close_plan(row, self.server.collector)
            handle = secrets.token_urlsafe(24)
            self.server.plans[handle] = plan
            return dict(plan=handle, pid=plan['pid'], affected=plan['affected'])
        tags = body.get('tags', [])
        name = body.get('name', row.get('title', ''))
        if not isinstance(name, str) or not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            raise ValueError('Invalid name or tags')
        if len(tags) > 20 or any(len(t.strip()) > 40 for t in tags):
            raise ValueError('最多 20 个标签，每个最多 40 字。')
        if name != row.get('title', ''):
            asyncio.run(rename(row, name, self.server.collector.home))
        self.server.store.save(row['key'], '', tags)
        return {'ok': True}


def serve(home, port=8765):
    try:
        server = DashboardServer(home, port)
    except OSError as exc:
        print(f'无法启动 HTTP 服务：{exc}。可用 --port 指定其他端口。')
        return 1
    print(f'ChatDock · http://127.0.0.1:{server.server_port}/#token={server.token}', flush=True)
    print('仅本机访问 · Ctrl+C 停止网页服务（Agent 继续运行）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
