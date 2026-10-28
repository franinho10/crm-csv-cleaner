# crm-csv-cleaner

Herramienta de línea de comandos que toma varios CSV/Excel desordenados de reservas o contactos y produce **un único CSV limpio** listo para importar a un CRM (GoHighLevel, HubSpot, Airtable).

> 🚧 En desarrollo (MVP). La CLI todavía no procesa archivos.

## Qué hará

- Unir varios archivos con columnas distintas mediante un mapeo configurable (YAML).
- Normalizar teléfonos (formato internacional E.164, España por defecto) y emails.
- Deduplicar por teléfono o email, conservando el registro más reciente y contando cuántas veces aparecía.
- Convertir fechas a ISO `AAAA-MM-DD`.
- Informe final: filas leídas, duplicados, filas descartadas y por qué.
- Modo `--dry-run` que no escribe nada.

## Instalación

Requiere Python ≥ 3.11.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Datos de ejemplo

`examples/` contiene datos **100 % ficticios** generados por `examples/generate_fake_data.py`:

- Teléfonos solo del bloque `600 000 xxx`. Cualquier móvil español con formato válido podría estar asignado a alguien, así que este bloque se usa para que se note que son datos de prueba. **No llames ni escribas a estos números.**
- Emails solo en `@example.com` / `@example.org`, dominios reservados para documentación (RFC 2606).

## Privacidad

Todo el procesamiento es local; la herramienta no se conecta a ningún servicio. El `.gitignore` ignora cualquier CSV/Excel fuera de `examples/` para evitar subir datos reales por accidente.

## Licencia

[MIT](LICENSE) © 2026 Francisco Oliver Mora
