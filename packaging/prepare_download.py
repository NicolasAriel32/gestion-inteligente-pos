"""Publicar solo después del smoke, con procedencia y archivos accesibles en raíz."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest_path = root / 'dist/GestionInteligentePOS/build-info.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
if manifest['source_commit'] != commit:
    raise SystemExit('El build no corresponde al commit actual')
if os.getenv('GITHUB_REF') and manifest['source_ref'] != os.environ['GITHUB_REF']:
    raise SystemExit('El build no corresponde a la referencia del workflow')
smoke_path = root / 'dist/windows-smoke.json'
smoke = json.loads(smoke_path.read_text(encoding='utf-8'))
required = {'install_per_user', 'prepare_explicit_without_python_node_on_PATH',
            'start_packaged', 'second_instance_excluded',
            'packaged_crypto_encrypted_key_and_offline_fiscal_status',
            'import_sales_void_backup_restore_reports_and_reauthentication',
            'controlled_shutdown', 'reinstall_preserves_database_backups_and_config',
            'uninstall_preserves_database_backups_and_config'}
if not required.issubset(smoke['steps_passed']):
    raise SystemExit('Faltan comprobaciones del ejecutable instalado')
installers = list((root / 'dist/installer').glob('*-setup.exe'))
if len(installers) != 1:
    raise SystemExit('Se esperaba exactamente un instalador verificado')
destination = root / 'dist/download'
if destination.exists():
    shutil.rmtree(destination)
destination.mkdir()
for source, name in [(installers[0], installers[0].name),
                     (root / 'packaging/PRIMER_INICIO.txt', 'LEEME.txt'),
                     (root / 'packaging/ARCA_HOMOLOGACION.txt', 'ARCA_HOMOLOGACION.txt'),
                     (manifest_path, 'build-info.json'), (smoke_path, 'windows-smoke.json')]:
    shutil.copyfile(source, destination / name)
checksums = '\n'.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}'
                      for path in sorted(destination.iterdir())) + '\n'
(destination / 'SHA256SUMS.txt').write_text(checksums, encoding='ascii')
print('Descarga preparada y verificada para', manifest['source_ref'], commit)
