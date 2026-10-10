"""Generate a shareable screenshot with fictional data only."""
import asyncio
import argparse
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentdeck.store import Store
from agentdeck.tui import AgentDeck


class Demo:
    def collect(self):
        rows = []
        for i, (name, agent, client, folder, pid, tags) in enumerate([
            ('手稿修订 · Introduction', 'Codex', 'VS Code 插件', '/workspace/paper', 24108, '写作'),
            ('实验结果与图表检查', 'Claude Code', '终端 CLI', '/workspace/paper/results', 24132, '实验'),
            ('API 性能分析', 'Codex', 'Desktop 后端', '/workspace/api', 24205, '性能'),
            ('前端组件审查', 'Cursor', 'CLI/后台进程', '/workspace/dashboard', 24220, '审查'),
            ('方法部分 · 第二轮修改', 'Codex', '历史记录', '/workspace/paper', None, '待跟进'),
            ('参考文献整理', 'Claude Code', '历史记录', '/workspace/paper', None, '文献'),
            ('数据库迁移方案', 'Codex', '历史记录', '/workspace/api', None, '归档'),
        ]):
            rows.append(dict(key=f'demo:{i}', id=f'019-demo-session-{i:04}', title=name, agent=agent,
                source=client, cwd=folder, pid=pid, start='demo', status='后端存活；前端未知' if pid else '无写锁',
                lock='持有写锁' if pid and agent=='Codex' else '进程存活' if pid else '无写锁',
                kind='session', updated_at=0, evidence='演示数据 · 不对应真实进程'))
        return dict(rows=rows, warnings=[], time='2026-10-11T09:41:00+08:00')


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--theme', default='vscode')
    parser.add_argument('--lang', default='zh')
    parser.add_argument('--output', default='preview.svg')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d)/'labels.sqlite')
        store.save('demo:0', '', ['写作', '进行中'])
        store.save('demo:4', '', ['待跟进'])
        os.environ.pop('NO_COLOR', None)
        app = AgentDeck(store=store, collector=Demo(), language=args.lang, theme_name=args.theme)
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause()
            target = Path(__file__).parent/args.output
            app.save_screenshot(str(target))
            svg = target.read_text()
            svg = svg.replace('Fira Code, monospace', '"Noto Sans Mono CJK SC", "Noto Sans CJK SC", monospace')
            target.write_text(svg)


if __name__ == '__main__':
    asyncio.run(main())
