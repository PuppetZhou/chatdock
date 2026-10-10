#!/usr/bin/env python3
"""Read-only Linux Codex session/lock inspector. No third-party dependencies."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unicodedata


def processes():
    result = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != os.getuid():
                continue
            args = p.joinpath('cmdline').read_bytes().decode(errors='replace').strip('\0').split('\0')
            stat = p.joinpath('stat').read_text().rsplit(')', 1)[1].split()
            result[int(p.name)] = dict(pid=int(p.name), ppid=int(stat[1]),
                state=stat[0], tty=int(stat[4]), args=args)
        except (OSError, ValueError, IndexError):
            pass
    return result


def classify(p, procs):
    args = p['args']
    exe = args[0] if args else ''
    chain, seen, q = [], set(), p
    while q and q['pid'] not in seen:
        seen.add(q['pid'])
        chain.append(' '.join(q['args']))
        q = procs.get(q['ppid'])
    ancestry = '\n'.join(chain)
    if '/extensions/openai.chatgpt-' in exe:
        source = 'Cursor 插件' if '.cursor' in exe else 'VS Code 插件'
    elif 'app-server' in args and 'proxy' in args:
        source = 'Codex 服务代理'
    elif '/chatgpt/' in exe.lower() or '/codex.app/' in exe.lower():
        source = 'Desktop 后端'
    elif 'app-server' in args:
        source = '独立 app-server'
    elif p['tty']:
        source = '终端（VS Code）' if '.vscode-server/' in ancestry else '终端 CLI'
    else:
        source = 'CLI/后台进程'
    if p['state'] == 'Z':
        state = '僵尸进程'
    elif p['ppid'] == 1:
        state = '后台存活；客户端未知'
    elif p['ppid'] not in procs:
        state = '存活；父进程不可见'
    elif p['tty']:
        state = 'TTY 存在；用户连接未知'
    else:
        state = '后端/父进程存活；前端未知'
    return source, state


def metadata(home, warnings):
    dbs = sorted(home.glob('state_*.sqlite'),
                  key=lambda p: int(p.stem.split('_')[-1]) if p.stem.split('_')[-1].isdigit() else -1,
                  reverse=True)
    if not dbs:
        warnings.append('未找到会话数据库；仍显示系统锁。')
        return {}
    try:
        with sqlite3.connect(dbs[0].resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as c:
            c.row_factory = sqlite3.Row
            cols = {r[1] for r in c.execute('pragma table_info(threads)')}
            wanted = [x for x in ('id', 'title', 'name', 'cwd', 'updated_at', 'archived') if x in cols]
            rows = {}
            for record in c.execute('select ' + ','.join(wanted) + ' from threads'):
                row = dict(record)
                row['original_title'] = row.get('title', '')
                row['title'] = row.get('name') or row.get('title') or ''
                rows[row['id']] = row
            return rows
    except sqlite3.Error as e:
        warnings.append('数据库读取失败：' + str(e))
        return {}


def snapshot(home, include_all):
    warnings = []
    procs = processes()
    r = subprocess.run(['lslocks', '--json', '-o', 'PID,TYPE,MODE,PATH'],
                       capture_output=True, text=True, check=True)
    locks = []
    lock_dir = str(home.resolve() / 'thread-writer-locks') + '/'
    for lock in json.loads(r.stdout).get('locks', []):
        path = lock.get('path') or ''
        if path.startswith(lock_dir) and 'WRITE' in lock.get('mode', ''):
            tid = Path(path).stem
            if tid != '.coordination':
                locks.append((tid, int(lock['pid'])))
    meta = metadata(home, warnings)
    sessions = []
    for tid, pid in locks:
        p = procs.get(pid)
        source, status = classify(p, procs) if p else ('未知', '进程不可见/采样期间退出')
        sessions.append(dict(meta.get(tid, {}), id=tid, pid=pid, source=source,
                             status=status, lock='持有写锁'))
    if include_all:
        held = {tid for tid, _ in locks}
        for tid, m in meta.items():
            if tid not in held:
                sessions.append(dict(m, pid=None, source='—', status='无写锁（不代表异常断连）', lock='无写锁'))
    sessions.sort(key=lambda s: (s['pid'] is None, -int(s.get('updated_at') or 0), s['id']))
    backends = []
    owners = {pid for _, pid in locks}
    for pid, p in sorted(procs.items()):
        if not p['args']:
            continue
        if Path(p['args'][0]).name not in ('codex', 'codex.exe') and pid not in owners:
            continue
        source, status = classify(p, procs)
        backends.append(dict(pid=pid, ppid=p['ppid'], source=source, status=status,
                             locks=sum(owner == pid for _, owner in locks)))
    return dict(time=datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                codex_home=str(home), sessions=sessions, backends=backends, warnings=warnings)


def clean(value):
    return ''.join(c if not unicodedata.category(c).startswith('C') else ' ' for c in str(value))


def render(data, language="zh"):
    if language == "en":
        from .i18n import translate
        t = lambda value: translate(value, "en")
        print("ChatDock · Codex snapshot  " + data["time"])
        print("Data directory: " + data["codex_home"])
        print("\nSessions (locked does not mean generating):")
        for row in data["sessions"]:
            print(f"  [{t(row['lock'])}] PID={row['pid'] or '—'}  {t(row['source'])}  {t(row['status'])}")
            print("    " + row["id"] + "  " + clean(row.get("title", ""))[:100])
            print("    Directory: " + clean(row.get("cwd", "Unknown")))
        if not data["sessions"]:
            print("  No write locks found. Use --all to include history.")
        print("\nCodex processes:")
        for row in data["backends"]:
            print(f"  PID={row['pid']} PPID={row['ppid']} Locks={row['locks']}  {t(row['source'])}  {t(row['status'])}")
        for warning in data["warnings"]:
            print("Diagnostic: " + t(warning))
        print("\nRead-only snapshot. Frontend connection status cannot be inferred from process liveness.")
        return
    print('Codex 会话检查  ' + data['time'])
    print('数据目录：' + data['codex_home'])
    print('\n会话（持锁不等于正在生成；无锁不等于断连）：')
    for s in data['sessions']:
        print(f"  [{s['lock']}] PID={s['pid'] or '—'}  {s['source']}  {s['status']}")
        print('    ' + s['id'] + '  ' + clean(s.get('title', '(标题未知)'))[:100])
        if s.get('cwd'):
            print('    目录：' + clean(s['cwd']))
    if not data['sessions']:
        print('  当前未发现会话写锁。使用 --all 查看数据库中的历史会话。')
    print('\nCodex 进程（含无会话锁的服务）：')
    for p in data['backends']:
        print(f"  PID={p['pid']} PPID={p['ppid']} 锁={p['locks']}  {p['source']}  {p['status']}")
    for warning in data['warnings']:
        print('提示：' + warning)
    print('\n只读快照：不终止进程、不删除锁。前端/远程桌面是否断连不能仅凭后端存活确定。')


def main():
    from .helptext import examples
    from .appearance import PALETTES
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument('--lang', choices=['zh', 'en'])
    ui_lang = language_parser.parse_known_args()[0].lang
    en = ui_lang == 'en'
    advanced = '--help-all' in sys.argv
    parser = argparse.ArgumentParser(
        add_help=False, usage='%(prog)s [--tui | --web] [options]',
        description='ChatDock · Local Agent session manager' if en else 'ChatDock · 本地 Agent 会话管理器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=examples(Path(sys.argv[0]).name, language=ui_lang or 'zh'))
    parser._optionals.title = 'Options' if en else '选项'
    parser.add_argument('-h', '--help', action='help', help='Show help' if en else '查看帮助')
    parser.add_argument('--help-all', action='help', help='All options' if en else '查看全部参数')
    parser.add_argument('--tui', action='store_true', help='Terminal dashboard' if en else '打开终端界面')
    parser.add_argument('--web', action='store_true', help='Local browser dashboard' if en else '打开本地网页版')
    parser.add_argument('--port', type=int, default=8765, help=('HTTP port (default 8765)' if en else 'HTTP 端口（默认 8765）') if advanced else argparse.SUPPRESS)
    parser.add_argument('--install-command', action='store_true', help='Add command to ~/.local/bin' if en else '安装命令到 ~/.local/bin')
    parser.add_argument('--all', action='store_true', help='Include history' if en else '包含历史会话')
    parser.add_argument('--json', action='store_true', help='Output JSON' if en else '输出 JSON')
    parser.add_argument('--watch', type=float, metavar='SECONDS', help='Refresh interval (seconds)' if en else '定时刷新（秒）')
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('CODEX_HOME', '~/.codex')).expanduser(), help=('Codex data directory' if en else 'Codex 数据目录') if advanced else argparse.SUPPRESS)
    parser.add_argument('--lang', choices=['zh', 'en'], help='Interface language / 界面语言' if advanced else argparse.SUPPRESS)
    parser.add_argument('--theme', choices=list(PALETTES), help='Color theme / 配色主题 (TUI)' if advanced else argparse.SUPPRESS)
    args = parser.parse_args()
    if args.install_command:
        from .install import install_command
        try:
            install_command()
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        return 0
    if args.web:
        if args.tui or args.all or args.json or args.watch is not None:
            parser.error('--web cannot be combined with --tui, --all, --json or --watch')
        if not 0 <= args.port <= 65535:
            parser.error('--port must be between 0 and 65535')
        from .web import serve
        return serve(args.home.expanduser(), args.port)
    if args.tui:
        if args.all or args.json or args.watch is not None:
            parser.error('--tui 不能与 --all、--json 或 --watch 合用；请使用界面内筛选。')
        from .tui import AgentDeck
        AgentDeck(home=args.home.expanduser(), language=args.lang, theme_name=args.theme).run()
        return 0
    if args.watch is not None and (not 1 <= args.watch <= 86400):
        parser.error('--watch 必须在 1 到 86400 秒之间')
    try:
        while True:
            data = snapshot(args.home.expanduser(), args.all)
            if args.json:
                print(json.dumps(data, ensure_ascii=False), flush=True)
            else:
                if args.watch and sys.stdout.isatty():
                    print('\033[2J\033[H', end='')
                render(data, language=args.lang or "zh")
            if args.watch is None:
                break
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print('检查失败：' + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
