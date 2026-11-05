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

5. **PDFs de acceso abierto** — encuentra qué artículos tienen una versión **legal y gratuita** y la
   descarga a `…\<carpeta de resultados>\PDFs\` (ver abajo).

## PDFs de acceso abierto (Paso 5)

1. Elige el alcance (*Incluidos*, *Incluidos + pendientes* o *Todos los cribados*) y pulsa
   **🔎 Buscar PDFs disponibles**. Se consulta [OpenAlex](https://openalex.org) con el DOI (gratis, sin
   registro); los registros sin DOI se buscan por título y solo se aceptan si título y año coinciden.
   Si escribes tu correo también se consulta [Unpaywall](https://unpaywall.org) (opcional).
2. Cada artículo queda como:

   | Estado | Significado |
   |---|---|
   | **PDF disponible** | Hay un PDF gratuito (revista abierta, repositorio, PubMed Central…) |
   | **Solo página web** | Es gratuito, pero sin enlace directo al PDF: ábrelo en el navegador |
   | **Cerrado** | Sin versión libre: biblioteca, préstamo interbibliotecario o pedirlo al autor |

3. **⬇ Descargar todos los disponibles** (o solo los seleccionados). Si una copia falla, se prueban las
   alternativas (p. ej. Europe PMC para artículos de MDPI/*Sensors*). Solo se guardan PDFs reales.
   Puede tardar varios minutos; volver a pulsar reintenta solo los que faltan.
4. Doble clic en una fila abre el PDF descargado o su enlace. En la ventana de revisión, el botón
   **🌐 Abrir artículo / PDF** hace lo mismo (útil para la evaluación a texto completo).
5. **💾 Exportar lista** guarda un Excel con el estado y los enlaces de cada artículo.

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

## Carpeta de resultados

Todo lo que genera el programa se guarda **automáticamente** en una sola carpeta, sin preguntar
dónde: Excel, CSV, RIS, diagramas, informes, hoja del 2º revisor, desacuerdos, plantillas y el
proyecto `.prisma`.

- En la barra lateral, **📁 Carpeta de resultados**: escribe el nombre que quieras (por defecto, el
  nombre de la revisión).
- **Cambiar ubicación…** elige dónde se crea (por defecto `Documentos\SysReview PRISMA`); se recuerda
  para la próxima vez. **Abrir** la muestra en el Explorador.
- Nunca se sobrescribe un archivo: si ya existe se guarda como `nombre (2).xlsx`, `(3)`…
  (excepto el proyecto `.prisma`, que `Ctrl+S` actualiza).
- Al abrir un proyecto `.prisma` se usa la carpeta donde está guardado.

Si ocurre un error, la app lo muestra y lo guarda en `~/.sysreview_errores.log`.

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
| `prisma_oa.py` | Consulta de acceso abierto (OpenAlex, Unpaywall) y descarga de PDFs |
| `prisma_screener_v3.py` | Interfaz gráfica (CustomTkinter) |
| `tests/test_core.py` | Pruebas del núcleo |

```bash
python -m unittest discover -s tests -v     # o: pytest
```
