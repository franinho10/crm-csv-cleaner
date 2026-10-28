# Contribuir

¡Gracias por tu interés! El proyecto es pequeño y quiere seguir siéndolo: cambios acotados, con tests y sin dependencias nuevas salvo que estén muy justificadas.

## Preparar el entorno

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Antes de abrir un pull request

```bash
ruff format .
ruff check .
pytest
```

Si cambias `examples/generate_fake_data.py`, regenera los ejemplos (`python examples/generate_fake_data.py`) e incluye los archivos resultantes en el mismo commit. La CI comprueba que estén sincronizados.

## Reglas de privacidad (obligatorias)

- **Nunca uses datos reales**, ni en tests, ni en ejemplos, ni en issues. Usa teléfonos del bloque `600 000 xxx` y emails `@example.com` / `@example.org`.
- `tests/test_privacy.py` falla si algo en `examples/` se sale de estas reglas.
- Si un error solo se reproduce con un archivo real, crea un ejemplo ficticio con la misma forma (cabeceras, formatos, codificación) en lugar de adjuntarlo.

## Buena primera contribución: nombres compuestos

Ahora una columna «Nombre completo» se parte por la primera palabra, así que «José Luis Rivas Soler» queda como nombre «José» y apellidos «Luis Rivas Soler» (ver `split_full_name` en `src/crm_csv_cleaner/normalize.py`). Ideas para mejorarlo:

- Una lista configurable de nombres compuestos frecuentes («José Luis», «María José», «Juan Carlos»…).
- Asumir dos apellidos al final cuando haya cuatro o más palabras.
- Respetar partículas en apellidos («de la Fuente», «del Río»).

Añade casos a `tests/test_normalize.py` y documenta el nuevo comportamiento en el README.

## Estilo

- Código y comentarios en el estilo del resto del repo (mensajes al usuario en español).
- Funciones puras y pequeñas donde se pueda; los normalizadores devuelven el valor limpio o `None`.
- Mensajes de commit breves en imperativo, por ejemplo: `feat: separar nombres compuestos`.
