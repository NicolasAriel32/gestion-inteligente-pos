"""ADR-019: el POS respeta el bloqueo de mantenimiento del actualizador externo."""
import json

from app import runtime
from app.update_gate import ENV_TOKEN, maintenance_block


def write_journal(tmp_path, phase, token='d' * 64):
    journal = tmp_path / 'GestionInteligentePOS' / 'updates' / 'update-journal.json'
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps({'phase': phase, 'handoff_token': token}), encoding='utf-8')
    return journal


def test_sin_journal_no_bloquea(tmp_path):
    assert maintenance_block(tmp_path / 'GestionInteligentePOS' / 'data' / 'pos.db') is None


def test_main_no_arranca_ni_mantiene_con_actualizacion_pendiente(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv(ENV_TOKEN, raising=False)
    write_journal(tmp_path, 'installing')
    for argv in (['--no-browser'], ['--prepare-stdin'], ['--recover-restore'], ['--renew-setup']):
        assert runtime.main(argv) == 3
        assert 'actualización del POS' in capsys.readouterr().out
    assert runtime.main(['--version']) == 0


def test_traspaso_solo_con_token_y_fase_correctos(tmp_path, monkeypatch):
    database = tmp_path / 'GestionInteligentePOS' / 'data' / 'pos.db'
    journal = write_journal(tmp_path, 'migrating')
    monkeypatch.setenv(ENV_TOKEN, 'd' * 64)
    assert maintenance_block(database) is None
    write_journal(tmp_path, 'installing')
    assert maintenance_block(database) is not None
    write_journal(tmp_path, 'checking', token='corto')
    monkeypatch.setenv(ENV_TOKEN, 'corto')
    assert maintenance_block(database) is not None
    journal.write_text('{dañado', encoding='utf-8')
    assert maintenance_block(database) is not None
