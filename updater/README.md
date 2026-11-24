# Actualizador firmado — Gestión Inteligente POS

Programa separado que el técnico usa en la PC del cliente para instalar una versión nueva
del POS. Se instala aparte (`%LOCALAPPDATA%\Programs\GestionInteligentePOS-Actualizador`)
porque tiene que poder reemplazar la carpeta del POS. Decisión: ADR-016.

## Seguridad en una línea

**Clave del técnico + contraseña del dueño** abren el botón; **la firma Ed25519** decide qué
se puede instalar. Una clave robada no sirve sin un paquete firmado por vos, y un paquete
copiado o modificado no pasa la verificación aunque tengan las dos claves.

Límite honesto: quien controla la cuenta de Windows puede reemplazar el propio
actualizador o el POS directamente (auditoría H-01). El actualizador evita paquetes
falsos y errores de procedimiento; no reemplaza separar las cuentas de Windows.

## Flujo (lo que hace al apretar Actualizar)

| Paso | Qué hace | Si falla |
|---|---|---|
| 1. Consultar versiones | Baja `latest.json` y `latest.json.sig`; verifica la firma | Usar un archivo `.gipupdate` |
| 2. Descargar | Baja el paquete a `updates\tmp`; compara el SHA-256 con el índice firmado | Se borra la descarga |
| 3. Verificar | Firma del manifiesto, archivos exactos, hash y tamaño del instalador, versión posterior a la instalada y a la más alta instalada antes | No se toca nada |
| 4. Cerrar el POS | Si está abierto: login del dueño por la API local y cierre ordenado | No se toca nada |
| 5. Respaldo | Copia `pos.db`, `-wal`, `-shm` (con el POS cerrado = consistente) y la carpeta del programa a `updates\rollback` | No se toca nada |
| 6. Instalar y migrar | Instalador silencioso y luego `GestionInteligentePOS.exe --prepare-stdin` (contraseña por entrada estándar, nunca en argumentos; hace además su respaldo `pre_upgrade`) | **Restaura** programa y datos |
| 7. Comprobar | `--version` igual a la firmada, arranque, `/api/health`, login del dueño como ADMIN, cierre | **Restaura** programa y datos |

Registro sin secretos: `%LOCALAPPDATA%\GestionInteligentePOS\updates\actualizaciones.log`.
Después de 5 claves incorrectas el actualizador se bloquea 15 minutos.

## Una sola vez, en TU PC

```powershell
cd updater
python -m pip install -r requirements.txt
python firmar.py claves        # crea C:\Users\<vos>\gip-firma\clave-privada.pem (cifrada)
python firmar.py configurar    # graba clave pública + clave de técnico en gip_updater\trust.json
git add gip_updater/trust.json; git commit -m "Configurar actualizador"; git push
```

- **Guardá la clave privada fuera del repo y con copia en un pendrive.** Si la perdés,
  los actualizadores ya instalados no aceptarán nuevas versiones; si te la roban, pueden
  firmar actualizaciones falsas.
- `trust.json` contiene la clave pública (no es secreta) y el hash Argon2id de tu clave de
  técnico. Con 16 caracteres o más no es práctico romperlo, pero conviene que el repo sea privado.

Con `trust.json` subido, GitHub Actions arma `ActualizadorPOS-1.0.0-setup.exe`
(artefacto **Actualizador-POS**). Lo instalás una vez en cada cliente.

## Cada vez que publicás una versión

1. Subí la versión en `backend/pyproject.toml` y en `backend/app/main.py` (`--version` la toma de ahí).
2. Bajá el instalador del POS del artefacto **POS-Windows-main**.
3. Firmalo:

```powershell
python firmar.py empaquetar GestionInteligentePOS-0.6.0-setup.exe 0.6.0 --notas "Cierre de caja" `
  --url https://github.com/NicolasAriel32/gestion-inteligente-pos/releases/download/v0.6.0/GestionInteligentePOS-0.6.0.gipupdate
```

4. **Por pendrive:** llevá `GestionInteligentePOS-0.6.0.gipupdate`.
   **Por internet:** creá el Release `v0.6.0` y subí el `.gipupdate`, `latest.json` y `latest.json.sig`.

## En la PC del cliente

Abrí **Actualizador del POS (técnico)** → clave de técnico + contraseña del dueño →
**Desbloquear** → **Elegir archivo** o **Buscar en internet** → **Actualizar**.

## Pruebas

```bash
cd updater
PYTHONPATH=.:../backend python -m pytest tests -q   # incluye integración con el POS real si está instalado
```
