# crm-csv-cleaner

Herramienta de línea de comandos que toma varios CSV/Excel desordenados de reservas o contactos y produce **un único CSV limpio** listo para importar a un CRM.

> **Versión 0.1 (alfa).** Funciona y está probada con los datos de ejemplo, pero la interfaz puede cambiar.

El CSV de salida usa columnas compatibles con los importadores de GoHighLevel, HubSpot y Airtable (configurables en el YAML). Este proyecto no está afiliado a ninguno de ellos: GoHighLevel, HubSpot y Airtable son marcas de sus respectivos propietarios y se mencionan solo como formatos de importación compatibles.

## Qué hace

- Une varios archivos CSV/XLSX con columnas distintas mediante un mapeo configurable (YAML).
- Normaliza teléfonos a formato internacional E.164 (España por defecto) y emails a minúsculas.
- Deduplica por teléfono o email, conserva el registro más reciente y cuenta cuántas veces aparecía.
- Convierte fechas a ISO `AAAA-MM-DD`.
- Genera un informe: filas leídas, duplicados, filas descartadas y por qué, avisos y fusiones dudosas.
- Modo `--dry-run` que no escribe nada.

## Instalación

Requiere Python ≥ 3.11. Desde una copia local del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .            # o: pip install -e ".[dev]" para desarrollar
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

## Antes / después

Salida real de `crm-csv-cleaner examples/input -c examples/mapping.yaml -o limpio.csv` sobre los datos ficticios de `examples/`.

**Antes:** la misma persona en tres archivos con formatos distintos.

`reservas_web.csv` (UTF-8, separador `;`):
```
Nombre completo;Móvil;Correo;F. reserva
 Marta Rivas Muñoz ;600 000 006;Marta.rivas14@example.com ;11/10/2025
```

`contactos_tpv.csv` (cp1252, separador `,`):
```
first name,last name,phone,email,date
MARTA,rivas muñoz  ,(+34) 600-000-006,,25-5-2025
```

`eventos.xlsx`:

| Nombre | Apellidos | Tlf | E-mail | Fecha |
|---|---|---|---|---|
| Marta | `Rivas  Muñoz` | 600000006 | ` Marta.rivas14@example.com` | `25.06.2025` |

**Después:** una sola fila.
```
First Name,Last Name,Email,Phone,Date,source_files,apariciones
Marta,Rivas Muñoz,marta.rivas14@example.com,+34600000006,2025-10-11,contactos_tpv.csv|eventos.xlsx|reservas_web.csv,3
```

**Informe** (extracto real):
```
Archivos:
  contactos_tpv.csv: 19 filas (cp1252, separador ,)
  eventos.xlsx: 25 filas (Excel)
  reservas_web.csv: 24 filas (utf-8, separador ;)

Filas leídas:          68
Duplicados fusionados: 21
Filas descartadas:     3
Avisos:                2
Fusiones dudosas:      1
Filas en la salida:    44

Descartadas:
  contactos_tpv.csv fila 18: teléfono inválido y sin email (•••45)
  reservas_web.csv fila 24: fila vacía
  reservas_web.csv fila 25: sin teléfono ni email

Avisos (la fila se conserva con la celda vacía):
  contactos_tpv.csv fila 19: fecha inválida (2025-02-30)
  eventos.xlsx fila 24: email inválido (c***)

Fusiones dudosas (sin ningún nombre ni apellido en común; revísalas):
  Sofía Robles Vega / Héctor Gallardo Rey  [+34•••••••58, h***@example.org, s***@example.com]  en contactos_tpv.csv:20, eventos.xlsx:26
```

## Configuración

Ejemplo completo en [`examples/mapping.yaml`](examples/mapping.yaml). Las cabeceras se comparan sin distinguir mayúsculas, tildes ni espacios sobrantes.

```yaml
default_region: ES            # región para teléfonos sin prefijo internacional
date: { dayfirst: true }      # 03/04/2025 = 3 de abril
dedupe:
  keys: [telefono, email]     # misma persona si coincide cualquiera
  recency_field: fecha        # gana el registro más reciente
fields:                       # campo interno -> cabeceras posibles
  telefono: ["telefono", "movil", "tlf", "phone"]
  # ...
output_columns:               # campo interno -> cabecera del CSV de salida
  telefono: Phone
  # ...
sources:                      # opcional: mapeo explícito para un archivo concreto
  - file: export_raro.csv
    columns: { "Col 3": telefono }
```

## Reglas de deduplicado

- Dos registros son la misma persona si comparten teléfono **o** email, también de forma encadenada: si A y B comparten teléfono y B y C comparten email, A, B y C se fusionan.
- Gana el registro más reciente; los registros sin fecha cuentan como los más antiguos. En caso de empate, gana el último leído.
- Los campos vacíos del ganador se completan con el siguiente registro más reciente que tenga valor. Un valor existente nunca se sobrescribe.
- Los archivos se leen siempre en orden alfabético por nombre (sin tildes ni mayúsculas), así que el resultado no depende del orden en que se pasen.

## Limitaciones

- **Fusiones dudosas.** Si dos personas distintas comparten teléfono o email (un fijo de empresa, un móvil familiar), se fusionan en una. El informe lista como «fusiones dudosas» los grupos con registros sin ningún nombre ni apellido en común, pero no los separa: revísalos antes de importar. **En una fusión se conserva solo el email del registro ganador**; los emails de los demás registros se pierden en la salida (en el ejemplo, se conserva `hector.g@example.org` y se pierde el de Sofía). Las variantes con iniciales o apodos («Mª», «Pepe») no se detectan como el mismo nombre.
- **Nombre completo.** Una columna «Nombre completo» se parte por la primera palabra: «José Luis Rivas» queda como nombre «José» y apellidos «Luis Rivas». Si la fuente tiene nombre y apellidos por separado, mapéalos directamente.
- **Orden de salida.** Se ordena por apellidos y nombre sin tildes ni mayúsculas, así que la «ñ» se ordena como «n».
- **Fechas ambiguas.** `03/04/2025` se interpreta según `date.dayfirst` (por defecto, día primero) para todos los archivos.
- **Formatos.** No lee `.xls` antiguos; guárdalos como `.xlsx` o `.csv`. De un Excel solo se lee la primera hoja.

## Datos de ejemplo

`examples/` contiene datos **100 % ficticios** generados por `examples/generate_fake_data.py` (semilla fija, salida reproducible):

- Teléfonos solo del bloque `600 000 xxx`. Cualquier móvil español con formato válido podría estar asignado a alguien, así que este bloque se usa para que se note que son datos de prueba. **No llames ni escribas a estos números.**
- Emails solo en `@example.com` / `@example.org`, dominios reservados para documentación (RFC 2606).

Incluyen casos límite a propósito: duplicados entre archivos y dentro de un mismo archivo, filas vacías o sin contacto, un teléfono y un email inválidos, una fecha imposible, un teléfono guardado como número por Excel y una **fusión dudosa** (dos personas distintas que comparten teléfono). `examples/output/clientes_limpios.csv` es la salida esperada y los tests comprueban que la herramienta la reproduce byte a byte. `tests/test_privacy.py` falla si algún dato de `examples/` se sale de estas reglas.

## Privacidad y RGPD

- Todo el procesamiento es local: la herramienta no se conecta a ningún servicio ni envía datos a terceros.
- **La herramienta procesa datos personales** (nombres, teléfonos, emails). Quien la usa es responsable de contar con una base legal para tratarlos (RGPD y normativa aplicable), de informar a los interesados y de custodiar los archivos de entrada y salida, en especial el de `--rejects`.
- El `.gitignore` ignora cualquier CSV/Excel fuera de `examples/` para evitar subir datos reales por accidente. No uses datos reales en issues, tests ni ejemplos.

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md). Una buena primera contribución es mejorar la separación de nombres compuestos.

## Licencia

[MIT](LICENSE) © 2026 Francisco Oliver Mora
