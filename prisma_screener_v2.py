"""
=============================================================
  SysReview PRISMA  v2.0  ·  Pipeline Universal de Cribado
  Revisiones Sistemáticas — Configurable por Temática
=============================================================
Requisitos:
    pip install customtkinter pandas openpyxl xlrd

Uso:
    python prisma_screener_v2.py
=============================================================
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import customtkinter as ctk
import pandas as pd
from pathlib import Path
import time
import json
import os
import subprocess
import sys
import importlib
import re
from datetime import datetime


# ─── Tema CLARO ───────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ACCENT    = "#4f46e5"   # indigo-600
ACCENT2   = "#6366f1"   # indigo-500
GREEN     = "#16a34a"   # green-600
GREEN_DIM = "#dcfce7"   # green-100
RED       = "#dc2626"   # red-600
RED_DIM   = "#fee2e2"   # red-100
YELLOW    = "#ca8a04"   # yellow-600
TEAL      = "#0d9488"   # teal-600
SCOPUS    = "#4f46e5"   # indigo
CLARIVATE = "#be185d"   # pink-700
BG        = "#f8f7f4"   # warm off-white
SURFACE   = "#ffffff"   # pure white
SURFACE2  = "#f1f0ed"   # warm gray-100
SURFACE3  = "#e8e6e1"   # warm gray-200
BORDER    = "#d6d3cd"   # warm gray-300
MUTED     = "#9ca3a0"   # muted mid
MUTED2    = "#6b7280"   # gray-500
TEXT      = "#1c1917"   # warm almost-black
CYAN      = "#0891b2"   # cyan-600
ORANGE    = "#c2410c"   # orange-700

PRESETS_FILE = Path.home() / ".sysreview_presets_v2.json"

# ─── Presets por defecto ──────────────────────────────────────────────────────
DEFAULT_PRESETS = {
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
            "B1_DOMAIN": {
                "label": "Bloque 1 — Dominio SHM",
                "terms": "structural health monitoring, structural monitoring, damage detection, structural damage detection"
            },
            "B2_OBJECT": {
                "label": "Bloque 2 — Objeto (Civil)",
                "terms": "civil structure, civil structures, civil infrastructure, bridge, bridges, building, buildings"
            },
            "B3_SENSOR": {
                "label": "Bloque 3 — Sensores",
                "terms": "mems, accelerometer, accelerometers, inertial measurement unit, imu, low-cost sensor, low cost sensor, embedded system, embedded systems"
            },
            "B4_CONNECTIVITY": {
                "label": "Bloque 4 — Conectividad IoT",
                "terms": "iot, internet of things, wireless sensor network, wireless sensor networks, wsn, remote monitoring"
            },
            "B5_SIGNAL": {
                "label": "Bloque 5 — Procesamiento de señal",
                "terms": "vibration, vibrations, natural frequency, fft, rms, modal analysis"
            },
        },
        "min_blocks": 5,
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
    },
}

PRESET_TEMPLATE = {
    "_instrucciones": {
        "descripcion_general": (
            "Este archivo configura una revisión sistemática PRISMA. "
            "Edita los valores según tu tema de investigación."
        ),
        "name": "STRING — Nombre de tu revisión.",
        "description": "STRING — Descripción breve del tema.",
        "year_from": "INTEGER — Año mínimo. Ej: 2015",
        "year_to": "INTEGER — Año máximo. Ej: 2026",
        "kw_required": "STRING — Términos OBLIGATORIOS separados por coma.",
        "kw_secondary": "STRING — Términos SECUNDARIOS separados por coma.",
        "kw_exclude": "STRING — Términos de EXCLUSIÓN separados por coma.",
        "doc_exclude": "STRING — Tipos de documento a excluir separados por coma.",
        "min_blocks": "INTEGER — Número mínimo de bloques que debe cumplir un artículo.",
        "search_blocks": "OBJECT — Bloques de la cadena de búsqueda.",
        "col_map": "OBJECT — OPCIONAL. Mapeo de columnas personalizadas.",
    },
    "name": "Mi Revisión Sistemática",
    "description": "Descripción breve",
    "year_from": 2015,
    "year_to": 2026,
    "kw_required": "término principal 1, término principal 2, sinónimo",
    "kw_secondary": "tecnología 1, método 1, herramienta",
    "kw_exclude": "área a excluir 1, dominio irrelevante",
    "doc_exclude": "review, systematic review, editorial, letter, note, book chapter",
    "min_blocks": 3,
    "search_blocks": {
        "B1_DOMINIO": {"label": "Bloque 1 — Dominio principal",
                        "terms": "término del dominio, sinónimo 1, sigla"},
        "B2_OBJETO": {"label": "Bloque 2 — Objeto de estudio",
                       "terms": "objeto de estudio, contexto de aplicación"},
        "B3_TECNOLOGIA": {"label": "Bloque 3 — Tecnología / Método",
                           "terms": "tecnología clave, método principal, algoritmo"},
        "B4_OUTCOME": {"label": "Bloque 4 — Resultado o medida",
                        "terms": "métrica de resultado, indicador, medición"},
    },
    "col_map": {}
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE VALIDACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def _validate_preset_cfg(cfg):
    errors = []
    if not isinstance(cfg, dict):
        raise ValueError("El archivo debe ser un objeto JSON {}.")
    year_from = cfg.get("year_from")
    year_to = cfg.get("year_to")
    if year_from is not None and not isinstance(year_from, int):
        errors.append(f"'year_from' debe ser entero, no '{year_from}'")
    if year_to is not None and not isinstance(year_to, int):
        errors.append(f"'year_to' debe ser entero, no '{year_to}'")
    if year_from and year_to and isinstance(year_from, int) and isinstance(year_to, int):
        if year_from > year_to:
            errors.append(f"'year_from' ({year_from}) debe ser ≤ 'year_to' ({year_to})")
    min_blocks = cfg.get("min_blocks")
    if min_blocks is not None and not isinstance(min_blocks, int):
        errors.append(f"'min_blocks' debe ser entero, no '{min_blocks}'")
    blocks = cfg.get("search_blocks")
    if blocks is not None:
        if not isinstance(blocks, dict):
            errors.append("'search_blocks' debe ser un objeto JSON {}")
        else:
            for bid, block in blocks.items():
                if not isinstance(block, dict):
                    errors.append(f"Bloque '{bid}' debe ser objeto con 'label' y 'terms'")
                elif "terms" not in block:
                    errors.append(f"Bloque '{bid}' debe tener campo 'terms'")
            if min_blocks and isinstance(min_blocks, int) and min_blocks > len(blocks):
                errors.append(f"'min_blocks' ({min_blocks}) > número de bloques ({len(blocks)})")
    if errors:
        raise ValueError("Errores en JSON:\n• " + "\n• ".join(errors))


def load_user_presets():
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_PRESETS)
            merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_PRESETS)


def save_user_presets(presets):
    user_only = {k: v for k, v in presets.items() if k not in DEFAULT_PRESETS or v != DEFAULT_PRESETS[k]}
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_only, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# TOOLTIP HELPER
# ══════════════════════════════════════════════════════════════════════════════
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, "bbox") else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tip, text=self.text, bg="#1e1e23", fg="#e4e4e7",
                       font=("Consolas", 9), relief="flat", padx=8, pady=4,
                       wraplength=320, justify="left")
        lbl.pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Editor de Bloques
# ══════════════════════════════════════════════════════════════════════════════
class BlocksEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, blocks, on_save):
        super().__init__(parent)
        self.title("Editor de Bloques de Cadena de Búsqueda")
        self.geometry("860x700")
        self.configure(fg_color=BG)
        self.blocks = {k: dict(v) for k, v in blocks.items()}
        self.on_save = on_save
        self._entries = {}
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🧩  Editor de Bloques", font=("Arial Black", 14), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(12, 0))
        ctk.CTkLabel(hdr, text="Cada bloque = grupo de sinónimos. Un artículo debe cumplir el mínimo de bloques.",
                     font=("Arial", 10), text_color=MUTED2).pack(anchor="w", padx=24)

        help_f = ctk.CTkFrame(self, fg_color="#eff6ff", corner_radius=8, border_color="#bfdbfe", border_width=1)
        help_f.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(help_f,
                     text="💡  Separa los términos con coma. Usa minúsculas. Incluye siglas, plural/singular y variantes del término.",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=780, justify="left").pack(anchor="w", padx=12, pady=6)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG)
        scroll.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        self._block_frame = scroll
        self._render_blocks()

        btn_row = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        ctk.CTkButton(btn_row, text="➕  Agregar bloque", height=36, width=160,
                      font=("Arial Bold", 12), fg_color=SURFACE2, hover_color=SURFACE3,
                      border_color=TEAL, border_width=1, text_color=TEAL, corner_radius=8,
                      command=self._add_block).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="✅  Guardar cambios", height=36, width=160,
                      font=("Arial Bold", 12), fg_color=ACCENT, hover_color=ACCENT2,
                      text_color="white", corner_radius=8,
                      command=self._save).pack(side="right", padx=16, pady=10)

    def _render_blocks(self):
        for w in self._block_frame.winfo_children():
            w.destroy()
        self._entries.clear()
        block_colors = [ACCENT2, TEAL, GREEN, YELLOW, CYAN, "#f472b6", "#fb923c"]
        for idx, (block_id, block) in enumerate(self.blocks.items()):
            color = block_colors[idx % len(block_colors)]
            card = ctk.CTkFrame(self._block_frame, fg_color=SURFACE, corner_radius=10,
                                border_color=color, border_width=1)
            card.pack(fill="x", pady=5)

            header = ctk.CTkFrame(card, fg_color=SURFACE2, corner_radius=8)
            header.pack(fill="x", padx=10, pady=(10, 4))

            ctk.CTkLabel(header, text="ID:", font=("Courier", 10), text_color=MUTED2, width=20).pack(side="left", padx=(10, 2))
            id_e = ctk.CTkEntry(header, width=150, height=30, font=("Courier Bold", 11),
                                fg_color=SURFACE3, border_color=color, text_color=color, corner_radius=6)
            id_e.insert(0, block_id)
            id_e.pack(side="left", padx=(0, 16))

            ctk.CTkLabel(header, text="Etiqueta:", font=("Courier", 10), text_color=MUTED2).pack(side="left")
            lbl_e = ctk.CTkEntry(header, width=320, height=30, font=("Arial", 11),
                                  fg_color=SURFACE3, border_color=BORDER, text_color=TEXT, corner_radius=6)
            lbl_e.insert(0, block.get("label", ""))
            lbl_e.pack(side="left", padx=4)

            del_btn = ctk.CTkButton(header, text="🗑", width=32, height=30,
                                     fg_color="transparent", hover_color=RED_DIM, text_color=RED,
                                     font=("Arial", 12), corner_radius=6,
                                     command=lambda bid=block_id: self._remove_block(bid))
            del_btn.pack(side="right", padx=8)

            ctk.CTkLabel(card, text="Términos (separados por coma, minúsculas):",
                         font=("Courier", 10), text_color=MUTED2).pack(anchor="w", padx=14, pady=(2, 2))
            terms_e = ctk.CTkTextbox(card, height=60, font=("Courier", 11),
                                      fg_color=SURFACE2, border_color=BORDER, border_width=1,
                                      text_color=TEXT, corner_radius=6)
            terms_e.insert("1.0", block.get("terms", ""))
            terms_e.pack(fill="x", padx=12, pady=(0, 10))

            term_list = [t.strip() for t in block.get("terms", "").split(",") if t.strip()]
            n_terms = len(term_list)
            ctk.CTkLabel(card, text=f"  {n_terms} término{'s' if n_terms != 1 else ''}",
                         font=("Courier", 9), text_color=MUTED).pack(anchor="e", padx=12, pady=(0, 6))

            self._entries[block_id] = {"id": id_e, "label": lbl_e, "terms": terms_e}

    def _add_block(self):
        new_id = f"B{len(self.blocks)+1}_NUEVO"
        self.blocks[new_id] = {"label": f"Bloque {len(self.blocks)+1}", "terms": ""}
        self._render_blocks()

    def _remove_block(self, block_id):
        if len(self.blocks) <= 1:
            messagebox.showwarning("Aviso", "Debe haber al menos un bloque.", parent=self)
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar el bloque '{block_id}'?", parent=self):
            del self.blocks[block_id]
            self._render_blocks()

    def _save(self):
        new_blocks = {}
        for old_id, entries in self._entries.items():
            nid = entries["id"].get().strip()
            if not nid:
                continue
            new_blocks[nid] = {
                "label": entries["label"].get().strip(),
                "terms": entries["terms"].get("1.0", "end").strip(),
            }
        if not new_blocks:
            messagebox.showwarning("Aviso", "Debe haber al menos un bloque.", parent=self)
            return
        self.on_save(new_blocks)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Gestión de Presets
# ══════════════════════════════════════════════════════════════════════════════
class PresetDialog(ctk.CTkToplevel):
    def __init__(self, parent, presets, current_cfg, on_load):
        super().__init__(parent)
        self.title("Gestionar Presets de Revisión")
        self.geometry("800x680")
        self.configure(fg_color=BG)
        self.presets = presets
        self.current_cfg = current_cfg
        self.on_load = on_load
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⚙  Gestionar Presets", font=("Arial Black", 14), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(12, 0))
        ctk.CTkLabel(hdr, text="Carga, guarda o exporta configuraciones de revisión",
                     font=("Arial", 10), text_color=MUTED2).pack(anchor="w", padx=24)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        sb = ctk.CTkScrollableFrame(body, fg_color=SURFACE, corner_radius=12, border_color=BORDER, border_width=1)
        sb.pack(fill="both", expand=True)

        for name, cfg in self.presets.items():
            is_default = name in DEFAULT_PRESETS
            row = ctk.CTkFrame(sb, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", padx=8, pady=3)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(info, text=name, font=("Arial Bold", 12), text_color=TEXT, anchor="w").pack(anchor="w")
            desc = cfg.get("description", "")
            yr_f = cfg.get("year_from", "?")
            yr_t = cfg.get("year_to", "?")
            meta = f"{desc}  ·  {yr_f}–{yr_t}" if desc else f"{yr_f}–{yr_t}"
            ctk.CTkLabel(info, text=meta, font=("Arial", 10), text_color=MUTED2, anchor="w").pack(anchor="w")

            tag = ctk.CTkLabel(row, text="SISTEMA" if is_default else "USUARIO",
                                font=("Courier", 9), text_color=MUTED if is_default else TEAL,
                                fg_color=BORDER if is_default else "#f0fdf4",
                                corner_radius=4, width=70)
            tag.pack(side="right", padx=(0, 6), pady=8)

            if not is_default:
                ctk.CTkButton(row, text="✕", width=28, height=28,
                               fg_color="transparent", hover_color=RED_DIM, text_color=RED,
                               font=("Arial Bold", 11), corner_radius=6,
                               command=lambda n=name: self._delete_preset(n)).pack(side="right", pady=8)

            ctk.CTkButton(row, text="Cargar →", width=90, height=30,
                           fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                           font=("Arial Bold", 10), corner_radius=6,
                           command=lambda c=cfg, n=name: self._load_preset(n, c)).pack(side="right", padx=4, pady=8)

        # Save row
        save_row = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        save_row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(save_row, text="💾  Guardar configuración actual como:",
                     font=("Courier", 11), text_color=MUTED2).pack(side="left", padx=12)
        self.name_entry = ctk.CTkEntry(save_row, width=240, height=34, font=("Courier", 12),
                                        fg_color=SURFACE3, border_color=BORDER, text_color=TEXT,
                                        placeholder_text="Nombre del preset...")
        self.name_entry.pack(side="left", padx=8)
        ctk.CTkButton(save_row, text="Guardar", height=34, width=100,
                       font=("Arial Bold", 12), fg_color=TEAL, hover_color="#0f766e",
                       text_color="black", corner_radius=8,
                       command=self._save_current).pack(side="left", pady=6)

        # IO buttons
        io_row = ctk.CTkFrame(body, fg_color="transparent")
        io_row.pack(fill="x", pady=4)
        for text, color, cmd in [
            ("📂  Importar JSON", TEAL, self._import_json),
            ("📤  Exportar actual", CYAN, self._export_current_json),
            ("📄  Descargar plantilla", MUTED2, self._export_template),
        ]:
            ctk.CTkButton(io_row, text=text, height=36, font=("Arial Bold", 11),
                           fg_color=SURFACE2, hover_color=SURFACE3,
                           border_color=color, border_width=1, text_color=color, corner_radius=8,
                           command=cmd).pack(side="left", padx=(0, 8))

    def _load_preset(self, name, cfg):
        self.on_load(name, cfg)
        self.destroy()

    def _save_current(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Aviso", "Escribe un nombre para el preset.", parent=self)
            return
        if name in DEFAULT_PRESETS:
            messagebox.showwarning("Aviso", "No puedes sobreescribir un preset de sistema.", parent=self)
            return
        self.presets[name] = self.current_cfg
        save_user_presets(self.presets)
        messagebox.showinfo("Guardado", f'Preset "{name}" guardado.', parent=self)
        self.destroy()

    def _delete_preset(self, name):
        if messagebox.askyesno("Confirmar", f'¿Eliminar el preset "{name}"?', parent=self):
            del self.presets[name]
            save_user_presets(self.presets)
            self.destroy()

    def _import_json(self):
        path = filedialog.askopenfilename(title="Importar configuración JSON",
                                           filetypes=[("JSON", "*.json"), ("Todos", "*.*")], parent=self)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _validate_preset_cfg(cfg)
            name = cfg.get("name") or Path(path).stem
            self.presets[name] = cfg
            save_user_presets(self.presets)
            self.on_load(name, cfg)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error al importar", f"Formato incorrecto:\n\n{e}", parent=self)

    def _export_current_json(self):
        cfg = dict(self.current_cfg)
        name = cfg.get("description", "mi_revision")
        path = filedialog.asksaveasfilename(title="Exportar configuración actual",
                                             defaultextension=".json",
                                             initialfile=name.replace(" ", "_"),
                                             filetypes=[("JSON", "*.json")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}", parent=self)

    def _export_template(self):
        path = filedialog.asksaveasfilename(title="Guardar plantilla",
                                             defaultextension=".json",
                                             initialfile="plantilla_revision_prisma",
                                             filetypes=[("JSON", "*.json")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(PRESET_TEMPLATE, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Plantilla guardada", f"Guardada en:\n{path}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Bienvenida
# ══════════════════════════════════════════════════════════════════════════════
class WelcomeDialog(ctk.CTkToplevel):
    def __init__(self, parent, presets, on_select):
        super().__init__(parent)
        self.title("Bienvenido — Configurar revisión")
        self.geometry("700x560")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.grab_set()
        self.presets = presets
        self.on_select = on_select
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._blank_start)

    def _build(self):
        logo_frame = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=100)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="SysReview PRISMA  v2.0",
                     font=("Arial Black", 24), text_color=ACCENT2).pack(pady=(20, 0))
        ctk.CTkLabel(logo_frame, text="Pipeline Universal de Cribado Bibliográfico",
                     font=("Arial", 12), text_color=MUTED2).pack()

        ctk.CTkLabel(self, text="¿Qué tema de revisión vas a trabajar?",
                     font=("Arial Bold", 13), text_color=TEXT).pack(anchor="w", padx=28, pady=(16, 6))

        sb = ctk.CTkScrollableFrame(self, height=280, fg_color=SURFACE, corner_radius=12,
                                     border_color=BORDER, border_width=1)
        sb.pack(fill="x", padx=28, pady=(0, 14))

        for name, cfg in self.presets.items():
            is_default = name in DEFAULT_PRESETS
            row = ctk.CTkFrame(sb, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", pady=3)
            dot = ctk.CTkFrame(row, fg_color=ACCENT if is_default else TEAL, width=4, corner_radius=2)
            dot.pack(side="left", fill="y", padx=(0, 10))
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, pady=8)
            ctk.CTkLabel(info, text=name, font=("Arial Bold", 12), text_color=TEXT, anchor="w").pack(anchor="w")
            yr_f = cfg.get("year_from", "")
            yr_t = cfg.get("year_to", "")
            desc = cfg.get("description", "")
            meta = f"{desc}  ·  {yr_f}–{yr_t}" if desc else f"{yr_f}–{yr_t}"
            ctk.CTkLabel(info, text=meta, font=("Arial", 10), text_color=MUTED2, anchor="w").pack(anchor="w")
            ctk.CTkButton(row, text="Usar →", width=86, height=32,
                           font=("Arial Bold", 10), fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                           corner_radius=6,
                           command=lambda c=cfg, n=name: self._pick(n, c)).pack(side="right", padx=10, pady=8)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=28, pady=(0, 8))
        ctk.CTkButton(btn_row, text="📂  Cargar desde JSON...", height=40,
                       font=("Arial Bold", 12), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=TEAL, border_width=1, text_color=TEAL, corner_radius=10,
                       command=self._import_json).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(btn_row, text="📄  Descargar plantilla JSON", height=40,
                       font=("Arial Bold", 12), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=CYAN, border_width=1, text_color=CYAN, corner_radius=10,
                       command=self._export_template).pack(side="left", fill="x", expand=True, padx=(6, 0))

        ctk.CTkButton(self, text="✦  Empezar desde cero", height=40,
                       font=("Arial Bold", 12), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=BORDER, border_width=1, text_color=MUTED2, corner_radius=10,
                       command=self._blank_start).pack(fill="x", padx=28, pady=(0, 20))

    def _pick(self, name, cfg):
        self.on_select(name, cfg)
        self.destroy()

    def _blank_start(self):
        self.on_select("Nueva revisión", {})
        self.destroy()

    def _import_json(self):
        path = filedialog.askopenfilename(title="Seleccionar JSON",
                                           filetypes=[("JSON", "*.json"), ("Todos", "*.*")], parent=self)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _validate_preset_cfg(cfg)
            name = cfg.get("name") or Path(path).stem
            self.on_select(name, cfg)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error al cargar JSON", f"Formato incorrecto:\n\n{e}", parent=self)

    def _export_template(self):
        path = filedialog.asksaveasfilename(title="Guardar plantilla",
                                             defaultextension=".json",
                                             initialfile="mi_revision_prisma_template",
                                             filetypes=[("JSON", "*.json")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(PRESET_TEMPLATE, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Plantilla guardada", f"Guardada en:\n{path}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Detalle de artículo con revisión manual
# ══════════════════════════════════════════════════════════════════════════════
class ArticleDetailDialog(ctk.CTkToplevel):
    def __init__(self, parent, row_data, on_override=None):
        super().__init__(parent)
        self.title("Detalle del artículo")
        self.geometry("920x680")
        self.configure(fg_color=BG)
        self.row_data = row_data
        self.on_override = on_override
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        title_short = str(self.row_data.get("title", ""))[:80]
        ctk.CTkLabel(hdr, text=title_short, font=("Arial Bold", 12), text_color=TEXT,
                     anchor="w", wraplength=700).pack(side="left", padx=20, pady=12)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        meta = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        meta.pack(fill="x", pady=(0, 10))
        for label, key in [("Año", "year"), ("Fuente", "source"), ("Tipo", "doc_type")]:
            f = ctk.CTkFrame(meta, fg_color="transparent")
            f.pack(side="left", padx=16, pady=8)
            ctk.CTkLabel(f, text=label, font=("Courier", 9), text_color=MUTED).pack()
            ctk.CTkLabel(f, text=str(self.row_data.get(key, "—")),
                         font=("Arial Bold", 11), text_color=ACCENT2).pack()

        decision = self.row_data.get("Search_String_Pass", "")
        dec_color = GREEN if decision == "Yes" else RED
        df = ctk.CTkFrame(meta, fg_color="transparent")
        df.pack(side="right", padx=16, pady=8)
        ctk.CTkLabel(df, text="Decisión PRISMA", font=("Courier", 9), text_color=MUTED).pack()
        ctk.CTkLabel(df, text="✓ INCLUIDO" if decision == "Yes" else "✗ EXCLUIDO",
                     font=("Arial Bold", 11), text_color=dec_color).pack()

        tab_view = ctk.CTkTabview(body, fg_color=SURFACE, segmented_button_fg_color=SURFACE2,
                                   segmented_button_selected_color=ACCENT,
                                   segmented_button_unselected_color=SURFACE2)
        tab_view.pack(fill="both", expand=True)
        tab_view.add("Resumen")
        tab_view.add("Abstract")
        tab_view.add("Bloques")
        tab_view.add("Metadatos")

        sum_tab = tab_view.tab("Resumen")
        for label, key in [("DOI", "doi"), ("Autores", "authors"), ("Keywords", "keywords")]:
            row = ctk.CTkFrame(sum_tab, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=("Courier", 10), text_color=MUTED, width=80,
                         anchor="w").pack(side="left", padx=10, pady=8)
            val = str(self.row_data.get(key, "—"))[:200]
            ctk.CTkLabel(row, text=val, font=("Arial", 10), text_color=TEXT, anchor="w",
                         wraplength=640).pack(side="left", padx=4)

        reason = str(self.row_data.get("Reason_for_exclusion", "") or self.row_data.get("Search_String_Reason", ""))
        if reason:
            rrow = ctk.CTkFrame(sum_tab, fg_color=RED_DIM if decision != "Yes" else GREEN_DIM,
                                corner_radius=8, border_color=RED if decision != "Yes" else GREEN, border_width=1)
            rrow.pack(fill="x", pady=6)
            ctk.CTkLabel(rrow, text=f"Razón: {reason}", font=("Arial", 10),
                         text_color=RED if decision != "Yes" else GREEN, wraplength=700, justify="left").pack(
                padx=12, pady=8, anchor="w")

        abs_tab = tab_view.tab("Abstract")
        st = scrolledtext.ScrolledText(abs_tab, bg=SURFACE2, fg=TEXT, font=("Arial", 11),
                                        wrap="word", relief="flat")
        st.pack(fill="both", expand=True)
        st.insert("1.0", str(self.row_data.get("abstract", "—")))
        st.configure(state="disabled")

        blk_tab = tab_view.tab("Bloques")
        matched = str(self.row_data.get("Matched_Blocks", ""))
        missing = str(self.row_data.get("Missing_Blocks", ""))
        blk_info = ctk.CTkScrollableFrame(blk_tab, fg_color=BG)
        blk_info.pack(fill="both", expand=True)
        ctk.CTkLabel(blk_info, text="✅  Bloques cumplidos:", font=("Courier Bold", 11), text_color=GREEN).pack(anchor="w", pady=(8, 2))
        for b in matched.split(","):
            b = b.strip()
            if b:
                ctk.CTkLabel(blk_info, text=f"    ✓  {b}", font=("Courier", 11), text_color=GREEN).pack(anchor="w")
        ctk.CTkLabel(blk_info, text="❌  Bloques faltantes:", font=("Courier Bold", 11), text_color=RED).pack(anchor="w", pady=(10, 2))
        for b in missing.split(","):
            b = b.strip()
            if b:
                ctk.CTkLabel(blk_info, text=f"    ✗  {b}", font=("Courier", 11), text_color=RED).pack(anchor="w")

        meta_tab = tab_view.tab("Metadatos")
        st2 = scrolledtext.ScrolledText(meta_tab, bg=SURFACE2, fg=TEXT, font=("Consolas", 10),
                                         wrap="word", relief="flat")
        st2.pack(fill="both", expand=True)
        for k, v in self.row_data.items():
            st2.insert("end", f"{k}:\n", "key")
            st2.insert("end", f"  {v}\n\n")
        st2.tag_configure("key", foreground=ACCENT2, font=("Consolas", 10, "bold"))
        st2.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Informe PRISMA con diagrama de flujo canvas
# ══════════════════════════════════════════════════════════════════════════════
class PrismaReportDialog(ctk.CTkToplevel):
    def __init__(self, parent, counts, review_name, search_blocks):
        super().__init__(parent)
        self.title(f"Informe PRISMA — {review_name}")
        self.geometry("900x760")
        self.configure(fg_color=BG)
        self.counts = counts
        self.review_name = review_name
        self.search_blocks = search_blocks
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📋  Informe PRISMA", font=("Arial Black", 15), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(10, 0))
        ctk.CTkLabel(hdr, text=self.review_name, font=("Arial", 11), text_color=MUTED2).pack(anchor="w", padx=24)

        tabs = ctk.CTkTabview(self, fg_color=BG, segmented_button_fg_color=SURFACE2,
                               segmented_button_selected_color=ACCENT,
                               segmented_button_unselected_color=SURFACE2)
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        tabs.add("Diagrama de flujo")
        tabs.add("Resumen texto")

        canvas_tab = tabs.tab("Diagrama de flujo")
        canvas = tk.Canvas(canvas_tab, bg=SURFACE2, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self.after(100, lambda: self._draw_prisma_diagram(canvas))

        text_tab = tabs.tab("Resumen texto")
        text_content = self._build_text()
        st = scrolledtext.ScrolledText(text_tab, bg=SURFACE2, fg=TEXT, font=("Consolas", 10),
                                        wrap="word", relief="flat")
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("1.0", text_content)
        st.configure(state="disabled")

        btn_row = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        ctk.CTkButton(btn_row, text="📋 Copiar texto", height=36, font=("Arial Bold", 12),
                       fg_color=ACCENT, text_color="white", corner_radius=8,
                       command=lambda: self._copy(text_content)).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="💾 Guardar .txt", height=36, font=("Arial Bold", 12),
                       fg_color=SURFACE2, border_color=TEAL, border_width=1, text_color=TEAL, corner_radius=8,
                       command=lambda: self._save_txt(text_content)).pack(side="left")

    def _draw_prisma_diagram(self, canvas):
        canvas.update_idletasks()
        W = canvas.winfo_width() or 860
        pc = self.counts

        total = pc.get("identified_total", 0)
        n_sco = pc.get("identified_scopus", 0)
        n_cla = pc.get("identified_clarivate", 0)
        dups = pc.get("duplicates_total", 0)
        after_dup = pc.get("after_duplicates", total - dups)
        exc_year = pc.get("excluded_year", 0)
        exc_doc = pc.get("excluded_doc_type", 0)
        exc_req = pc.get("excluded_required", 0)
        exc_sec = pc.get("excluded_secondary", 0)
        exc_kw = pc.get("excluded_keywords", 0)
        exc_search = pc.get("excluded_search_string", 0)
        included = pc.get("included_final", 0)

        bw, bh = 280, 52
        cx = W // 2
        col_exc = W - 160
        y_gap = 90

        def box(x, y, label, value, color=ACCENT, width=bw):
            x0, y0 = x - width // 2, y - bh // 2
            x1, y1 = x + width // 2, y + bh // 2
            r = 8
            canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=SURFACE3, outline=color, width=2)
            canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=SURFACE3, outline=color, width=2)
            canvas.create_oval(x0, y0, x0 + 2*r, y0 + 2*r, fill=SURFACE3, outline=color, width=2)
            canvas.create_oval(x1 - 2*r, y0, x1, y0 + 2*r, fill=SURFACE3, outline=color, width=2)
            canvas.create_oval(x0, y1 - 2*r, x0 + 2*r, y1, fill=SURFACE3, outline=color, width=2)
            canvas.create_oval(x1 - 2*r, y1 - 2*r, x1, y1, fill=SURFACE3, outline=color, width=2)
            canvas.create_text(x, y - 10, text=str(value), font=("Arial Black", 18), fill=color)
            canvas.create_text(x, y + 14, text=label, font=("Arial", 9), fill=MUTED2)

        def exc_box(x, y, label, value):
            w = 200
            x0, y0 = x - w // 2, y - 24
            x1, y1 = x + w // 2, y + 24
            canvas.create_rectangle(x0, y0, x1, y1, fill=RED_DIM, outline=RED, width=1, dash=(4, 3))
            canvas.create_text(x, y - 8, text=str(value), font=("Arial Bold", 12), fill=RED)
            canvas.create_text(x, y + 10, text=label, font=("Arial", 8), fill=MUTED2)

        def arrow(x1, y1, x2, y2, color=MUTED):
            canvas.create_line(x1, y1, x2, y2, fill=color, width=2, arrow=tk.LAST)

        def section_label(x, y, text, color):
            canvas.create_text(x, y, text=text, font=("Courier Bold", 9), fill=color, anchor="w")

        phases = [
            (30, 56, "IDENTIFICACIÓN", ACCENT2),
            (30, 166, "CRIBADO", YELLOW),
            (30, 300, "ELEGIBILIDAD", ORANGE),
            (30, 490, "INCLUIDOS", GREEN),
        ]
        for px, py, plabel, pcolor in phases:
            section_label(px, py, plabel, pcolor)

        y = 80
        box(cx - 180, y, f"Scopus ({n_sco})", n_sco, SCOPUS, 180)
        box(cx + 180, y, f"Clarivate ({n_cla})", n_cla, CLARIVATE, 180)
        arrow(cx - 180, y + 26, cx - 50, y + 60)
        arrow(cx + 180, y + 26, cx + 50, y + 60)

        y2 = 160
        box(cx, y2, "Total identificados", total, ACCENT2)
        arrow(cx, y2 + 26, cx, y2 + 64)

        y3 = y2 + y_gap
        box(cx, y3, "Después de duplicados", after_dup, YELLOW)
        exc_box(col_exc, y3, f"Duplicados: {dups}", dups)
        arrow(cx + bw // 2, y3, col_exc - 100, y3, RED)
        arrow(cx, y3 + 26, cx, y3 + 64)

        y4 = y3 + y_gap
        box(cx, y4, "Tras filtro de año", after_dup - exc_year, ORANGE)
        exc_box(col_exc, y4, f"Fuera de rango: {exc_year}", exc_year)
        arrow(cx + bw // 2, y4, col_exc - 100, y4, RED)
        arrow(cx, y4 + 26, cx, y4 + 64)

        y5 = y4 + y_gap
        box(cx, y5, "Tras filtro de tipo", after_dup - exc_year - exc_doc, ORANGE)
        exc_box(col_exc, y5, f"Tipo excluido: {exc_doc}", exc_doc)
        arrow(cx + bw // 2, y5, col_exc - 100, y5, RED)
        arrow(cx, y5 + 26, cx, y5 + 64)

        y6 = y5 + y_gap
        total_kw = exc_req + exc_sec + exc_kw
        box(cx, y6, "Tras cribado keywords", after_dup - exc_year - exc_doc - total_kw, ORANGE)
        exc_box(col_exc, y6, f"Kw excluidos: {total_kw}", total_kw)
        arrow(cx + bw // 2, y6, col_exc - 100, y6, RED)
        arrow(cx, y6 + 26, cx, y6 + 64)

        y7 = y6 + y_gap
        box(cx, y7, "Tras validación bloques", included + exc_search, ORANGE)
        exc_box(col_exc, y7, f"Faltan bloques: {exc_search}", exc_search)
        arrow(cx + bw // 2, y7, col_exc - 100, y7, RED)
        arrow(cx, y7 + 26, cx, y7 + 64)

        y8 = y7 + y_gap
        box(cx, y8, "✅ ARTÍCULOS INCLUIDOS", included, GREEN)

    def _build_text(self):
        pc = self.counts
        total = pc.get("identified_total", 0)
        included = pc.get("included_final", 0)
        pct = f"{included/total*100:.1f}%" if total else "—"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        text = f"""
INFORME PRISMA — {self.review_name}
Generado: {ts}
{'═'*60}

IDENTIFICACIÓN
  Total identificados:            {total}
    ↳ Scopus:                     {pc.get('identified_scopus', 0)}
    ↳ Clarivate / WoS:            {pc.get('identified_clarivate', 0)}

DEDUPLICACIÓN
  Duplicados eliminados:          {pc.get('duplicates_total', 0)}
    ↳ Por DOI:                    {pc.get('duplicates_doi', 0)}
    ↳ Por título:                 {pc.get('duplicates_title', 0)}
  Únicos para cribar:             {pc.get('after_duplicates', 0)}

ELEGIBILIDAD — EXCLUSIONES
  Por año (fuera del rango):      {pc.get('excluded_year', 0)}
  Por tipo de documento:          {pc.get('excluded_doc_type', 0)}
  Por bloque obligatorio:         {pc.get('excluded_required', 0)}
  Por bloque secundario:          {pc.get('excluded_secondary', 0)}
  Por términos de exclusión:      {pc.get('excluded_keywords', 0)}
  Por bloques de cadena:          {pc.get('excluded_search_string', 0)}

INCLUIDOS
  Artículos incluidos finales:    {included}
  Tasa de inclusión:              {pct}

BLOQUES DE BÚSQUEDA
{'─'*40}
"""
        for bid, block in self.search_blocks.items():
            terms = [t.strip() for t in block.get("terms", "").split(",") if t.strip()]
            text += f"  {bid}: {block.get('label', bid)}\n"
            text += f"    Términos ({len(terms)}): {', '.join(terms[:6])}{'...' if len(terms) > 6 else ''}\n\n"
        return text

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copiado", "Informe copiado al portapapeles.", parent=self)

    def _save_txt(self, text):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             initialfile=f"Informe_PRISMA_{self.review_name.replace(' ', '_')}",
                                             filetypes=[("Texto", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Guardado", f"Informe guardado en:\n{path}")


# ══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class SysReviewApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SysReview PRISMA  v2.0  ·  Pipeline Universal de Cribado")
        self.geometry("1440x960")
        self.minsize(1120, 780)
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self.presets = load_user_presets()
        self.review_name = tk.StringVar(value="Nueva revisión")
        self.scopus_path = None
        self.clarivate_path = None

        self.df_combinado = None
        self.df_dedup = None
        self.df_limpio = None
        self.df_screening = None
        self.df_final = None

        self._search_blocks = dict(list(DEFAULT_PRESETS.values())[0]["search_blocks"])

        self.prisma_counts = {
            "identified_total": 0, "identified_scopus": 0, "identified_clarivate": 0,
            "duplicates_doi": 0, "duplicates_title": 0, "duplicates_total": 0,
            "after_duplicates": 0, "excluded_year": 0, "excluded_doc_type": 0,
            "excluded_required": 0, "excluded_secondary": 0, "excluded_keywords": 0,
            "excluded_search_string": 0, "included_final": 0,
        }
        self._sort_col = None
        self._sort_asc = True

        self._build_ui()
        self.after(300, self._show_welcome)

    # ══════════════════════════════════════════════════════════════════════════
    # UI PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=66)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        logo = ctk.CTkFrame(hdr, fg_color=ACCENT, width=40, height=40, corner_radius=10)
        logo.pack(side="left", padx=(18, 10), pady=13)
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="P", font=("Arial Black", 20), text_color="white").place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(hdr, text="SysReview PRISMA", font=("Arial Black", 16), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hdr, text="  v2.0  ·  Pipeline Universal de Cribado Bibliográfico",
                     font=("Arial", 11), text_color=MUTED2).pack(side="left")

        name_frame = ctk.CTkFrame(hdr, fg_color=SURFACE2, corner_radius=8)
        name_frame.pack(side="right", padx=(0, 12), pady=14)
        ctk.CTkLabel(name_frame, text="Revisión:", font=("Courier", 10), text_color=MUTED).pack(side="left", padx=(10, 4))
        ctk.CTkEntry(name_frame, textvariable=self.review_name, width=220, height=28,
                      font=("Arial Bold", 11), fg_color="transparent", border_width=0,
                      text_color=ACCENT2).pack(side="left", padx=(0, 8))

        ctk.CTkButton(hdr, text="⚙ Presets", width=100, height=34,
                       font=("Arial Bold", 11), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=BORDER, border_width=1, text_color=MUTED2, corner_radius=8,
                       command=self._open_presets).pack(side="right", padx=(0, 8), pady=16)
        ctk.CTkButton(hdr, text="📋 Informe PRISMA", width=150, height=34,
                       font=("Arial Bold", 11), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=BORDER, border_width=1, text_color=CYAN, corner_radius=8,
                       command=self._show_prisma_report).pack(side="right", padx=(0, 4), pady=16)

        main_row = ctk.CTkFrame(self, fg_color=BG)
        main_row.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(main_row, fg_color=SURFACE, width=240, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="PIPELINE", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(20, 8))

        self._tab_btns = []
        steps_def = [
            ("1", "Cargar Archivos", "📁", "Importa Scopus CSV y WoS Excel"),
            ("2", "Deduplicar", "🔗", "Detecta duplicados por DOI y título"),
            ("3", "Cribado PRISMA", "🔬", "Aplica filtros y cadena de búsqueda"),
            ("4", "Resultados", "📊", "Tabla interactiva y exportación"),
        ]
        for num, label, icon, hint in steps_def:
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon}  Paso {num} — {label}",
                anchor="w", height=46,
                fg_color="transparent", hover_color=SURFACE2,
                font=("Arial", 12), text_color=MUTED, corner_radius=10,
                command=lambda n=int(num)-1: self._show_tab(n),
            )
            btn.pack(fill="x", padx=8, pady=2)
            Tooltip(btn, hint)
            self._tab_btns.append(btn)

        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(sidebar, text="RESUMEN RÁPIDO", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 8))
        self.sidebar_stats = {}
        stat_defs = [
            ("total", "Identificados", MUTED2),
            ("unique", "Únicos", ACCENT2),
            ("final", "Incluidos ✓", GREEN),
        ]
        for key, label, color in stat_defs:
            row = ctk.CTkFrame(sidebar, fg_color=SURFACE2, corner_radius=8, height=50)
            row.pack(fill="x", padx=8, pady=2)
            row.pack_propagate(False)
            var = tk.StringVar(value="—")
            self.sidebar_stats[key] = var
            ctk.CTkLabel(row, textvariable=var, font=("Arial Black", 18), text_color=color).pack(side="right", padx=12)
            ctk.CTkLabel(row, text=label, font=("Courier", 10), text_color=MUTED, anchor="w").pack(side="left", padx=10)

        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(sidebar, text="PROGRESO GLOBAL", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 6))
        self.global_progress = ctk.CTkProgressBar(sidebar, height=8, corner_radius=4,
                                                    fg_color=SURFACE2, progress_color=ACCENT)
        self.global_progress.pack(fill="x", padx=12)
        self.global_progress.set(0)
        self.lbl_progress = ctk.CTkLabel(sidebar, text="Sin datos", font=("Courier", 9), text_color=MUTED)
        self.lbl_progress.pack(anchor="w", padx=14, pady=4)

        self._content = ctk.CTkFrame(main_row, fg_color=BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        self._screens = [
            self._build_screen_load(),
            self._build_screen_dedup(),
            self._build_screen_cribar(),
            self._build_screen_results(),
        ]
        self._show_tab(0)

    def _show_tab(self, idx):
        for s in self._screens:
            s.pack_forget()
        self._screens[idx].pack(fill="both", expand=True)
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.configure(fg_color=ACCENT, text_color="white", font=("Arial Bold", 12))
            else:
                btn.configure(fg_color="transparent", text_color=MUTED, font=("Arial", 12))

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 1 — CARGA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_load(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "📁  Paso 1 — Cargar Archivos de Búsqueda",
                        "Importa los resultados exportados de Scopus (.csv) y Web of Science / Clarivate (.xlsx/.xls)")

        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)

        help_frame = ctk.CTkFrame(body, fg_color="#eff6ff", corner_radius=8,
                                   border_color="#bfdbfe", border_width=1)
        help_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(help_frame,
                     text="💡  Scopus → Exportar como CSV (todos los campos).  "
                          "WoS/Clarivate → Exportar como Excel (.xlsx).  "
                          "Columnas necesarias: Title, Year, Abstract, DOI, Document Type, Authors, Author Keywords.",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=960, justify="left").pack(anchor="w", padx=14, pady=8)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))

        self.btn_scopus = ctk.CTkButton(btn_row, text="📄  SCOPUS  (.csv)", height=64,
                                         fg_color=SURFACE2, hover_color=SURFACE3,
                                         border_color=SCOPUS, border_width=2,
                                         font=("Arial Black", 13), text_color=TEXT, corner_radius=14,
                                         command=lambda: self._pick_file("scopus"))
        self.btn_scopus.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_clarivate = ctk.CTkButton(btn_row, text="📊  CLARIVATE / WoS  (.xlsx/.xls)", height=64,
                                            fg_color=SURFACE2, hover_color=SURFACE3,
                                            border_color=CLARIVATE, border_width=2,
                                            font=("Arial Black", 13), text_color=TEXT, corner_radius=14,
                                            command=lambda: self._pick_file("clarivate"))
        self.btn_clarivate.pack(side="left", fill="x", expand=True, padx=(8, 0))

        lbl_row = ctk.CTkFrame(body, fg_color="transparent")
        lbl_row.pack(fill="x")
        self.lbl_scopus = ctk.CTkLabel(lbl_row, text="Sin archivo", font=("Courier", 11), text_color=MUTED)
        self.lbl_clarivate = ctk.CTkLabel(lbl_row, text="Sin archivo", font=("Courier", 11), text_color=MUTED)
        self.lbl_scopus.pack(side="left", expand=True)
        self.lbl_clarivate.pack(side="right", expand=True)

        map_card = _card_frame(body, "MAPEO DE COLUMNAS  (opcional — solo si tus exportaciones usan nombres no estándar)")
        map_inner = ctk.CTkFrame(map_card, fg_color="transparent")
        map_inner.pack(fill="x")
        self._col_map = {}
        col_defaults = {
            "title": "Title", "year": "Year / Publication Year",
            "abstract": "Abstract", "doi": "DOI",
            "doc_type": "Document Type", "authors": "Authors",
            "keywords": "Author Keywords",
        }
        pairs = list(col_defaults.items())
        for i in range(0, len(pairs), 2):
            row = ctk.CTkFrame(map_inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            for j in range(2):
                if i + j >= len(pairs):
                    break
                k, v = pairs[i + j]
                sub = ctk.CTkFrame(row, fg_color="transparent")
                sub.pack(side="left", fill="x", expand=True, padx=(0 if j == 0 else 8, 0))
                ctk.CTkLabel(sub, text=f"{k}:", font=("Courier", 10), text_color=MUTED2, width=80, anchor="w").pack(side="left")
                e = ctk.CTkEntry(sub, height=28, font=("Courier", 11), fg_color=SURFACE2,
                                  border_color=BORDER, text_color=TEXT, placeholder_text=v)
                e.pack(side="left", fill="x", expand=True)
                self._col_map[k] = e

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=14)
        self.load_stat_sco = _stat_card(stats, "Scopus", "—", SCOPUS)
        self.load_stat_cla = _stat_card(stats, "Clarivate/WoS", "—", CLARIVATE)
        self.load_stat_tot = _stat_card(stats, "Total identificados", "—", TEXT)

        self.btn_combine = ctk.CTkButton(body, text="▶  Combinar y preparar datos",
                                          height=50, font=("Arial Black", 14),
                                          fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                                          corner_radius=12, state="disabled",
                                          command=self._run_combine)
        self.btn_combine.pack(fill="x", pady=(4, 12))

        _log_label(body, "LOG DE CARGA")
        self.log_load = _log_area(body, height=10)
        return frame

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 2 — DEDUPLICACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_dedup(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "🔗  Paso 2 — Eliminar Duplicados",
                        "Detecta y elimina duplicados por DOI exacto y por coincidencia de título")

        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 14))
        self.dedup_stat_total = _stat_card(stats, "Total inicial", "—", MUTED2)
        self.dedup_stat_doi = _stat_card(stats, "Dupl. por DOI", "—", RED)
        self.dedup_stat_title = _stat_card(stats, "Dupl. por Título", "—", YELLOW)
        self.dedup_stat_total2 = _stat_card(stats, "Total eliminados", "—", RED)
        self.dedup_stat_uniq = _stat_card(stats, "Artículos únicos", "—", GREEN)

        opts = _card_frame(body, "OPCIONES DE DEDUPLICACIÓN")
        opts_inner = ctk.CTkFrame(opts, fg_color="transparent")
        opts_inner.pack(fill="x")

        self.dedup_by_doi = tk.BooleanVar(value=True)
        self.dedup_by_title = tk.BooleanVar(value=True)
        self.title_sim_var = tk.StringVar(value="Normalizada")

        ctk.CTkCheckBox(opts_inner, text="Deduplicar por DOI", variable=self.dedup_by_doi,
                         font=("Arial", 11), text_color=TEXT,
                         fg_color=ACCENT, hover_color=ACCENT2).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(opts_inner, text="Deduplicar por Título", variable=self.dedup_by_title,
                         font=("Arial", 11), text_color=TEXT,
                         fg_color=ACCENT, hover_color=ACCENT2).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(opts_inner, text="Coincidencia:", font=("Courier", 10), text_color=MUTED2).pack(side="left", padx=(20, 4))
        ctk.CTkSegmentedButton(opts_inner, values=["Exacta", "Normalizada"],
                                variable=self.title_sim_var, font=("Arial", 11),
                                fg_color=SURFACE2, selected_color=ACCENT, selected_hover_color=ACCENT2,
                                unselected_color=SURFACE2, text_color=TEXT).pack(side="left")

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 14))

        self.btn_dedup = ctk.CTkButton(btn_row, text="▶  Eliminar duplicados",
                                        height=46, font=("Arial Black", 13),
                                        fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                                        corner_radius=10, state="disabled",
                                        command=self._run_dedup)
        self.btn_dedup.pack(side="left", padx=(0, 10))

        self.btn_save_flagged = ctk.CTkButton(btn_row, text="💾  Exportar todos con banderas",
                                               height=46, font=("Arial Bold", 13),
                                               fg_color=SURFACE2, hover_color=SURFACE3,
                                               border_color=TEAL, border_width=1, text_color=TEAL,
                                               corner_radius=10, state="disabled",
                                               command=self._save_flagged)
        self.btn_save_flagged.pack(side="left")

        pipe_card = _card_frame(body, "PROGRESO DE DEDUPLICACIÓN")
        self.dedup_steps = {}
        for n, name, hint in [
            (1, "Carga DOI + Título", "Prepara campos para comparación"),
            (2, "Marcar duplicados por DOI", "DOI idéntico → duplicado"),
            (3, "Marcar duplicados por Título", "Título normalizado idéntico → duplicado"),
            (4, "Eliminar y guardar únicos", "Genera dataset limpio sin duplicados"),
        ]:
            row = ctk.CTkFrame(pipe_card, fg_color=SURFACE2, corner_radius=8, height=44)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            num_l = ctk.CTkLabel(row, text=str(n), width=30, height=30, fg_color=BORDER, corner_radius=15,
                                  font=("Arial Black", 11), text_color=MUTED)
            num_l.pack(side="left", padx=10, pady=6)
            name_l = ctk.CTkLabel(row, text=name, font=("Arial", 12), text_color=MUTED, anchor="w")
            name_l.pack(side="left")
            val_l = ctk.CTkLabel(row, text="—", font=("Courier", 10), text_color=MUTED, anchor="w")
            val_l.pack(side="right", padx=10)
            self.dedup_steps[n] = {"row": row, "num": num_l, "name": name_l, "val": val_l}
            Tooltip(row, hint)

        _log_label(body, "LOG DE DEDUPLICACIÓN")
        self.log_dedup = _log_area(body, height=12)
        return frame

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 3 — CRIBADO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_cribar(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "🔬  Paso 3 — Cribado PRISMA",
                        "Aplica filtros por año, tipo, keywords y validación por bloques de cadena de búsqueda")

        outer = ctk.CTkScrollableFrame(frame, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        body = ctk.CTkFrame(outer, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)

        left_col = ctk.CTkFrame(body, fg_color=BG)
        right_col = ctk.CTkFrame(body, fg_color=BG)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right_col.pack(side="left", fill="both", expand=True, padx=(10, 0))

        cfg = _card_frame(left_col, "CONFIGURACIÓN DEL FILTRO")

        yr_row = ctk.CTkFrame(cfg, fg_color="transparent")
        yr_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(yr_row, text="Rango de años:", font=("Courier", 11), text_color=MUTED2).pack(side="left")
        self.year_from = _num_entry(yr_row, 2016)
        ctk.CTkLabel(yr_row, text="  —  ", text_color=MUTED2).pack(side="left")
        self.year_to = _num_entry(yr_row, 2026)

        self.kw_required = _textarea(cfg,
            "🟠 Bloque OBLIGATORIO — al menos UNA debe aparecer en título/resumen/keywords",
            "Structural Health Monitoring, SHM, structural monitoring, structural damage detection",
            height=65, color=ORANGE)
        Tooltip(self.kw_required, "Si ninguno de estos términos aparece → artículo EXCLUIDO")

        self.kw_secondary = _textarea(cfg,
            "🟢 Bloque SECUNDARIO — al menos UNA debe aparecer",
            "Internet of Things, IoT, wireless sensor networks, MEMS, accelerometer, embedded systems",
            height=80, color=GREEN)
        Tooltip(self.kw_secondary, "Complementa el bloque obligatorio. Si falta → EXCLUIDO")

        self.kw_exclude = _textarea(cfg,
            "🔴 Términos de EXCLUSIÓN — si cualquiera aparece → EXCLUIDO",
            "medical monitoring, biomedical, patient monitoring, healthcare, ECG, EEG",
            height=90, color=RED)
        Tooltip(self.kw_exclude, "Términos que descalifican un artículo inmediatamente")

        self.doc_exclude = _textarea(cfg,
            "🚫 Tipos de documento a excluir",
            "review, systematic review, conference paper, editorial, letter, note, book chapter",
            height=52, color=MUTED)
        Tooltip(self.doc_exclude, "Tipos de documento que no entran al cribado")

        blk_hdr = ctk.CTkFrame(cfg, fg_color="transparent")
        blk_hdr.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(blk_hdr, text="🧩 Bloques de cadena de búsqueda",
                     font=("Courier", 11), text_color=MUTED2).pack(side="left")
        ctk.CTkButton(blk_hdr, text="✏ Editar bloques", height=28, width=130,
                       font=("Arial", 10), fg_color=SURFACE2, hover_color=SURFACE3,
                       border_color=TEAL, border_width=1, text_color=TEAL, corner_radius=6,
                       command=self._open_blocks_editor).pack(side="right")
        self.blocks_summary = ctk.CTkFrame(cfg, fg_color=SURFACE2, corner_radius=8)
        self.blocks_summary.pack(fill="x", pady=(0, 8))
        self._refresh_blocks_summary()

        min_row = ctk.CTkFrame(cfg, fg_color="transparent")
        min_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(min_row, text="Bloques mínimos requeridos:",
                     font=("Courier", 11), text_color=MUTED2).pack(side="left")
        self.min_blocks_entry = _num_entry(min_row, 5)
        Tooltip(self.min_blocks_entry, "Número de bloques que un artículo debe cumplir para ser INCLUIDO")

        pipe_card = _card_frame(right_col, "PROGRESO DEL CRIBADO")
        self.cribar_steps = {}
        steps = [
            (1, "Carga y normalización", "Prepara el dataframe"),
            (2, "Base sin duplicados", "Usa resultado del Paso 2"),
            (3, "Filtro de año", "Descarta fuera del rango"),
            (4, "Filtro de tipo de documento", "Elimina tipos excluidos"),
            (5, "Cribado por keywords", "Aplica bloques obligatorio/secundario/exclusión"),
            (6, "Validación por bloques", "Verifica cadena de búsqueda estructurada"),
        ]
        for n, name, hint in steps:
            row = ctk.CTkFrame(pipe_card, fg_color=SURFACE2, corner_radius=8, height=48)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            num_l = ctk.CTkLabel(row, text=str(n), width=32, height=32, fg_color=BORDER, corner_radius=16,
                                  font=("Arial Black", 12), text_color=MUTED)
            num_l.pack(side="left", padx=10, pady=7)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            name_l = ctk.CTkLabel(info, text=name, font=("Arial Bold", 12), text_color=MUTED, anchor="w")
            name_l.pack(anchor="w")
            val_l = ctk.CTkLabel(info, text="—", font=("Courier", 10), text_color=MUTED, anchor="w")
            val_l.pack(anchor="w")
            self.cribar_steps[n] = {"row": row, "num": num_l, "name": name_l, "val": val_l}
            Tooltip(row, hint)

        stats = ctk.CTkFrame(pipe_card, fg_color="transparent")
        stats.pack(fill="x", pady=(10, 0))
        self.cribar_stat_vars = {}
        for key, label, color in [
            ("total", "Identificados", TEXT),
            ("dedup", "Duplicados", YELLOW),
            ("filtered", "Excluidos", RED),
            ("final", "Incluidos", GREEN),
        ]:
            box = ctk.CTkFrame(stats, fg_color=SURFACE2, corner_radius=10)
            box.pack(side="left", fill="x", expand=True, padx=3)
            var = tk.StringVar(value="—")
            self.cribar_stat_vars[key] = var
            ctk.CTkLabel(box, textvariable=var, font=("Arial Black", 22), text_color=color).pack(pady=(8, 0))
            ctk.CTkLabel(box, text=label, font=("Courier", 10), text_color=MUTED2).pack(pady=(0, 8))

        ctk.CTkLabel(pipe_card, text="Distribución por fuente (incluidos)",
                     font=("Courier", 10), text_color=MUTED2).pack(anchor="w", pady=(10, 2))
        self.bar_canvas = tk.Canvas(pipe_card, height=14, bg=SURFACE3, highlightthickness=0, bd=0)
        self.bar_canvas.pack(fill="x")
        src_row = ctk.CTkFrame(pipe_card, fg_color="transparent")
        src_row.pack(fill="x", pady=(4, 0))
        self.lbl_src_sco = ctk.CTkLabel(src_row, text="Scopus: —", font=("Courier", 11), text_color=MUTED2)
        self.lbl_src_cla = ctk.CTkLabel(src_row, text="Clarivate: —", font=("Courier", 11), text_color=MUTED2)
        self.lbl_src_sco.pack(side="left", padx=(0, 20))
        self.lbl_src_cla.pack(side="left")

        _log_label(right_col, "LOG DEL CRIBADO")
        self.log_cribar = _log_area(right_col, height=12)

        self.btn_run = ctk.CTkButton(right_col, text="⚡  Ejecutar Cribado PRISMA",
                                      height=52, font=("Arial Black", 15),
                                      fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                                      corner_radius=14, state="disabled",
                                      command=self._start_pipeline)
        self.btn_run.pack(fill="x", pady=(10, 4))

        self.btn_save_cribar = ctk.CTkButton(right_col, text="⬇  Guardar artículos incluidos (.xlsx)",
                                              height=42, font=("Arial Bold", 13),
                                              fg_color=SURFACE2, hover_color=SURFACE3,
                                              border_color=GREEN, border_width=1, text_color=GREEN,
                                              corner_radius=12, state="disabled",
                                              command=self._save_results)
        self.btn_save_cribar.pack(fill="x", pady=(0, 4))

        self.btn_save_screening = ctk.CTkButton(right_col, text="📋  Guardar cribado completo con decisiones",
                                                 height=42, font=("Arial Bold", 13),
                                                 fg_color=SURFACE2, hover_color=SURFACE3,
                                                 border_color=CYAN, border_width=1, text_color=CYAN,
                                                 corner_radius=12, state="disabled",
                                                 command=self._save_screening_decisions)
        self.btn_save_screening.pack(fill="x", pady=(0, 8))
        return frame

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 4 — RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_results(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "📊  Paso 4 — Resultados y Exportación",
                        "Tabla interactiva de artículos incluidos. Doble clic en una fila para ver el detalle completo.")

        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 12))
        self.res_total = _stat_card(stats, "Identificados", "—", MUTED2)
        self.res_dedup = _stat_card(stats, "Dupl. eliminados", "—", YELLOW)
        self.res_cribar = _stat_card(stats, "Excluidos", "—", RED)
        self.res_final = _stat_card(stats, "Incluidos final", "—", ACCENT2)
        self.res_scopus = _stat_card(stats, "Scopus", "—", SCOPUS)
        self.res_clarivate = _stat_card(stats, "Clarivate/WoS", "—", CLARIVATE)

        toolbar = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        toolbar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(toolbar, text="🔍", font=("Arial", 14), text_color=MUTED2).pack(side="left", padx=(12, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_table())
        ctk.CTkEntry(toolbar, textvariable=self.search_var, width=360, height=34,
                      font=("Courier", 12), fg_color=SURFACE3, border_color=BORDER,
                      text_color=TEXT, placeholder_text="Buscar en título, DOI, autores, bloques...").pack(side="left", padx=(0, 12), pady=8)

        self.filter_source = tk.StringVar(value="Todas")
        ctk.CTkLabel(toolbar, text="Fuente:", font=("Courier", 10), text_color=MUTED2).pack(side="left")
        ctk.CTkSegmentedButton(toolbar, values=["Todas", "Scopus", "Clarivate"],
                                variable=self.filter_source, font=("Arial", 11),
                                fg_color=SURFACE3, selected_color=ACCENT, selected_hover_color=ACCENT2,
                                unselected_color=SURFACE3, text_color=TEXT,
                                command=lambda _: self._filter_table()).pack(side="left", padx=8)

        self.lbl_count = ctk.CTkLabel(toolbar, text="", font=("Courier", 10), text_color=MUTED2)
        self.lbl_count.pack(side="right", padx=12)

        tree_frame = tk.Frame(body, bg=BG)
        tree_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("SHM.Treeview", background=SURFACE, foreground=TEXT,
                         fieldbackground=SURFACE, rowheight=30, font=("Consolas", 9))
        style.configure("SHM.Treeview.Heading", background=SURFACE2, foreground=MUTED2,
                         font=("Arial Bold", 9), relief="flat")
        style.map("SHM.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])

        cols = ("#", "Año", "Título", "DOI", "Fuente", "Tipo Doc", "Bloques cumplidos")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="SHM.Treeview")
        widths = [38, 54, 420, 200, 90, 130, 170]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=f"{col} ▲▼", command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=w, minwidth=30)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("scopus",    background="#eef2ff", foreground="#3730a3")
        self.tree.tag_configure("clarivate", background="#fdf2f8", foreground="#9d174d")
        self.tree.bind("<Double-1>", self._on_row_dblclick)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))
        for text, color, border, cmd in [
            ("🔄 Actualizar tabla", MUTED2, BORDER, self._refresh_results),
            ("💾 Excel (incluidos)", TEXT, ACCENT, self._export_excel),
            ("💾 CSV (incluidos)", TEXT, TEAL, self._export_csv),
            ("📋 Todos con banderas", YELLOW, YELLOW, self._save_flagged),
            ("🧾 Decisiones PRISMA", GREEN, GREEN, self._save_screening_decisions),
        ]:
            ctk.CTkButton(btn_row, text=text, height=40, font=("Arial Bold", 11),
                           fg_color=SURFACE2, hover_color=SURFACE3,
                           border_color=border, border_width=1, text_color=color, corner_radius=10,
                           command=cmd).pack(side="left", padx=(0, 6))
        return frame

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE NEGOCIO
    # ══════════════════════════════════════════════════════════════════════════
    def _show_welcome(self):
        WelcomeDialog(self, self.presets, self._apply_preset).lift()

    def _open_presets(self):
        PresetDialog(self, self.presets, self._get_current_config(), self._apply_preset)

    def _get_current_config(self):
        return {
            "description": self.review_name.get(),
            "year_from": int(self.year_from.get() or 2015),
            "year_to": int(self.year_to.get() or 2026),
            "kw_required": self.kw_required.get("1.0", "end").strip(),
            "kw_secondary": self.kw_secondary.get("1.0", "end").strip(),
            "kw_exclude": self.kw_exclude.get("1.0", "end").strip(),
            "doc_exclude": self.doc_exclude.get("1.0", "end").strip(),
            "search_blocks": {k: dict(v) for k, v in self._search_blocks.items()},
            "min_blocks": int(self.min_blocks_entry.get() or 3),
        }

    def _apply_preset(self, name, cfg):
        self.review_name.set(name)
        if not cfg:
            return

        def _set(widget, val):
            widget.delete("1.0", "end")
            widget.insert("1.0", val)

        if "year_from" in cfg:
            self.year_from.delete(0, "end")
            self.year_from.insert(0, str(cfg["year_from"]))
        if "year_to" in cfg:
            self.year_to.delete(0, "end")
            self.year_to.insert(0, str(cfg["year_to"]))
        for field in ["kw_required", "kw_secondary", "kw_exclude", "doc_exclude"]:
            if field in cfg:
                _set(getattr(self, field), cfg[field])
        if "search_blocks" in cfg:
            self._search_blocks = {k: dict(v) for k, v in cfg["search_blocks"].items()}
            self._refresh_blocks_summary()
        if "min_blocks" in cfg:
            self.min_blocks_entry.delete(0, "end")
            self.min_blocks_entry.insert(0, str(cfg["min_blocks"]))
        col_map_data = cfg.get("col_map", {})
        if col_map_data and isinstance(col_map_data, dict):
            for field, col_name in col_map_data.items():
                if field in self._col_map and col_name:
                    self._col_map[field].delete(0, "end")
                    self._col_map[field].insert(0, str(col_name))

    def _open_blocks_editor(self):
        BlocksEditorDialog(self, self._search_blocks, self._on_blocks_saved)

    def _on_blocks_saved(self, new_blocks):
        self._search_blocks = new_blocks
        self._refresh_blocks_summary()
        try:
            n = int(self.min_blocks_entry.get())
            if n > len(new_blocks):
                self.min_blocks_entry.delete(0, "end")
                self.min_blocks_entry.insert(0, str(len(new_blocks)))
        except Exception:
            pass

    def _refresh_blocks_summary(self):
        for w in self.blocks_summary.winfo_children():
            w.destroy()
        inner = ctk.CTkFrame(self.blocks_summary, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=6)
        colors = [ACCENT2, TEAL, GREEN, YELLOW, CYAN, "#f472b6", "#fb923c"]
        for i, (bid, b) in enumerate(self._search_blocks.items()):
            c = colors[i % len(colors)]
            chip = ctk.CTkFrame(inner, fg_color=SURFACE3, corner_radius=6)
            chip.pack(side="left", padx=3)
            n_terms = len([t for t in b.get("terms", "").split(",") if t.strip()])
            ctk.CTkLabel(chip, text=f"{bid} ({n_terms}t)", font=("Courier", 9), text_color=c).pack(padx=8, pady=3)

    def _get_col_map(self):
        defaults = {
            "title": "Title", "year": "Year",
            "abstract": "Abstract", "doi": "DOI",
            "doc_type": "Document Type", "authors": "Authors",
            "keywords": "Author Keywords",
        }
        result = {}
        for k, e in self._col_map.items():
            val = e.get().strip()
            result[k] = val if val else defaults[k]
        return result

    def _pick_file(self, which):
        if which == "scopus":
            path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
            if path:
                self.scopus_path = path
                name = Path(path).name
                self.lbl_scopus.configure(text=f"✓  {name}", text_color=GREEN)
                self.btn_scopus.configure(border_color=GREEN)
                self._log_w(self.log_load, f"✓ Scopus: {name}\n", GREEN)
        else:
            path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")])
            if path:
                self.clarivate_path = path
                name = Path(path).name
                self.lbl_clarivate.configure(text=f"✓  {name}", text_color=GREEN)
                self.btn_clarivate.configure(border_color=GREEN)
                self._log_w(self.log_load, f"✓ Clarivate/WoS: {name}\n", GREEN)
        if self.scopus_path and self.clarivate_path:
            self.btn_combine.configure(state="normal")

    def _run_combine(self):
        self.btn_combine.configure(state="disabled", text="⏳  Cargando...")
        threading.Thread(target=self._task_combine, daemon=True).start()

    def _task_combine(self):
        try:
            self._log_w(self.log_load, "── Iniciando carga ──\n", ACCENT2)
            col_map = self._get_col_map()
            df_sco = self._read_file(self.scopus_path, "Scopus", col_map)
            df_cla = self._read_file(self.clarivate_path, "Clarivate", col_map)

            if df_cla["year"].isna().all() and "Publication Year" in df_cla.columns:
                df_cla["year"] = df_cla["Publication Year"]

            cols = ["title", "year", "abstract", "doi", "doc_type", "keywords", "authors", "source"]
            for c in cols:
                if c not in df_sco.columns:
                    df_sco[c] = ""
                if c not in df_cla.columns:
                    df_cla[c] = ""

            df_sco = self._normalize_base(df_sco[cols].copy())
            df_cla = self._normalize_base(df_cla[cols].copy())

            self.df_combinado = pd.concat([df_sco, df_cla], ignore_index=True)
            n_sco, n_cla = len(df_sco), len(df_cla)
            total = len(self.df_combinado)

            self.prisma_counts.update({
                "identified_scopus": int(n_sco),
                "identified_clarivate": int(n_cla),
                "identified_total": int(total),
            })

            def _ui():
                self.load_stat_sco.configure(text=str(n_sco))
                self.load_stat_cla.configure(text=str(n_cla))
                self.load_stat_tot.configure(text=str(total))
                self.btn_combine.configure(state="normal", text="▶  Combinar y preparar datos")
                self.btn_dedup.configure(state="normal")
                self.sidebar_stats["total"].set(str(total))
                self._update_progress()
            self.after(0, _ui)
            self._log_w(self.log_load,
                        f"\n✅ Combinación exitosa.\n"
                        f"   Scopus:        {n_sco}\n"
                        f"   Clarivate/WoS: {n_cla}\n"
                        f"   Total:         {total}\n"
                        f"➡ Continúa con el Paso 2.\n", GREEN)
        except Exception as e:
            import traceback
            self._log_w(self.log_load, f"✗ Error: {e}\n{traceback.format_exc()}\n", RED)
            self.after(0, lambda: self.btn_combine.configure(state="normal", text="▶  Combinar y preparar datos"))

    def _read_file(self, path, source_name, col_map):
        path_l = path.lower()
        if path_l.endswith(".csv"):
            try:
                df = pd.read_csv(path, on_bad_lines="skip", encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(path, on_bad_lines="skip", encoding="latin-1")
        elif path_l.endswith(".xls"):
            try:
                df = pd.read_excel(path, engine="xlrd")
            except ImportError:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "xlrd>=2.0.1", "-q"])
                importlib.invalidate_caches()
                df = pd.read_excel(path, engine="xlrd")
        else:
            df = pd.read_excel(path, engine="openpyxl")

        self._log_w(self.log_load, f"   {source_name} — columnas: {list(df.columns[:10])}\n", MUTED2)

        rename_map = {}
        for field, user_col in col_map.items():
            if user_col in df.columns:
                rename_map[user_col] = field
            else:
                wos_variants = {
                    "year": ["Publication Year", "PY"],
                    "title": ["Article Title", "TI"],
                    "doc_type": ["Document Type", "DT"],
                    "authors": ["Authors", "AU"],
                    "keywords": ["Author Keywords", "Author Keywords Plus", "ID"],
                }
                for variant in wos_variants.get(field, []):
                    if variant in df.columns:
                        rename_map[variant] = field
                        break

        df = df.rename(columns=rename_map)
        df["source"] = source_name
        return df

    def _normalize_base(self, df):
        for c in ["title", "abstract", "doi", "doc_type", "keywords", "authors", "source"]:
            if c not in df.columns:
                df[c] = ""
            df[c] = df[c].fillna("").astype(str).str.strip()
        if "year" not in df.columns:
            df["year"] = pd.NA
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        return df

    def _run_dedup(self):
        if self.df_combinado is None:
            messagebox.showwarning("Aviso", "Primero combina los archivos (Paso 1).")
            return
        self.btn_dedup.configure(state="disabled", text="⏳  Deduplicando...")
        threading.Thread(target=self._task_dedup, daemon=True).start()

    def _task_dedup(self):
        try:
            self._log_w(self.log_dedup, "── Iniciando deduplicación ──\n", ACCENT2)
            df = self.df_combinado.copy()
            total = len(df)

            self._set_dstep(1, "active", "Procesando...")
            df["_idx"] = range(len(df))
            self._set_dstep(1, "done", f"✓ {total} registros")

            self._set_dstep(2, "active", "Buscando...")
            dup_doi_idx = set()
            if self.dedup_by_doi.get():
                df_doi = df.copy()
                df_doi["_doi_norm"] = df_doi["doi"].astype(str).str.strip().str.lower()
                df_doi = df_doi[df_doi["_doi_norm"].str.len() > 4]
                dup_doi_idx = set(df_doi[df_doi.duplicated(subset="_doi_norm", keep="first")]["_idx"].tolist())
            self._set_dstep(2, "done", f"✓ {len(dup_doi_idx)} duplicados por DOI")

            self._set_dstep(3, "active", "Buscando...")
            dup_title_idx = set()
            if self.dedup_by_title.get():
                kept = df[~df["_idx"].isin(dup_doi_idx)].copy()
                if self.title_sim_var.get() == "Normalizada":
                    kept["_title_norm"] = (
                        kept["title"].astype(str).str.strip().str.lower()
                        .str.replace(r"[^a-z0-9\s]", "", regex=True)
                        .str.replace(r"\s+", " ", regex=True)
                    )
                else:
                    kept["_title_norm"] = kept["title"].astype(str).str.strip().str.lower()
                kept = kept[kept["_title_norm"].str.len() > 5]
                dup_title_idx = set(kept[kept.duplicated(subset="_title_norm", keep="first")]["_idx"].tolist())
            self._set_dstep(3, "done", f"✓ {len(dup_title_idx)} duplicados por título")

            self._set_dstep(4, "active", "Guardando únicos...")
            all_dups = dup_doi_idx | dup_title_idx
            df["Is_Duplicate"] = df["_idx"].apply(lambda i: "Duplicate" if i in all_dups else "Unique")
            df["Duplicate_Reason"] = ""
            df.loc[df["_idx"].isin(dup_doi_idx), "Duplicate_Reason"] = "Duplicate DOI"
            df.loc[df["_idx"].isin(dup_title_idx), "Duplicate_Reason"] = "Duplicate Title"

            for col in ["Stage", "Decision", "Reason_for_exclusion",
                        "Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]:
                df[col] = ""

            df.loc[df["Is_Duplicate"] == "Duplicate", "Stage"] = "Identification"
            df.loc[df["Is_Duplicate"] == "Duplicate", "Decision"] = "Exclude"
            df.loc[df["Is_Duplicate"] == "Duplicate", "Reason_for_exclusion"] = df.loc[
                df["Is_Duplicate"] == "Duplicate", "Duplicate_Reason"
            ]

            self.df_dedup = df.drop(columns=["_idx"], errors="ignore")
            self.df_limpio = (
                df[df["Is_Duplicate"] == "Unique"]
                .drop(columns=["_idx", "_doi_norm", "_title_norm"], errors="ignore")
                .reset_index(drop=True)
            )

            n_dups = len(all_dups)
            n_unique = total - n_dups
            self.prisma_counts.update({
                "duplicates_doi": int(len(dup_doi_idx)),
                "duplicates_title": int(len(dup_title_idx)),
                "duplicates_total": int(n_dups),
                "after_duplicates": int(n_unique),
            })
            self._set_dstep(4, "done", f"✓ {n_unique} únicos guardados")

            def _ui():
                self.dedup_stat_total.configure(text=str(total))
                self.dedup_stat_doi.configure(text=str(len(dup_doi_idx)))
                self.dedup_stat_title.configure(text=str(len(dup_title_idx)))
                self.dedup_stat_total2.configure(text=str(n_dups))
                self.dedup_stat_uniq.configure(text=str(n_unique))
                self.btn_dedup.configure(state="normal", text="▶  Eliminar duplicados")
                self.btn_save_flagged.configure(state="normal")
                self.btn_run.configure(state="normal")
                self.sidebar_stats["unique"].set(str(n_unique))
                self._update_progress()
            self.after(0, _ui)
            self._log_w(self.log_dedup,
                        f"\n✅ Deduplicación completada.\n"
                        f"   Total inicial:    {total}\n"
                        f"   Dupl. DOI:        {len(dup_doi_idx)}\n"
                        f"   Dupl. título:     {len(dup_title_idx)}\n"
                        f"   Total eliminados: {n_dups}\n"
                        f"   Únicos restantes: {n_unique}\n"
                        f"➡ Continúa con el Paso 3.\n", GREEN)
        except Exception as e:
            self._log_w(self.log_dedup, f"✗ Error: {e}\n", RED)
            self.after(0, lambda: self.btn_dedup.configure(state="normal", text="▶  Eliminar duplicados"))

    def _start_pipeline(self):
        self.btn_run.configure(state="disabled", text="⏳  Procesando...")
        self.btn_save_cribar.configure(state="disabled")
        self.btn_save_screening.configure(state="disabled")
        for i in range(1, 7):
            self._set_cstep(i, "idle", "—")
        self._log_w(self.log_cribar, "── Iniciando cribado PRISMA ──\n", ACCENT2)
        threading.Thread(target=self._task_pipeline, daemon=True).start()

    def _task_pipeline(self):
        try:
            kw_req = [k.strip().lower() for k in self.kw_required.get("1.0", "end").split(",") if k.strip()]
            kw_sec = [k.strip().lower() for k in self.kw_secondary.get("1.0", "end").split(",") if k.strip()]
            kw_exc = [k.strip().lower() for k in self.kw_exclude.get("1.0", "end").split(",") if k.strip()]
            doc_exc = [k.strip().lower() for k in self.doc_exclude.get("1.0", "end").split(",") if k.strip()]
            min_blocks = int(self.min_blocks_entry.get())
            year_from = int(self.year_from.get())
            year_to = int(self.year_to.get())

            if self.df_limpio is not None:
                df = self.df_limpio.copy()
                duplicates_removed = self.prisma_counts["duplicates_total"]
            elif self.df_combinado is not None:
                base = self.df_combinado.copy()
                before = len(base)
                base["_doi_c"] = base["doi"].astype(str).str.strip().str.lower()
                base["_title_c"] = base["title"].astype(str).str.strip().str.lower()
                base = base.drop_duplicates(subset="_doi_c", keep="first")
                base = base.drop_duplicates(subset="_title_c", keep="first")
                duplicates_removed = before - len(base)
                df = base.drop(columns=["_doi_c", "_title_c"], errors="ignore")
                self.prisma_counts.update({
                    "duplicates_total": int(duplicates_removed),
                    "after_duplicates": int(len(df)),
                })
            else:
                self._log_w(self.log_cribar, "✗ No hay datos. Completa los pasos previos.\n", RED)
                self.after(0, lambda: self.btn_run.configure(state="normal", text="⚡  Ejecutar Cribado PRISMA"))
                return

            for col in ["Stage", "Decision", "Reason_for_exclusion",
                        "Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]:
                if col not in df.columns:
                    df[col] = ""

            # STEP 1
            self._set_cstep(1, "active", "Normalizando...")
            total_loaded = int(self.prisma_counts.get("identified_total", len(df)))
            n_sco_all = int(self.prisma_counts.get("identified_scopus", 0))
            n_cla_all = int(self.prisma_counts.get("identified_clarivate", 0))
            self._set_cstep(1, "done", f"✓ {n_sco_all} Scopus + {n_cla_all} Clarivate = {total_loaded}")
            self._log_w(self.log_cribar, f"✓ STEP 1 — {total_loaded} registros\n", GREEN)

            # STEP 2
            self._set_cstep(2, "active", "Base sin duplicados...")
            for c in ["title", "abstract", "keywords", "doc_type", "source"]:
                df[c] = df[c].fillna("").astype(str)
            df["year"] = pd.to_numeric(df["year"], errors="coerce")
            self._set_cstep(2, "done", f"✓ {duplicates_removed} eliminados → {len(df)} únicos")
            self._log_w(self.log_cribar, f"✓ STEP 2 — {duplicates_removed} duplicados | {len(df)} únicos\n", GREEN)

            # STEP 3 — Año
            self._set_cstep(3, "active", f"Filtrando {year_from}–{year_to}...")
            mask_year = df["year"].between(year_from, year_to, inclusive="both")
            excluded_year = int((~mask_year).sum())
            df.loc[~mask_year & (df["Decision"] == ""), ["Stage", "Decision"]] = ["Screening", "Exclude"]
            df.loc[~mask_year & (df["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = f"Fuera del rango {year_from}-{year_to}"
            df_year = df[mask_year].copy()
            self.prisma_counts["excluded_year"] = excluded_year
            self._set_cstep(3, "done", f"✓ Excl: {excluded_year} | Restantes: {len(df_year)}")
            self._log_w(self.log_cribar, f"✓ STEP 3 — Fuera de rango: {excluded_year} | Restantes: {len(df_year)}\n", GREEN)

            # STEP 4 — Tipo
            self._set_cstep(4, "active", "Filtrando tipos...")
            mask_doc = df_year["doc_type"].apply(
                lambda d: not any(ex in str(d).lower() for ex in doc_exc)
            )
            excluded_doc = int((~mask_doc).sum())
            df_year.loc[~mask_doc & (df_year["Decision"] == ""), ["Stage", "Decision"]] = ["Screening", "Exclude"]
            df_year.loc[~mask_doc & (df_year["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = "Tipo de documento excluido"
            df_doc = df_year[mask_doc].copy()
            self.prisma_counts["excluded_doc_type"] = excluded_doc
            self._set_cstep(4, "done", f"✓ Excl: {excluded_doc} | Restantes: {len(df_doc)}")
            self._log_w(self.log_cribar, f"✓ STEP 4 — Tipo excluido: {excluded_doc} | Restantes: {len(df_doc)}\n", GREEN)

            # STEP 5 — Keywords
            self._set_cstep(5, "active", "Aplicando keywords...")
            df_doc["_text_screen"] = (
                df_doc["title"] + " " + df_doc["abstract"] + " " + df_doc["keywords"]
            ).str.lower()

            mask_req = df_doc["_text_screen"].apply(lambda t: any(k in t for k in kw_req) if kw_req else True)
            mask_sec = df_doc["_text_screen"].apply(lambda t: any(k in t for k in kw_sec) if kw_sec else True)
            mask_exc_kw = df_doc["_text_screen"].apply(lambda t: any(k in t for k in kw_exc))

            fail_req = ~mask_req
            fail_sec = mask_req & ~mask_sec
            fail_exc = mask_req & mask_sec & mask_exc_kw

            df_doc.loc[fail_req & (df_doc["Decision"] == ""), ["Stage", "Decision"]] = ["Screening", "Exclude"]
            df_doc.loc[fail_req & (df_doc["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = "No contiene términos del bloque obligatorio"
            df_doc.loc[fail_sec & (df_doc["Decision"] == ""), ["Stage", "Decision"]] = ["Eligibility", "Exclude"]
            df_doc.loc[fail_sec & (df_doc["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = "No contiene términos del bloque secundario"
            df_doc.loc[fail_exc & (df_doc["Decision"] == ""), ["Stage", "Decision"]] = ["Screening", "Exclude"]
            df_doc.loc[fail_exc & (df_doc["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = "Contiene términos de exclusión"

            pass_kw = mask_req & mask_sec & ~mask_exc_kw
            df_kw = df_doc[pass_kw].copy()
            exc_req, exc_sec, exc_kw = int(fail_req.sum()), int(fail_sec.sum()), int(fail_exc.sum())
            self.prisma_counts.update({
                "excluded_required": exc_req,
                "excluded_secondary": exc_sec,
                "excluded_keywords": exc_kw,
            })
            self._set_cstep(5, "done", f"✓ Restantes: {len(df_kw)}")
            self._log_w(self.log_cribar,
                        f"✓ STEP 5 — Bloque oblig.: -{exc_req} | Bloque sec.: -{exc_sec} | Excl. kw: -{exc_kw} | Restantes: {len(df_kw)}\n", GREEN)

            # STEP 6 — Bloques
            self._set_cstep(6, "active", "Validando bloques...")

            # ── CORRECCIÓN: manejar df_kw vacío o de una sola fila ──
            if df_kw.empty:
                self._log_w(self.log_cribar,
                            "⚠ Ningún artículo pasó el cribado de keywords (STEP 5).\n"
                            "   Revisa tus términos obligatorios/secundarios/exclusión.\n", YELLOW)
                validated = df_kw.copy()
                for col in ["Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]:
                    validated[col] = ""
                exc_search = 0
                included = pd.DataFrame(columns=validated.columns)
            else:
                validated = self._apply_search_blocks(df_kw, self._search_blocks, min_blocks)
                fail_search = validated["Search_String_Pass"] == "No"
                exc_search = int(fail_search.sum())
                validated.loc[fail_search & (validated["Decision"] == ""), ["Stage", "Decision"]] = ["Eligibility", "Exclude"]
                validated.loc[fail_search & (validated["Reason_for_exclusion"] == ""), "Reason_for_exclusion"] = \
                    validated.loc[fail_search, "Search_String_Reason"]
                included = validated[validated["Search_String_Pass"] == "Yes"].copy()
                included["Stage"] = "Included"
                included["Decision"] = "Include"
                included["Reason_for_exclusion"] = ""

            included_final = len(included)
            self.prisma_counts.update({
                "excluded_search_string": exc_search,
                "included_final": included_final,
            })

            self.df_final = included.drop(columns=["_text_screen"], errors="ignore").reset_index(drop=True)
            self._build_screening_df(df, df_year, df_doc, validated)

            n_sc = int((self.df_final["source"] == "Scopus").sum()) if not self.df_final.empty else 0
            n_cl = int((self.df_final["source"] == "Clarivate").sum()) if not self.df_final.empty else 0
            total_exc = sum(self.prisma_counts.get(k, 0) for k in [
                "duplicates_total", "excluded_year", "excluded_doc_type",
                "excluded_required", "excluded_secondary", "excluded_keywords", "excluded_search_string"
            ])
            pct = f"{(included_final / total_loaded * 100):.1f}%" if total_loaded else "—"

            def _ui():
                self.cribar_stat_vars["total"].set(str(total_loaded))
                self.cribar_stat_vars["dedup"].set(str(duplicates_removed))
                self.cribar_stat_vars["filtered"].set(str(total_exc))
                self.cribar_stat_vars["final"].set(f"{included_final}\n{pct}")
                self.lbl_src_sco.configure(text=f"Scopus: {n_sc}", text_color=SCOPUS)
                self.lbl_src_cla.configure(text=f"Clarivate/WoS: {n_cl}", text_color=CLARIVATE)
                self._draw_bar(n_sc, included_final)
                self.btn_run.configure(state="normal", text="⚡  Ejecutar Cribado PRISMA")
                self.btn_save_cribar.configure(state="normal")
                self.btn_save_screening.configure(state="normal")
                self.sidebar_stats["final"].set(str(included_final))
                self._update_progress()
                self._refresh_results()
            self.after(0, _ui)

            self._set_cstep(6, "done", f"✓ Excl: {exc_search} | ✅ Incluidos: {included_final}")
            self._log_w(self.log_cribar,
                        f"\n{'═'*50}\n"
                        f"✅ PIPELINE COMPLETADO\n"
                        f"   Identificados:         {total_loaded}\n"
                        f"   Duplicados elim.:      {duplicates_removed}\n"
                        f"   Excl. año:             {self.prisma_counts['excluded_year']}\n"
                        f"   Excl. tipo:            {self.prisma_counts['excluded_doc_type']}\n"
                        f"   Excl. keywords:        {exc_req + exc_sec + exc_kw}\n"
                        f"   Excl. bloques:         {exc_search}\n"
                        f"   ✅ INCLUIDOS FINALES:  {included_final} ({pct})\n"
                        f"➡ Ve al Paso 4 para revisar y exportar.\n", ACCENT2)

        except Exception as e:
            import traceback
            self._log_w(self.log_cribar, f"✗ Error: {e}\n{traceback.format_exc()}\n", RED)
            self.after(0, lambda: self.btn_run.configure(state="normal", text="⚡  Ejecutar Cribado PRISMA"))

    def _build_screening_df(self, df, df_year, df_doc, validated):
        base = self.df_limpio.copy() if self.df_limpio is not None else df.copy()
        for col in ["Stage", "Decision", "Reason_for_exclusion",
                    "Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]:
            if col not in base.columns:
                base[col] = ""
        key_cols = ["Stage", "Decision", "Reason_for_exclusion",
                    "Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]

        pieces = []
        for frame in [df, df_year, df_doc, validated]:
            if frame is not None and not frame.empty:
                available = [c for c in ["title", "doi", "source"] + key_cols if c in frame.columns]
                pieces.append(frame[available])

        if self.df_final is not None and not self.df_final.empty:
            available = [c for c in ["title", "doi", "source"] + key_cols if c in self.df_final.columns]
            pieces.append(self.df_final[available])

        if pieces:
            smap = pd.concat(pieces, ignore_index=True).drop_duplicates(subset=["title", "doi", "source"], keep="last")
            base = base.drop(columns=key_cols, errors="ignore")
            base = base.merge(smap, how="left", on=["title", "doi", "source"])
        for col in key_cols:
            if col not in base.columns:
                base[col] = ""
            base[col] = base[col].fillna("")
        base.loc[base["Decision"] == "", "Stage"] = "Included"
        base.loc[base["Decision"] == "", "Decision"] = "Include"
        self.df_screening = base.reset_index(drop=True)

    def _apply_search_blocks(self, df, blocks, min_blocks):
        out = df.copy()

        # Si el DataFrame está vacío, devolver con columnas vacías
        if out.empty:
            for col in ["Search_String_Pass", "Search_String_Reason", "Matched_Blocks", "Missing_Blocks"]:
                out[col] = pd.Series(dtype=str)
            return out

        def norm(t):
            return re.sub(r"\s+", " ", str(t).lower())

        text_series = (
            out["title"].fillna("") + " " +
            out["abstract"].fillna("") + " " +
            out["keywords"].fillna("")
        ).apply(norm)

        def check(txt):
            matched, missing = [], []
            for bid, block in blocks.items():
                terms = [t.strip().lower() for t in block.get("terms", "").split(",") if t.strip()]
                found = any(t in txt for t in terms)
                (matched if found else missing).append(bid)
            passes = len(matched) >= min_blocks
            return pd.Series({
                "Search_String_Pass": "Yes" if passes else "No",
                "Search_String_Reason": (
                    f"Bloques: {', '.join(matched)}" if passes
                    else f"Faltan: {', '.join(missing)} ({len(matched)}/{len(blocks)})"
                ),
                "Matched_Blocks": ", ".join(matched),
                "Missing_Blocks": ", ".join(missing),
            })

        results = text_series.apply(check)

        # Cuando solo hay UNA fila, apply() devuelve Series en lugar de DataFrame
        if isinstance(results, pd.Series):
            results = results.to_frame().T.reset_index(drop=True)

        for col in results.columns:
            out[col] = results[col].values
        return out

    def _show_prisma_report(self):
        if self.prisma_counts.get("identified_total", 0) == 0:
            messagebox.showinfo("Sin datos", "Ejecuta el pipeline antes de generar el informe.")
            return
        PrismaReportDialog(self, self.prisma_counts, self.review_name.get(), self._search_blocks)

    def _update_progress(self):
        steps_done = 0
        total = self.prisma_counts.get("identified_total", 0)
        if total > 0:
            steps_done += 1
        if self.prisma_counts.get("after_duplicates", 0) > 0:
            steps_done += 1
        if self.prisma_counts.get("included_final", 0) > 0:
            steps_done += 2
        pct = steps_done / 4
        included = self.prisma_counts.get("included_final", 0)
        tot = self.prisma_counts.get("identified_total", 0)
        pct_txt = f"{included/tot*100:.1f}% incluidos" if tot and included else f"Paso {steps_done}/4"

        def _do():
            self.global_progress.set(pct)
            self.lbl_progress.configure(text=pct_txt)
        self.after(0, _do)

    # ── Exportación ────────────────────────────────────────────────────────────
    def _save_flagged(self):
        df = self.df_dedup
        if df is None:
            messagebox.showwarning("Aviso", "Ejecuta primero la deduplicación (Paso 2).")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Todos_con_banderas_{self.review_name.get().replace(' ', '_')}",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not path:
            return
        if path.endswith(".xlsx"):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        messagebox.showinfo("Guardado", f"Archivo guardado:\n{path}")

    def _save_results(self):
        df = self.df_final
        if df is None or df.empty:
            messagebox.showwarning("Sin datos", "Ejecuta el cribado primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Articulos_Incluidos_{self.review_name.get().replace(' ', '_')}",
            filetypes=[("Excel", "*.xlsx")]
        )
        if not path:
            return
        df.to_excel(path, index=False)
        messagebox.showinfo("Listo", f"Guardado:\n{path}")

    def _save_screening_decisions(self):
        df = self.df_screening
        if df is None or df.empty:
            messagebox.showwarning("Sin datos", "Ejecuta el cribado primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Cribado_PRISMA_{self.review_name.get().replace(' ', '_')}",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")]
        )
        if not path:
            return
        if path.endswith(".xlsx"):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        messagebox.showinfo("Guardado", f"Guardado:\n{path}")

    def _export_excel(self):
        if self.df_final is None:
            messagebox.showwarning("Aviso", "Ejecuta el cribado primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Articulos_Incluidos_{self.review_name.get().replace(' ', '_')}",
            filetypes=[("Excel", "*.xlsx")]
        )
        if path:
            self.df_final.to_excel(path, index=False)
            messagebox.showinfo("Exportado", f"Guardado:\n{path}")

    def _export_csv(self):
        if self.df_final is None:
            messagebox.showwarning("Aviso", "Ejecuta el cribado primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"Articulos_Incluidos_{self.review_name.get().replace(' ', '_')}",
            filetypes=[("CSV", "*.csv")]
        )
        if path:
            self.df_final.to_csv(path, index=False, encoding="utf-8-sig")
            messagebox.showinfo("Exportado", f"Guardado:\n{path}")

    # ── Tabla resultados ────────────────────────────────────────────────────────
    def _refresh_results(self):
        df = self.df_final
        if df is None:
            return
        n_tot = len(df)
        n_sco = int((df["source"] == "Scopus").sum()) if "source" in df.columns else 0
        n_cla = int((df["source"] == "Clarivate").sum()) if "source" in df.columns else 0
        n_loaded = self.prisma_counts.get("identified_total", n_tot)
        n_dedup = self.prisma_counts.get("duplicates_total", 0)
        n_exc = sum(self.prisma_counts.get(k, 0) for k in [
            "excluded_year", "excluded_doc_type", "excluded_required",
            "excluded_secondary", "excluded_keywords", "excluded_search_string"
        ])

        def _ui():
            self.res_total.configure(text=str(n_loaded))
            self.res_dedup.configure(text=str(n_dedup))
            self.res_cribar.configure(text=str(n_exc))
            self.res_final.configure(text=str(n_tot))
            self.res_scopus.configure(text=str(n_sco))
            self.res_clarivate.configure(text=str(n_cla))
        self.after(0, _ui)
        self._populate_tree(df)

    def _populate_tree(self, df):
        for item in self.tree.get_children():
            self.tree.delete(item)
        count = 0
        for i, (_, row) in enumerate(df.iterrows()):
            tag = "scopus" if str(row.get("source", "")) == "Scopus" else "clarivate"
            yr = row.get("year", "")
            try:
                yr = int(float(yr)) if pd.notna(yr) else "—"
            except Exception:
                yr = str(yr)
            self.tree.insert("", "end", iid=i, tags=(tag,), values=(
                i + 1, yr,
                str(row.get("title", ""))[:100],
                str(row.get("doi", ""))[:50],
                str(row.get("source", "")),
                str(row.get("doc_type", ""))[:22],
                str(row.get("Matched_Blocks", ""))[:50],
            ))
            count += 1

        def _ui():
            self.lbl_count.configure(text=f"{count} artículos")
        self.after(0, _ui)

    def _filter_table(self):
        if self.df_final is None:
            return
        q = self.search_var.get().strip().lower()
        src_filter = self.filter_source.get()
        df = self.df_final.copy()
        if src_filter != "Todas":
            src_map = {"Scopus": "Scopus", "Clarivate": "Clarivate"}
            df = df[df["source"] == src_map.get(src_filter, src_filter)]
        if q:
            df = df[df.apply(
                lambda r: any(q in str(r.get(c, "")).lower()
                              for c in ["title", "abstract", "keywords", "doi", "authors", "Matched_Blocks"]),
                axis=1
            )]
        self._populate_tree(df)

    def _sort_tree(self, col):
        if self.df_final is None:
            return
        col_map = {
            "Año": "year", "Título": "title", "DOI": "doi",
            "Fuente": "source", "Tipo Doc": "doc_type", "Bloques cumplidos": "Matched_Blocks"
        }
        key = col_map.get(col)
        if key:
            asc = (self._sort_col != col) or (not self._sort_asc)
            self._sort_col = col
            self._sort_asc = asc
            self._populate_tree(self.df_final.sort_values(key, ascending=asc, na_position="last"))

    def _on_row_dblclick(self, event):
        sel = self.tree.selection()
        if not sel or self.df_final is None:
            return
        idx = int(sel[0])
        row = self.df_final.iloc[idx].to_dict()
        ArticleDetailDialog(self, row)

    # ── Helpers visuales ─────────────────────────────────────────────────────
    def _set_cstep(self, n, state, val=""):
        colors = {"active": (ACCENT, "white"), "done": (GREEN, "black"),
                  "error": (RED, "white"), "idle": (BORDER, MUTED)}
        bg, fg = colors.get(state, colors["idle"])
        s = self.cribar_steps[n]
        def _do():
            s["num"].configure(fg_color=bg, text_color=fg)
            s["name"].configure(text_color=TEXT if state != "idle" else MUTED)
            s["val"].configure(text=val, text_color=GREEN if state == "done" else RED if state == "error" else MUTED)
        self.after(0, _do)

    def _set_dstep(self, n, state, val=""):
        colors = {"active": (ACCENT, "white"), "done": (GREEN, "black"),
                  "error": (RED, "white"), "idle": (BORDER, MUTED)}
        bg, fg = colors.get(state, colors["idle"])
        s = self.dedup_steps[n]
        def _do():
            s["num"].configure(fg_color=bg, text_color=fg)
            s["name"].configure(text_color=TEXT if state != "idle" else MUTED)
            s["val"].configure(text=val, text_color=GREEN if state == "done" else RED if state == "error" else MUTED)
        self.after(0, _do)

    def _draw_bar(self, n_scopus, n_total):
        self.bar_canvas.update_idletasks()
        w = self.bar_canvas.winfo_width() or 400
        self.bar_canvas.delete("all")
        self.bar_canvas.create_rectangle(0, 0, w, 14, fill=BORDER, outline="")
        if n_total:
            sw = int(w * n_scopus / n_total)
            if sw > 0:
                self.bar_canvas.create_rectangle(0, 0, sw, 14, fill=SCOPUS, outline="")
            if sw < w:
                self.bar_canvas.create_rectangle(sw, 0, w, 14, fill=CLARIVATE, outline="")

    def _log_w(self, widget, msg, color=None):
        color = color or TEXT
        tag = f"c_{time.time_ns()}"
        def _do():
            widget.configure(state="normal")
            widget.insert("end", msg, tag)
            widget.tag_configure(tag, foreground=color)
            widget.see("end")
            widget.configure(state="disabled")
        self.after(0, _do)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS UI
# ══════════════════════════════════════════════════════════════════════════════
def _screen_header(parent, title, subtitle=""):
    hdr = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=0, height=62)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=title, font=("Arial Black", 14), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(10, 0))
    if subtitle:
        ctk.CTkLabel(hdr, text=subtitle, font=("Arial", 11), text_color=MUTED2).pack(anchor="w", padx=24)


def _card_frame(parent, title):
    outer = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12, border_color=BORDER, border_width=1)
    outer.pack(fill="x", pady=(0, 10))
    ctk.CTkLabel(outer, text=title, font=("Arial Bold", 10), text_color=MUTED2).pack(anchor="w", padx=14, pady=(10, 4))
    inner = ctk.CTkFrame(outer, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=(0, 12))
    return inner


def _stat_card(parent, label, value, color):
    box = ctk.CTkFrame(parent, fg_color=SURFACE2, corner_radius=10)
    box.pack(side="left", fill="x", expand=True, padx=4)
    lbl = ctk.CTkLabel(box, text=value, font=("Arial Black", 24), text_color=color)
    lbl.pack(pady=(10, 0))
    ctk.CTkLabel(box, text=label, font=("Courier", 10), text_color=MUTED2).pack(pady=(0, 10))
    return lbl


def _num_entry(parent, default):
    e = ctk.CTkEntry(parent, width=72, height=32, font=("Courier", 13),
                      fg_color=SURFACE2, border_color=BORDER, text_color=TEXT)
    e.insert(0, str(default))
    e.pack(side="left", padx=4)
    return e


def _textarea(parent, label, default, height=68, color=None):
    color = color or MUTED2
    ctk.CTkLabel(parent, text=label, font=("Courier", 10), text_color=color).pack(anchor="w", pady=(6, 2))
    tb = ctk.CTkTextbox(parent, height=height, font=("Courier", 12),
                         fg_color=SURFACE2, border_color=BORDER, border_width=1,
                         text_color=TEXT, corner_radius=8)
    tb.insert("1.0", default)
    tb.pack(fill="x")
    return tb


def _log_label(parent, text):
    ctk.CTkLabel(parent, text=text, font=("Arial Bold", 10), text_color=MUTED2).pack(anchor="w", pady=(8, 2))


def _log_area(parent, height=8):
    log = scrolledtext.ScrolledText(
        parent, height=height, bg=SURFACE2, fg=TEXT,
        insertbackground=TEXT, font=("Consolas", 9),
        relief="flat", state="disabled", wrap="word"
    )
    log.pack(fill="both", expand=True)
    return log


if __name__ == "__main__":
    app = SysReviewApp()
    app.mainloop()