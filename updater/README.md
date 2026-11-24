# Actualizador firmado — Gestión Inteligente POS

Programa separado que el técnico usa en la PC del cliente para instalar una versión nueva
del POS. Se instala aparte (`%LOCALAPPDATA%\Programs\GestionInteligentePOS-Actualizador`)
porque tiene que poder reemplazar la carpeta del POS. Decisión: **ADR-019**.
Correcciones de la segunda iteración: [docs/UPDATER_REVIEW_2.md](../docs/UPDATER_REVIEW_2.md).

## Seguridad en una línea

**Clave del técnico + contraseña del dueño** abren el botón (y el motor las vuelve a validar
justo antes de actuar); **la firma Ed25519** decide qué se puede instalar. Una clave robada
no sirve sin un paquete firmado por vos; un paquete copiado o modificado no pasa la
verificación aunque tengan las dos claves.

Límite honesto: quien controla la cuenta de Windows puede reemplazar el propio actualizador
o el POS directamente (auditoría H-01). El actualizador evita paquetes falsos, errores de
procedimiento y estados a medias; no reemplaza separar las cuentas de Windows.

## Flujo

| Paso | Qué hace | Si falla o se corta |
|---|---|---|
| 1. Consultar | Baja `latest.json` + `.sig`; verifica firma y `key_id` | Usar archivo `.gipupdate` |
| 2. Descargar | A `updates\tmp`; SHA-256 contra el índice firmado | Se borra la descarga |
| 3. Verificar | Firma, exactamente 3 archivos sin duplicados, hash y tamaño, versión posterior | Nada cambia |
| — | Revalida técnico + dueño (contadores separados) | Nada cambia |
| 4. Cerrar el POS | Cierre ordenado por API y **toma el bloqueo de instancia del POS** | Si no lo obtiene: nada cambia |
| 5. Respaldo | Journal `snapshotting`; copia programa + `pos.db/-wal/-shm` a `updates\rollback\<id>`, hashes, `integrity_check` | Corte: la recuperación descarta la copia parcial |
| 6. Instalar y migrar | Revalida el hash con el instalador bloqueado contra escritura; Inno silencioso; `--prepare-stdin` con token de traspaso | **Restaura** programa y datos |
| 7. Comprobar | `--version`, arranque con token, `/api/health`, login ADMIN, cierre | **Restaura** programa y datos |
| Confirmar | Fase `committing`, `state.json` atómico, borra journal y copias **anteriores** | Corte: la recuperación completa la confirmación |

### Bloqueo de mantenimiento y recuperación

Mientras exista `%LOCALAPPDATA%\GestionInteligentePOS\updates\update-journal.json`, el POS
**no abre** y muestra: "Hay una actualización del POS en curso o interrumpida…". Es una
protección de integridad, no de versión (ADR-019). Solo el proceso que lanza el
actualizador con el token de esa actualización pasa, y solo para migrar y comprobar.

Si hubo un corte de luz, un reinicio o se mató el proceso: abrí el actualizador. Arranca en
**modo recuperación** y solo ofrece **Recuperar**, que acepta la **clave del técnico o la
contraseña del dueño** (validada contra la copia verificada, porque la base actual puede
estar a medio migrar). La recuperación:

- antes del respaldo completo: descarta la copia parcial (programa y datos no se tocaron);
- en instalación, migración, comprobación o restauración: verifica la copia y restaura
  programa y datos; se puede repetir si se vuelve a cortar;
- en la confirmación: completa la versión nueva.

Un journal dañado bloquea igual y pide revisión manual del técnico (no se adivina).
La ventana no se puede cerrar mientras actualiza o recupera.

Archivos: `updates\actualizaciones.log` (sin secretos), `updates\state.json`,
`updates\intentos-tecnico.json`, `updates\intentos-dueno.json`, `updates\rollback\<id>`.

## Claves de firma

- **Principal** (`gip-firma\principal.pem`): la usás para firmar.
- **Respaldo** (`respaldo.pem` en un pendrive guardado offline, otra frase): no se usa
  salvo emergencia. Su clave pública va desde el día uno en todos los actualizadores.

| Situación | Qué hacer |
|---|---|
| Perdiste la principal | Firmá con la de respaldo (`--clave E:\gip-firma\respaldo.pem`); los actualizadores ya la aceptan. Creá una nueva principal y, en tu próxima visita, reinstalá el actualizador con `--publica nueva.pub --publica respaldo.pub`. |
| Te robaron la principal | Igual que arriba **y** reinstalá cuanto antes el actualizador en cada cliente sin la clave robada. Hasta entonces, quien la tenga puede firmar paquetes que esos actualizadores aceptan (aún necesita tu clave de técnico y la del dueño). |
| Rotación planificada | Agregá la nueva al anillo, reinstalá el actualizador en cada visita y recién después dejá de usar la vieja. |

El actualizador no se actualiza solo (ADR-015): cambiar el anillo implica reinstalarlo en
cada cliente. No hay revocación remota a propósito: el sistema funciona offline.

## Una sola vez, en TU PC

```powershell
cd updater
python -m pip install -r requirements.txt
python firmar.py claves --nombre principal
python firmar.py claves --nombre respaldo --salida E:\gip-firma\respaldo.pem
python firmar.py configurar --publica $HOME\gip-firma\principal.pub --publica E:\gip-firma\respaldo.pub
git add gip_updater/trust.json; git commit -m "Configurar actualizador"; git push
```

`trust.json` contiene claves públicas (no son secretas) y el hash Argon2id de tu clave de
técnico (16+ caracteres: no es práctico romperlo, pero conviene repo privado). Con
`trust.json` subido, GitHub Actions arma `ActualizadorPOS-1.0.0-setup.exe`.

## Cada versión

1. Subí la versión en `backend/pyproject.toml` y `backend/app/main.py`.
2. Bajá el instalador del artefacto **POS-Windows-main**.
3. `python firmar.py empaquetar GestionInteligentePOS-0.6.0-setup.exe 0.6.0 --notas "…" [--url https://…/x.gipupdate]`
4. Pendrive: llevá el `.gipupdate`. Internet: Release con `.gipupdate`, `latest.json`, `latest.json.sig`.

## Pruebas

```bash
cd updater
PYTHONPATH=.:../backend python -m pytest tests -q        # motor, paquetes, claves, POS real
PYTHONPATH=. xvfb-run -a python -m pytest tests/test_gui.py   # ventana (Linux sin pantalla)
```

CI (`.github/workflows/windows-candidate.yml`): job `updater` corre las pruebas en Windows;
job `updater-e2e` instala **main** con ventas reales y actualiza con Inno Setup a una
versión de prueba 0.6.0 con migración 0007 (`packaging/e2e/`, solo CI), fuerza una falla
con restauración y mata el actualizador a mitad de la instalación para probar la
recuperación. Claves y contraseñas de prueba: descartables, generadas en cada corrida.
