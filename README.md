# crm-csv-cleaner

Herramienta de línea de comandos que toma varios CSV/Excel desordenados de reservas o contactos y produce **un único CSV limpio** listo para importar a un CRM (GoHighLevel, HubSpot, Airtable).

> 🚧 MVP en desarrollo.

## Qué hace

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

## Uso

```bash
crm-csv-cleaner examples/input -c examples/mapping.yaml -o limpio.csv \
    --rejects rechazados.csv --report informe.json
```

| Opción | Qué hace |
|---|---|
| `ARCHIVO...` | CSV/XLSX de entrada, o carpetas (se leen sus CSV/XLSX). |
| `-c, --config` | Mapeo YAML. Sin él se usan los sinónimos integrados. |
| `-o, --output` | CSV limpio. Obligatorio salvo con `--dry-run`. |
| `--rejects` | CSV con las filas descartadas, su motivo y **sus datos originales sin enmascarar**. |
| `--report` | Informe en JSON, con teléfonos y emails enmascarados. |
| `--dry-run` | Procesa y muestra el informe sin crear ningún archivo ni carpeta. |
| `--force` | Permite sobrescribir archivos existentes (por defecto, nunca se sobrescriben). |

> ⚠️ **`--rejects` contiene datos personales completos** (teléfonos y emails sin enmascarar) para que puedas corregirlos. No lo compartas ni lo subas a ningún repositorio.

El informe en consola nunca muestra teléfonos ni emails completos. Códigos de salida: `0` correcto, `1` error de entrada, configuración o escritura, `2` argumentos incorrectos.

## Datos de ejemplo

`examples/` contiene datos **100 % ficticios** generados por `examples/generate_fake_data.py`:

- Teléfonos solo del bloque `600 000 xxx`. Cualquier móvil español con formato válido podría estar asignado a alguien, así que este bloque se usa para que se note que son datos de prueba. **No llames ni escribas a estos números.**
- Emails solo en `@example.com` / `@example.org`, dominios reservados para documentación (RFC 2606).

Incluyen casos límite a propósito: duplicados entre archivos y dentro de un mismo archivo, filas vacías o sin contacto, un teléfono y un email inválidos, una fecha imposible, un teléfono guardado como número por Excel y una **fusión dudosa** (dos personas distintas que comparten teléfono). `examples/output/clientes_limpios.csv` es la salida esperada y los tests comprueban que la herramienta la reproduce byte a byte.

## Reglas de deduplicado

- Dos registros son la misma persona si comparten teléfono **o** email, también de forma encadenada: si A y B comparten teléfono y B y C comparten email, A, B y C se fusionan.
- Gana el registro más reciente; los registros sin fecha cuentan como los más antiguos. En caso de empate, gana el último leído.
- Los campos vacíos del ganador se completan con el siguiente registro más reciente que tenga valor. Un valor existente nunca se sobrescribe.
- Los archivos se leen siempre en orden alfabético por nombre (sin tildes ni mayúsculas), así que el resultado no depende del orden en que se pasen.

## Limitaciones

- **Fusiones dudosas.** Si dos personas distintas comparten teléfono o email (un fijo de empresa, un móvil familiar), se fusionan en una. El informe lista como «fusiones dudosas» los grupos con registros sin ningún nombre ni apellido en común, pero no los separa: revísalos antes de importar. Las variantes con iniciales o apodos («Mª», «Pepe») no se detectan como el mismo nombre.
- **Nombre completo.** Una columna «Nombre completo» se parte por la primera palabra: «José Luis Rivas» queda como nombre «José» y apellidos «Luis Rivas». Si la fuente tiene nombre y apellidos por separado, mapéalos directamente.
- **Orden de salida.** Se ordena por apellidos y nombre sin tildes ni mayúsculas, así que la «ñ» se ordena como «n».
- **Fechas ambiguas.** `03/04/2025` se interpreta según `date.dayfirst` (por defecto, día primero) para todos los archivos.

## Privacidad

Todo el procesamiento es local; la herramienta no se conecta a ningún servicio. El `.gitignore` ignora cualquier CSV/Excel fuera de `examples/` para evitar subir datos reales por accidente.

## Licencia

[MIT](LICENSE) © 2026 Francisco Oliver Mora
