"""
SysReview PRISMA v3 — Presets de revisión (carga, guardado y validación).
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from prisma_core import EXCLUDE_MODES, MISSING_YEAR_MODES

PRESETS_FILE = Path.home() / ".sysreview_presets_v2.json"   # mismo archivo que v2 → se conservan presets

MEMS_QUERY = (
    'TITLE-ABS-KEY ( ( mems OR "micro-electro-mechanical" OR microelectromechanical ) AND ( accelerometer* OR '
    'accelerograph* ) AND ( "low-noise" OR "low noise" OR "ultra-low noise" OR "high-resolution" OR adxl35* OR '
    'adxl1002 OR iis3dwb OR sf1500 OR sf1600 OR "Silicon Designs" ) AND ( "structural health monitoring" OR shm OR '
    '"modal identification" OR "operational modal analysis" OR "ambient vibration" OR "natural frequenc*" OR '
    '"dynamic characteri*" OR "system identification" OR building* OR bridge* OR tower* OR "civil structure*" OR '
    '"civil infrastructure" OR "shake table" OR footbridge* OR heritage ) ) AND PUBYEAR > 2011 AND ( LIMIT-TO ( '
    'DOCTYPE , "ar" ) OR LIMIT-TO ( DOCTYPE , "cp" ) ) AND ( LIMIT-TO ( LANGUAGE , "English" ) OR LIMIT-TO ( '
    'LANGUAGE , "Spanish" ) )'
)

DEFAULT_PRESETS = {
    "MEMS de bajo ruido — SHM (cadena Scopus)": {
        "description": "Acelerómetros MEMS de bajo ruido / alta resolución para monitoreo estructural",
        "search_query": MEMS_QUERY,
        "year_from": 2012, "year_to": None,
        "kw_required": "", "kw_secondary": "", "kw_exclude": "",
        "doc_include": "article, conference paper",
        "doc_exclude": "",
        "languages": "english, spanish",
        "search_blocks": {
            "B1": {"label": "Bloque 1 — MEMS",
                   "terms": "mems, micro electro mechanical, microelectromechanical"},
            "B2": {"label": "Bloque 2 — Acelerómetro",
                   "terms": "accelerometer*, accelerograph*"},
            "B3": {"label": "Bloque 3 — Bajo ruido / alta resolución",
                   "terms": "low noise, ultra low noise, high resolution, adxl35*, adxl1002, iis3dwb, sf1500, "
                            "sf1600, silicon designs"},
            "B4": {"label": "Bloque 4 — Aplicación estructural",
                   "terms": "structural health monitoring, shm, modal identification, operational modal analysis, "
                            "ambient vibration, natural frequenc*, dynamic characteri*, system identification, "
                            "building*, bridge*, tower*, civil structure*, civil infrastructure, shake table, "
                            "footbridge*, heritage"},
        },
        "min_blocks": 4,
        "exclude_mode": "balanced", "missing_year": "review", "auto_plural": True,
        "review_near_miss": True,   # 3 de 4 bloques → revisión manual (p. ej. exportaciones sin keywords)
    },
    "SHM — Monitoreo Estructural": {
        "description": "Structural Health Monitoring con IoT/MEMS",
        "year_from": 2016, "year_to": 2026,
        "kw_required": (
            "Structural Health Monitoring, SHM, structural monitoring, "
            "structural damage detection, vibration monitoring, modal analysis, "
            "civil infrastructure monitoring, infrastructure monitoring"
        ),
        "kw_secondary": (
            "Internet of Things, IoT, wireless sensor networks, WSN, remote monitoring, "
            "MEMS sensors, MEMS accelerometer, accelerometer, IMU sensor, inertial measurement unit, "
            "low cost sensors, Raspberry Pi, Arduino, embedded systems, sensor nodes, edge computing"
        ),
        "kw_exclude": (
            "medical monitoring, biomedical monitoring, patient monitoring, healthcare monitoring, "
            "ECG, EEG, brain monitoring, heart monitoring, medical sensors, smart agriculture, "
            "precision agriculture, soil monitoring, crop monitoring, plant monitoring, "
            "environmental monitoring, air quality monitoring, water quality monitoring, "
            "pollution monitoring, machine condition monitoring, rotating machinery monitoring, "
            "motor fault detection, industrial process monitoring, manufacturing monitoring, "
            "smart home, smart city, traffic monitoring, vehicle monitoring"
        ),
        "doc_exclude": (
            "review, systematic review, conference paper, proceedings paper, editorial, "
            "letter, note, meeting abstract, book chapter, short survey"
        ),
        "search_blocks": {
            "B1_DOMAIN": {"label": "Bloque 1 — Dominio SHM",
                          "terms": "structural health monitoring, structural monitoring, damage detection, structural damage detection"},
            "B2_OBJECT": {"label": "Bloque 2 — Objeto (Civil)",
                          "terms": "civil structure, civil infrastructure, bridge, building"},
            "B3_SENSOR": {"label": "Bloque 3 — Sensores",
                          "terms": "mems, accelerometer, inertial measurement unit, imu, low-cost sensor, embedded system"},
            "B4_CONNECTIVITY": {"label": "Bloque 4 — Conectividad IoT",
                                "terms": "iot, internet of things, wireless sensor network, wsn, remote monitoring"},
            "B5_SIGNAL": {"label": "Bloque 5 — Procesamiento de señal",
                          "terms": "vibration, natural frequency, fft, rms, modal analysis"},
        },
        "min_blocks": 5,
        "exclude_mode": "balanced", "missing_year": "review", "auto_plural": True, "review_near_miss": True,
    },
    "IA en Educación": {
        "description": "Inteligencia Artificial aplicada a procesos educativos",
        "year_from": 2018, "year_to": 2026,
        "kw_required": (
            "artificial intelligence, AI, machine learning, deep learning, "
            "educational technology, e-learning, learning analytics"
        ),
        "kw_secondary": (
            "student performance, personalized learning, adaptive learning, "
            "natural language processing, NLP, chatbot, intelligent tutoring system, "
            "automatic assessment, feedback, curriculum"
        ),
        "kw_exclude": (
            "robotics, manufacturing, industrial AI, military AI, medical diagnosis, "
            "clinical AI, financial AI, marketing AI, computer vision industrial"
        ),
        "doc_exclude": "editorial, letter, note, book chapter, meeting abstract, short survey",
        "search_blocks": {
            "B1_AI": {"label": "Bloque 1 — IA/ML",
                      "terms": "artificial intelligence, machine learning, deep learning, neural network"},
            "B2_EDU": {"label": "Bloque 2 — Educación",
                       "terms": "education, educational, learning, teaching, student, classroom, curriculum, university, school"},
            "B3_OUTCOME": {"label": "Bloque 3 — Resultado educativo",
                           "terms": "student performance, learning outcome, academic achievement, assessment, grade, score"},
            "B4_TOOL": {"label": "Bloque 4 — Herramienta tecnológica",
                        "terms": "e-learning, lms, moodle, chatbot, intelligent tutoring, adaptive system, platform"},
        },
        "min_blocks": 3,
        "exclude_mode": "balanced", "missing_year": "review", "auto_plural": True, "review_near_miss": False,
    },
    "Energías Renovables": {
        "description": "Solar, eólica e integración en red eléctrica",
        "year_from": 2015, "year_to": 2026,
        "kw_required": (
            "renewable energy, solar energy, wind energy, photovoltaic, PV, wind turbine, "
            "clean energy, sustainable energy, green energy"
        ),
        "kw_secondary": (
            "grid integration, smart grid, energy storage, battery storage, "
            "power conversion, inverter, microgrid, energy management, forecasting, optimization, efficiency"
        ),
        "kw_exclude": "nuclear energy, fossil fuel, coal, natural gas, oil, petroleum, combustion, diesel, gasoline",
        "doc_exclude": "editorial, letter, note, book chapter, short survey",
        "search_blocks": {
            "B1_SOURCE": {"label": "Bloque 1 — Fuente renovable",
                          "terms": "solar, photovoltaic, pv, wind, wind turbine, hydropower, geothermal, biomass"},
            "B2_GRID": {"label": "Bloque 2 — Red eléctrica",
                        "terms": "grid, smart grid, microgrid, power grid, energy grid, grid integration"},
            "B3_STORAGE": {"label": "Bloque 3 — Almacenamiento",
                           "terms": "energy storage, battery, lithium, capacitor, pumped hydro, flywheel"},
            "B4_MGMT": {"label": "Bloque 4 — Gestión/control",
                        "terms": "energy management, power management, control, optimization, scheduling, dispatch"},
        },
        "min_blocks": 3,
        "exclude_mode": "balanced", "missing_year": "review", "auto_plural": True, "review_near_miss": False,
    },
}

BLANK_CONFIG = {
    "description": "",
    "year_from": "", "year_to": "",
    "kw_required": "", "kw_secondary": "", "kw_exclude": "", "doc_exclude": "",
    "doc_include": "", "languages": "",
    "search_blocks": {"B1": {"label": "Bloque 1", "terms": ""}},
    "min_blocks": 1,
    "exclude_mode": "balanced", "missing_year": "review", "auto_plural": True, "review_near_miss": False,
    "col_map": {},
}

PRESET_TEMPLATE = {
    "_instrucciones": {
        "descripcion_general": "Este archivo configura una revisión sistemática PRISMA. Edita los valores según tu tema.",
        "name": "STRING — Nombre de tu revisión.",
        "description": "STRING — Descripción breve del tema.",
        "year_from": "INTEGER — Año mínimo. Ej: 2015",
        "year_to": "INTEGER — Año máximo. Ej: 2026",
        "kw_required": "STRING — Términos OBLIGATORIOS separados por coma. Admite comodines: monitor*",
        "kw_secondary": "STRING — Términos SECUNDARIOS separados por coma.",
        "kw_exclude": "STRING — Términos de EXCLUSIÓN separados por coma.",
        "doc_exclude": "STRING — Tipos de documento a excluir (coincidencia exacta por tipo).",
        "doc_include": "STRING — Tipos de documento PERMITIDOS (vacío = todos). Ej: Article, Proceedings Paper",
        "languages": "STRING — Idiomas permitidos (vacío = todos). Ej: English, Spanish",
        "min_blocks": "INTEGER — Bloques mínimos que debe cumplir un artículo (0 = todos).",
        "search_blocks": "OBJECT — Bloques de la cadena de búsqueda {ID: {label, terms}}.",
        "exclude_mode": "STRING — strict | balanced | flag",
        "missing_year": "STRING — review | exclude | include",
        "auto_plural": "BOOLEAN — Reconocer plurales automáticamente (s, es, y→ies).",
        "review_near_miss": "BOOLEAN — Enviar a revisión los que quedan a 1 bloque del mínimo.",
        "col_map": "OBJECT — OPCIONAL. Mapeo de columnas personalizadas {campo: columna}.",
    },
    "name": "Mi Revisión Sistemática",
    "description": "Descripción breve",
    "year_from": 2015,
    "year_to": 2026,
    "kw_required": "término principal 1, término principal 2, sinónimo",
    "kw_secondary": "tecnología 1, método 1, herramienta",
    "kw_exclude": "área a excluir 1, dominio irrelevante",
    "doc_exclude": "review, editorial, letter, note, book chapter",
    "doc_include": "",
    "languages": "English, Spanish",
    "min_blocks": 3,
    "exclude_mode": "balanced",
    "missing_year": "review",
    "auto_plural": True,
    "review_near_miss": False,
    "search_blocks": {
        "B1_DOMINIO": {"label": "Bloque 1 — Dominio principal", "terms": "término del dominio, sinónimo 1, sigla"},
        "B2_OBJETO": {"label": "Bloque 2 — Objeto de estudio", "terms": "objeto de estudio, contexto de aplicación"},
        "B3_TECNOLOGIA": {"label": "Bloque 3 — Tecnología / Método", "terms": "tecnología clave, método*, algoritmo"},
        "B4_OUTCOME": {"label": "Bloque 4 — Resultado o medida", "terms": "métrica de resultado, indicador, medición"},
    },
    "col_map": {},
}

_STRING_FIELDS = ["name", "description", "kw_required", "kw_secondary", "kw_exclude", "doc_exclude",
                  "doc_include", "languages"]


def validate_preset_cfg(cfg) -> None:
    """Lanza ValueError con la lista de problemas encontrados."""
    if not isinstance(cfg, dict):
        raise ValueError("El archivo debe ser un objeto JSON {}.")
    errors = []
    for f in _STRING_FIELDS:
        if f in cfg and cfg[f] is not None and not isinstance(cfg[f], str):
            errors.append(f"'{f}' debe ser texto")
    yf, yt = cfg.get("year_from"), cfg.get("year_to")
    for name, v in (("year_from", yf), ("year_to", yt)):
        if v not in (None, "") and (not isinstance(v, int) or isinstance(v, bool)):
            errors.append(f"'{name}' debe ser entero, no '{v}'")
    if "search_query" in cfg and not isinstance(cfg["search_query"], str):
        errors.append("'search_query' debe ser texto")
    if isinstance(yf, int) and isinstance(yt, int) and yf > yt:
        errors.append(f"'year_from' ({yf}) debe ser ≤ 'year_to' ({yt})")
    mb = cfg.get("min_blocks")
    if mb is not None and (not isinstance(mb, int) or isinstance(mb, bool) or mb < 0):
        errors.append(f"'min_blocks' debe ser entero ≥ 0, no '{mb}'")
    if "exclude_mode" in cfg and cfg["exclude_mode"] not in EXCLUDE_MODES:
        errors.append(f"'exclude_mode' debe ser uno de: {', '.join(EXCLUDE_MODES)}")
    if "missing_year" in cfg and cfg["missing_year"] not in MISSING_YEAR_MODES:
        errors.append(f"'missing_year' debe ser uno de: {', '.join(MISSING_YEAR_MODES)}")
    for f in ("auto_plural", "review_near_miss"):
        if f in cfg and not isinstance(cfg[f], bool):
            errors.append(f"'{f}' debe ser true o false")
    blocks = cfg.get("search_blocks")
    if blocks is not None:
        if not isinstance(blocks, dict):
            errors.append("'search_blocks' debe ser un objeto JSON {}")
        else:
            for bid, block in blocks.items():
                if not isinstance(block, dict):
                    errors.append(f"Bloque '{bid}' debe ser objeto con 'label' y 'terms'")
                elif "terms" not in block or not isinstance(block["terms"], str):
                    errors.append(f"Bloque '{bid}' debe tener campo 'terms' de texto")
            if isinstance(mb, int) and mb > len(blocks):
                errors.append(f"'min_blocks' ({mb}) > número de bloques ({len(blocks)})")
    cm = cfg.get("col_map")
    if cm is not None and not isinstance(cm, dict):
        errors.append("'col_map' debe ser un objeto JSON {}")
    if errors:
        raise ValueError("Errores en JSON:\n• " + "\n• ".join(errors))


def load_user_presets() -> tuple[dict, str | None]:
    """
    Devuelve (presets, aviso). Si el archivo del usuario está dañado, se respalda
    como .bak-<fecha> en lugar de perderse silenciosamente.
    """
    merged = {k: dict(v) for k, v in DEFAULT_PRESETS.items()}
    if not PRESETS_FILE.exists():
        return merged, None
    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("el contenido no es un objeto JSON")
        merged.update(data)
        return merged, None
    except Exception as e:
        backup = PRESETS_FILE.with_name(PRESETS_FILE.name + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            shutil.copy2(PRESETS_FILE, backup)
            msg = (f"El archivo de presets estaba dañado ({e}).\n"
                   f"Se guardó una copia en:\n{backup}\nSe cargaron solo los presets del sistema.")
        except OSError:
            msg = f"El archivo de presets estaba dañado ({e}) y no se pudo respaldar."
        return merged, msg


def save_user_presets(presets: dict) -> None:
    user_only = {k: v for k, v in presets.items() if k not in DEFAULT_PRESETS or v != DEFAULT_PRESETS[k]}
    tmp = PRESETS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(user_only, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PRESETS_FILE)   # escritura atómica: nunca queda un archivo a medias
