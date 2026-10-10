"""Scoped-in-process compatibility for Textual 1.x horizontal SGR wheel events.

Textual 1.x maps both SGR 64/65 and 66/67 to vertical wheel events.
Translate horizontal events to its existing Shift+wheel horizontal path.
Never edits installed library files; non-horizontal events pass through unchanged.
"""
from functools import wraps
import re

_SGR = re.compile(r'\x1b\[<(\d+);(\d+);(\d+)([Mm])\Z')


def install_horizontal_wheel_support():
    from textual._xterm_parser import XTermParser
    from textual import events
    original = XTermParser.parse_mouse_code
    if getattr(original, '_chatdock_horizontal_wheel', False):
        return
    # Only adapt the known older behavior. Leave native horizontal support alone.
    probe = XTermParser().parse_mouse_code('\x1b[<67;1;1M')
    if not isinstance(probe, events.MouseScrollDown) or probe.shift:
        return

    @wraps(original)
    def parse_mouse_code(self, code):
        match = _SGR.fullmatch(code)
        if match:
            buttons = int(match[1])
            if buttons & 64 and buttons & 2 and not buttons & 128:
                # 66 -> 68 (Shift+up), 67 -> 69 (Shift+down).
                # Preserve Alt/Ctrl/Shift and pointer coordinates.
                buttons = (buttons & ~2) | 4
                code = f'\x1b[<{buttons};{match[2]};{match[3]}{match[4]}'
        return original(self, code)

    parse_mouse_code._chatdock_horizontal_wheel = True
    XTermParser.parse_mouse_code = parse_mouse_code
