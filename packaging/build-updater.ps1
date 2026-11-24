$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path 'updater/gip_updater/trust.json')) { throw 'Falta trust.json: python updater/firmar.py configurar' }
python -m pip install -r updater/requirements.txt -r updater/requirements-build.txt
if ($LASTEXITCODE) { throw 'Falló instalación de dependencias del actualizador' }
$env:PYTHONPATH = 'updater'
python -m pytest updater/tests -q
if ($LASTEXITCODE) { throw 'Fallaron las pruebas del actualizador' }
python -m PyInstaller --clean --noconfirm --distpath dist --workpath build/updater packaging/updater.spec
if ($LASTEXITCODE) { throw 'Falló PyInstaller del actualizador' }
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) { $iscc = Get-Item "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue }
if (-not $iscc) { throw 'Instalá Inno Setup 6.x' }
$isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
& $isccPath packaging/updater.iss
if ($LASTEXITCODE) { throw 'Falló Inno Setup del actualizador' }
Get-ChildItem dist/installer/ActualizadorPOS-*.exe | Get-FileHash -Algorithm SHA256 | Format-List
