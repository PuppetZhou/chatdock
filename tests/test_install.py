from pathlib import Path
import pytest
from agentdeck.install import install_command


def test_install_is_idempotent_and_never_overwrites(tmp_path, monkeypatch, capsys):
    source=tmp_path/'repo/chatdock'
    source.parent.mkdir()
    source.write_text('launcher')
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('PATH', '/usr/bin')
    monkeypatch.setenv('SHELL', '/bin/bash')
    monkeypatch.setattr('sys.argv', [str(source)])
    install_command()
    install_command()
    target=tmp_path/'.local/bin/chatdock'
    assert target.is_symlink() and target.resolve()==source
    assert 'export PATH=' in capsys.readouterr().out
    target.unlink()
    target.write_text('existing command')
    with pytest.raises(ValueError):
        install_command()
    assert target.read_text() == 'existing command'
