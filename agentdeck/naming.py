"""Native Codex names via the official app-server protocol, never SQL writes."""
import asyncio
import json
import os
from pathlib import Path
import shutil


class CodexRPC:
    def __init__(self, home, executable=None):
        self.home = Path(home)
        self.executable = executable or shutil.which('codex')
        self.process = None
        self.counter = 0

    async def __aenter__(self):
        if not self.executable:
            raise ValueError('未找到 codex 命令，无法执行原生重命名。请安装 Codex CLI。')
        env = dict(os.environ, CODEX_HOME=str(self.home.resolve()))
        self.process = await asyncio.create_subprocess_exec(
            self.executable, 'app-server', '--stdio', env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=8 * 1024 * 1024)
        try:
            await self.request('initialize', {'clientInfo': {'name': 'chat_monitor', 'version': '0.2.0'}})
            await self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def send(self, message):
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + '\n').encode())
        await self.process.stdin.drain()

    async def request(self, method, params):
        self.counter += 1
        request_id = self.counter
        await self.send(dict(id=request_id, method=method, params=params))
        async def response():
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    raise ValueError('Codex 后端已退出，未确认操作结果。')
                message = json.loads(line)
                if message.get('id') != request_id:
                    continue
                if 'error' in message:
                    raise ValueError('Codex: ' + message['error'].get('message', str(message['error'])))
                return message.get('result', {})
        try:
            return await asyncio.wait_for(response(), 20)
        except asyncio.TimeoutError as exc:
            raise ValueError('Codex 请求超时；操作可能已执行，请刷新核对原生名称。') from exc

    async def __aexit__(self, *args):
        p = self.process
        if p is None:
            return
        if p.stdin:
            p.stdin.close()
        try:
            await asyncio.wait_for(p.wait(), 2)
        except asyncio.TimeoutError:
            try:
                p.terminate()
                await asyncio.wait_for(p.wait(), 2)
            except ProcessLookupError:
                pass
            except asyncio.TimeoutError:
                p.kill()
                await p.wait()


def can_rename(row):
    return row.get('agent') == 'Codex' and row.get('kind') == 'session'


async def rename(row, name, home):
    if not can_rename(row):
        raise ValueError('此 Agent 尚未接入原生重命名，请在原客户端修改名称。')
    name = name.strip()
    if not name or len(name) > 160 or any(ord(c) < 32 for c in name):
        raise ValueError('会话名称需为 1–160 字，且不能含换行或控制字符。')
    async with CodexRPC(home) as client:
        await client.request('thread/name/set', {'threadId': row['id'], 'name': name})
        result = await client.request('thread/read', {'threadId': row['id'], 'includeTurns': False})
        if result.get('thread', {}).get('name') != name:
            raise ValueError('重命名请求已发送，但读取结果不一致，请刷新核对。')
    return name
