"""Shared terminal and in-app help."""
KEYBOARD_HELP = '''日常操作
  q / Ctrl+Q      退出管理器，Agent 任务继续运行
  ? / F1          打开帮助
  Esc             关闭弹窗；搜索框中按 Esc 返回会话列表
  Tab / Shift+Tab 切换控件
  ↑ ↓ / Enter     选择会话、目录或操作按钮
  ← →             表格获得焦点时横向滚动
  Ctrl+F          搜索名称、ID、路径和标签
  Ctrl+R          立即刷新（默认每 5 秒刷新）
  Ctrl+E          编辑会话名称与分类标签

鼠标操作
  点击左侧目录筛选，点击“全部工作空间”清除目录限制。
  点击会话行查看详情，使用右侧按钮编辑或关闭后端。
  下拉框按 Agent、客户端及状态筛选；滚轮滚动列表。
  横向滑动或 Shift+滚轮查看右侧列，也可点击表格下方 ← →。
  若终端不转发横向手势，请使用方向键或左右按钮。

输入时
  在输入框内，q 和 ? 是普通字符，不会退出或打开帮助。
  编辑、确认弹窗中按 Esc 取消；帮助页按 q / Esc 返回。

状态和操作
  持锁：进程占用会话写入权，不代表正在生成。
  进程：检测到后端，但不一定能关联具体会话。
  历史：本地记录，无写锁不等于异常断连。
  Codex 名称修改会同步原生名称；分类标签仅在管理器保存。
  关闭后端影响同 PID 的全部任务；退出管理器不关闭 Agent。'''


def examples(program, language='zh'):
    if language == 'en':
        return f"""Start: {program} --tui  |  {program} --web
No options: show a status snapshot.
Install once: ./chatdock --install-command (then use chatdock anywhere).
"""
    return f"""启动：{program} --tui  |  {program} --web
不加参数：查看状态摘要。
首次安装：./chatdock --install-command，之后可在任意目录使用 chatdock。
"""
