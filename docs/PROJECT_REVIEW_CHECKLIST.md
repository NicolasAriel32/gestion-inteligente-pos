# Checklist reutilizable de revisión técnica

Plantilla para adaptar al inicio del próximo proyecto y antes de cerrar una fase.
No marcar una comprobación como realizada sin registrar comando, entorno y resultado.

## Persistencia y migraciones

- [ ] Confirmar el comportamiento transaccional real del driver y la base objetivo.
- [ ] Probar instalación nueva, upgrade desde la revisión anterior y reaplicación.
- [ ] Inyectar un fallo a mitad del DDL; verificar esquema y revisión desde otra conexión.
- [ ] Demostrar rollback y reintento sin borrar datos ni editar marcadores de versión.
- [ ] Asegurar que metadatos y esquema real coincidan; si no hay modelo completo,
  bloquear autogeneración y comprobar que no escriba archivos ni altere la DB.
- [ ] Revisar manualmente cualquier propuesta DROP/DELETE y mantener política de respaldos.

## Arranque y disponibilidad

- [ ] Declarar la revisión y estructura mínimas que acepta cada versión de la aplicación.
- [ ] Probar rechazo de base vacía, anterior, futura e incompleta antes de habilitar endpoints.
- [ ] Comprobar que el rechazo conserva datos, libera recursos y muestra un error sin secretos.
- [ ] Evitar reparaciones o migraciones implícitas que el usuario no pueda revisar.

## Cierre verificable

- [ ] Mantener pruebas de permisos, concurrencia y rollback cuando dependen de la DB real.
- [ ] Ejecutar tests, lint, build y comunicación real local requeridos por la fase.
- [ ] Revisar escenarios negativos: que pase el flujo habitual no basta para cerrar la fase.
- [ ] Registrar hallazgos con causa, reproducción, fix, regresión y limitaciones comprobadas.
- [ ] Verificar rama, diff, commits remotos y conservación de ramas fuera del alcance.

Origen: [hallazgos H-F2-001 a H-F2-003](ENGINEERING_FINDINGS.md). Adaptar a la arquitectura
real del nuevo proyecto; no trasladar comandos o garantías de SQLite a otro motor sin probarlos.
