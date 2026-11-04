# SysReview PRISMA v3

Herramienta de escritorio para el cribado de revisiones sistemáticas según **PRISMA 2020**:
combina exportaciones de varias bases, elimina duplicados, aplica un cribado automático
configurable y guía la revisión manual (título/resumen y texto completo) hasta el diagrama final.

## Instalación y uso

```bash
pip install -r requirements.txt
python prisma_screener_v3.py
```

`prisma_screener_v2.py` se conserva sin cambios como versión anterior.

## Flujo

1. **Cargar** — una o varias fuentes en cualquiera de estos formatos:

   | Formato | Extensiones | Típico de |
   |---|---|---|
   | CSV (coma o punto y coma) | `.csv` | Scopus, IEEE, Lens, Excel en español |
   | Excel / LibreOffice | `.xlsx` `.xlsm` `.xls` `.ods` | WoS («Excel»), cualquier hoja |
   | Texto tabulado | `.txt` `.tsv` | WoS («Tab delimited») |
   | Texto plano etiquetado | `.txt` `.ciw` | WoS («Plain text», «EndNote Desktop») |
   | RIS | `.ris` | Scopus, WoS, Zotero, Mendeley |
   | BibTeX | `.bib` | Scopus, Google Scholar, Zotero |
   | MEDLINE | `.nbib` `.txt` | PubMed |
   | EndNote / Refer | `.enw` | EndNote, Google Scholar |

   El formato se detecta por el **contenido**, aunque la extensión no coincida (p. ej. un `.xls`
   que en realidad es texto tabulado). Si falta una librería (como `xlrd` para `.xls`), la app
   ofrece instalarla. La fuente (Scopus, WoS, PubMed, IEEE) se detecta sola y su nombre es editable.
2. **Deduplicar** — DOI normalizado (`https://doi.org/`, `doi:`, mayúsculas), título normalizado
   (sin acentos ni puntuación) y, opcionalmente, títulos similares. Nunca fusiona por título
   registros con DOI distintos, ni títulos similares con números distintos (*Part I* ≠ *Part II*)
   o años separados por más de 1. De cada grupo conserva el registro más completo.
3. **Cribado automático** — año, tipo de documento (coincidencia exacta por tipo), bloque
   obligatorio, bloque secundario, términos de exclusión y bloques de la cadena de búsqueda.
4. **Revisión y resultados** — revisión manual con resaltado de términos, segundo revisor con κ de
   Cohen, diagrama PRISMA 2020 y exportaciones.

## Sintaxis de términos

| Escribes | Coincide con | No coincide con |
|---|---|---|
| `ai` | "AI-based", "ai" | "m**ai**n", "s**ai**d" |
| `monitor*` | monitor, monitoring, monitored | — |
| `organi?ation` | organization, organisation | — |
| `low-cost sensor` | low cost sensors, Low-cost sensor | — |
| `bridge` (plural automático) | bridge, bridges | — |
| `technology` (plural automático) | technology, technologies | — |

- Coincidencia por **palabra completa**, sin distinguir mayúsculas ni acentos.
- Bloques vacíos se ignoran; "bloques mínimos = 0" significa *todos*.
- **Importar cadena**: pega tu cadena de Scopus (`TITLE-ABS-KEY(...)`) o WoS (`TS=(...)`), o **ambas juntas**,
  y se convierte en criterios de cribado:

  | En la cadena | Se convierte en |
  |---|---|
  | Grupos unidos por `AND` | Bloques (sus `OR` son sinónimos); todos obligatorios |
  | `AND NOT (...)` | Términos de exclusión |
  | `PUBYEAR > 2011`, `PY=(2012-2026)`, `Publication Years 2012–2026` | Rango de años |
  | `LIMIT-TO(DOCTYPE,"ar")`, `DT=(Article)`, `Document Types: Article, Proceedings Paper` | Tipos de documento permitidos |
  | `LIMIT-TO(LANGUAGE,"English")`, `LA=(English)`, `Languages: English, Spanish` | Idiomas permitidos |

  La línea `Refine:` de WoS se lee como filtros, no como términos. *Proceedings Paper* (WoS) y
  *Conference Paper* (Scopus) se tratan como el mismo tipo. Los registros sin tipo o sin idioma no se excluyen.

## Decisiones automáticas → revisión manual

En lugar de excluir sin mirar, estos casos van a **Pendientes de revisión**:

- año faltante (configurable: revisar / excluir / ignorar),
- término de exclusión que aparece **solo en el abstract** (modo *Equilibrado*),
- artículos a un bloque del mínimo (opción *A 1 bloque del mínimo → revisión*).

Las decisiones manuales prevalecen y se conservan al volver a cribar. Un artículo excluido
automáticamente puede **rescatarse** marcándolo como *Incluir* o *Dudoso*.

### Atajos en la ventana de revisión

`Ctrl+1` Incluir · `Ctrl+2` Excluir · `Ctrl+3` Dudoso · `Ctrl+0` Sin decidir ·
`Ctrl+Enter` guardar y siguiente · `Ctrl+S` guardar · `Ctrl+←/→` navegar · `Esc` cerrar

## Segundo revisor y κ de Cohen

1. *Hoja 2º revisor* exporta un Excel **ciego** (sin las decisiones del revisor 1).
2. El segundo revisor llena `Decision_R2` con *Incluir / Excluir / Dudoso*.
3. *Importar 2º revisor (κ)* calcula acuerdo observado, κ de Cohen (Landis & Koch) y permite
   exportar los desacuerdos.

## Exportaciones y reproducibilidad

- **Excel completo**: hojas Resumen_PRISMA, Incluidos, Pendientes, Excluidos (texto completo,
  cribado manual, automáticos), Duplicados, Todos, Configuración y Procedencia.
- **CSV** y **RIS** de los incluidos (RIS se importa directo en Zotero/Mendeley/EndNote).
- **Diagrama PRISMA 2020** en SVG o PNG, e informe en texto.
- Cada exportación guarda junto al archivo un `*_config.json` con la configuración usada,
  versión de la app, fecha y huella **SHA-256** de cada archivo de entrada.
- **Proyecto `.prisma`** (`Ctrl+S` / `Ctrl+O`): guarda datos, decisiones y configuración para
  continuar después.

## Estructura

| Archivo | Contenido |
|---|---|
| `prisma_core.py` | Lógica sin interfaz: lectura, normalización, deduplicación, cribado, conteos PRISMA, κ, parser de cadenas, exportaciones, sesiones |
| `prisma_presets.py` | Presets de ejemplo, validación y guardado (con respaldo si el archivo se daña) |
| `prisma_screener_v3.py` | Interfaz gráfica (CustomTkinter) |
| `tests/test_core.py` | Pruebas del núcleo |

```bash
python -m unittest discover -s tests -v     # o: pytest
```
