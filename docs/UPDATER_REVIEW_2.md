# Actualizador firmado — segunda iteración (ADR-019)

Base: auditoría independiente (ChatGPT) sobre el commit `5a608c1` del PR #10 y hallazgos
de Codex en el mismo PR (2 × P1, 1 × P2). Rama: `feat/actualizador-firmado`. Sin merge a
`main` hasta aprobación explícita del propietario. Claves y contraseñas de las pruebas:
descartables, generadas en cada corrida; no se generó ni publicó ninguna clave real.

## Correcciones

| # | Hallazgo | Corrección | Archivos | Pruebas |
|---|---|---|---|---|
| 1 | Sin journal: un corte dejaba programa/base a medias y la próxima corrida borraba la única copia | Journal atómico `updates/update-journal.json` con fases `snapshotting → snapshot_ok → installing → migrating → checking → committing` (+ `restoring`). Al reabrir, el actualizador entra en **modo recuperación** y no permite otra cosa. Recuperación por fase: descarta copia parcial / restaura / completa la confirmación | `engine.py`, `storage.py`, `gui.py` | `test_corte_de_luz_*` (instalación, migración, comprobación), `test_corte_durante_el_respaldo_no_toca_nada`, `test_corte_al_confirmar_completa_la_version_nueva`; E2E: mata el árbol del actualizador durante Inno Setup |
| 2 | Sin exclusión: "/api/health no responde" no prueba que el POS esté cerrado (Codex P1) | Mutex propio `Local\GestionInteligentePOS-Actualizador`. El actualizador **toma el bloqueo de instancia del POS** (mismo mutex/flock) durante respaldo y restauración. El POS respeta el journal: no arranca ni hace mantenimiento (salida 3), salvo el traspaso con token aleatorio de 256 bits en migración y comprobación | `locks.py`, `engine.py`, `backend/app/update_gate.py`, `backend/app/runtime.py` | `test_un_solo_actualizador_a_la_vez`, `test_pos_que_no_suelta_su_bloqueo_frena_sin_cambios`, `test_bloqueo_de_instancia_se_mantiene_durante_el_respaldo`, `test_gate_*`, `backend/tests/test_update_gate.py`, `test_pos_real_respeta_el_bloqueo_de_mantenimiento`; E2E: POS 0.6.0 sale con código 3 tras el corte |
| 3 | Respaldo no verificable; `rmtree` de la copia previa antes de crear la nueva | Copia nueva por actualización (`rollback/<id>`), `snapshot.json` con SHA-256 de cada archivo, comparación contra el original, `integrity_check` de SQLite sobre copia descartable. Copias anteriores se borran **solo después** de confirmar. Restauración: verifica la copia antes de tocar nada; staging + renombres; borra WAL/SHM ajenos antes de reponer la base; verifica hashes al final; repetible | `engine.py`, `storage.py` | `test_la_copia_anterior_solo_se_borra_tras_el_exito`, `test_error_restaura_programa_y_datos` (3 fallas), `test_recuperacion_idempotente_tras_corte_durante_la_restauracion` (corte con la carpeta apartada), `test_copia_danada_no_se_restaura_y_no_toca_nada`; E2E falla controlada |
| 4 | `state.json` no atómico y errores ignorados | Escritura temporal + `fsync` + `os.replace` (+ `fsync` de directorio en POSIX). Lectura estricta: campos y versiones válidos o se frena con mensaje | `storage.py`, `engine.py` | `test_state_danado_frena_y_escritura_atomica`, `test_journal_danado_exige_revision` |
| 5 | Contador compartido: técnico correcto reiniciaba los fallos del dueño (Codex P2) | Dos contadores (`intentos-tecnico.json`, `intentos-dueno.json`), atómicos; archivo dañado = bloqueado | `auth.py`, `engine.py` | `test_contadores_separados_tecnico_correcto_no_reinicia_al_dueno`, `test_contador_danado_falla_cerrado` |
| 6 | Autorización decidida por la ventana | `Updater.authorize()` centraliza; `update()` exige ambas credenciales y las revalida inmediatamente antes de cerrar el POS | `engine.py`, `gui.py` | `test_autorizacion_revalidada_en_el_motor` |
| 7 | Cerrar la ventana mataba el hilo daemon a mitad de camino | `WM_DELETE_WINDOW` bloqueado durante operaciones críticas; hilo no daemon. Si igual se mata el proceso, rige el punto 1 | `gui.py` | `test_gui.py::test_no_se_cierra_durante_operacion_critica`, `test_modo_recuperacion_al_abrir_*` |
| 8 | ZIP con nombres repetidos | Se rechaza si `len(names) != len(set(names))` | `package.py` | `test_nombres_duplicados_en_el_zip_se_rechazan` |
| 9 | Ventana entre verificar y ejecutar el instalador | El instalador se abre con `CreateFileW` compartiendo solo lectura (nadie puede escribirlo), se rehashea desde ese handle y se ejecuta con el handle abierto | `engine.py` (`System.locked_file`, `install`) | `test_instalador_cambiado_tras_verificar_no_se_ejecuta`; E2E: Inno corre con el bloqueo activo |
| 10 | Una sola clave sin plan de rotación ni pérdida | Anillo de claves (`public_keys`) y `key_id` en manifiesto e índice; clave de respaldo offline; procedimiento de pérdida, robo y rotación; `trust.json` viejo sigue aceptado | `package.py`, `firmar.py`, `README.md` | `test_rotacion_clave_de_respaldo_y_trust_viejo`, `test_clave_desconocida_y_firma_cruzada_se_rechazan` |
| 11 | Pruebas | 38 pruebas del actualizador + 3 de ventana + 3 del POS (`test_update_gate.py`) | `updater/tests/*`, `backend/tests/test_update_gate.py` | Ver "Resultados" |
| 12 | Actualización real en Windows | Job `updater-e2e`: instala **main 0.5.1**, crea dueño, 3 productos y 12 ventas por la API; con el POS abierto actualiza a una versión de prueba **0.6.0 con migración Alembic 0007** (solo CI, `packaging/e2e/make_probe_version.py`); verifica versión, migración y datos comerciales idénticos; vende con la nueva; falla controlada con restauración; corte forzado y recuperación; dos actualizadores | `packaging/e2e/*`, workflow | Ver "Resultados" |

Otros cambios: la decisión se renumeró a **ADR-019** (la primera iteración usó por error
ADR-016, que es facturación fiscal); el módulo del POS se llama `update_gate.py` para no
confundirlo con `MaintenanceGate` (restauraciones), cuyo test se había pisado por error
en el primer intento de esta iteración y fue restaurado antes de commitear.

## Resultados

RESULTADOS_PENDIENTES

## Riesgos residuales

- **Cuenta de Windows compartida (H-01):** quien la controla puede reemplazar el
  actualizador, el POS o borrar el journal. Las protecciones son de integridad y
  procedimiento, no contra un usuario con control local.
- **Primera actualización desde 0.5.1:** esa versión no conoce el journal. Entre que el
  actualizador suelta el bloqueo de instancia (Inno lo exige libre) y el instalador cierra
  sus archivos, alguien podría abrir el 0.5.1 a mano; el instalador fallaría por su
  AppMutex y la restauración pide el bloqueo antes de tocar nada. Desde 0.6.0 el POS
  respeta el journal.
- **Bloqueo de arranque por journal:** es una excepción explícita a "nunca bloquear el
  arranque" (ADR-019). Si el técnico no está, el dueño puede recuperar con su contraseña.
  Un journal dañado exige al técnico.
- **Clave privada robada:** los actualizadores instalados la aceptan hasta reinstalarlos
  sin ella; aún se necesitan la clave del técnico y la del dueño. No hay revocación remota
  (decisión offline).
- **Entrada de desinstalación de Windows** puede mostrar la versión nueva tras una
  restauración; el actualizador usa `--version` del ejecutable.
- **Firma de código Authenticode** del instalador y del actualizador sigue pendiente.
- **E2E en Windows Server de GitHub**, no en Windows 11 limpio ni con antivirus de terceros.
- Corte en la fase `snapshotting` con disco lleno o error de E/S: la recuperación descarta
  la copia parcial; no se probó con disco realmente lleno.
