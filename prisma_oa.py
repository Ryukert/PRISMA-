"""
SysReview PRISMA v3 — PDFs de acceso abierto.

Consulta qué artículos tienen una versión LEGAL y gratuita (editorial o repositorio) y la descarga.
  · OpenAlex (https://openalex.org): gratuito, sin registro. Fuente principal.
  · Unpaywall (https://unpaywall.org): opcional, solo si el usuario escribe su correo (lo exige el servicio).
Solo usa la biblioteca estándar (urllib); no requiere dependencias nuevas.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import prisma_core as pc

OPENALEX = "https://api.openalex.org/works"
UNPAYWALL = "https://api.unpaywall.org/v2/"
USER_AGENT = f"SysReviewPRISMA/{pc.APP_VERSION}"
# Para descargar PDFs de acceso abierto: algunas editoriales (p. ej. MDPI) rechazan clientes que no parecen
# un navegador, aunque el PDF sea libre. No se evade ningún control de acceso: solo se descargan enlaces OA.
DOWNLOAD_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   f"Chrome/130.0 Safari/537.36 SysReviewPRISMA/{pc.APP_VERSION}"),
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}
MAX_PDF_BYTES = 150 * 1024 * 1024

# Estados de acceso
OA_PDF = "PDF disponible"
OA_WEB = "Solo página web"
OA_CLOSED = "Cerrado"
OA_NOT_FOUND = "No encontrado"
OA_NO_DOI = "Sin DOI"
OA_ERROR = "Error de consulta"

OA_TYPES = {
    "gold": "Oro (revista abierta)", "diamond": "Diamante (revista abierta)", "green": "Verde (repositorio)",
    "hybrid": "Híbrido (abierto en revista)", "bronze": "Bronce (gratis en la editorial)", "closed": "Cerrado",
}


# ══════════════════════════════════════════════════════════════════════════════
# Red
# ══════════════════════════════════════════════════════════════════════════════
def _get_json(url: str, timeout: int = 30, retries: int = 3) -> dict:
    """GET con reintentos ante 429/5xx (límite de peticiones o fallo temporal del servidor)."""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise ConnectionError(f"No se pudo consultar el servicio: {last}")


def _parse_openalex(w: dict) -> dict:
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    pdf, loc_used = best.get("pdf_url"), best
    if not pdf:
        for loc in w.get("locations") or []:
            if loc.get("is_oa") and loc.get("pdf_url"):
                pdf, loc_used = loc["pdf_url"], loc
                break
    # Todas las copias OA con PDF (editorial, PubMed Central, arXiv, repositorios…) para probar en orden
    alts = [loc["pdf_url"] for loc in (w.get("locations") or []) if loc.get("is_oa") and loc.get("pdf_url")]
    # Copia en PubMed Central → Europe PMC entrega el PDF directamente (p. ej. artículos de MDPI/Sensors)
    pmcid = str((w.get("ids") or {}).get("pmcid") or "").rstrip("/").split("/")[-1]
    if pmcid:
        pmcid = pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"
        alts.insert(0, f"https://europepmc.org/articles/{pmcid}?pdf=render")
        if not pdf and oa.get("is_oa") is not False:
            pdf = alts.pop(0)
    alts = [u for u in dict.fromkeys(alts) if u != pdf]
    alts.sort(key=lambda u: "ncbi.nlm.nih.gov" in u)      # PMC de NCBI bloquea programas: al final
    src = (loc_used or {}).get("source") or {}
    kind = oa.get("oa_status") or ("closed" if not oa.get("is_oa") else "")
    url = oa.get("oa_url") or (loc_used or {}).get("landing_page_url") or ""
    if pdf:
        status = OA_PDF
    elif oa.get("is_oa") and url:
        status = OA_WEB
    else:
        status = OA_CLOSED
    return {"OA_Status": status, "OA_Type": OA_TYPES.get(kind, kind), "OA_PDF_URL": pdf or "",
            "OA_Alt_URLs": " | ".join(alts), "OA_URL": url if oa.get("is_oa") else "",
            "OA_Host": src.get("display_name", "") or "", "OA_License": (loc_used or {}).get("license") or "",
            "OA_Via": "OpenAlex"}


def lookup_openalex_title(title: str, year=None, email: str | None = None) -> dict | None:
    """Para registros SIN DOI: busca por título y solo acepta si el título y el año coinciden."""
    from difflib import SequenceMatcher
    t = pc.normalize_title(title)
    if len(t) < 20:
        return None
    params = {"search": str(title)[:250], "per-page": 5,
              "select": "doi,ids,title,publication_year,open_access,best_oa_location,locations"}
    if email:
        params["mailto"] = email
    data = _get_json(OPENALEX + "?" + urllib.parse.urlencode(params))
    for w in data.get("results", []):
        cand = pc.normalize_title(w.get("title") or "")
        if not cand or SequenceMatcher(None, t, cand).ratio() < 0.93:
            continue
        wy = w.get("publication_year")
        try:
            if year is not None and str(year) not in ("", "<NA>", "nan") and wy and abs(int(year) - int(wy)) > 1:
                continue
        except (TypeError, ValueError):
            pass
        info = _parse_openalex(w)
        info["OA_Via"] = "OpenAlex (por título)"
        info["OA_Found_DOI"] = pc.normalize_doi(w.get("doi"))
        return info
    return None


def lookup_openalex(dois: list[str], email: str | None = None, progress=None) -> dict:
    """Consulta OpenAlex por lotes de 40 DOI. Devuelve {doi_normalizado: info}."""
    dois = list(dict.fromkeys(d for d in (pc.normalize_doi(x) for x in dois) if d))
    simple = [d for d in dois if not re.search(r"[,|]", d)]
    odd = [d for d in dois if re.search(r"[,|]", d)]          # DOI raros: consulta individual
    out, done = {}, 0
    for i in range(0, len(simple), 40):
        chunk = simple[i:i + 40]
        params = {"filter": "doi:" + "|".join(chunk), "per-page": 50,
                  "select": "doi,ids,open_access,best_oa_location,locations"}
        if email:
            params["mailto"] = email
        data = _get_json(OPENALEX + "?" + urllib.parse.urlencode(params, safe=":|/"))
        for w in data.get("results", []):
            out[pc.normalize_doi(w.get("doi"))] = _parse_openalex(w)
        done += len(chunk)
        if progress:
            progress(done, len(dois))
    for d in odd:
        w = _get_json(f"{OPENALEX}/https://doi.org/{urllib.parse.quote(d, safe='/')}")
        if w:
            out[d] = _parse_openalex(w)
        done += 1
        if progress:
            progress(done, len(dois))
    return out


def lookup_unpaywall(doi: str, email: str) -> dict | None:
    data = _get_json(f"{UNPAYWALL}{urllib.parse.quote(doi, safe='/')}?{urllib.parse.urlencode({'email': email})}")
    if not data:
        return None
    best = data.get("best_oa_location") or {}
    pdf = best.get("url_for_pdf")
    if not pdf:
        for loc in data.get("oa_locations") or []:
            if loc.get("url_for_pdf"):
                pdf, best = loc["url_for_pdf"], loc
                break
    url = best.get("url") or best.get("url_for_landing_page") or ""
    kind = data.get("oa_status") or "closed"
    status = OA_PDF if pdf else (OA_WEB if data.get("is_oa") and url else OA_CLOSED)
    host = best.get("repository_institution") or data.get("journal_name") or best.get("host_type") or ""
    alts = [loc["url_for_pdf"] for loc in (data.get("oa_locations") or []) if loc.get("url_for_pdf")]
    alts = [u for u in dict.fromkeys(alts) if u != pdf]
    return {"OA_Status": status, "OA_Type": OA_TYPES.get(kind, kind), "OA_PDF_URL": pdf or "",
            "OA_Alt_URLs": " | ".join(alts), "OA_URL": url if data.get("is_oa") else "", "OA_Host": host,
            "OA_License": best.get("license") or "", "OA_Via": "Unpaywall"}


def check_records(df, rids: list[str], email: str | None = None, progress=None) -> dict:
    """
    Calcula la disponibilidad de acceso abierto de los registros indicados.
    Devuelve {record_id: {columna: valor}} — NO modifica df (seguro para hilos).
    """
    rows = df.loc[rids]
    dois = {rid: pc.normalize_doi(d) for rid, d in rows["doi"].items()}
    found = lookup_openalex(list(dois.values()), email, progress)
    updates = {}
    stamp = time.strftime("%Y-%m-%d %H:%M")
    pending_up = []
    empty = {"OA_Type": "", "OA_PDF_URL": "", "OA_Alt_URLs": "", "OA_URL": "", "OA_Host": "", "OA_License": ""}
    no_doi = [rid for rid, d in dois.items() if not d]
    for rid, d in dois.items():
        if not d:
            info = dict(empty, OA_Status=OA_NO_DOI, OA_Via="")
        else:
            info = found.get(d) or dict(empty, OA_Status=OA_NOT_FOUND, OA_Via="OpenAlex")
            if email and info["OA_Status"] != OA_PDF:
                pending_up.append(rid)
        info["OA_Checked"] = stamp
        updates[rid] = info
    # Registros sin DOI: búsqueda por título (con verificación de título y año)
    if "title" in rows.columns:
        for k, rid in enumerate(no_doi, start=1):
            try:
                hit = lookup_openalex_title(rows.loc[rid, "title"], rows.loc[rid].get("year"), email)
            except Exception:
                hit = None
            if hit:
                hit["OA_Checked"] = stamp
                updates[rid] = hit
            if progress:
                progress(k, len(no_doi), "Sin DOI → por título")
            time.sleep(0.1)
    for k, rid in enumerate(pending_up, start=1):    # segunda opinión con Unpaywall
        try:
            up = lookup_unpaywall(dois[rid], email)
        except Exception:
            up = None
        if up and (up["OA_Status"] == OA_PDF or updates[rid]["OA_Status"] in (OA_NOT_FOUND, OA_CLOSED)):
            up["OA_Checked"] = stamp
            updates[rid] = up
        if progress:
            progress(len(dois) + k, len(dois) + len(pending_up), "Unpaywall")
        time.sleep(0.1)
    return updates


# ══════════════════════════════════════════════════════════════════════════════
# Descarga
# ══════════════════════════════════════════════════════════════════════════════
def pdf_file_name(row) -> str:
    author = re.split(r"[;,]", str(row.get("authors", "")) or "")[0].strip().split(" ")[0] or "SinAutor"
    year = "" if row.get("year") is None or str(row.get("year")) in ("", "<NA>", "nan") else str(int(row["year"]))
    title = "_".join(pc.normalize_title(row.get("title", "")).split()[:7])
    name = "_".join(x for x in (str(row.get("record_id", "")), author, year, title) if x)
    name = re.sub(r"[^\w\-]+", "_", pc.strip_accents(name))[:110].strip("_")
    return f"{name}.pdf"


def download_pdf(url: str, dest: Path, timeout: int = 45) -> tuple[bool, str]:
    """
    Descarga solo si el contenido es realmente un PDF (empieza con %PDF).
    Repositorios como Europe PMC limitan la velocidad (responden 403/429): se reintenta con espera.
    """
    rate_limited_host = "europepmc.org" in url
    waits = [4, 12] if rate_limited_host else [5]
    for attempt in range(len(waits) + 1):
        ok, note, code = _download_once(url, Path(dest), timeout)
        retry = code == 429 or (code == 403 and rate_limited_host)
        if ok or not retry or attempt == len(waits):
            return ok, note
        time.sleep(waits[attempt])
    return ok, note


def _download_once(url: str, dest: Path, timeout: int) -> tuple[bool, str, int | None]:
    """Un intento de descarga. Devuelve (éxito, nota, código HTTP o None)."""
    tmp = dest.with_suffix(".part")
    try:
        req = urllib.request.Request(url, headers=DOWNLOAD_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            head = r.read(5)
            if head != b"%PDF-":
                return False, "El enlace abre una página web, no un PDF directo (ábrelo en el navegador).", None
            size = len(head)
            with open(tmp, "wb") as f:
                f.write(head)
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_PDF_BYTES:
                        raise ValueError("archivo demasiado grande")
                    f.write(chunk)
        shutil.move(str(tmp), str(dest))
        return True, f"Descargado ({size / 1024 / 1024:.1f} MB)", None
    except urllib.error.HTTPError as e:
        msg = {401: "requiere acceso", 403: "la editorial bloquea descargas automáticas",
               404: "el enlace ya no existe", 429: "demasiadas solicitudes al servidor"}.get(e.code, f"error HTTP {e.code}")
        return False, f"No se pudo descargar: {msg}. Ábrelo en el navegador.", e.code
    except urllib.error.URLError as e:
        if "CERTIFICATE" in str(e.reason).upper():
            return False, "No se pudo descargar: el certificado del sitio no es válido. Ábrelo en el navegador.", None
        return False, f"No se pudo descargar: {e.reason}. Ábrelo en el navegador.", None
    except Exception as e:
        return False, f"No se pudo descargar: {e}", None
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def candidate_urls(row) -> list[str]:
    """PDF principal + copias alternativas (repositorios, PubMed Central…), sin repetir."""
    urls = [str(row.get("OA_PDF_URL", "") or "")] + str(row.get("OA_Alt_URLs", "") or "").split(" | ")
    return [u.strip() for u in dict.fromkeys(urls) if u and u.strip()]


def download_records(jobs: list[tuple], folder: Path, progress=None, pause: float = 0.5) -> dict:
    """
    jobs = [(record_id, url_o_lista_de_urls, nombre_archivo)]. Prueba cada copia hasta obtener un PDF real.
    Devuelve {record_id: (ruta_o_vacío, nota)}.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, (rid, urls, name) in enumerate(jobs, start=1):
        urls = [urls] if isinstance(urls, str) else list(urls)
        dest = folder / name
        if dest.exists() and dest.stat().st_size > 0:
            out[rid] = (str(dest), "Ya estaba descargado")
        else:
            ok, note = False, "Sin enlace de PDF"
            for i, url in enumerate(urls):
                ok, note = download_pdf(url, dest)
                if ok:
                    if i:
                        note += f" — copia alternativa {i + 1}: {urllib.parse.urlparse(url).netloc}"
                    break
                time.sleep(pause / 2)
            if not ok and len(urls) > 1:
                note += f" (se probaron {len(urls)} copias)"
            out[rid] = (str(dest) if ok else "", note)
            time.sleep(pause)
        if progress:
            progress(k, len(jobs))
    return out
