"""UI translations. Agent titles, tags and paths are never translated."""
EN = {
'自动刷新':'Auto refresh', '自动 5s':'Auto 5s', '手动刷新':'Manual refresh', '会话变化':'Changes', '资源按 PID':'Resources per PID', '本地会话 · 按目录筛选':'Local · Filter by folder', '关闭后端影响同 PID 的全部会话。':'Stopping affects all sessions on this PID.',
'内存': 'Memory', '线程': 'Threads', '进程资源（同 PID 共享）': 'Process resources (shared PID)', '每 5 秒刷新 · 资源按 PID 统计': 'Refresh: 5s · Resources per PID',
'会话与工作空间':'Sessions & workspaces', '使用帮助':'Help & shortcuts', '返回会话列表  Esc / q':'Back to sessions  Esc / q',
'编辑会话':'Edit session', '会话名称 · Agent 原始名称':'Session name · native Agent name',
'会话名称直接修改 Codex 原始名称；APP 可能需要重新打开会话才能刷新。分类标签仅在本管理器保存。':'Changes the native Codex name. Reopen the chat in the app if needed. Tags are local to ChatDock.',
'当前 Agent 尚不支持原生重命名，名称只读；分类标签可编辑。':'Native renaming is not supported for this Agent yet. The name is read-only; tags are editable.',
'分类标签 · 本地保存，逗号分隔':'Tags · local, comma-separated', '手稿, 待跟进, 实验':'paper, follow-up, experiment',
'取消':'Cancel', '保存':'Save', '关闭整个后端进程':'Stop the entire backend',
'输入 PID 确认；聊天记录不会被删除':'Type the PID to confirm. Chat history will not be deleted.',
'终止后端':'Stop backend', '(无标题)':'(Untitled)', '(未命名会话)':'(Unnamed session)',
'退出':'Quit', '帮助':'Help', '返回列表':'Sessions', '刷新':'Refresh', '搜索':'Search', '名称 / 标签':'Name / tags',
'正在读取本地会话…':'Loading local sessions…', '工作空间':'WORKSPACES', '筛选目录…':'Filter directories…',
'包含子目录':'Include subfolders', '全部工作空间':'All workspaces',
'● 持锁 ≠ 正在生成\n○ 历史 ≠ 异常断连\n前端连接状态可能未知':'● Locked ≠ generating\n○ History ≠ disconnected\nClient connection may be unknown',
'搜索会话、ID、目录、标签  Ctrl+F':'Search name, ID, path, tags  Ctrl+F',
'所有 Agent':'All Agents', '所有客户端':'All clients', '全部记录':'All records', '持锁 / 进程':'Locked / processes',
'历史 / 未关联':'History / unlinked', '会话详情':'SESSION DETAILS', '选择会话查看详情':'Select a session to inspect',
'编辑名称 / 标签':'Edit name / tags', '复制会话 ID':'Copy session ID', '分离连接 · 不支持':'Detach · unavailable',
'关闭后端…':'Stop backend…',
'外部会话不由本工具托管，不能单独分离连接。关闭后端会影响同 PID 的所有会话。':'External sessions cannot be detached here. Stopping a backend affects every session sharing its PID.',
'本地管理 · 不上传数据':'Local session management', '状态':'Status', '会话':'Session', '客户端':'Client', '目录':'Directory', '标签':'Tags',
'每 5 秒刷新 · 前端连接未知不等于断连 · 会话名称来自 Agent；分类标签保存在管理器':'Refresh: 5s · Unknown does not mean disconnected · Native names / local tags',
'刷新失败，保留上次结果：':'Refresh failed; showing the last snapshot: ', '● 持锁':'● Locked', '◉ 进程':'◉ Process', '○ 历史':'○ History',
'未知':'Unknown', '没有匹配的会话。请调整目录、搜索词或筛选条件。':'No matching sessions. Adjust the directory, search or filters.',
'尚未添加':'No tags yet', '已发送到终端剪贴板（需要终端支持 OSC 52）':'Sent to terminal clipboard (requires OSC 52 support)',
'已发送 SIGTERM；等待下次刷新确认退出':'SIGTERM sent; the next refresh will confirm the process state',
'最多 20 个标签，每个最多 40 字。':'Up to 20 tags, 40 characters each.', '正在修改 Agent 原始名称…':'Updating the native Agent name…',
'原始会话名称已更新；APP 如未刷新，请重新打开会话。':'Native name updated. Reopen the chat if the app has not refreshed.',
'分类标签已保存':'Tags saved', '原始名称已修改，但分类标签保存失败：':'Native name updated, but saving tags failed: ', '保存未完成：':'Save incomplete: ',
'会话名称（Agent 原始名称）':'Session name (native)', '会话 ID':'Session ID', '工作目录':'Working directory', '后台状态':'Backend status',
'写锁':'Write lock', '同 PID 记录':'Records sharing PID', '检测依据':'Detection evidence', '旧版管理器别名（未同步）':'Legacy local alias (not synced)',
'持有写锁':'Write lock held', '无写锁':'No write lock', '进程存活':'Process alive', '未关联进程':'Process not linked',
'VS Code 插件':'VS Code extension', 'Cursor 插件':'Cursor extension', 'Codex 服务代理':'Codex proxy', 'Desktop 后端':'Desktop backend',
'独立 app-server':'Standalone app-server', '终端（VS Code）':'VS Code terminal', '终端 CLI':'Terminal CLI', 'CLI/后台进程':'CLI / background',
'历史记录':'History', '后端存活；前端未知':'Backend alive; frontend unknown', '演示数据 · 不对应真实进程':'Demo data · no real process', '—':'—', '僵尸进程':'Zombie process', '后台存活；客户端未知':'Background alive; client unknown',
'存活；父进程不可见':'Alive; parent not visible', 'TTY 存在；用户连接未知':'TTY present; user connection unknown',
'后端/父进程存活；前端未知':'Backend / parent alive; frontend unknown', '进程不可见/采样期间退出':'Process not visible / exited during sampling',
'无写锁（不代表异常断连）':'No write lock (not evidence of disconnection)', '运行关联未知':'Runtime association unknown',
'采样期间进程退出':'Process exited during sampling', '仅检测到进程，未确认对应的会话 ID。':'Process detected; session ID mapping is not confirmed.',
'Claude 本地记录；没有可靠的会话 → PID 映射，不按目录猜测。':'Local Claude record; no reliable session-to-PID mapping. Directories are not used to guess ownership.',
'系统 FLOCK 写锁 + Codex 本地数据库。':'System FLOCK write lock + local Codex database.',
'本地历史记录；无写锁不能证明异常断连。':'Local history; no write lock does not prove a disconnection.',
'外观 / 语言':'Appearance', '外观':'Appearance', '语言':'Language', '配色主题':'Color theme', '应用':'Apply',
'选择主题可实时预览；取消恢复原配色。':'Preview a theme instantly. Cancel restores the previous theme.',
'外观设置已保存':'Appearance settings saved', '设置保存失败：':'Could not save settings: ',
}


def translate(text, language='zh'):
    return EN.get(text, text) if language == 'en' else text


HELP_EN = '''NAVIGATION
  q / Ctrl+Q      Quit ChatDock; keep Agents running
  ? / F1          Open help
  F2              Appearance and language
  Esc             Cancel a dialog / return to session list
  Tab / Shift+Tab Move between controls
  Up Down / Enter Select sessions, directories or buttons
  Left / Right    Scroll horizontally when the table is focused
  Ctrl+F          Search names, IDs, paths and tags
  Ctrl+R          Refresh now (auto-refresh every 5 seconds)
  Ctrl+E          Edit session name and tags

MOUSE
  Click a workspace to filter; select All workspaces to reset.
  Click a session to inspect it. Use the right-side action buttons.
  Filter by Agent, client or state. Scroll tables with the wheel.
  Drag the bottom or right scrollbar; wheel and trackpad also work.
  Auto-refresh checks every 5s; toggle it at the top or click Refresh.
  Refresh pauses during scrollbar drags and while dialogs are open.

WHILE TYPING
  q and ? are ordinary characters inside inputs.
  Esc cancels dialogs. q / Esc closes this help page.

STATUS & ACTIONS
  Locked: a backend holds the write lock, not necessarily generating.
  Process: a program was detected, without a confirmed session link.
  History: no lock does not imply disconnection.
  Codex names are native; tags are local to ChatDock.
  Stopping a backend affects all its sessions. Quitting ChatDock does not.'''
