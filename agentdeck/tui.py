"""Keyboard and mouse dashboard. All destructive operations require review."""
import argparse
import asyncio
from collections import Counter
import os
from pathlib import Path
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Select, Static, Tree
from .core import clean
from .registry import Collector, close_plan, filtered, terminate
from .store import Store
from .naming import can_rename, rename
from .helptext import KEYBOARD_HELP, examples
from .i18n import translate, HELP_EN
from .appearance import PALETTES, colors, register_themes
from .terminal import install_horizontal_wheel_support


def plain(value):
    return Text(clean(value), overflow='fold', no_wrap=False)


class AppearanceScreen(ModalScreen):
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def compose(self):
        self.previous_theme = self.app.theme
        with Vertical(id='settings-dialog'):
            yield Label(self.app.tr('外观 / 语言'), classes='dialog-title')
            yield Label(self.app.tr('语言'))
            yield Select([('简体中文', 'zh'), ('English', 'en')], value=self.app.language, allow_blank=False, id='ui-language')
            yield Label(self.app.tr('配色主题'))
            yield Select([(values[0], key) for key, values in PALETTES.items()], value=self.app.palette_name, allow_blank=False, id='ui-theme')
            yield Static('', id='palette-preview')
            yield Static(self.app.tr('选择主题可实时预览；取消恢复原配色。'), classes='muted')
            with Horizontal(classes='dialog-actions'):
                yield Button(self.app.tr('取消'), id='appearance-cancel')
                yield Button(self.app.tr('应用'), id='appearance-apply', variant='primary')

    @on(Select.Changed, '#ui-theme')
    def preview_theme(self, event):
        if event.value not in PALETTES:
            return
        self.app.theme = event.value
        c = colors(event.value)
        swatches = Text(c['name'] + '\n')
        for role in ('accent', 'success', 'warning', 'error', 'muted'):
            swatches.append('  ●  ', style=c[role])
        self.query_one('#palette-preview', Static).update(swatches)

    @on(Button.Pressed)
    def apply_settings(self, event):
        event.stop()
        if event.button.id == 'appearance-apply':
            self.dismiss((self.query_one('#ui-language', Select).value, self.query_one('#ui-theme', Select).value))
        else:
            self.action_cancel()

    def action_cancel(self):
        self.app.theme = self.previous_theme
        self.dismiss(None)


class HelpScreen(ModalScreen):
    BINDINGS = [('escape', 'dismiss_help', '返回'), ('q', 'dismiss_help', '返回'),
                ('f1', 'dismiss_help', '返回')]

    def compose(self):
        with Vertical(id='dialog'):
            yield Label(self.app.tr('使用帮助'), classes='dialog-title')
            with VerticalScroll(id='help-content'):
                yield Static(HELP_EN if self.app.language == 'en' else KEYBOARD_HELP + '\n  F2              外观与语言设置', markup=False)
            yield Button(self.app.tr('返回会话列表  Esc / q'), id='help-close', variant='primary')

    @on(Button.Pressed, '#help-close')
    def close_help(self):
        self.dismiss()

    def action_dismiss_help(self):
        self.dismiss()


class EditScreen(ModalScreen):
    BINDINGS = [('escape', 'cancel', '取消')]
    def __init__(self, row, meta):
        super().__init__()
        self.row, self.meta = row, meta

    def compose(self):
        with Vertical(id='dialog'):
            yield Label(self.app.tr('编辑会话'), classes='dialog-title')
            yield Static(self.app.tr('会话名称直接修改 Codex 原始名称；APP 可能需要重新打开会话才能刷新。分类标签仅在本管理器保存。') if can_rename(self.row) else self.app.tr('当前 Agent 尚不支持原生重命名，名称只读；分类标签可编辑。'), classes='muted')
            yield Label(self.app.tr('会话名称 · Agent 原始名称'))
            yield Input(self.row.get('title') or '', id='alias', max_length=160, disabled=not can_rename(self.row))
            yield Label(self.app.tr('分类标签 · 本地保存，逗号分隔'))
            yield Input(', '.join(self.meta.get('tags', [])), placeholder=self.app.tr('手稿, 待跟进, 实验'), id='tags')
            with Horizontal(classes='dialog-actions'):
                yield Button(self.app.tr('取消'), id='cancel')
                yield Button(self.app.tr('保存'), id='save', variant='primary')

    @on(Button.Pressed)
    def submit(self, event):
        if event.button.id == 'save':
            self.dismiss((self.query_one('#alias', Input).value,
                          self.query_one('#tags', Input).value.replace('，', ',').split(',')))
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class CloseScreen(ModalScreen):
    BINDINGS = [('escape', 'cancel', '取消')]
    def __init__(self, plan):
        super().__init__()
        self.plan = plan

    def compose(self):
        with Vertical(id='dialog'):
            yield Label(self.app.tr('关闭整个后端进程'), classes='dialog-title')
            yield Static((f"Send SIGTERM to PID {self.plan['pid']}, not just the selected chat.\n{len(self.plan['affected'])} known records share this process. Unidentified tasks may also be affected." if self.app.language == 'en' else f"将向 PID {self.plan['pid']} 发送 SIGTERM。不是仅关闭选中的聊天。\n以下 {len(self.plan['affected'])} 项共用该进程；其他未识别任务也可能受影响。"))
            with VerticalScroll(id='affected'):
                for row in self.plan['affected']:
                    yield Static(plain(row['id'] + '\n' + (row.get('title') or self.app.tr('(无标题)'))))
            yield Label(self.app.tr('输入 PID 确认；聊天记录不会被删除'))
            yield Input(placeholder=str(self.plan['pid']), id='confirm-pid')
            with Horizontal(classes='dialog-actions'):
                yield Button(self.app.tr('取消'), id='cancel')
                yield Button(self.app.tr('终止后端'), id='confirm-close', variant='error', disabled=True)

    @on(Input.Changed, '#confirm-pid')
    def validate_pid(self, event):
        self.query_one('#confirm-close', Button).disabled = event.value.strip() != str(self.plan['pid'])

    @on(Button.Pressed)
    def submit(self, event):
        self.dismiss(event.button.id == 'confirm-close')

    def action_cancel(self):
        self.dismiss(False)


class AgentDeck(App):
    TITLE = 'CHATDOCK'
    SUB_TITLE = '会话与工作空间'
    CSS_PATH = 'deck.tcss'
    BINDINGS = [('q', 'quit_dashboard', '退出'), ('question_mark', 'help', '帮助'),
                ('f1', 'help', '帮助'), ('f2', 'appearance', '外观'), ('escape', 'focus_sessions', '返回列表'),
                ('ctrl+q', 'quit', '退出'), ('ctrl+r', 'reload', '刷新'),
                ('ctrl+f', 'search', '搜索'), ('ctrl+e', 'edit', '名称 / 标签')]

    def __init__(self, home=None, store=None, collector=None, language=None, theme_name=None):
        install_horizontal_wheel_support()
        super().__init__()
        self.collector = collector or Collector(home or Path(os.environ.get('CODEX_HOME', '~/.codex')).expanduser())
        self.store = store or Store()
        preferences = self.store.preferences()
        self.language = language or preferences.get('language', 'zh')
        self.palette_name = theme_name or preferences.get('theme', 'vscode')
        if self.language not in ('zh', 'en'):
            self.language = 'zh'
        if self.palette_name not in PALETTES:
            self.palette_name = 'vscode'
        register_themes(self)
        self.theme = self.palette_name
        self.localize_bindings()
        self.rows, self.filtered_rows, self.labels = [], [], {}
        self.selected = None
        self.directory = ''
        self.busy = False
        self.ready = False
        self.directory_signature = None
        self.client_options = None
        self.polling_enabled = True
        self.refresh_revision = 0
        self.observed_sessions = {}

    def get_css_variables(self):
        variables = super().get_css_variables()
        for key, value in colors(getattr(self, 'palette_name', 'vscode')).items():
            if key != 'name':
                variables.setdefault('deck-' + key, value)
        return variables

    def tr(self, text):
        return translate(text, self.language)

    def localize_bindings(self):
        self.sub_title = self.tr('会话与工作空间')
        for key, action, description in self.BINDINGS:
            self._bindings.key_to_bindings.pop(key, None)
            self.bind(key, action, description=self.tr(description), show=key not in ('f1', 'escape', 'ctrl+q'))

    def compose(self) -> ComposeResult:
        with Horizontal(id='topbar'):
            yield Static(self.tr('正在读取本地会话…'), id='summary')
            yield Checkbox(self.tr('自动刷新'), value=self.polling_enabled, id='auto-refresh')
        with Horizontal(id='workspace'):
            with Vertical(id='sidebar'):
                yield Label(self.tr('工作空间'), classes='section-title')
                yield Input(placeholder=self.tr('筛选目录…'), id='folder-search')
                yield Checkbox(self.tr('包含子目录'), value=True, id='recursive')
                yield Tree(self.tr('全部工作空间'), data='', id='folders')
                yield Static(self.tr('本地会话 · 按目录筛选'), id='legend')
            with Vertical(id='center'):
                with Horizontal(id='toolbar'):
                    yield Input(placeholder=self.tr('搜索会话、ID、目录、标签  Ctrl+F'), id='search')
                    yield Button(self.tr('刷新'), id='refresh')
                    yield Button(self.tr('外观 / 语言'), id='appearance')
                with Horizontal(id='filters'):
                    yield Select([(self.tr('所有 Agent'), 'all'), ('Codex', 'Codex'), ('Claude Code', 'Claude Code'),
                                  ('Cursor', 'Cursor'), ('Gemini CLI', 'Gemini CLI'), ('OpenCode', 'OpenCode')],
                                 value='all', allow_blank=False, id='agent')
                    yield Select([(self.tr('所有客户端'), 'all')], value='all', allow_blank=False, id='client')
                    yield Select([(self.tr('全部记录'), 'all'), (self.tr('持锁 / 进程'), 'live'), (self.tr('历史 / 未关联'), 'history')],
                                 value='all', allow_blank=False, id='state')
                yield Static(self.tr('全部工作空间'), id='scope')
                yield DataTable(id='sessions', cursor_type='row', zebra_stripes=True)
                yield Static('', id='empty')
            with Vertical(id='inspector'):
                yield Label(self.tr('会话详情'), classes='section-title')
                with VerticalScroll(id='detail-scroll'):
                    yield Static(self.tr('选择会话查看详情'), id='detail', markup=False)
                yield Button(self.tr('编辑名称 / 标签'), id='edit', variant='primary', disabled=True)
                yield Button(self.tr('复制会话 ID'), id='copy', disabled=True)
                yield Button(self.tr('关闭后端…'), id='close', variant='error', disabled=True)
                yield Static(self.tr('关闭后端影响同 PID 的全部会话。'), classes='muted', id='action-note')
        yield Static(self.tr('本地管理 · 不上传数据'), id='statusline')
        yield Footer()

    async def on_mount(self):
        table = self.query_one('#sessions', DataTable)
        for label, width in [(self.tr('状态'), 9), (self.tr('会话'), 26), ('Agent', 12), (self.tr('客户端'), 18), ('PID', 8), (self.tr('目录'), None), (self.tr('内存'), 12), (self.tr('线程'), 7), (self.tr('标签'), 22)]:
            table.add_column(label, width=width)
        self.ready = True
        await self.refresh_data()
        self.set_interval(5, self.poll_data)
        table.focus()

    def on_resize(self, event):
        self.set_class(event.size.width < 120, 'compact')
        self.set_class(event.size.width < 85, 'narrow')

    async def poll_data(self):
        if self.polling_enabled:
            await self.refresh_data()

    async def refresh_data(self):
        if self.busy or len(self.screen_stack) > 1 or self.mouse_captured is not None:
            return
        self.busy = True
        try:
            data = await asyncio.to_thread(self.collector.collect)
            if self.mouse_captured is not None or len(self.screen_stack) > 1:
                return
            fields = ('title', 'cwd', 'pid', 'start', 'source', 'status', 'lock')
            old = self.observed_sessions
            new = {r['key']: tuple(r.get(k) for k in fields) for r in data['rows']}
            added, removed = len(new.keys() - old.keys()), len(old.keys() - new.keys())
            changed = sum(old[k] != new[k] for k in old.keys() & new.keys())
            self.labels = self.store.all()
            self.rows = data['rows']
            self.observed_sessions = new
            self.refresh_revision += 1
            live = sum(bool(r.get('pid')) for r in self.rows)
            held = sum(r.get('lock') == '持有写锁' for r in self.rows)
            spaces = len({r['cwd'] for r in self.rows if r.get('cwd')})
            self.query_one('#summary', Static).update(f'  CHATDOCK     {len(self.rows)} records     {live} live     {held} locked     {spaces} workspaces' if self.language == 'en' else f'  CHATDOCK     {len(self.rows)} 记录     {live} 持锁 / 进程     {held} 会话写锁     {spaces} 工作目录')
            clients = sorted({r['source'] for r in self.rows})
            if clients != self.client_options:
                widget = self.query_one('#client', Select)
                old = widget.value
                widget.set_options([(self.tr('所有客户端'), 'all')] + [(self.tr(s), s) for s in clients])
                widget.value = old if old in clients else 'all'
                self.client_options = clients
            self.update_folders()
            self.apply_filters()
            mode = self.tr('自动 5s') if self.polling_enabled else self.tr('手动刷新')
            delta = f'+{added} / −{removed} / Δ{changed}'
            message = ' · '.join(data['warnings']) or f'{mode}  ·  {self.tr("会话变化")} {delta}  ·  {self.tr("资源按 PID")}'
            self.query_one('#statusline', Static).update(plain(message + '  |  ' + data['time'][11:19]))
        except Exception as exc:
            self.query_one('#statusline', Static).update(plain(self.tr('刷新失败，保留上次结果：') + str(exc)))
        finally:
            self.busy = False

    def update_folders(self):
        query = self.query_one('#folder-search', Input).value.casefold()
        counts = Counter(r.get('cwd', '') for r in self.rows if r.get('cwd'))
        signature = (tuple(sorted(counts.items())), query)
        if signature == self.directory_signature:
            return
        self.directory_signature = signature
        tree = self.query_one('#folders', Tree)
        tree.clear()
        tree.root.data = ''
        home = str(Path.home())
        for directory, count in sorted(counts.items()):
            if query not in directory.casefold():
                continue
            short = '~' + directory[len(home):] if directory == home or directory.startswith(home + '/') else directory
            tree.root.add_leaf(plain(f'{short}  ({count})'), data=directory)
        tree.root.expand()

    def apply_filters(self):
        if not self.ready or len(self.screen_stack) > 1:
            return
        self.filtered_rows = filtered(self.rows, self.labels,
            query=self.query_one('#search', Input).value, directory=self.directory,
            recursive=self.query_one('#recursive', Checkbox).value,
            agent=self.query_one('#agent', Select).value, client=self.query_one('#client', Select).value,
            state=self.query_one('#state', Select).value)
        table = self.query_one('#sessions', DataTable)
        old = self.selected
        scroll_x, scroll_y = table.scroll_x, table.scroll_y
        keys = [r['key'] for r in self.filtered_rows]
        rebuild = [key.value for key in table.rows] != keys
        if rebuild:
            table.clear()
        for r in self.filtered_rows:
            meta = self.labels.get(r['key'], {})
            name = r.get('title') or self.tr('(未命名会话)')
            status = Text(self.tr('● 持锁'), style=colors(self.palette_name)['success']) if r['lock'] == '持有写锁' else Text(self.tr('◉ 进程'), style=colors(self.palette_name)['warning']) if r.get('pid') else Text(self.tr('○ 历史'), style=colors(self.palette_name)['muted'])
            cells = (status, plain(name), plain(r['agent']), plain(self.tr(r['source'])),
                          str(r.get('pid') or '—'), plain(r.get('cwd') or self.tr('未知')),
                          f"{r['rss_bytes'] / 1024**2:.1f} MiB" if r.get('rss_bytes') is not None else '—',
                          str(r['threads']) if r.get('threads') is not None else '—',
                          plain(' · '.join(meta.get('tags', []))))
            if rebuild:
                table.add_row(*cells, key=r['key'])
            else:
                for column, value in zip(table.ordered_columns, cells):
                    if table.get_cell(r['key'], column.key) != value:
                        table.update_cell(r['key'], column.key, value, update_width=True)
        index = next((i for i, r in enumerate(self.filtered_rows) if r['key'] == old), 0)
        self.selected = self.filtered_rows[index]['key'] if self.filtered_rows else None
        if self.filtered_rows and (rebuild or table.cursor_row != index):
            table.move_cursor(row=index)
        self.query_one('#empty', Static).update(self.tr('没有匹配的会话。请调整目录、搜索词或筛选条件。') if not self.filtered_rows else '')
        self.query_one('#scope', Static).update(plain(f'{self.directory or self.tr("全部工作空间")}  /  {len(self.filtered_rows)}'))
        self.show_detail()
        if rebuild:
            self.call_after_refresh(table.scroll_to, x=scroll_x, y=scroll_y, animate=False)

    def current(self):
        return next((r for r in self.filtered_rows if r['key'] == self.selected), None)

    def show_detail(self):
        if not self.ready or len(self.screen_stack) > 1:
            return
        row = self.current()
        for button in ('edit', 'copy', 'close'):
            self.query_one('#' + button, Button).disabled = not row or (button == 'close' and not row.get('pid'))
        if not row:
            self.query_one('#detail', Static).update(self.tr('选择会话查看详情'))
            return
        meta = self.labels.get(row['key'], {})
        shared = sum(r.get('pid') == row.get('pid') for r in self.rows) if row.get('pid') else 0
        sections = [
            (self.tr('会话名称（Agent 原始名称）'), row.get('title') or self.tr('(未命名会话)')),
            ('Agent / ' + self.tr('客户端'), row['agent'] + ' · ' + self.tr(row['source'])),
            (self.tr('会话 ID'), row['id']), (self.tr('工作目录'), row.get('cwd') or self.tr('未知')),
            (self.tr('后台状态'), self.tr(row['status'])),
            ('PID / ' + self.tr('同 PID 记录'), f"{row.get('pid') or '—'} / {shared}"),
            (self.tr('进程资源（同 PID 共享）'), (f"{row['rss_bytes'] / 1024**2:.1f} MiB RSS" if row.get('rss_bytes') is not None else '—') + ' / ' + str(row.get('threads') if row.get('threads') is not None else '—') + ' ' + self.tr('线程')),
            (self.tr('写锁'), self.tr(row['lock'])),
            (self.tr('标签'), ' · '.join(meta.get('tags', [])) or self.tr('尚未添加')),
            (self.tr('检测依据'), self.tr(row['evidence'])),
        ]
        if meta.get('alias'):
            sections.append((self.tr('旧版管理器别名（未同步）'), meta['alias']))
        text = '\n\n'.join(label + '\n' + str(value) for label, value in sections)
        self.query_one('#detail', Static).update(Text('\n'.join(clean(line) for line in text.splitlines()), overflow='fold', no_wrap=False))

    @on(DataTable.RowHighlighted, '#sessions')
    def highlight(self, event):
        self.selected = event.row_key.value
        self.show_detail()

    @on(Tree.NodeSelected, '#folders')
    def directory_selected(self, event):
        self.query_one('#folders', Tree).tooltip = event.node.data or self.tr('全部工作空间')
        self.directory = event.node.data or ''
        self.apply_filters()

    @on(Input.Changed, '#search')
    def search_changed(self):
        self.apply_filters()

    @on(Input.Changed, '#folder-search')
    def folder_changed(self):
        if self.ready:
            self.update_folders()

    @on(Select.Changed)
    @on(Checkbox.Changed)
    def filter_changed(self, event):
        if event.control.id == 'auto-refresh':
            self.polling_enabled = event.value
            if self.ready and len(self.screen_stack) == 1:
                self.query_one('#statusline', Static).update(self.tr('自动 5s') if self.polling_enabled else self.tr('手动刷新'))
            return
        self.apply_filters()

    @on(Button.Pressed)
    async def button_pressed(self, event):
        if event.button.id == 'appearance':
            self.action_appearance()
        elif event.button.id == 'refresh':
            await self.refresh_data()
        elif event.button.id == 'edit':
            self.action_edit()
        elif event.button.id == 'copy' and self.current():
            self.copy_to_clipboard(self.current()['id'])
            self.notify(self.tr('已发送到终端剪贴板（需要终端支持 OSC 52）'))
        elif event.button.id == 'close':
            await self.prepare_close()

    async def prepare_close(self):
        row = self.current()
        if not row:
            return
        try:
            plan = await asyncio.to_thread(close_plan, row, self.collector)
        except (OSError, ValueError) as exc:
            self.notify(self.tr(str(exc)), severity='error')
            return
        async def confirmed(answer):
            if answer:
                try:
                    await asyncio.to_thread(terminate, plan, self.collector)
                    self.notify(self.tr('已发送 SIGTERM；等待下次刷新确认退出'))
                    await self.refresh_data()
                except (OSError, ValueError) as exc:
                    self.notify(self.tr(str(exc)), severity='error')
        self.push_screen(CloseScreen(plan), confirmed)

    def action_edit(self):
        row = self.current()
        if not row:
            return
        async def saved(value):
            if value is None:
                return
            name, tags = value
            # Validate tags before making the external name change.
            tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
            if len(tags) > 20 or any(len(t) > 40 for t in tags):
                self.notify(self.tr('最多 20 个标签，每个最多 40 字。'), severity='error')
                return
            self.busy = True
            renamed = False
            try:
                if name.strip() != (row.get('title') or '').strip():
                    self.notify(self.tr('正在修改 Agent 原始名称…'))
                    row['title'] = await rename(row, name, self.collector.home)
                    row['name'] = row['title']
                    renamed = True
                self.store.save(row['key'], '', tags)
                self.labels = self.store.all()
                self.apply_filters()
                self.notify(self.tr('原始会话名称已更新；APP 如未刷新，请重新打开会话。') if renamed else self.tr('分类标签已保存'))
            except Exception as exc:
                prefix = self.tr('原始名称已修改，但分类标签保存失败：') if renamed else self.tr('保存未完成：')
                self.notify(prefix + str(exc), severity='error', timeout=8)
            finally:
                self.busy = False
            await self.refresh_data()
        self.push_screen(EditScreen(row, self.labels.get(row['key'], {})), saved)

    def action_appearance(self):
        if len(self.screen_stack) != 1 or self.busy:
            return
        async def applied(value):
            if value is None:
                return
            language, palette = value
            try:
                self.store.save_preferences(language, palette)
            except Exception as exc:
                self.theme = self.palette_name
                self.notify(self.tr('设置保存失败：') + str(exc), severity='error')
                return
            saved = {id: self.query_one('#'+id, Input).value for id in ('search', 'folder-search')}
            filters = {id: self.query_one('#'+id, Select).value for id in ('agent', 'client', 'state')}
            recursive = self.query_one('#recursive', Checkbox).value
            self.ready = False
            self.language, self.palette_name = language, palette
            self.theme = palette
            self.localize_bindings()
            self.directory_signature = self.client_options = None
            await self.recompose()
            table = self.query_one('#sessions', DataTable)
            for label, width in [('状态', 9), ('会话', 26), ('Agent', 12), ('客户端', 18), ('PID', 8), ('目录', None), ('内存', 12), ('线程', 7), ('标签', 22)]:
                table.add_column(self.tr(label), width=width)
            for id, value in saved.items():
                self.query_one('#'+id, Input).value = value
            self.query_one('#recursive', Checkbox).value = recursive
            self.ready = True
            await self.refresh_data()
            for id, value in filters.items():
                self.query_one('#'+id, Select).value = value
            self.apply_filters()
            table.focus()
            self.notify(self.tr('外观设置已保存'))
        self.push_screen(AppearanceScreen(), applied)

    def action_quit_dashboard(self):
        if not isinstance(self.focused, Input) and len(self.screen_stack) == 1:
            self.exit()

    def action_help(self):
        if len(self.screen_stack) == 1:
            self.push_screen(HelpScreen())

    def action_focus_sessions(self):
        if len(self.screen_stack) == 1:
            self.query_one('#sessions', DataTable).focus()

    async def action_reload(self):
        await self.refresh_data()

    def action_search(self):
        self.query_one('#search', Input).focus()


def main():
    import sys
    from .core import main as run
    if '--tui' not in sys.argv:
        sys.argv.insert(1, '--tui')
    return run()
