"""Local demo server with fictional sessions, never real Agent data."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentdeck.web import DashboardServer
from agentdeck.store import Store
from render_preview import Demo


class WebDemo(Demo):
    home = Path('/unused-demo')

    def collect(self):
        data = super().collect()
        for i, row in enumerate(data['rows']):
            row['rss_bytes'] = (96 + i * 43) * 1024**2 if row['pid'] else None
            row['threads'] = 7 + i * 3 if row['pid'] else None
        return data


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory)/'labels.sqlite')
        store.save('demo:0', '', ['写作', '进行中'])
        store.save('demo:4', '', ['待跟进'])
        with DashboardServer(None, 8766, collector=WebDemo(), store=store) as server:
            print(f'http://127.0.0.1:{server.server_port}/#token={server.token}', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
