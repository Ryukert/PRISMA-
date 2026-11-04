"""
=============================================================
  SysReview PRISMA v3 — Núcleo de procesamiento (sin GUI)
=============================================================
Toda la lógica testeable vive aquí:
  · Lectura de fuentes (Scopus, WoS, PubMed, IEEE, RIS, BibTeX, CSV/Excel)
  · Normalización de texto, DOI y títulos
  · Deduplicación (DOI, título exacto/normalizado, título similar)
  · Cribado automático con coincidencia por palabra completa y comodines
  · Estado PRISMA 2020 por registro y conteos del diagrama
  · Revisión manual, segundo revisor y κ de Cohen
  · Análisis de cadenas de búsqueda Scopus / WoS → bloques
  · Exportaciones (Excel por etapas, CSV, RIS, SVG/PNG) y sesiones
"""
from __future__ import annotations

import gzip
import hashlib
import json
import platform
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path

import pandas as pd

APP_VERSION = "3.0.0"

try:  # Deduplicación difusa rápida (opcional)
    from rapidfuzz import fuzz as _rf_fuzz, process as _rf_process
    HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - depende del entorno
    HAS_RAPIDFUZZ = False

# ─── Esquema de columnas ──────────────────────────────────────────────────────
FIELDS = ["title", "year", "abstract", "doi", "doc_type", "authors", "keywords", "journal", "language"]
TEXT_FIELDS = [f for f in FIELDS if f != "year"]
DEDUP_COLS = ["Is_Duplicate", "Duplicate_Of", "Duplicate_Reason"]
AUTO_COLS = ["Auto_Decision", "Auto_Stage", "Auto_Reason", "Matched_Required", "Matched_Secondary",
             "Matched_Exclude", "Matched_Blocks", "Missing_Blocks", "N_Blocks"]
MANUAL_COLS = ["TA_Decision", "TA_Reason", "TA_Note", "FT_Decision", "FT_Reason",
               "TA_Decision_R2", "TA_Reason_R2"]
STATUS_COLS = ["Status", "PRISMA_Stage"]
ALL_FLAG_COLS = DEDUP_COLS + AUTO_COLS + MANUAL_COLS + STATUS_COLS

# Códigos de decisión (se guardan en inglés, compatibles con v2)
INCLUDE, EXCLUDE, REVIEW, MAYBE, NOT_RETRIEVED = "Include", "Exclude", "Review", "Maybe", "Not retrieved"
PENDING = "Pending"

# Etapas del cribado automático
STAGE_DUP = "Duplicado"
STAGE_YEAR = "Año fuera de rango"
STAGE_NOYEAR = "Año faltante"
STAGE_DOCTYPE = "Tipo de documento"
STAGE_LANG = "Idioma"
STAGE_REQ = "Bloque obligatorio"
STAGE_SEC = "Bloque secundario"
STAGE_EXC = "Términos de exclusión"
STAGE_BLOCKS = "Bloques de búsqueda"
STAGE_REVIEW = "Revisión manual"
STAGE_PASS = "Aprobado"

# Estado final PRISMA de cada registro
STATUS_DUP = "Duplicado"
STATUS_UNSCREENED = "Sin cribar"
STATUS_EXC_AUTO = "Excluido (automático)"
STATUS_EXC_TA = "Excluido (cribado manual)"
STATUS_PENDING = "Pendiente de revisión"
STATUS_NOT_RETRIEVED = "No recuperado"
STATUS_EXC_FT = "Excluido (texto completo)"
STATUS_INCLUDED = "Incluido"
SCREENED_STATUSES = [STATUS_EXC_TA, STATUS_PENDING, STATUS_NOT_RETRIEVED, STATUS_EXC_FT, STATUS_INCLUDED]

TA_EXCLUSION_REASONS = [
    "Fuera del tema", "Objeto/población no pertinente", "Tecnología/método no pertinente",
    "Tipo de estudio no pertinente", "Sin resultados empíricos", "Idioma", "Otro",
]
FT_EXCLUSION_REASONS = [
    "Texto completo no pertinente", "Datos insuficientes", "Metodología no adecuada",
    "Publicación duplicada", "Idioma", "Otro",
]

DEFAULT_SCREEN_CFG = {
    "year_from": None,
    "year_to": None,
    "kw_required": "",
    "kw_secondary": "",
    "kw_exclude": "",
    "doc_exclude": "",
    "doc_include": "",           # vacío = todos los tipos
    "languages": "",             # vacío = todos los idiomas
    "search_blocks": {},
    "min_blocks": 0,            # 0 = todos los bloques activos
    "exclude_mode": "balanced",  # strict | balanced | flag
    "missing_year": "review",    # review | exclude | include
    "auto_plural": True,
    "review_near_miss": False,
}
EXCLUDE_MODES = {
    "strict": "Estricto — cualquier campo excluye",
    "balanced": "Equilibrado — título/keywords excluye, solo abstract → revisar",
    "flag": "Solo marcar — siempre a revisión manual",
}
MISSING_YEAR_MODES = {"review": "Enviar a revisión", "exclude": "Excluir", "include": "Ignorar (dejar pasar)"}

MIN_TITLE_LEN = 15
EXCEL_CELL_LIMIT = 32000

# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════
_SEPARATORS = re.compile(r"[\-\u2010-\u2015_/]+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_TITLE_NUMBERS = re.compile(r"\b(?:\d+|[ivxlc]+)\b")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_text(s) -> str:
    """Minúsculas, sin acentos, guiones/barras → espacio, espacios colapsados."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = strip_accents(str(s)).lower()
    s = _SEPARATORS.sub(" ", s)
    return _WS.sub(" ", s).strip()


def normalize_title(s) -> str:
    """Título comparable: sin acentos ni puntuación (conserva letras acentuadas como base)."""
    return _WS.sub(" ", _NON_ALNUM.sub(" ", normalize_text(s))).strip()


def normalize_doi(s) -> str:
    """Extrae el DOI canónico ('10.xxxx/...') sin prefijos URL ni 'doi:'."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).strip().lower()
    if s in ("", "nan", "none", "null"):
        return ""
    m = _DOI_RE.search(s)
    if not m:
        return ""
    return m.group(0).rstrip(".;,)]}>\"'")


def clean_cell(v):
    if isinstance(v, str):
        v = _ILLEGAL_XML.sub("", v)
        if len(v) > EXCEL_CELL_LIMIT:
            v = v[:EXCEL_CELL_LIMIT] + " …[truncado]"
    return v


# ══════════════════════════════════════════════════════════════════════════════
# TÉRMINOS Y EXPRESIONES REGULARES
# ══════════════════════════════════════════════════════════════════════════════
def parse_terms(value) -> list[str]:
    """Separa por coma, punto y coma o salto de línea; normaliza y quita duplicados."""
    if value is None:
        return []
    parts = value if isinstance(value, (list, tuple)) else re.split(r"[,;\n]+", str(value))
    out, seen = [], set()
    for p in parts:
        t = normalize_text(p).strip(" \"'{}")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _word_rx(w: str, last: bool, auto_plural: bool, alnum: str) -> str:
    if "*" in w or "?" in w:
        return "".join(f"{alnum}*" if c == "*" else alnum if c == "?" else re.escape(c) for c in w)
    rx = re.escape(w)
    if last and auto_plural and len(w) > 3 and w.isalpha():
        if w.endswith("y") and w[-2] not in "aeiou":
            rx = re.escape(w[:-1]) + "(?:y|ies)"
        elif w.endswith(("s", "x", "z", "ch", "sh")):
            rx += "(?:es)?"
        else:
            rx += "s?"
    return rx


def term_to_regex(term: str, auto_plural: bool = True, display: bool = False) -> str:
    """
    Convierte un término en regex de PALABRA COMPLETA.
      · '*' = cualquier sufijo, '?' = un carácter
      · plural automático opcional (s / es / y→ies) en la última palabra
      · display=True genera un patrón para resaltar sobre el texto original
    """
    t = normalize_text(term).strip(" \"'{}")
    if not t:
        return ""
    alnum = r"\w" if display else "[a-z0-9]"
    sep = r"[\s\-\u2010-\u2015_/]+" if display else " "
    words = t.split(" ")
    body = sep.join(_word_rx(w, i == len(words) - 1, auto_plural, alnum) for i, w in enumerate(words))
    if display:
        return rf"(?<!\w){body}(?!\w)"
    return rf"(?<![a-z0-9]){body}(?![a-z0-9])"


def compile_terms(terms, auto_plural: bool = True, display: bool = False):
    """Compila una lista de términos a un único patrón (None si la lista está vacía)."""
    rxs = [term_to_regex(t, auto_plural, display) for t in terms]
    rxs = [r for r in rxs if r]
    if not rxs:
        return None
    rxs.sort(key=len, reverse=True)
    return re.compile("|".join(f"(?:{r})" for r in rxs), re.IGNORECASE if display else 0)


LANG_CODES = {
    "eng": "english", "en": "english", "ingles": "english",
    "spa": "spanish", "es": "spanish", "espanol": "spanish", "castellano": "spanish",
    "por": "portuguese", "pt": "portuguese", "portugues": "portuguese",
    "fre": "french", "fra": "french", "fr": "french", "frances": "french",
    "ger": "german", "deu": "german", "de": "german", "aleman": "german",
    "chi": "chinese", "zho": "chinese", "chino": "chinese", "ita": "italian", "italiano": "italian",
    "jpn": "japanese", "rus": "russian", "kor": "korean",
}
DOCTYPE_SYNONYMS = {
    # WoS «Proceedings Paper» ≡ Scopus «Conference Paper»
    "proceedings paper": "conference paper", "conference proceedings": "conference paper",
    "documento de sesion": "conference paper", "ponencia": "conference paper",
    "articulo de conferencia": "conference paper", "cpaper": "conference paper",
    "journal article": "article", "articulo": "article", "articulo de revista": "article",
    "article in press": "article",
    "editorial material": "editorial", "material editorial": "editorial",
    "revision": "review", "capitulo de libro": "book chapter", "libro": "book",
}
SCOPUS_DOCTYPES = {"ar": "Article", "cp": "Conference Paper", "re": "Review", "ch": "Book Chapter", "bk": "Book",
                   "ed": "Editorial", "le": "Letter", "no": "Note", "sh": "Short Survey", "cr": "Conference Review",
                   "er": "Erratum", "dp": "Data Paper", "ip": "Article in Press", "tb": "Retracted"}


def canon_list(value, kind: str) -> list[str]:
    """
    Lista canónica de tipos de documento (kind='doctype') o idiomas (kind='language').
    Separa por ; , | u OR, normaliza y aplica sinónimos (eng→english, Proceedings Paper→conference paper).
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    items = value if isinstance(value, (list, tuple)) else re.split(r"[;,|\n]|\s+OR\s+", str(value), flags=re.I)
    syn = LANG_CODES if kind == "language" else DOCTYPE_SYNONYMS
    out = []
    for p in items:
        t = normalize_text(p).strip(" \"'(){}")
        t = syn.get(t, t)
        if t and t not in out:
            out.append(t)
    return out


def _contains(series: pd.Series, pattern) -> pd.Series:
    return series.map(lambda s: pattern.search(s) is not None).astype(bool)


def _found(series: pd.Series, pattern) -> pd.Series:
    return series.map(lambda s: ", ".join(sorted(set(pattern.findall(s)))))


# ══════════════════════════════════════════════════════════════════════════════
# LECTURA DE FUENTES
# ══════════════════════════════════════════════════════════════════════════════
COLUMN_ALIASES = {
    "title": ["Title", "Article Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "Publication_Year", "Year Published", "Publication Date"],
    "abstract": ["Abstract", "AB"],
    "doi": ["DOI", "DI", "DOI Link"],
    "doc_type": ["Document Type", "DT", "Publication Type", "Document Identifier", "Type"],
    "authors": ["Authors", "Author full names", "AU", "Author(s)", "AF"],
    "keywords": ["Author Keywords", "DE", "Keywords"],
    "index_keywords": ["Index Keywords", "Keywords Plus", "ID", "IEEE Terms", "INSPEC Controlled Terms",
                       "MeSH Terms", "Mesh Terms"],
    "journal": ["Source title", "Source Title", "SO", "Publication Title", "Journal/Book", "Journal"],
    "language": ["Language of Original Document", "Language", "LA", "Languages"],
}
SUPPORTED_EXTENSIONS = [".csv", ".xlsx", ".xlsm", ".xls", ".ods", ".txt", ".tsv", ".ris", ".bib", ".nbib",
                        ".ciw", ".enw"]


class MissingDependency(ImportError):
    """Falta una librería opcional; `package` es el nombre para pip."""

    def __init__(self, package: str, message: str):
        super().__init__(message)
        self.package = package


def _excel_engine(fmt: str):
    """calamine (lee xls/xlsx/ods, si está instalado) → si no, xlrd para .xls, openpyxl para .xlsx, odf para .ods."""
    try:
        import python_calamine  # noqa: F401
        return "calamine"
    except ImportError:
        pass
    if fmt == "xls":
        try:
            import xlrd  # noqa: F401
        except ImportError:
            raise MissingDependency("xlrd", "Para leer archivos .xls (formato Excel antiguo, p. ej. WoS) "
                                            "se necesita la librería xlrd.") from None
        return "xlrd"
    if fmt == "ods":
        try:
            import odf  # noqa: F401
        except ImportError:
            raise MissingDependency("odfpy", "Para leer archivos .ods se necesita la librería odfpy.") from None
        return "odf"
    return "openpyxl"
RIS_TYPES = {"JOUR": "Article", "JFULL": "Article", "EJOUR": "Article", "CONF": "Conference Paper",
             "CPAPER": "Conference Paper", "CHAP": "Book Chapter", "BOOK": "Book", "RPRT": "Report",
             "THES": "Thesis", "GEN": "Generic", "MGZN": "Magazine Article", "NEWS": "Newspaper Article"}
BIB_TYPES = {"article": "Article", "inproceedings": "Conference Paper", "conference": "Conference Paper",
             "incollection": "Book Chapter", "inbook": "Book Chapter", "book": "Book",
             "phdthesis": "Thesis", "mastersthesis": "Thesis", "techreport": "Report", "misc": "Misc"}


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _decode(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def sniff_format(path, raw: bytes) -> str:
    """Detecta el formato por el CONTENIDO (no solo la extensión): un '.xls' puede ser texto, etc."""
    ext = Path(path).suffix.lower()
    if raw[:4] == b"\xd0\xcf\x11\xe0":
        return "xls"                      # Excel 97-2003 (OLE2)
    if raw[:2] == b"PK":
        return "ods" if ext == ".ods" else "excel"   # xlsx/xlsm/ods son ZIP
    head = _decode(raw[:6000]) if raw else ""
    if re.match(r"\s*<(?:!doctype|html|table|\?xml)", head, re.I):
        return "html"
    return detect_format(path, head)


def detect_format(path, head: str = "") -> str:
    ext = Path(path).suffix.lower()
    if re.search(r"^TY  - ", head, re.M):
        return "ris"
    if re.match(r"^\s*(FN |VR |PT [A-Z])", head) or ext == ".ciw":
        return "wos_tagged"
    if re.search(r"^PMID-", head, re.M):
        return "medline"
    if re.search(r"^%0 ", head, re.M) or ext == ".enw":
        return "endnote"
    if re.search(r"^\s*@\w+\s*[{(]", head, re.M):
        return "bibtex"
    ext_map = {".bib": "bibtex", ".nbib": "medline", ".ris": "ris", ".xlsx": "excel", ".xlsm": "excel",
               ".xls": "xls", ".ods": "ods"}
    if ext in ext_map and ext not in (".xls", ".xlsx", ".xlsm", ".ods"):
        return ext_map[ext]
    first = head.splitlines()[0] if head.strip() else ""
    if first.count("\t") > first.count(",") and first.count("\t") > first.count(";"):
        return "tsv"
    if first.count(";") > first.count(","):
        return "csv_semicolon"            # CSV de Excel en configuración regional española
    return "csv"


def _parse_ris(text: str) -> list[dict]:
    recs, cur, last = [], defaultdict(list), None
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  -\s?(.*)$", line)
        if m:
            tag, val = m.group(1), m.group(2).strip()
            if tag == "ER":
                if cur:
                    recs.append(dict(cur))
                cur, last = defaultdict(list), None
                continue
            cur[tag].append(val)
            last = tag
        elif last and line.strip():
            cur[last][-1] += " " + line.strip()
    if cur:
        recs.append(dict(cur))
    return recs


def _parse_wos_tagged(text: str) -> list[dict]:
    recs, cur, last = [], defaultdict(list), None
    for line in text.splitlines():
        if line.startswith("ER"):
            if cur:
                recs.append(dict(cur))
            cur, last = defaultdict(list), None
            continue
        if line.startswith(("FN ", "VR ", "EF")) and not cur:
            continue
        m = re.match(r"^([A-Z][A-Z0-9]) (.*)$", line)
        if m:
            last = m.group(1)
            cur[last].append(m.group(2).strip())
        elif last and line.startswith("   ") and line.strip():
            cur[last].append(line.strip())
    if cur:
        recs.append(dict(cur))
    return recs


def _parse_medline(text: str) -> list[dict]:
    recs, cur, last = [], defaultdict(list), None
    for line in text.splitlines():
        if not line.strip():
            if cur:
                recs.append(dict(cur))
            cur, last = defaultdict(list), None
            continue
        m = re.match(r"^([A-Z]{2,4})\s*- (.*)$", line)
        if m:
            tag = m.group(1)
            if tag == "PMID" and cur:
                recs.append(dict(cur))
                cur = defaultdict(list)
            cur[tag].append(m.group(2).strip())
            last = tag
        elif last and line.startswith("      "):
            cur[last][-1] += " " + line.strip()
    if cur:
        recs.append(dict(cur))
    return recs


def _parse_endnote(text: str) -> list[dict]:
    """EndNote / Refer (.enw): líneas '%T título', '%A autor'…; registros separados por línea en blanco."""
    recs, cur, last = [], defaultdict(list), None
    for line in text.splitlines():
        if not line.strip():
            if cur:
                recs.append(dict(cur))
            cur, last = defaultdict(list), None
            continue
        m = re.match(r"^%(\S)\s?(.*)$", line)
        if m:
            tag = m.group(1)
            if tag == "0" and cur:
                recs.append(dict(cur))
                cur = defaultdict(list)
            cur[tag].append(m.group(2).strip())
            last = tag
        elif last:
            cur[last][-1] += " " + line.strip()
    if cur:
        recs.append(dict(cur))
    return recs


def _bib_value(text: str, pos: int):
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n:
        return "", pos
    if text[pos] == "{":
        depth, i = 1, pos + 1
        while i < n and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        return text[pos + 1:i - 1], i
    if text[pos] == '"':
        depth, i = 0, pos + 1
        while i < n:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == '"' and depth == 0 and text[i - 1] != "\\":
                break
            i += 1
        return text[pos + 1:i], i + 1
    m = re.compile(r"[^,}\)\s]+").match(text, pos)
    return (m.group(0), m.end()) if m else ("", pos)


def _bib_clean(v: str) -> str:
    v = re.sub(r"\\[a-zA-Z]+\s*", "", v.replace("\\&", "&").replace("\\%", "%"))
    v = v.replace("{", "").replace("}", "").replace("\\", "")
    return _WS.sub(" ", v).strip()


def _parse_bibtex(text: str) -> list[dict]:
    recs = []
    entry_re = re.compile(r"@(\w+)\s*[{(]")
    field_re = re.compile(r"\s*,?\s*([\w\-:.]+)\s*=\s*")
    pos, n = 0, len(text)
    while True:
        m = entry_re.search(text, pos)
        if not m:
            break
        etype = m.group(1).lower()
        pos = m.end()
        if etype in ("comment", "preamble", "string"):
            _, pos = _bib_value(text, m.end() - 1)
            continue
        comma = text.find(",", pos)
        if comma == -1:
            break
        pos = comma + 1
        fields = {"_type": etype}
        while pos < n:
            while pos < n and text[pos] in " \t\r\n,":
                pos += 1
            if pos >= n or text[pos] in "})":
                pos += 1
                break
            fm = field_re.match(text, pos)
            if not fm:
                nxt = text.find("@", pos)
                pos = nxt if nxt != -1 else n
                break
            name = fm.group(1).lower()
            val, pos = _bib_value(text, fm.end())
            fields[name] = _bib_clean(val)
        recs.append(fields)
    return recs


def _tag_get(rec: dict, tags, sep=" ") -> str:
    for t in tags:
        if rec.get(t):
            return sep.join(v for v in rec[t] if v)
    return ""


def _tag_all(rec: dict, tags, sep="; ") -> str:
    return sep.join(v for t in tags for v in rec.get(t, []) if v)


def _records_from_tagged(fmt: str, recs: list[dict]) -> pd.DataFrame:
    rows = []
    for r in recs:
        if fmt == "ris":
            ty = _tag_get(r, ["TY"])
            rows.append({
                "title": _tag_get(r, ["TI", "T1", "CT"]),
                "abstract": _tag_get(r, ["AB", "N2"]),
                "year": _tag_get(r, ["PY", "Y1", "DA", "Y2"]),
                "doi": _tag_get(r, ["DO", "DI"]) or _tag_get(r, ["UR", "L3"]),
                "doc_type": RIS_TYPES.get(ty.upper(), ty),
                "authors": _tag_all(r, ["AU", "A1", "A2"]),
                "keywords": _tag_all(r, ["KW"]),
                "journal": _tag_get(r, ["T2", "JO", "JF", "JA"]),
                "language": _tag_all(r, ["LA"]),
            })
        elif fmt == "wos_tagged":
            rows.append({
                "title": _tag_get(r, ["TI"]),
                "abstract": _tag_get(r, ["AB"]),
                "year": _tag_get(r, ["PY", "EY"]),
                "doi": _tag_get(r, ["DI", "DL"]),
                "doc_type": _tag_get(r, ["DT"], "; "),
                "authors": _tag_get(r, ["AU", "AF"], "; "),
                "keywords": "; ".join(x for x in [_tag_get(r, ["DE"]), _tag_get(r, ["ID"])] if x),
                "journal": _tag_get(r, ["SO"]),
                "language": _tag_get(r, ["LA"], "; "),
            })
        elif fmt == "medline":
            doi = ""
            for v in r.get("AID", []) + r.get("LID", []):
                if "[doi]" in v:
                    doi = v.replace("[doi]", "").strip()
                    break
            rows.append({
                "title": _tag_get(r, ["TI", "BTI"]),
                "abstract": _tag_get(r, ["AB"]),
                "year": _tag_get(r, ["DP", "DEP"]),
                "doi": doi,
                "doc_type": _tag_all(r, ["PT"]),
                "authors": _tag_all(r, ["FAU"]) or _tag_all(r, ["AU"]),
                "keywords": _tag_all(r, ["OT", "MH"]),
                "journal": _tag_get(r, ["JT", "TA"]),
                "language": _tag_all(r, ["LA"]),
            })
        elif fmt == "endnote":
            rows.append({
                "title": _tag_get(r, ["T"]),
                "abstract": _tag_get(r, ["X"]),
                "year": _tag_get(r, ["D", "8"]),
                "doi": _tag_get(r, ["R"]) or _tag_get(r, ["U"]),
                "doc_type": _tag_get(r, ["0"]),
                "authors": _tag_all(r, ["A"]),
                "keywords": _tag_all(r, ["K"]),
                "journal": _tag_get(r, ["J", "B"]),
                "language": _tag_get(r, ["G"]),
            })
        elif fmt == "bibtex":
            rows.append({
                "title": r.get("title", ""),
                "abstract": r.get("abstract", ""),
                "year": r.get("year", ""),
                "doi": r.get("doi", ""),
                "doc_type": BIB_TYPES.get(r.get("_type", ""), r.get("_type", "")),
                "authors": "; ".join(a.strip() for a in re.split(r"\s+and\s+", r.get("author", "")) if a.strip()),
                "keywords": r.get("keywords", r.get("author_keywords", "")),
                "journal": r.get("journal", r.get("booktitle", "")),
                "language": r.get("language", r.get("langid", "")),
            })
    return pd.DataFrame(rows, columns=TEXT_FIELDS + ["year"])


def map_columns(columns, col_map: dict | None = None) -> dict:
    """Devuelve {campo: columna_original} combinando el mapeo del usuario con los alias conocidos."""
    lower = {str(c).strip().lstrip("\ufeff").lower(): c for c in columns}
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        user = (col_map or {}).get(field)
        for a in ([user] if user else []) + aliases:
            c = lower.get(str(a).strip().lower())
            if c is not None:
                mapping[field] = c
                break
    return mapping


def extract_year(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str).str.extract(r"((?:1[89]|20)\d{2})", expand=False)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def _standardize_table(raw: pd.DataFrame, col_map: dict | None):
    raw = raw.loc[:, ~pd.Index(raw.columns).duplicated()]
    mapping = map_columns(raw.columns, col_map)
    out = pd.DataFrame(index=range(len(raw)))
    for f in TEXT_FIELDS:
        if f in mapping:
            out[f] = raw[mapping[f]].fillna("").astype(str).str.strip().to_numpy()
        else:
            out[f] = ""
    if "index_keywords" in mapping:
        idx_kw = raw[mapping["index_keywords"]].fillna("").astype(str).str.strip().to_numpy()
        out["keywords"] = [("; ".join(x for x in (a, b) if x)) for a, b in zip(out["keywords"], idx_kw)]
    out["year"] = raw[mapping["year"]].to_numpy() if "year" in mapping else ""
    return out, mapping


def guess_source_name(path, columns, fmt: str) -> str:
    cols = {str(c).strip().lstrip("\ufeff").lower() for c in columns}
    stem = Path(path).stem.lower()
    if fmt == "medline" or "pmid" in cols or "pubmed" in stem:
        return "PubMed"
    if "eid" in cols or "scopus" in stem or ("source title" in cols and "link" in cols):
        return "Scopus"
    if (fmt == "wos_tagged" or "ut (unique wos id)" in cols or "ut (unique id)" in cols or "ut" in cols
            or "wos" in stem or "savedrecs" in stem):
        return "WoS"
    if "ieee terms" in cols or "document identifier" in cols or "ieee" in stem:
        return "IEEE"
    return Path(path).stem[:24] or "Fuente"


def read_source(path, source_name: str | None = None, col_map: dict | None = None):
    """
    Lee un archivo exportado y lo devuelve estandarizado.
    Retorna (DataFrame con FIELDS + 'source', info dict).
    """
    path = str(path)
    raw_bytes = Path(path).read_bytes()
    if not raw_bytes:
        raise ValueError("El archivo está vacío.")
    fmt = sniff_format(path, raw_bytes)
    columns, mapping = [], {}

    if fmt == "html":
        raise ValueError("Este archivo es en realidad una página web (HTML) con otra extensión. "
                         "Ábrelo en Excel y guárdalo como .xlsx o .csv, o vuelve a exportarlo desde la base de datos.")
    if fmt in ("excel", "xls", "ods"):
        import warnings
        engine = _excel_engine(fmt)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")      # aviso de pandas sobre xlrd obsoleto
            raw = pd.read_excel(path, dtype=str, engine=engine)
        raw = raw.loc[:, [not str(c).startswith("Unnamed:") or raw[c].notna().any() for c in raw.columns]]
        columns = list(raw.columns)
        df, mapping = _standardize_table(raw, col_map)
        if "title" not in mapping and "doi" not in mapping:
            raise ValueError("No se encontró una columna de título ni de DOI. Revisa el 'Mapeo de columnas' del "
                             f"Paso 1. Columnas del archivo: {', '.join(map(str, columns[:15]))}…")
    elif fmt in ("csv", "csv_semicolon", "tsv"):
        text = _decode(raw_bytes)
        if fmt == "csv":
            raw = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="skip")
        elif fmt == "csv_semicolon":
            raw = pd.read_csv(StringIO(text), sep=";", dtype=str, keep_default_na=False, on_bad_lines="skip")
        else:
            raw = pd.read_csv(StringIO(text), sep="\t", dtype=str, keep_default_na=False,
                              on_bad_lines="skip", quoting=3, index_col=False)
        columns = list(raw.columns)
        df, mapping = _standardize_table(raw, col_map)
        if "title" not in mapping and "doi" not in mapping:
            raise ValueError("No se encontró una columna de título ni de DOI. Revisa el 'Mapeo de columnas' del "
                             f"Paso 1. Columnas del archivo: {', '.join(map(str, columns[:15]))}…")
    else:
        text = _decode(raw_bytes)
        parser = {"ris": _parse_ris, "wos_tagged": _parse_wos_tagged, "medline": _parse_medline,
                  "bibtex": _parse_bibtex, "endnote": _parse_endnote}[fmt]
        df = _records_from_tagged(fmt, parser(text))
        columns = sorted({k for k in df.columns})
        mapping = {f: f for f in FIELDS}

    for f in TEXT_FIELDS:
        df[f] = df[f].fillna("").astype(str).str.replace(_ILLEGAL_XML, "", regex=True).str.strip()
    df["year"] = extract_year(df["year"])
    n_raw = len(df)
    df = df[(df["title"] != "") | (df["doi"] != "")].reset_index(drop=True)

    name = (source_name or "").strip() or guess_source_name(path, columns, fmt)
    df["source"] = name
    missing = [f for f in ("title", "year", "abstract", "doi", "doc_type", "keywords") if f not in mapping]
    info = {
        "path": path,
        "file": Path(path).name,
        "name": name,
        "format": fmt,
        "n": int(len(df)),
        "n_dropped_empty": int(n_raw - len(df)),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "columns": [str(c) for c in columns[:40]],
        "mapping": {k: str(v) for k, v in mapping.items()},
        "missing_fields": missing,
    }
    return df[FIELDS + ["source"]], info


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for c in TEXT_FIELDS + ["source", "record_id"] + ALL_FLAG_COLS:
        if c not in df.columns:
            df[c] = ""
        else:
            df[c] = df[c].fillna("").astype(str)
    if "year" not in df.columns:
        df["year"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    else:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df


def combine_sources(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatena fuentes estandarizadas y asigna un ID estable a cada registro."""
    if not frames:
        return ensure_columns(pd.DataFrame(columns=FIELDS + ["source"]))
    df = pd.concat(frames, ignore_index=True)
    df = ensure_columns(df)
    df["record_id"] = [f"R{i + 1:05d}" for i in range(len(df))]
    df.index = df["record_id"].to_numpy()
    cols = ["record_id", "source"] + FIELDS
    return df[cols + [c for c in df.columns if c not in cols]]


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def fuzzy_title_pairs(titles: list[str], threshold: float = 95) -> list[tuple[int, int]]:
    """Pares (i, j) de índices con títulos similares (≥ threshold, escala 0–100)."""
    uniq: dict[str, list[int]] = {}
    for i, t in enumerate(titles):
        if len(t) >= MIN_TITLE_LEN:
            uniq.setdefault(t, []).append(i)
    keys = list(uniq)
    pairs: set[tuple[int, int]] = set()
    if HAS_RAPIDFUZZ and keys:
        for start in range(0, len(keys), 500):
            chunk = keys[start:start + 500]
            mat = _rf_process.cdist(chunk, keys, scorer=_rf_fuzz.ratio, score_cutoff=threshold, workers=-1)
            rows, cols = mat.nonzero()
            for r, c in zip(rows.tolist(), cols.tolist()):
                a = start + r
                if c > a:
                    pairs.add((a, c))
    else:
        thr = threshold / 100.0
        blocks = defaultdict(list)
        for k, t in enumerate(keys):
            w = t.split()
            blocks["P:" + " ".join(w[:2])].append(k)
            blocks["S:" + " ".join(w[-2:])].append(k)
        for members in blocks.values():
            if len(members) < 2:
                continue
            for x in range(len(members)):
                for y in range(x + 1, len(members)):
                    a, b = members[x], members[y]
                    key = (min(a, b), max(a, b))
                    if key in pairs:
                        continue
                    ta, tb = keys[a], keys[b]
                    if min(len(ta), len(tb)) / max(len(ta), len(tb)) < thr - 0.05:
                        continue
                    sm = SequenceMatcher(None, ta, tb, autojunk=False)
                    if sm.real_quick_ratio() >= thr and sm.quick_ratio() >= thr and sm.ratio() >= thr:
                        pairs.add(key)
    out = [(uniq[keys[a]][0], uniq[keys[b]][0]) for a, b in pairs]
    for idxs in uniq.values():  # títulos idénticos dentro de cada grupo
        out.extend((idxs[0], j) for j in idxs[1:])
    return out


def _completeness(df: pd.DataFrame) -> list[int]:
    return (
        (df["abstract"].str.len() > 50).astype(int) * 4
        + df["doi"].map(lambda s: bool(normalize_doi(s))).astype(int) * 3
        + df["year"].notna().astype(int) * 2
        + (df["keywords"].str.len() > 0).astype(int)
        + (df["authors"].str.len() > 0).astype(int)
    ).tolist()


def deduplicate(df: pd.DataFrame, by_doi=True, by_title=True, title_mode="normalized",
                fuzzy=False, threshold=95):
    """
    Marca duplicados con union-find (DOI, título, título similar).
    De cada grupo conserva el registro más completo (abstract, DOI, año, keywords, autores).
    Nunca fusiona por título dos registros que tienen DOI válidos y distintos.
    Restablece las columnas de cribado automático (hay que volver a cribar).
    """
    d = ensure_columns(df.copy())
    n = len(d)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    dois = d["doi"].map(normalize_doi).tolist()
    if title_mode == "normalized":
        titles = d["title"].map(normalize_title).tolist()
    else:
        titles = d["title"].map(lambda s: str(s).strip().lower()).tolist()

    def compatible(i, j):
        return not (dois[i] and dois[j] and dois[i] != dois[j])

    years = pd.to_numeric(d["year"], errors="coerce").tolist()
    numbers = [frozenset(_TITLE_NUMBERS.findall(t)) for t in titles]

    def compatible_fuzzy(i, j):
        """Títulos similares: además exige los mismos números (Part 1 ≠ Part 2) y años a ≤1 de distancia."""
        if not compatible(i, j) or numbers[i] != numbers[j]:
            return False
        yi, yj = years[i], years[j]
        return pd.isna(yi) or pd.isna(yj) or abs(yi - yj) <= 1

    if by_doi:
        first = {}
        for i, x in enumerate(dois):
            if x:
                if x in first:
                    union(first[x], i)
                else:
                    first[x] = i
    if by_title:
        groups = defaultdict(list)
        for i, t in enumerate(titles):
            if len(t) >= MIN_TITLE_LEN:
                groups[t].append(i)
        for members in groups.values():
            for k, j in enumerate(members[1:], start=1):
                for i in members[:k]:
                    if compatible(i, j):
                        union(i, j)
                        break
    if fuzzy:
        for i, j in fuzzy_title_pairs(titles, threshold):
            if compatible_fuzzy(i, j):
                union(i, j)

    comp = _completeness(d)
    rids = d["record_id"].tolist()
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    is_dup = ["Unique"] * n
    dup_of = [""] * n
    reason = [""] * n
    for members in groups.values():
        if len(members) < 2:
            continue
        keeper = max(members, key=lambda i: (comp[i], -i))
        for m in members:
            if m == keeper:
                continue
            is_dup[m] = "Duplicate"
            dup_of[m] = rids[keeper]
            if dois[m] and dois[m] == dois[keeper]:
                reason[m] = "DOI idéntico"
            elif titles[m] == titles[keeper] and len(titles[m]) >= MIN_TITLE_LEN:
                reason[m] = "Título idéntico"
            elif not fuzzy:
                reason[m] = "Grupo de duplicados (transitivo)"
            else:
                reason[m] = "Título similar"

    d["Is_Duplicate"] = is_dup
    d["Duplicate_Of"] = dup_of
    d["Duplicate_Reason"] = reason
    for c in AUTO_COLS:
        d[c] = ""
    d = compute_status(d)
    stats = {
        "total": n,
        "duplicates_doi": reason.count("DOI idéntico"),
        "duplicates_title": reason.count("Título idéntico"),
        "duplicates_fuzzy": reason.count("Título similar"),
        "duplicates_other": reason.count("Grupo de duplicados (transitivo)"),
        "duplicates_total": is_dup.count("Duplicate"),
        "unique": is_dup.count("Unique"),
        "fuzzy_engine": ("rapidfuzz" if HAS_RAPIDFUZZ else "difflib") if fuzzy else "",
    }
    return d, stats


# ══════════════════════════════════════════════════════════════════════════════
# CRIBADO AUTOMÁTICO
# ══════════════════════════════════════════════════════════════════════════════
def _to_int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def normalize_config(cfg: dict | None) -> dict:
    c = dict(DEFAULT_SCREEN_CFG)
    c.update({k: v for k, v in (cfg or {}).items() if v is not None})
    c["year_from"] = _to_int(c.get("year_from"))
    c["year_to"] = _to_int(c.get("year_to"))
    c["min_blocks"] = _to_int(c.get("min_blocks"), 0) or 0
    if c["exclude_mode"] not in EXCLUDE_MODES:
        c["exclude_mode"] = "balanced"
    if c["missing_year"] not in MISSING_YEAR_MODES:
        c["missing_year"] = "review"
    c["auto_plural"] = bool(c.get("auto_plural", True))
    c["review_near_miss"] = bool(c.get("review_near_miss", False))
    c["search_blocks"] = {str(k): {"label": str(v.get("label", k)), "terms": str(v.get("terms", ""))}
                          for k, v in (c.get("search_blocks") or {}).items() if isinstance(v, dict)}
    return c


def active_blocks(cfg: dict):
    ap = cfg.get("auto_plural", True)
    out = []
    for bid, b in (cfg.get("search_blocks") or {}).items():
        p = compile_terms(parse_terms(b.get("terms", "")), ap)
        if p is not None:
            out.append((bid, p))
    return out


def run_screening(df: pd.DataFrame, cfg: dict):
    """
    Aplica los filtros automáticos en orden; cada registro queda con la PRIMERA razón de exclusión.
    Las decisiones manuales (TA_*/FT_*) se conservan.
    Retorna (df, step_counts).
    """
    cfg = normalize_config(cfg)
    d = ensure_columns(df.copy())
    for c in AUTO_COLS:
        d[c] = ""
    dup = d["Is_Duplicate"].eq("Duplicate")
    d.loc[dup, "Auto_Decision"] = EXCLUDE
    d.loc[dup, "Auto_Stage"] = STAGE_DUP
    d.loc[dup, "Auto_Reason"] = d.loc[dup, "Duplicate_Reason"]

    w = d.loc[~dup]
    steps = {"input": int(len(w)), "year_out": 0, "year_missing_excluded": 0, "year_missing_review": 0,
             "doc_type": 0, "language": 0, "required": 0, "secondary": 0, "exclude_terms": 0, "exclude_review": 0,
             "blocks": 0, "near_miss_review": 0, "review": 0, "include": 0}
    if w.empty:
        return compute_status(d), steps

    idx = w.index
    ap = cfg["auto_plural"]
    t_title = w["title"].map(normalize_text)
    t_abs = w["abstract"].map(normalize_text)
    t_kw = w["keywords"].map(normalize_text)
    text_all = t_title + " " + t_abs + " " + t_kw
    text_tk = t_title + " " + t_kw

    decision = pd.Series("", index=idx, dtype=object)
    stage = pd.Series("", index=idx, dtype=object)
    reason = pd.Series("", index=idx, dtype=object)
    review = pd.Series("", index=idx, dtype=object)

    def exclude(mask, st, rs):
        m = mask & decision.eq("")
        decision.loc[m] = EXCLUDE
        stage.loc[m] = st
        reason.loc[m] = rs if isinstance(rs, str) else rs.loc[m]
        return int(m.sum())

    def flag(mask, rs):
        m = mask & decision.eq("")
        if not m.any():
            return 0
        add = rs if isinstance(rs, str) else rs.loc[m]
        review.loc[m] = (review.loc[m] + " | " + add).str.lstrip(" |")
        return int(m.sum())

    # 1 — Año
    yf, yt = cfg["year_from"], cfg["year_to"]
    year = pd.to_numeric(w["year"], errors="coerce")
    missing = year.isna()
    if yf is not None or yt is not None:
        out = pd.Series(False, index=idx)
        if yf is not None:
            out |= ~missing & (year < yf)
        if yt is not None:
            out |= ~missing & (year > yt)
        steps["year_out"] = exclude(out, STAGE_YEAR, f"Fuera del rango {yf or '…'}–{yt or '…'}")
        if cfg["missing_year"] == "exclude":
            steps["year_missing_excluded"] = exclude(missing, STAGE_NOYEAR, "Año faltante")
        elif cfg["missing_year"] == "review":
            steps["year_missing_review"] = flag(missing, "Año faltante: verificar")

    # 2 — Tipo de documento (coincidencia exacta por parte, p. ej. 'Article; Proceedings Paper').
    #     Registros sin tipo o sin idioma no se excluyen (no hay dato para decidir).
    doc_parts = w["doc_type"].map(lambda s: canon_list(s, "doctype"))
    inc_types = set(canon_list(cfg["doc_include"], "doctype"))
    if inc_types:
        miss = doc_parts.map(lambda ps: bool(ps) and not any(p in inc_types for p in ps)).astype(bool)
        steps["doc_type"] += exclude(miss, STAGE_DOCTYPE, "Tipo de documento no permitido: " + w["doc_type"])
    exc_types = set(canon_list(cfg["doc_exclude"], "doctype"))
    if exc_types:
        hit = doc_parts.map(lambda ps: next((p for p in ps if p in exc_types), ""))
        steps["doc_type"] += exclude(hit.ne(""), STAGE_DOCTYPE, "Tipo de documento excluido: " + hit)

    # 2b — Idioma
    langs = set(canon_list(cfg["languages"], "language"))
    if langs:
        lp = w["language"].map(lambda s: canon_list(s, "language"))
        bad = lp.map(lambda ps: bool(ps) and not any(p in langs for p in ps)).astype(bool)
        steps["language"] = exclude(bad, STAGE_LANG, "Idioma no permitido: " + w["language"])

    # 3 — Bloque obligatorio
    p_req = compile_terms(parse_terms(cfg["kw_required"]), ap)
    if p_req is not None:
        d.loc[idx, "Matched_Required"] = _found(text_all, p_req)
        steps["required"] = exclude(~_contains(text_all, p_req), STAGE_REQ, "Sin términos del bloque obligatorio")

    # 4 — Bloque secundario
    p_sec = compile_terms(parse_terms(cfg["kw_secondary"]), ap)
    if p_sec is not None:
        d.loc[idx, "Matched_Secondary"] = _found(text_all, p_sec)
        steps["secondary"] = exclude(~_contains(text_all, p_sec), STAGE_SEC, "Sin términos del bloque secundario")

    # 5 — Términos de exclusión
    p_exc = compile_terms(parse_terms(cfg["kw_exclude"]), ap)
    if p_exc is not None:
        hits_all = _found(text_all, p_exc)
        d.loc[idx, "Matched_Exclude"] = hits_all
        in_tk = _contains(text_tk, p_exc)
        in_abs = _contains(t_abs, p_exc)
        mode = cfg["exclude_mode"]
        if mode == "strict":
            steps["exclude_terms"] = exclude(in_tk | in_abs, STAGE_EXC, "Término de exclusión: " + hits_all)
        elif mode == "balanced":
            steps["exclude_terms"] = exclude(in_tk, STAGE_EXC,
                                             "Término de exclusión en título/keywords: " + _found(text_tk, p_exc))
            steps["exclude_review"] = flag(in_abs & ~in_tk,
                                           "Término de exclusión solo en el abstract: " + _found(t_abs, p_exc))
        else:
            steps["exclude_review"] = flag(in_tk | in_abs, "Contiene término de exclusión: " + hits_all)

    # 6 — Bloques de la cadena de búsqueda
    blocks = active_blocks(cfg)
    if blocks:
        n_act = len(blocks)
        min_eff = cfg["min_blocks"] if cfg["min_blocks"] > 0 else n_act
        min_eff = max(1, min(min_eff, n_act))
        hits = pd.DataFrame({bid: _contains(text_all, p) for bid, p in blocks}, index=idx)
        n_hit = hits.sum(axis=1).astype(int)
        cols = hits.columns.tolist()
        arr = hits.to_numpy()
        matched = pd.Series([", ".join(c for c, v in zip(cols, row) if v) for row in arr], index=idx)
        missing_b = pd.Series([", ".join(c for c, v in zip(cols, row) if not v) for row in arr], index=idx)
        d.loc[idx, "Matched_Blocks"] = matched
        d.loc[idx, "Missing_Blocks"] = missing_b
        d.loc[idx, "N_Blocks"] = n_hit.astype(str) + f"/{n_act}"
        fail = n_hit < min_eff
        if cfg["review_near_miss"] and min_eff > 1:
            near = fail & n_hit.eq(min_eff - 1)
            steps["near_miss_review"] = flag(near, f"Casi cumple los bloques ({min_eff - 1}/{min_eff})")
            fail = fail & ~near
        rs = ("Cumple " + n_hit.astype(str) + f"/{n_act} bloques (mínimo {min_eff}). Faltan: " + missing_b)
        steps["blocks"] = exclude(fail, STAGE_BLOCKS, rs)

    # 7 — Resultado
    rest = decision.eq("")
    to_review = rest & review.ne("")
    decision.loc[to_review] = REVIEW
    stage.loc[to_review] = STAGE_REVIEW
    reason.loc[to_review] = review.loc[to_review]
    ok = rest & ~to_review
    decision.loc[ok] = INCLUDE
    stage.loc[ok] = STAGE_PASS
    reason.loc[ok] = "Cumple todos los criterios automáticos"
    steps["review"] = int(to_review.sum())
    steps["include"] = int(ok.sum())

    d.loc[idx, "Auto_Decision"] = decision
    d.loc[idx, "Auto_Stage"] = stage
    d.loc[idx, "Auto_Reason"] = reason
    return compute_status(d), steps


# ══════════════════════════════════════════════════════════════════════════════
# ESTADO PRISMA 2020 Y CONTEOS
# ══════════════════════════════════════════════════════════════════════════════
def effective_ta(df: pd.DataFrame) -> pd.Series:
    """Decisión de cribado efectiva: manual si existe; si no, la automática (Include) o Pending."""
    ta = df["TA_Decision"]
    auto_default = df["Auto_Decision"].map(lambda a: INCLUDE if a == INCLUDE else PENDING)
    return ta.where(ta.ne(""), auto_default)


def compute_status(df: pd.DataFrame) -> pd.DataFrame:
    d = ensure_columns(df)
    dup = d["Is_Duplicate"].eq("Duplicate")
    auto = d["Auto_Decision"]
    ta = d["TA_Decision"]
    ft = d["FT_Decision"]
    rescued = ~dup & auto.eq(EXCLUDE) & ta.isin([INCLUDE, MAYBE])
    screened = ~dup & (auto.isin([INCLUDE, REVIEW]) | rescued)
    ta_eff = effective_ta(d)

    status = pd.Series(STATUS_UNSCREENED, index=d.index, dtype=object)
    stage = pd.Series("Sin cribar", index=d.index, dtype=object)

    def put(mask, st, sg):
        status.loc[mask] = st
        stage.loc[mask] = sg

    put(dup, STATUS_DUP, "Identificación")
    put(~dup & ~screened & auto.ne(""), STATUS_EXC_AUTO, "Identificación (antes del cribado)")
    put(screened & ta_eff.eq(EXCLUDE), STATUS_EXC_TA, "Cribado")
    put(screened & ta_eff.isin([PENDING, MAYBE]), STATUS_PENDING, "Cribado")
    sought = screened & ta_eff.eq(INCLUDE)
    put(sought & ft.eq(NOT_RETRIEVED), STATUS_NOT_RETRIEVED, "Recuperación")
    put(sought & ft.eq(EXCLUDE), STATUS_EXC_FT, "Elegibilidad")
    put(sought & ~ft.isin([NOT_RETRIEVED, EXCLUDE]), STATUS_INCLUDED, "Incluidos")
    d["Status"] = status
    d["PRISMA_Stage"] = stage
    return d


def _reason_counts(series: pd.Series) -> dict:
    s = series.replace("", "Sin razón especificada")
    return {str(k): int(v) for k, v in s.value_counts().items()}


def compute_counts(df: pd.DataFrame) -> dict:
    d = df
    st = d["Status"]
    auto_exc = st.eq(STATUS_EXC_AUTO)
    stage = d["Auto_Stage"]
    dup = st.eq(STATUS_DUP)
    sources = {str(s): int((d["source"] == s).sum()) for s in d["source"].unique()}
    c = {
        "sources": sources,
        "identified_total": int(len(d)),
        "duplicates_total": int(dup.sum()),
        "duplicates_doi": int((dup & d["Duplicate_Reason"].eq("DOI idéntico")).sum()),
        "duplicates_title": int((dup & d["Duplicate_Reason"].eq("Título idéntico")).sum()),
        "duplicates_fuzzy": int((dup & d["Duplicate_Reason"].isin(["Título similar", "Grupo de duplicados (transitivo)"])).sum()),
        "excluded_year": int((auto_exc & stage.eq(STAGE_YEAR)).sum()),
        "excluded_missing_year": int((auto_exc & stage.eq(STAGE_NOYEAR)).sum()),
        "excluded_doc_type": int((auto_exc & stage.eq(STAGE_DOCTYPE)).sum()),
        "excluded_language": int((auto_exc & stage.eq(STAGE_LANG)).sum()),
        "excluded_required": int((auto_exc & stage.eq(STAGE_REQ)).sum()),
        "excluded_secondary": int((auto_exc & stage.eq(STAGE_SEC)).sum()),
        "excluded_terms": int((auto_exc & stage.eq(STAGE_EXC)).sum()),
        "excluded_blocks": int((auto_exc & stage.eq(STAGE_BLOCKS)).sum()),
        "not_screened": int(st.eq(STATUS_UNSCREENED).sum()),
        "records_screened": int(st.isin(SCREENED_STATUSES).sum()),
        "screened_auto_review": int((st.isin(SCREENED_STATUSES) & d["Auto_Decision"].eq(REVIEW)).sum()),
        "rescued": int((st.isin(SCREENED_STATUSES) & d["Auto_Decision"].eq(EXCLUDE)).sum()),
        "manual_ta_done": int((st.isin(SCREENED_STATUSES) & d["TA_Decision"].ne("")).sum()),
        "excluded_screening": int(st.eq(STATUS_EXC_TA).sum()),
        "excluded_screening_reasons": _reason_counts(d.loc[st.eq(STATUS_EXC_TA), "TA_Reason"]),
        "pending": int(st.eq(STATUS_PENDING).sum()),
        "reports_sought": int(st.isin([STATUS_NOT_RETRIEVED, STATUS_EXC_FT, STATUS_INCLUDED]).sum()),
        "not_retrieved": int(st.eq(STATUS_NOT_RETRIEVED).sum()),
        "reports_assessed": int(st.isin([STATUS_EXC_FT, STATUS_INCLUDED]).sum()),
        "excluded_fulltext": int(st.eq(STATUS_EXC_FT).sum()),
        "excluded_fulltext_reasons": _reason_counts(d.loc[st.eq(STATUS_EXC_FT), "FT_Reason"]),
        "included": int(st.eq(STATUS_INCLUDED).sum()),
        "ft_pending": int((st.eq(STATUS_INCLUDED) & d["FT_Decision"].eq("")).sum()),
        "included_by_source": {str(s): int((st.eq(STATUS_INCLUDED) & d["source"].eq(s)).sum())
                               for s in d["source"].unique()},
    }
    c["removed_other"] = (c["excluded_year"] + c["excluded_missing_year"] + c["excluded_doc_type"]
                          + c["excluded_language"])
    c["removed_automation"] = (c["excluded_required"] + c["excluded_secondary"]
                               + c["excluded_terms"] + c["excluded_blocks"])
    c["unique"] = c["identified_total"] - c["duplicates_total"]
    return c


# ══════════════════════════════════════════════════════════════════════════════
# SEGUNDO REVISOR Y κ DE COHEN
# ══════════════════════════════════════════════════════════════════════════════
DECISION_ALIASES = {
    "include": INCLUDE, "incluir": INCLUDE, "incluido": INCLUDE, "incluye": INCLUDE, "i": INCLUDE,
    "si": INCLUDE, "yes": INCLUDE, "y": INCLUDE, "1": INCLUDE,
    "exclude": EXCLUDE, "excluir": EXCLUDE, "excluido": EXCLUDE, "excluye": EXCLUDE, "e": EXCLUDE,
    "no": EXCLUDE, "n": EXCLUDE, "0": EXCLUDE,
    "maybe": MAYBE, "dudoso": MAYBE, "duda": MAYBE, "d": MAYBE, "?": MAYBE, "quizas": MAYBE, "m": MAYBE,
}


def parse_decision(v) -> str:
    return DECISION_ALIASES.get(normalize_text(v), "")


def cohen_kappa(a: list, b: list) -> float | None:
    n = len(a)
    if n == 0 or n != len(b):
        return None
    labels = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    if pe >= 1:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret_kappa(k: float | None) -> str:
    if k is None:
        return "—"
    if k < 0:
        return "Pobre (peor que el azar)"
    for lim, txt in [(0.20, "Leve"), (0.40, "Aceptable"), (0.60, "Moderado"),
                     (0.80, "Sustancial"), (1.01, "Casi perfecto")]:
        if k <= lim:
            return txt
    return "Casi perfecto"


def reviewer_sheet(df: pd.DataFrame) -> pd.DataFrame:
    m = df["Status"].isin(SCREENED_STATUSES)
    out = df.loc[m, ["record_id", "source", "year", "title", "keywords", "abstract"]].copy()
    out["Decision_R2"] = ""
    out["Reason_R2"] = ""
    return out.map(clean_cell)


def import_reviewer_sheet(path) -> tuple[pd.DataFrame, int]:
    p = str(path)
    if p.lower().endswith(".csv"):
        raw = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    else:
        raw = pd.read_excel(p, dtype=str)
    raw.columns = [str(c).strip() for c in raw.columns]
    if "record_id" not in raw.columns or "Decision_R2" not in raw.columns:
        raise ValueError("La hoja debe tener las columnas 'record_id' y 'Decision_R2'.")
    raw = raw.fillna("")
    raw["code"] = raw["Decision_R2"].map(parse_decision)
    invalid = int(((raw["Decision_R2"].str.strip() != "") & (raw["code"] == "")).sum())
    out = raw[raw["code"] != ""][["record_id", "code"]].rename(columns={"code": "TA_Decision_R2"})
    out["TA_Reason_R2"] = raw.loc[out.index, "Reason_R2"] if "Reason_R2" in raw.columns else ""
    return out, invalid


def compare_reviewers(df: pd.DataFrame) -> dict:
    screened = df["Status"].isin(SCREENED_STATUSES)
    r1_manual = df["TA_Decision"]
    r1 = r1_manual.where(r1_manual.ne(""), df["Auto_Decision"].map(lambda a: INCLUDE if a == INCLUDE else ""))
    r2 = df["TA_Decision_R2"]
    both = screened & r1.ne("") & r2.ne("")
    a, b = r1[both].tolist(), r2[both].tolist()
    k = cohen_kappa(a, b)
    agree = sum(1 for x, y in zip(a, b) if x == y)
    dis_mask = both & (r1 != r2)
    dis = df.loc[dis_mask, ["record_id", "title", "TA_Reason", "TA_Reason_R2"]].copy()
    dis.insert(2, "Revisor_1", r1[dis_mask])
    dis.insert(3, "Revisor_2", r2[dis_mask])
    return {
        "n": len(a),
        "agreement": agree / len(a) if a else None,
        "kappa": k,
        "interpretation": interpret_kappa(k),
        "r1_from_auto": int((both & r1_manual.eq("")).sum()),
        "disagreements": dis,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CADENAS DE BÚSQUEDA SCOPUS / WOS → BLOQUES
# ══════════════════════════════════════════════════════════════════════════════
_FIELD_OPEN = re.compile(r"\b(?:TITLE-ABS-KEY-AUTH|TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTHKEY|INDEXTERMS|ALL|SRCTITLE)\s*\(", re.I)
_WOS_FIELD = re.compile(r"\b(?:TS|TI|AB|AK|KP|ALL)\s*=\s*", re.I)
_REMOVE_CALLS = ["LIMIT-TO", "EXCLUDE", "DOCTYPE", "LANGUAGE", "SUBJAREA", "SRCTYPE", "PUBSTAGE",
                 "AFFILCOUNTRY", "EXACTKEYWORD", "EXACTSRCTITLE", "PUBDATETXT", "OPENACCESS", "AFFIL", "AUTH"]
_TOKEN = re.compile(
    r'\s*(?:(?P<lp>\()|(?P<rp>\))|"(?P<q>[^"]*)"|\{(?P<b>[^}]*)\}|(?P<andnot>AND\s+NOT\b)|(?P<and>AND\b)|'
    r'(?P<or>OR\b)|(?P<not>NOT\b)|(?P<prox>(?:W|PRE|NEAR)/\d+|NEAR\b|SAME\b)|(?P<w>[^\s()"{}]+))', re.I)


def _remove_calls(q: str):
    pat = re.compile(r"\b(" + "|".join(re.escape(n) for n in _REMOVE_CALLS) + r")\s*\(", re.I)
    removed = []
    while True:
        m = pat.search(q)
        if not m:
            break
        depth, i = 1, m.end()
        while i < len(q) and depth:
            if q[i] == "(":
                depth += 1
            elif q[i] == ")":
                depth -= 1
            i += 1
        removed.append(q[m.start():i].strip())
        q = q[:m.start()] + " " + q[i:]
    return q, removed


def _extract_years(q: str):
    yf = yt = None
    for m in re.finditer(r"\bPUBYEAR\s*(>=|<=|>|<|=|AFT|BEF|IS)\s*(\d{4})", q, re.I):
        op, y = m.group(1).upper(), int(m.group(2))
        if op in (">", "AFT"):
            yf = y + 1
        elif op == ">=":
            yf = y
        elif op in ("<", "BEF"):
            yt = y - 1
        elif op == "<=":
            yt = y
        else:
            yf = yt = y
    q = re.sub(r"\bPUBYEAR\s*(>=|<=|>|<|=|AFT|BEF|IS)\s*\d{4}", " ", q, flags=re.I)
    for m in re.finditer(r"\bPY\s*=\s*\(?\s*(\d{4})(?:\s*-\s*(\d{4}))?\s*\)?", q, re.I):
        yf = int(m.group(1))
        yt = int(m.group(2) or m.group(1))
    q = re.sub(r"\bPY\s*=\s*\(?\s*\d{4}(?:\s*-\s*\d{4})?\s*\)?", " ", q, flags=re.I)
    return q, yf, yt


def _tokenize(q: str):
    toks, pos = [], 0
    while pos < len(q):
        m = _TOKEN.match(q, pos)
        if not m or m.end() == pos:
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        if kind is None:
            continue
        toks.append((kind, m.group(kind)))
    return toks


class _QueryParser:
    """Precedencia Scopus: OR > AND/proximidad > AND NOT."""

    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i][0] if self.i < len(self.t) else None

    def take(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def parse(self):
        nodes = []
        while self.peek() is not None:
            start = self.i
            if self.peek() == "rp":
                self.take()
                continue
            n = self.andnot()
            if n is not None:
                nodes.append(n)
            if self.i == start:
                self.take()
        if not nodes:
            return None
        return nodes[0] if len(nodes) == 1 else ("and", nodes)

    def andnot(self):
        left = self.and_()
        negs = []
        while self.peek() in ("andnot", "not"):
            self.take()
            n = self.and_()
            if n is not None:
                negs.append(n)
        if negs:
            return ("not", left, negs)
        return left

    def and_(self):
        items = [self.or_()]
        while self.peek() in ("and", "prox"):
            self.take()
            items.append(self.or_())
        items = [x for x in items if x is not None]
        if not items:
            return None
        return items[0] if len(items) == 1 else ("and", items)

    def or_(self):
        items = [self.atom()]
        while self.peek() == "or":
            self.take()
            items.append(self.atom())
        items = [x for x in items if x is not None]
        if not items:
            return None
        return items[0] if len(items) == 1 else ("or", items)

    def atom(self):
        k = self.peek()
        if k == "lp":
            self.take()
            n = self.andnot()
            while self.peek() not in (None, "rp"):  # tolera basura dentro del paréntesis
                extra = self.andnot()
                if extra is None:
                    self.take()
                else:
                    n = ("and", [x for x in (n, extra) if x is not None])
            if self.peek() == "rp":
                self.take()
            return n
        if k in ("q", "b"):
            return ("term", self.take()[1])
        if k == "w":
            words = [self.take()[1]]
            while self.peek() == "w":
                words.append(self.take()[1])
            return ("term", " ".join(words))
        return None


def _leaves(n) -> list[str]:
    if n is None:
        return []
    if n[0] == "term":
        return [n[1]]
    if n[0] == "not":
        return _leaves(n[1])
    return [x for c in n[1] for x in _leaves(c)]


def _negs(n) -> list[str]:
    if n is None or n[0] == "term":
        return []
    if n[0] == "not":
        return [x for g in n[2] for x in _leaves(g)] + _negs(n[1])
    return [x for c in n[1] for x in _negs(c)]


def _conjuncts(n):
    if n is None:
        return []
    if n[0] == "and":
        return [x for c in n[1] for x in _conjuncts(c)]
    if n[0] == "not":
        return _conjuncts(n[1])
    return [n]


def _has_inner_and(n) -> bool:
    if n is None or n[0] == "term":
        return False
    if n[0] == "and":
        return True
    if n[0] == "not":
        return _has_inner_and(n[1])
    return any(_has_inner_and(c) for c in n[1])


_QUERY_START = re.compile(r'^"?\s*(?:TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTHKEY|ALL|TS|TI|AB|AK)\s*[=(]', re.I)
_REFINE_RE = re.compile(r"\b(?:Refined\s+by|Refine|Refinado\s+por|Refinar(?:\s+por)?)\s*:", re.I)


def split_queries(text: str) -> list[str]:
    """
    Separa varias cadenas pegadas juntas (p. ej. la de WoS y la de Scopus), aunque vengan
    envueltas en comillas ("…""…"). Una cadena nueva empieza en una línea con código de campo
    (TS=, TITLE-ABS-KEY(…)) cuando los paréntesis anteriores ya están cerrados.
    """
    t = (text.replace("“", '"').replace("”", '"').replace("’", "'")
         .replace("‘", "'").replace('""', "\n"))
    queries, cur, depth = [], [], 0
    for line in t.splitlines():
        s = line.strip()
        if not s:
            continue
        if cur and depth == 0 and _QUERY_START.match(s) and not re.search(r"\b(?:AND|OR|NOT)\s*$", cur[-1], re.I):
            queries.append("\n".join(cur))
            cur = []
        cur.append(s)
        depth = max(0, depth + s.count("(") - s.count(")"))
    if cur:
        queries.append("\n".join(cur))
    out = []
    for q in queries:
        q = q.strip()
        if q.count('"') % 2 == 1 and q.startswith('"'):
            q = q[1:]
        if q.count('"') % 2 == 1 and q.endswith('"'):
            q = q[:-1]
        if q.strip():
            out.append(q.strip())
    return out


def _extract_refine(q: str):
    """Línea 'Refine:' de WoS: años, tipos de documento e idiomas."""
    info = {"years": [], "doc_include": [], "languages": []}
    m = _REFINE_RE.search(q)
    if not m:
        return q, info
    ref, q = q[m.end():], q[:m.start()]
    ym = re.search(r"(?:Publication\s+Years?|A[nñ]os?\s+de\s+publicaci[oó]n)\s*:?\s*([0-9 ,–—\-]+|[0-9 OR]+)",
                   ref, re.I)
    if ym:
        info["years"] = [int(y) for y in re.findall(r"\d{4}", ym.group(1))]
    dm = re.search(r"(?:Document\s+Types?|Tipos?\s+de\s+documentos?)\s*:?\s*([^;\n]+)", ref, re.I)
    if dm:
        info["doc_include"] = canon_list(dm.group(1), "doctype")
    lm = re.search(r"(?:Languages?|Idiomas?)\s*:?\s*([^;\n]+)", ref, re.I)
    if lm:
        info["languages"] = canon_list(lm.group(1), "language")
    return q, info


def _extract_wos_inline(q: str):
    """Filtros WoS dentro de la cadena: DT=(…) y LA=(…)."""
    dts, las = [], []
    for m in re.finditer(r"\bDT\s*=\s*\(([^)]*)\)", q, re.I):
        dts += canon_list(m.group(1), "doctype")
    for m in re.finditer(r"\bLA\s*=\s*\(([^)]*)\)", q, re.I):
        las += canon_list(m.group(1), "language")
    q = re.sub(r"\b(?:DT|LA)\s*=\s*\([^)]*\)", " ", q, flags=re.I)
    return q, dts, las


def _limits_from_removed(removed: list[str]):
    """Traduce LIMIT-TO / EXCLUDE / DOCTYPE() / LANGUAGE() de Scopus a criterios."""
    inc, exc, langs, years, ignored = [], [], [], [], []
    for r in removed:
        found = False
        for m in re.finditer(r'(LIMIT-TO|EXCLUDE)\s*\(\s*(DOCTYPE|LANGUAGE|PUBYEAR)\s*,\s*"?([^",)]+)"?', r, re.I):
            found = True
            kind, field, val = m.group(1).upper(), m.group(2).upper(), m.group(3).strip()
            if field == "DOCTYPE":
                name = canon_list(SCOPUS_DOCTYPES.get(val.lower(), val), "doctype")
                (inc if kind == "LIMIT-TO" else exc).extend(name)
            elif field == "LANGUAGE":
                if kind == "LIMIT-TO":
                    langs.extend(canon_list(val, "language"))
                else:
                    ignored.append(r)
            elif field == "PUBYEAR" and kind == "LIMIT-TO" and val.isdigit():
                years.append(int(val))
        m = re.match(r'(DOCTYPE|LANGUAGE)\s*\(\s*"?([^")]+)"?\s*\)', r, re.I)
        if m:
            found = True
            if m.group(1).upper() == "DOCTYPE":
                inc.extend(canon_list(SCOPUS_DOCTYPES.get(m.group(2).strip().lower(), m.group(2)), "doctype"))
            else:
                langs.extend(canon_list(m.group(2), "language"))
        if not found:
            ignored.append(r)
    return inc, exc, langs, years, ignored


def _parse_one_query(query: str) -> dict:
    warnings = []
    q, refine = _extract_refine(query)
    q, dt_inline, la_inline = _extract_wos_inline(q)
    q, removed = _remove_calls(q)
    inc, exc, langs, lim_years, ignored = _limits_from_removed(removed)
    q, yf, yt = _extract_years(q)
    years = refine["years"] + lim_years
    if years:
        yf = min(years) if yf is None else max(yf, min(years))
        yt = max(years) if yt is None else min(yt, max(years))
    q = _FIELD_OPEN.sub("(", q)
    q = _WOS_FIELD.sub(" ", q)
    toks = _tokenize(q)
    tree = _QueryParser(toks).parse()
    if tree is None:
        raise ValueError("No se encontraron términos en la cadena.")
    blocks = []
    for conj in _conjuncts(tree):
        terms = parse_terms(_leaves(conj))
        if not terms:
            continue
        if _has_inner_and(conj):
            warnings.append(f"B{len(blocks) + 1}: contiene AND anidado dentro de un OR; se aproximó como sinónimos.")
        blocks.append(terms)
    if any(t[0] == "prox" for t in toks):
        warnings.append("Los operadores de proximidad (W/n, PRE/n, NEAR) se trataron como AND.")
    if ignored:
        warnings.append("Filtros de la base de datos sin equivalente (ignorados): " + "; ".join(ignored[:5])
                        + (" …" if len(ignored) > 5 else ""))
    return {"blocks": blocks, "exclude": parse_terms(_negs(tree)), "year_from": yf, "year_to": yt,
            "doc_include": list(dict.fromkeys(refine["doc_include"] + dt_inline + inc)),
            "doc_exclude": list(dict.fromkeys(exc)),
            "languages": list(dict.fromkeys(refine["languages"] + la_inline + langs)),
            "warnings": warnings}


def parse_search_query(text: str) -> dict:
    """
    Convierte una o varias cadenas booleanas Scopus/WoS en criterios de cribado:
      · cada grupo unido por AND en el nivel superior → un bloque (sus OR → sinónimos)
      · AND NOT → términos de exclusión
      · PUBYEAR / PY= / LIMIT-TO(PUBYEAR) / 'Publication Years' → rango de años
      · LIMIT-TO(DOCTYPE) / DT=( ) / 'Document Types' → tipos de documento permitidos
      · LIMIT-TO(LANGUAGE) / LA=( ) / 'Languages' → idiomas permitidos
    Si se pegan varias cadenas (p. ej. WoS + Scopus) los bloques se combinan por posición.
    """
    queries = split_queries(text)
    if not queries:
        raise ValueError("No se encontraron términos en la cadena.")
    results = []
    for k, q in enumerate(queries, start=1):
        try:
            results.append(_parse_one_query(q))
        except ValueError as e:
            raise ValueError(f"Cadena {k}: {e}") from None
    warnings = []
    multi = len(results) > 1
    for k, r in enumerate(results, start=1):
        warnings += [f"Cadena {k}: {w}" if multi else w for w in r["warnings"]]
    sizes = {len(r["blocks"]) for r in results}
    if len(sizes) > 1:
        warnings.append("Las cadenas tienen distinto número de bloques; se combinaron por posición.")
    blocks = {}
    for i in range(max(sizes)):
        terms = parse_terms([t for r in results if i < len(r["blocks"]) for t in r["blocks"][i]])
        blocks[f"B{i + 1}"] = {"label": f"Bloque {i + 1} — {terms[0]}", "terms": ", ".join(terms)}
    yfs = [r["year_from"] for r in results if r["year_from"] is not None]
    yts = [r["year_to"] for r in results if r["year_to"] is not None]
    if len(set(yfs)) > 1 or len(set(yts)) > 1:
        warnings.append("Las cadenas tienen rangos de años distintos; se usó el más amplio.")

    def union(key):
        return ", ".join(dict.fromkeys(x for r in results for x in r[key]))
    return {"search_blocks": blocks, "min_blocks": len(blocks), "kw_exclude": union("exclude"),
            "year_from": min(yfs) if yfs else None, "year_to": max(yts) if yts else None,
            "doc_include": union("doc_include"), "doc_exclude": union("doc_exclude"),
            "languages": union("languages"), "n_queries": len(results), "warnings": warnings}


# ══════════════════════════════════════════════════════════════════════════════
# DIAGRAMA PRISMA 2020 (layout común para Tk, SVG y PNG)
# ══════════════════════════════════════════════════════════════════════════════
STYLE_COLORS = {
    "main": ("#4f46e5", "#eef2ff"),
    "exclude": ("#dc2626", "#fef2f2"),
    "included": ("#16a34a", "#f0fdf4"),
    "band_id": ("#4f46e5", "#e0e7ff"),
    "band_sc": ("#ca8a04", "#fef9c3"),
    "band_in": ("#16a34a", "#dcfce7"),
}


def prisma_layout(counts: dict, title: str = "") -> dict:
    W = 1000
    LX, LW, RX, RW = 90, 380, 530, 450
    LINE, PAD, GAP = 18, 12, 46
    boxes, arrows, bands = [], [], []
    y = 56 if title else 20

    def bh(lines):
        return PAD * 2 + LINE * len(lines)

    c = counts
    src_lines = [f"   {s}: n = {n}" for s, n in c.get("sources", {}).items()]
    row1_l = ["Registros identificados en bases de datos"] + src_lines + [f"Total: n = {c.get('identified_total', 0)}"]
    row1_r = [
        "Registros eliminados antes del cribado:",
        f"   Duplicados: n = {c.get('duplicates_total', 0)}",
        f"   Marcados no elegibles por herramientas automáticas: n = {c.get('removed_automation', 0)}",
        f"      · sin bloque obligatorio: {c.get('excluded_required', 0)}",
        f"      · sin bloque secundario: {c.get('excluded_secondary', 0)}",
        f"      · términos de exclusión: {c.get('excluded_terms', 0)}",
        f"      · bloques de búsqueda insuficientes: {c.get('excluded_blocks', 0)}",
        f"   Eliminados por otras razones: n = {c.get('removed_other', 0)}",
        f"      · fuera del rango de años: {c.get('excluded_year', 0)}",
        f"      · año faltante: {c.get('excluded_missing_year', 0)}",
        f"      · tipo de documento: {c.get('excluded_doc_type', 0)}",
        f"      · idioma: {c.get('excluded_language', 0)}",
    ]
    if c.get("not_screened"):
        row1_r.append(f"   Aún sin cribar: n = {c['not_screened']}")

    sc_l = ["Registros cribados (título / resumen)", f"n = {c.get('records_screened', 0)}"]
    if c.get("pending"):
        sc_l.append(f"Pendientes de decisión: n = {c['pending']}")
    sc_r = ["Registros excluidos en el cribado", f"n = {c.get('excluded_screening', 0)}"]
    sc_r += [f"   · {k}: {v}" for k, v in list(c.get("excluded_screening_reasons", {}).items())[:6]]

    rt_l = ["Reportes buscados para recuperación", f"n = {c.get('reports_sought', 0)}"]
    rt_r = ["Reportes no recuperados", f"n = {c.get('not_retrieved', 0)}"]

    el_l = ["Reportes evaluados para elegibilidad", f"n = {c.get('reports_assessed', 0)}"]
    el_r = ["Reportes excluidos (texto completo)", f"n = {c.get('excluded_fulltext', 0)}"]
    el_r += [f"   · {k}: {v}" for k, v in list(c.get("excluded_fulltext_reasons", {}).items())[:6]]

    in_l = ["Estudios incluidos en la revisión", f"n = {c.get('included', 0)}"]
    if c.get("ft_pending"):
        in_l.append(f"({c['ft_pending']} sin evaluación a texto completo)")

    rows = [(row1_l, row1_r, "main"), (sc_l, sc_r, "main"), (rt_l, rt_r, "main"),
            (el_l, el_r, "main"), (in_l, None, "included")]
    row_pos = []
    for left, right, style in rows:
        h = max(bh(left), bh(right) if right else 0)
        boxes.append({"x": LX, "y": y, "w": LW, "h": h, "lines": left, "style": style})
        if right:
            boxes.append({"x": RX, "y": y, "w": RW, "h": h, "lines": right, "style": "exclude"})
            arrows.append((LX + LW, y + h / 2, RX, y + h / 2))
        row_pos.append((y, h))
        y += h + GAP
    for (y0, h0), (y1, _) in zip(row_pos, row_pos[1:]):
        arrows.append((LX + LW / 2, y0 + h0, LX + LW / 2, y1))

    def band(r0, r1, label, style):
        top = row_pos[r0][0]
        bottom = row_pos[r1][0] + row_pos[r1][1]
        bands.append({"x": 20, "y": top, "w": 46, "h": bottom - top, "label": label, "style": style})

    band(0, 0, "Identificación", "band_id")
    band(1, 3, "Cribado", "band_sc")
    band(4, 4, "Incluidos", "band_in")
    return {"width": W, "height": y - GAP + 24, "boxes": boxes, "arrows": arrows, "bands": bands,
            "title": title, "line_h": LINE, "pad": PAD}


def _xml(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def layout_to_svg(lay: dict) -> str:
    W, H = lay["width"], lay["height"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="Arial, Helvetica, sans-serif">',
           '<defs><marker id="ah" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
           '<path d="M0,0 L10,4 L0,8 z" fill="#6b7280"/></marker></defs>',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    if lay.get("title"):
        out.append(f'<text x="{W / 2}" y="32" font-size="18" font-weight="bold" text-anchor="middle" '
                   f'fill="#1c1917">{_xml(lay["title"])}</text>')
    for b in lay["bands"]:
        stroke, fill = STYLE_COLORS[b["style"]]
        cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        out.append(f'<rect x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" rx="8" '
                   f'fill="{fill}" stroke="{stroke}"/>')
        out.append(f'<text x="{cx}" y="{cy}" font-size="13" font-weight="bold" fill="{stroke}" '
                   f'text-anchor="middle" dominant-baseline="middle" transform="rotate(-90 {cx} {cy})">'
                   f'{_xml(b["label"])}</text>')
    for b in lay["boxes"]:
        stroke, fill = STYLE_COLORS[b["style"]]
        out.append(f'<rect x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}" rx="8" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        for i, line in enumerate(b["lines"]):
            ty = b["y"] + lay["pad"] + lay["line_h"] * i + 13
            weight = "bold" if i == 0 else "normal"
            out.append(f'<text x="{b["x"] + 12}" y="{ty}" font-size="12" font-weight="{weight}" '
                       f'fill="#1c1917" xml:space="preserve">{_xml(line)}</text>')
    for x1, y1, x2, y2 in lay["arrows"]:
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2 - (4 if x2 > x1 else 0)}" '
                   f'y2="{y2 - (4 if y2 > y1 else 0)}" stroke="#6b7280" stroke-width="1.6" marker-end="url(#ah)"/>')
    out.append("</svg>")
    return "\n".join(out)


def layout_to_png(lay: dict, path, scale: int = 2):
    """Renderiza el diagrama a PNG con Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    def font(size, bold=False):
        names = (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"])
        for nm in names:
            try:
                return ImageFont.truetype(nm, size * scale)
            except OSError:
                continue
        return ImageFont.load_default()

    S = scale
    W, H = lay["width"] * S, lay["height"] * S
    img = Image.new("RGB", (int(W), int(H)), "white")
    dr = ImageDraw.Draw(img)
    f_reg, f_bold, f_band, f_title = font(12), font(12, True), font(13, True), font(18, True)
    if lay.get("title"):
        tw = dr.textlength(lay["title"], font=f_title)
        dr.text(((W - tw) / 2, 16 * S), lay["title"], fill="#1c1917", font=f_title)
    for b in lay["bands"]:
        stroke, fill = STYLE_COLORS[b["style"]]
        box = [b["x"] * S, b["y"] * S, (b["x"] + b["w"]) * S, (b["y"] + b["h"]) * S]
        dr.rounded_rectangle(box, radius=8 * S, fill=fill, outline=stroke, width=S)
        tw = int(dr.textlength(b["label"], font=f_band)) + 4
        timg = Image.new("RGBA", (tw, 20 * S), (0, 0, 0, 0))
        ImageDraw.Draw(timg).text((2, 0), b["label"], fill=stroke, font=f_band)
        timg = timg.rotate(90, expand=True)
        cx, cy = (b["x"] + b["w"] / 2) * S, (b["y"] + b["h"] / 2) * S
        img.paste(timg, (int(cx - timg.width / 2), int(cy - timg.height / 2)), timg)
    for b in lay["boxes"]:
        stroke, fill = STYLE_COLORS[b["style"]]
        box = [b["x"] * S, b["y"] * S, (b["x"] + b["w"]) * S, (b["y"] + b["h"]) * S]
        dr.rounded_rectangle(box, radius=8 * S, fill=fill, outline=stroke, width=2 * S // 2 + 1)
        for i, line in enumerate(b["lines"]):
            ty = (b["y"] + lay["pad"] + lay["line_h"] * i) * S
            dr.text(((b["x"] + 12) * S, ty), line, fill="#1c1917", font=f_bold if i == 0 else f_reg)
    for x1, y1, x2, y2 in lay["arrows"]:
        x1, y1, x2, y2 = x1 * S, y1 * S, x2 * S, y2 * S
        dr.line([x1, y1, x2, y2], fill="#6b7280", width=2 * S)
        a = 7 * S
        if abs(x2 - x1) > abs(y2 - y1):
            dr.polygon([(x2, y2), (x2 - a, y2 - a / 2), (x2 - a, y2 + a / 2)], fill="#6b7280")
        else:
            dr.polygon([(x2, y2), (x2 - a / 2, y2 - a), (x2 + a / 2, y2 - a)], fill="#6b7280")
    img.save(path)


# ══════════════════════════════════════════════════════════════════════════════
# INFORMES Y EXPORTACIONES
# ══════════════════════════════════════════════════════════════════════════════
def build_provenance(sources_info: list[dict], dedup_stats: dict | None = None) -> dict:
    return {
        "app": "SysReview PRISMA",
        "app_version": APP_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "pandas": pd.__version__,
        "platform": platform.platform(),
        "fuzzy_engine": "rapidfuzz" if HAS_RAPIDFUZZ else "difflib",
        "sources": [{k: s.get(k) for k in ("name", "file", "format", "n", "sha256")} for s in sources_info],
        "dedup": dedup_stats or {},
    }


def build_text_report(counts: dict, review_name: str, cfg: dict | None = None, prov: dict | None = None) -> str:
    c = counts
    total = c.get("identified_total", 0)
    inc = c.get("included", 0)
    pct = f"{inc / total * 100:.1f}%" if total else "—"
    L = [f"INFORME PRISMA 2020 — {review_name}",
         f"Generado: {datetime.now():%Y-%m-%d %H:%M}   ·   SysReview PRISMA v{APP_VERSION}", "═" * 64, "",
         "IDENTIFICACIÓN"]
    for s, n in c.get("sources", {}).items():
        L.append(f"  {s:<30} {n:>6}")
    L += [f"  {'Total identificados':<30} {total:>6}", "",
          "REGISTROS ELIMINADOS ANTES DEL CRIBADO",
          f"  Duplicados                     {c.get('duplicates_total', 0):>6}",
          f"    · DOI idéntico               {c.get('duplicates_doi', 0):>6}",
          f"    · Título idéntico            {c.get('duplicates_title', 0):>6}",
          f"    · Título similar/transitivo  {c.get('duplicates_fuzzy', 0):>6}",
          f"  Herramientas automáticas       {c.get('removed_automation', 0):>6}",
          f"    · Bloque obligatorio         {c.get('excluded_required', 0):>6}",
          f"    · Bloque secundario          {c.get('excluded_secondary', 0):>6}",
          f"    · Términos de exclusión      {c.get('excluded_terms', 0):>6}",
          f"    · Bloques de búsqueda        {c.get('excluded_blocks', 0):>6}",
          f"  Otras razones                  {c.get('removed_other', 0):>6}",
          f"    · Fuera de rango de años     {c.get('excluded_year', 0):>6}",
          f"    · Año faltante               {c.get('excluded_missing_year', 0):>6}",
          f"    · Tipo de documento          {c.get('excluded_doc_type', 0):>6}",
          f"    · Idioma                     {c.get('excluded_language', 0):>6}"]
    if c.get("not_screened"):
        L.append(f"  Aún sin cribar                 {c['not_screened']:>6}")
    L += ["", "CRIBADO (título / resumen)",
          f"  Registros cribados             {c.get('records_screened', 0):>6}",
          f"    · enviados a revisión auto.  {c.get('screened_auto_review', 0):>6}",
          f"    · rescatados manualmente     {c.get('rescued', 0):>6}",
          f"    · con decisión manual        {c.get('manual_ta_done', 0):>6}",
          f"  Excluidos en el cribado        {c.get('excluded_screening', 0):>6}"]
    L += [f"    · {k:<27}{v:>6}" for k, v in c.get("excluded_screening_reasons", {}).items()]
    L += [f"  Pendientes de decisión         {c.get('pending', 0):>6}", "",
          "RECUPERACIÓN Y ELEGIBILIDAD (texto completo)",
          f"  Reportes buscados              {c.get('reports_sought', 0):>6}",
          f"  Reportes no recuperados        {c.get('not_retrieved', 0):>6}",
          f"  Reportes evaluados             {c.get('reports_assessed', 0):>6}",
          f"  Excluidos a texto completo     {c.get('excluded_fulltext', 0):>6}"]
    L += [f"    · {k:<27}{v:>6}" for k, v in c.get("excluded_fulltext_reasons", {}).items()]
    L += ["", "INCLUIDOS",
          f"  Estudios incluidos             {inc:>6}   ({pct} de los identificados)"]
    for s, n in c.get("included_by_source", {}).items():
        L.append(f"    · {s:<27}{n:>6}")
    warns = []
    if c.get("pending"):
        warns.append(f"Hay {c['pending']} registros pendientes de decisión en el cribado.")
    if c.get("ft_pending"):
        warns.append(f"{c['ft_pending']} incluidos no tienen evaluación a texto completo "
                     "(se cuentan como incluidos provisionalmente).")
    if c.get("not_screened"):
        warns.append(f"{c['not_screened']} registros aún no se han cribado.")
    if warns:
        L += ["", "ADVERTENCIAS"] + [f"  ⚠ {w}" for w in warns]
    if cfg:
        cfg = normalize_config(cfg)
        L += ["", "CONFIGURACIÓN DEL CRIBADO", "─" * 40,
              f"  Años: {cfg['year_from'] or '…'}–{cfg['year_to'] or '…'}   ·   Año faltante: {MISSING_YEAR_MODES[cfg['missing_year']]}",
              f"  Exclusión: {EXCLUDE_MODES[cfg['exclude_mode']]}",
              f"  Plural automático: {'sí' if cfg['auto_plural'] else 'no'}   ·   Casi-cumple → revisión: "
              f"{'sí' if cfg['review_near_miss'] else 'no'}",
              f"  Obligatorio: {cfg['kw_required'] or '—'}",
              f"  Secundario:  {cfg['kw_secondary'] or '—'}",
              f"  Exclusión:   {cfg['kw_exclude'] or '—'}",
              f"  Tipos permitidos: {cfg['doc_include'] or 'todos'}",
              f"  Tipos excl.: {cfg['doc_exclude'] or '—'}",
              f"  Idiomas permitidos: {cfg['languages'] or 'todos'}",
              f"  Bloques mínimos: {cfg['min_blocks'] or 'todos'}"]
        for bid, b in cfg["search_blocks"].items():
            terms = parse_terms(b.get("terms", ""))
            L.append(f"  {bid}: {b.get('label', bid)}  ({len(terms)} términos)")
            L.append(f"      {', '.join(terms)}")
    if prov:
        L += ["", "PROCEDENCIA", "─" * 40]
        for s in prov.get("sources", []):
            L.append(f"  {s.get('name')}: {s.get('file')}  ({s.get('n')} reg.)  sha256={str(s.get('sha256'))[:16]}…")
    return "\n".join(L) + "\n"


EXPORT_COL_ORDER = ["record_id", "source", "Status", "PRISMA_Stage", "year", "title", "authors", "journal",
                    "doc_type", "doi", "keywords", "abstract", "Auto_Decision", "Auto_Stage", "Auto_Reason",
                    "Matched_Required", "Matched_Secondary", "Matched_Exclude", "Matched_Blocks",
                    "Missing_Blocks", "N_Blocks", "TA_Decision", "TA_Reason", "TA_Note", "FT_Decision",
                    "FT_Reason", "TA_Decision_R2", "TA_Reason_R2", "Is_Duplicate", "Duplicate_Of",
                    "Duplicate_Reason"]


def export_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in EXPORT_COL_ORDER if c in df.columns] + [c for c in df.columns if c not in EXPORT_COL_ORDER]
    out = df[cols].copy()
    for c in out.columns:
        if out[c].dtype == object or str(out[c].dtype) in ("str", "string"):
            out[c] = out[c].map(clean_cell)
    return out.reset_index(drop=True)


def counts_table(counts: dict) -> pd.DataFrame:
    rows = []
    for k, v in counts.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                rows.append({"Concepto": f"{k} · {kk}", "n": vv})
        else:
            rows.append({"Concepto": k, "n": v})
    return pd.DataFrame(rows)


def config_table(cfg: dict) -> pd.DataFrame:
    rows = []
    for k, v in normalize_config(cfg).items():
        if k == "search_blocks":
            for bid, b in v.items():
                rows.append({"Parámetro": f"search_blocks.{bid}", "Valor": f"{b['label']} :: {b['terms']}"})
        else:
            rows.append({"Parámetro": k, "Valor": "" if v is None else str(v)})
    return pd.DataFrame(rows)


def export_workbook(path, df: pd.DataFrame, counts: dict, cfg: dict, prov: dict):
    """Libro Excel con una hoja por etapa + resumen, configuración y procedencia."""
    d = export_frame(df)
    st = d["Status"]
    sheets = [
        ("Incluidos", st.eq(STATUS_INCLUDED)),
        ("Pendientes", st.eq(STATUS_PENDING)),
        ("Excl_texto_completo", st.isin([STATUS_EXC_FT, STATUS_NOT_RETRIEVED])),
        ("Excl_cribado_manual", st.eq(STATUS_EXC_TA)),
        ("Excl_automaticos", st.eq(STATUS_EXC_AUTO)),
        ("Duplicados", st.eq(STATUS_DUP)),
    ]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        counts_table(counts).to_excel(xw, sheet_name="Resumen_PRISMA", index=False)
        for name, mask in sheets:
            d[mask].to_excel(xw, sheet_name=name, index=False)
        d.to_excel(xw, sheet_name="Todos", index=False)
        config_table(cfg).to_excel(xw, sheet_name="Configuracion", index=False)
        prov_rows = [{"Clave": k, "Valor": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v}
                     for k, v in prov.items()]
        pd.DataFrame(prov_rows).to_excel(xw, sheet_name="Procedencia", index=False)
    write_sidecar(path, cfg, prov, counts)


def write_sidecar(path, cfg: dict, prov: dict, counts: dict | None = None) -> str:
    """Guarda <archivo>_config.json junto a la exportación (reproducibilidad)."""
    p = Path(path)
    side = p.with_name(p.stem + "_config.json")
    payload = {"provenance": prov, "config": normalize_config(cfg)}
    if counts is not None:
        payload["counts"] = counts
    side.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(side)


def export_csv(path, df: pd.DataFrame, cfg: dict, prov: dict):
    export_frame(df).to_csv(path, index=False, encoding="utf-8-sig")
    write_sidecar(path, cfg, prov)


def _ris_type(doc_type: str) -> str:
    t = normalize_text(doc_type)
    if "conference" in t or "proceeding" in t:
        return "CONF"
    if "chapter" in t:
        return "CHAP"
    if t.startswith("book"):
        return "BOOK"
    if "thesis" in t:
        return "THES"
    return "JOUR"


def export_ris(path, df: pd.DataFrame):
    lines = []
    for _, r in df.iterrows():
        lines.append(f"TY  - {_ris_type(r.get('doc_type', ''))}")
        lines.append(f"TI  - {r.get('title', '')}")
        authors = str(r.get("authors", ""))
        for a in (authors.split(";") if ";" in authors else [authors]):
            if a.strip():
                lines.append(f"AU  - {a.strip()}")
        y = r.get("year")
        if pd.notna(y) and str(y) != "":
            lines.append(f"PY  - {int(y)}")
        for tag, key in (("JO", "journal"), ("DO", "doi"), ("AB", "abstract")):
            v = str(r.get(key, "") or "").strip()
            if v:
                lines.append(f"{tag}  - {v}")
        for k in str(r.get("keywords", "")).split(";"):
            if k.strip():
                lines.append(f"KW  - {k.strip()}")
        lines.append(f"N1  - SysReview {r.get('record_id', '')} · {r.get('Status', '')}")
        lines.append("ER  - ")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# SESIONES (.prisma = JSON comprimido con gzip)
# ══════════════════════════════════════════════════════════════════════════════
def _json_default(o):
    if hasattr(o, "item"):
        return o.item()
    return str(o)


def save_session(path, df: pd.DataFrame, cfg: dict, review_name: str, sources_info: list,
                 dedup_stats: dict | None = None, extra: dict | None = None):
    data = df.astype(object).where(df.notna(), None)
    payload = {
        "format": "sysreview-prisma-session",
        "version": 1,
        "app_version": APP_VERSION,
        "saved": datetime.now().isoformat(timespec="seconds"),
        "review_name": review_name,
        "config": cfg,
        "sources": sources_info,
        "dedup_stats": dedup_stats or {},
        "extra": extra or {},
        "columns": list(df.columns),
        "data": data.values.tolist(),
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=_json_default)


def load_session(path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    if payload.get("format") != "sysreview-prisma-session":
        raise ValueError("El archivo no es una sesión de SysReview PRISMA.")
    df = pd.DataFrame(payload["data"], columns=payload["columns"])
    df = ensure_columns(df)
    if "record_id" in df.columns:
        df.index = df["record_id"].to_numpy()
    payload["df"] = compute_status(df)
    return payload
