# Construir desde raíz: python -m PyInstaller --clean --noconfirm packaging/updater.spec
# Requiere updater/gip_updater/trust.json (python updater/firmar.py configurar).
from pathlib import Path

root = Path(SPECPATH).parent
trust = root / 'updater/gip_updater/trust.json'
if not trust.is_file():
    raise SystemExit('Falta updater/gip_updater/trust.json: ejecutá python updater/firmar.py configurar')
analysis = Analysis(
    [str(root / 'updater/gip_updater/__main__.py')],
    pathex=[str(root / 'updater')],
    datas=[(str(trust), 'gip_updater')],
    hiddenimports=['argon2.low_level', 'gip_updater.gui'],
    excludes=['pytest', 'app'], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, analysis.binaries, analysis.datas, name='ActualizadorPOS',
          debug=False, strip=False, upx=False, console=False)
