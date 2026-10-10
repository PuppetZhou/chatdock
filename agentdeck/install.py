"""Install a launcher without modifying shell startup files."""
import os
from pathlib import Path
import shlex
import sys


def install_command():
    source = Path(sys.argv[0]).resolve()
    target = Path.home() / '.local/bin/chatdock'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() and target.resolve() == source:
        pass
    elif target.exists() or target.is_symlink():
        raise ValueError(f'{target} 已存在，未覆盖。')
    elif source == target:
        pass
    else:
        target.symlink_to(source)
    print(f'命令已安装 / Command installed: {target}')
    if str(target.parent) not in os.environ.get('PATH', '').split(os.pathsep):
        shell = Path(os.environ.get('SHELL', '/bin/bash')).name
        if shell == 'fish':
            print('在终端执行 / Run in your shell:\n  fish_add_path ~/.local/bin')
        else:
            rc = '~/.zshrc' if shell == 'zsh' else '~/.bashrc'
            print(f'将下面一行加入 {rc}，并在当前终端执行：\n  export PATH="$HOME/.local/bin:$PATH"')
    print('启动 / Start: chatdock --tui  |  chatdock --web')
