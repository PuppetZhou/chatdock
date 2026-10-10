"""Provider observations. No inferred 'connected' or 'working' states."""
import json
import os
from pathlib import Path
import signal
import ctypes
import time
from . import core


def identity(pid):
    p = Path('/proc') / str(pid)
    if p.stat().st_uid != os.getuid():
        raise ValueError('进程不属于当前用户')
    stat = p.joinpath('stat').read_text().rsplit(')', 1)[1].split()
    return stat[19]  # /proc field 22, process start ticks


def process_resources(pid, start, proc_root=Path('/proc')):
    """RSS and OS threads for a verified PID, never per-session attribution."""
    empty = dict(rss_bytes=None, threads=None)
    if not pid or not start:
        return empty
    try:
        path = proc_root / str(pid)
        def started():
            return path.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
        if started() != str(start):
            return empty
        fields = dict(line.split(':', 1) for line in path.joinpath('status').read_text().splitlines() if ':' in line)
        result = dict(rss_bytes=int(fields['VmRSS'].split()[0]) * 1024 if 'VmRSS' in fields else None,
                      threads=int(fields['Threads']) if 'Threads' in fields else None)
        return result if started() == str(start) else empty
    except (OSError, ValueError, IndexError):
        return empty


def provider(p):
    args = p['args']
    if not args:
        return None
    name = Path(args[0]).name
    if name in ('codex', 'codex.exe'):
        return 'Codex'
    if name in ('claude', 'claude-code'):
        return 'Claude Code'
    if name == 'opencode':
        return 'OpenCode'
    if name == 'gemini':
        return 'Gemini CLI'
    if name in ('cursor-agent', 'agent') and 'cursor' in args[0].lower():
        return 'Cursor'
    # Match Node entrypoints only; never search user prompt arguments.
    if name in ('node', 'bun') and len(args) > 1:
        entry = args[1]
        for needle, label in (('@anthropic-ai/claude-code/', 'Claude Code'), ('@google/gemini-cli/', 'Gemini CLI'), ('@openai/codex/', 'Codex')):
            if needle in entry:
                return label
    return None


def proc_row(p, procs, agent):
    source, status = core.classify(p, procs)
    try:
        cwd = str((Path('/proc') / str(p['pid']) / 'cwd').resolve(strict=True))
        start = identity(p['pid'])
    except (OSError, ValueError):
        return None
    return dict(key=f'process:{p["pid"]}:{start}', id=f'PID {p["pid"]}', title=f'{agent} 后端',
                agent=agent, kind='process', pid=p['pid'], start=start, ppid=p['ppid'],
                cwd=cwd, source=source, status=status, lock='进程存活', updated_at=0,
                evidence='仅检测到进程，未确认对应的会话 ID。')


class Collector:
    def __init__(self, home, claude_home=None):
        self.home = Path(home)
        self.claude_home = Path(claude_home) if claude_home else Path.home() / '.claude'
        self.cache = {}

    def claude(self, warnings):
        rows = []
        for path in self.claude_home.glob('projects/*/*.jsonl'):
            try:
                stamp = (path.stat().st_mtime_ns, path.stat().st_size)
                if path in self.cache and self.cache[path][0] == stamp:
                    rows.append(dict(self.cache[path][1]))
                    continue
                cwd, title = '', ''
                # Bounded read: never load entire transcripts or expose message bodies.
                with path.open() as f:
                    for _ in range(100):
                        line = f.readline(262144)
                        if not line:
                            break
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        cwd = item.get('cwd') or cwd
                        if item.get('type') == 'summary':
                            title = str(item.get('summary', ''))[:160]
                        if cwd and title:
                            break
                # Claude appends custom-title events; read a bounded tail for the latest native name.
                custom_title = ''
                with path.open('rb') as f:
                    f.seek(max(0, stamp[1] - 1024 * 1024))
                    for raw in f:
                        try:
                            item = json.loads(raw)
                        except (ValueError, UnicodeError):
                            continue
                        if item.get('type') == 'custom-title' and item.get('customTitle'):
                            custom_title = str(item['customTitle'])
                row = dict(key='claude:' + path.stem, id=path.stem,
                    title=custom_title or title or 'Claude 会话 ' + path.stem[:8], cwd=cwd,
                    agent='Claude Code', kind='session', pid=None, start=None, source='历史记录',
                    status='运行关联未知', lock='未关联进程', updated_at=path.stat().st_mtime,
                    evidence='Claude 本地记录；没有可靠的会话 → PID 映射，不按目录猜测。')
                self.cache[path] = (stamp, row)
                rows.append(dict(row))
            except (OSError, ValueError) as exc:
                warnings.append('Claude 记录读取失败：' + str(exc))
        return rows

    def collect(self):
        data = core.snapshot(self.home, True)
        procs = core.processes()
        rows = []
        for s in data['sessions']:
            row = dict(s, key='codex:' + s['id'], agent='Codex', kind='session', start=None,
                       evidence='系统 FLOCK 写锁 + Codex 本地数据库。' if s['pid'] else '本地历史记录；无写锁不能证明异常断连。')
            if s['pid']:
                try:
                    row['start'] = identity(s['pid'])
                except (OSError, ValueError):
                    row['pid'] = None
                    row['status'] = '采样期间进程退出'
            rows.append(row)
        rows += self.claude(data['warnings'])
        owned = {r['pid'] for r in rows if r.get('pid')}
        for p in procs.values():
            agent = provider(p)
            if agent and p['pid'] not in owned:
                row = proc_row(p, procs, agent)
                if row:
                    rows.append(row)
        resources = {}
        for row in rows:
            key = (row.get('pid'), row.get('start'))
            if key not in resources:
                resources[key] = process_resources(*key)
            row.update(resources[key])
        rows.sort(key=lambda r: (not bool(r.get('pid')), -r.get('updated_at', 0), r['key']))
        return dict(rows=rows, warnings=data['warnings'], time=data['time'])


def in_directory(cwd, directory, recursive=True):
    if not directory:
        return True
    if not cwd:
        return False
    p, root = Path(cwd), Path(directory)
    return p == root or (recursive and root in p.parents)


def filtered(rows, labels, query='', directory='', recursive=True, agent='all', client='all', state='all'):
    result = []
    query = query.casefold().strip()
    for r in rows:
        meta = labels.get(r['key'], {})
        if agent != 'all' and r['agent'] != agent:
            continue
        if client != 'all' and r['source'] != client:
            continue
        if state == 'live' and not r.get('pid'):
            continue
        if state == 'history' and r.get('pid'):
            continue
        if not in_directory(r.get('cwd'), directory, recursive):
            continue
        text = ' '.join(str(r.get(k, '')) for k in ('title', 'id', 'cwd', 'source', 'agent'))
        text += ' ' + meta.get('alias', '') + ' ' + ' '.join(meta.get('tags', []))
        if query and query not in text.casefold():
            continue
        result.append(r)
    return result


def protected_pids():
    procs = core.processes()
    pid, result = os.getpid(), set()
    while pid in procs and pid not in result:
        result.add(pid)
        pid = procs[pid]['ppid']
    return result


def close_plan(row, collector):
    pid = row.get('pid')
    if not pid or not row.get('start'):
        raise ValueError('此项没有可确认的活动进程。')
    if pid in protected_pids():
        raise ValueError('此进程承载当前管理器，不能从这里终止。请从独立终端打开管理器。')
    if identity(pid) != row['start']:
        raise ValueError('进程已变化，请刷新后重试。')
    fresh = collector.collect()['rows']
    affected = [r for r in fresh if r.get('pid') == pid]
    if not any(r['key'] == row['key'] and r.get('start') == row['start'] for r in affected):
        raise ValueError('会话占用已变化，请刷新后重试。')
    return dict(pid=pid, start=row['start'], key=row['key'],
                affected=affected, created=time.monotonic())


def terminate(plan, collector):
    if time.monotonic() - plan['created'] > 60:
        raise ValueError('确认已过期，请重新检查影响范围。')
    row = dict(pid=plan['pid'], start=plan['start'], key=plan['key'])
    fresh = close_plan(row, collector)
    if {r['key'] for r in fresh['affected']} != {r['key'] for r in plan['affected']}:
        raise ValueError('此后端的会话列表已变化，请重新确认。')
    # pidfd pins the actual process so a recycled PID can never receive the signal.
    # Some Python builds omit wrappers even though glibc and the kernel support them.
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, 'pidfd_open') or not hasattr(libc, 'pidfd_send_signal'):
        raise ValueError('当前 Linux 不支持 pidfd，已禁用终止操作。')
    libc.pidfd_open.argtypes = [ctypes.c_int, ctypes.c_uint]
    libc.pidfd_open.restype = ctypes.c_int
    libc.pidfd_send_signal.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
    libc.pidfd_send_signal.restype = ctypes.c_int
    fd = libc.pidfd_open(plan['pid'], 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), '无法获取进程句柄')
    try:
        if identity(plan['pid']) != plan['start']:
            raise ValueError('进程已变化。')
        if libc.pidfd_send_signal(fd, signal.SIGTERM, None, 0) < 0:
            raise OSError(ctypes.get_errno(), '无法发送 SIGTERM')
    finally:
        os.close(fd)
