"""Classic palette adaptations for ChatDock, not official theme ports."""
# Background, panel, raised surface, border, text, muted, accent, selection, success, warning, error.
PALETTES = {
    'vscode': ('VS Code Dark Modern', '#1f1f1f', '#181818', '#252526', '#3c3c3c', '#cccccc', '#a3a3a3', '#0078d4', '#264f78', '#89d185', '#cca700', '#f48771'),
    'tokyo-night': ('Tokyo Night', '#1a1b26', '#16161e', '#24283b', '#3b4261', '#c0caf5', '#9aa5ce', '#7aa2f7', '#283457', '#9ece6a', '#e0af68', '#f7768e'),
    'catppuccin': ('Catppuccin Mocha', '#1e1e2e', '#181825', '#313244', '#45475a', '#cdd6f4', '#a6adc8', '#cba6f7', '#45405c', '#a6e3a1', '#f9e2af', '#f38ba8'),
    'dracula': ('Dracula', '#282a36', '#21222c', '#343746', '#44475a', '#f8f8f2', '#a5abc6', '#bd93f9', '#44475a', '#50fa7b', '#f1fa8c', '#ff5555'),
    'nord': ('Nord', '#2e3440', '#292e39', '#3b4252', '#4c566a', '#eceff4', '#b6c0d2', '#88c0d0', '#434c5e', '#a3be8c', '#ebcb8b', '#bf616a'),
    'github-light': ('GitHub Light', '#ffffff', '#f6f8fa', '#eaeef2', '#d0d7de', '#24292f', '#57606a', '#0969da', '#ddf4ff', '#1a7f37', '#7d4e00', '#cf222e'),
}


def colors(key):
    values = PALETTES[key]
    result = dict(zip(('name', 'bg', 'panel', 'surface', 'border', 'text', 'muted', 'accent', 'selection', 'success', 'warning', 'error'), values))
    result['on-accent'] = '#ffffff' if key in ('vscode', 'github-light') else result['bg']
    return result


def register_themes(app):
    from textual.theme import Theme
    for key in PALETTES:
        c = colors(key)
        app.register_theme(Theme(name=key, primary=c['accent'], secondary=c['accent'],
            accent=c['accent'], foreground=c['text'], background=c['bg'], surface=c['surface'],
            panel=c['panel'], success=c['success'], warning=c['warning'], error=c['error'],
            dark=key != 'github-light', variables={'deck-'+k: v for k,v in c.items() if k != 'name'}))
