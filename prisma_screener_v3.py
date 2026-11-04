"""
=============================================================
  SysReview PRISMA  v3.0  ·  Pipeline Universal de Cribado
  Revisiones Sistemáticas — PRISMA 2020
=============================================================
Requisitos:
    pip install -r requirements.txt

Uso:
    python prisma_screener_v3.py

La lógica de procesamiento está en prisma_core.py (probada en tests/).
Este archivo contiene únicamente la interfaz gráfica.
=============================================================
"""
from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import customtkinter as ctk
import pandas as pd

import prisma_core as pc
from prisma_presets import (BLANK_CONFIG, DEFAULT_PRESETS, PRESET_TEMPLATE, load_user_presets,
                            save_user_presets, validate_preset_cfg)

# ─── Tema ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

ACCENT, ACCENT2 = "#4f46e5", "#6366f1"
GREEN, GREEN_DIM = "#16a34a", "#dcfce7"
RED, RED_DIM = "#dc2626", "#fee2e2"
YELLOW, TEAL, CYAN, ORANGE = "#ca8a04", "#0d9488", "#0891b2", "#c2410c"
BG, SURFACE, SURFACE2, SURFACE3 = "#f8f7f4", "#ffffff", "#f1f0ed", "#e8e6e1"
BORDER, MUTED, MUTED2, TEXT = "#d6d3cd", "#9ca3a0", "#6b7280", "#1c1917"

# Selectores segmentados y pestañas: texto oscuro sobre fondos claros (contraste legible)
SEG_STYLE = dict(fg_color=SURFACE3, selected_color="#c7d2fe", selected_hover_color="#a5b4fc",
                 unselected_color=SURFACE3, unselected_hover_color=BORDER, text_color=TEXT)
SEG_STYLE_FT = dict(SEG_STYLE, selected_color="#99f6e4", selected_hover_color="#5eead4")
TAB_STYLE = dict(segmented_button_fg_color=SURFACE3, segmented_button_selected_color="#c7d2fe",
                 segmented_button_selected_hover_color="#a5b4fc", segmented_button_unselected_color=SURFACE3,
                 segmented_button_unselected_hover_color=BORDER, text_color=TEXT)

BLOCK_COLORS = [ACCENT2, TEAL, GREEN, YELLOW, CYAN, "#db2777", "#ea580c", "#7c3aed"]
BLOCK_HL = ["#e0e7ff", "#ccfbf1", "#dcfce7", "#fef9c3", "#cffafe", "#fce7f3", "#ffedd5", "#ede9fe"]
SOURCE_COLORS = ["#4f46e5", "#be185d", "#0d9488", "#ca8a04", "#0891b2", "#7c3aed", "#ea580c"]

STATUS_STYLE = {
    pc.STATUS_INCLUDED: ("#f0fdf4", "#166534"),
    pc.STATUS_PENDING: ("#fefce8", "#854d0e"),
    pc.STATUS_EXC_AUTO: ("#ffffff", "#6b7280"),
    pc.STATUS_EXC_TA: ("#fef2f2", "#991b1b"),
    pc.STATUS_EXC_FT: ("#fef2f2", "#991b1b"),
    pc.STATUS_NOT_RETRIEVED: ("#fff7ed", "#9a3412"),
    pc.STATUS_DUP: ("#f5f5f4", "#a8a29e"),
    pc.STATUS_UNSCREENED: ("#ffffff", "#1c1917"),
}
DECISION_LABEL = {"": "—", pc.INCLUDE: "Incluir", pc.EXCLUDE: "Excluir", pc.MAYBE: "Dudoso",
                  pc.REVIEW: "Revisar", pc.NOT_RETRIEVED: "No recuperado", pc.PENDING: "Pendiente"}
TA_OPTIONS = {"Sin decidir": "", "Incluir": pc.INCLUDE, "Excluir": pc.EXCLUDE, "Dudoso": pc.MAYBE}
FT_OPTIONS = {"Sin evaluar": "", "Incluir": pc.INCLUDE, "Excluir": pc.EXCLUDE, "No recuperado": pc.NOT_RETRIEVED}
VIEW_FILTERS = {
    "Incluidos": [pc.STATUS_INCLUDED],
    "Pendientes": [pc.STATUS_PENDING],
    "Excluidos": [pc.STATUS_EXC_AUTO, pc.STATUS_EXC_TA, pc.STATUS_EXC_FT, pc.STATUS_NOT_RETRIEVED],
    "Duplicados": [pc.STATUS_DUP],
    "Todos": None,
}
FILE_TYPES = [("Exportaciones bibliográficas", " ".join(f"*{e}" for e in pc.SUPPORTED_EXTENSIONS)),
              ("CSV / texto tabulado", "*.csv *.tsv *.txt"), ("Excel / LibreOffice", "*.xlsx *.xlsm *.xls *.ods"),
              ("RIS (Zotero, Mendeley, Scopus, WoS)", "*.ris"), ("BibTeX", "*.bib"),
              ("WoS texto plano", "*.txt *.ciw"), ("PubMed", "*.nbib *.txt"), ("EndNote", "*.enw"),
              ("Todos los archivos", "*.*")]


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s.strip())[:60] or "revision"


def fmt_year(y) -> str:
    return "—" if y is None or pd.isna(y) else str(int(y))


def read_int(entry, label, lo=None, hi=None, allow_empty=False):
    """Lee un entero de un CTkEntry con validación clara (ValueError con mensaje en español)."""
    raw = entry.get().strip()
    if raw == "":
        if allow_empty:
            return None
        raise ValueError(f"'{label}' no puede estar vacío.")
    try:
        v = int(raw)
    except ValueError:
        raise ValueError(f"'{label}' debe ser un número entero (escribiste '{raw}').") from None
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ValueError(f"'{label}' debe estar entre {lo} y {hi}.")
    return v


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS UI
# ══════════════════════════════════════════════════════════════════════════════
class Tooltip:
    """Tooltip con retardo. Posición calculada desde la geometría del widget (sin bbox)."""

    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip, self._job = None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self.show)

    def _cancel(self):
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def show(self):
        if self.tip or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#1e1e23", fg="#e4e4e7", font=("Segoe UI", 9),
                 padx=8, pady=4, wraplength=360, justify="left").pack()

    def hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def make_modal(win, parent):
    """Ventana modal: encima del padre y bloquea la interacción con él (evita copias duplicadas)."""
    win.transient(parent)

    def grab():
        try:
            win.lift()
            win.grab_set()
            win.focus_force()
        except tk.TclError:
            pass
    win.after(150, grab)


def _screen_header(parent, title, subtitle=""):
    hdr = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=0, height=62)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=title, font=("Arial Black", 14), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(10, 0))
    if subtitle:
        ctk.CTkLabel(hdr, text=subtitle, font=("Arial", 11), text_color=MUTED2).pack(anchor="w", padx=24)
    return hdr


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
    lbl = ctk.CTkLabel(box, text=value, font=("Arial Black", 22), text_color=color)
    lbl.pack(pady=(10, 0))
    ctk.CTkLabel(box, text=label, font=("Courier", 10), text_color=MUTED2).pack(pady=(0, 10))
    return lbl


def _num_entry(parent, default, width=72):
    e = ctk.CTkEntry(parent, width=width, height=32, font=("Courier", 13),
                     fg_color=SURFACE2, border_color=BORDER, text_color=TEXT)
    if default not in (None, ""):
        e.insert(0, str(default))
    e.pack(side="left", padx=4)
    return e


def _textarea(parent, label, height=68, color=None):
    ctk.CTkLabel(parent, text=label, font=("Courier", 10), text_color=color or MUTED2).pack(anchor="w", pady=(6, 2))
    tb = ctk.CTkTextbox(parent, height=height, font=("Consolas", 11), fg_color=SURFACE2, wrap="word",
                        border_color=BORDER, border_width=1, text_color=TEXT, corner_radius=8)
    tb.pack(fill="x")
    return tb


def _set_text(widget, value):
    widget.delete("1.0", "end")
    widget.insert("1.0", value or "")


def _get_text(widget) -> str:
    return widget.get("1.0", "end").strip()


def _log_label(parent, text):
    ctk.CTkLabel(parent, text=text, font=("Arial Bold", 10), text_color=MUTED2).pack(anchor="w", pady=(8, 2))


def _log_area(parent, height=8):
    log = scrolledtext.ScrolledText(parent, height=height, bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                                    font=("Consolas", 9), relief="flat", state="disabled", wrap="word")
    log.pack(fill="both", expand=True)
    return log


def _ghost_button(parent, text, color, command, height=36, width=None, **kw):
    opts = dict(text=text, height=height, font=("Arial Bold", 11), fg_color=SURFACE2, hover_color=SURFACE3,
                border_color=color, border_width=1, text_color=color, corner_radius=8, command=command)
    if width:
        opts["width"] = width
    opts.update(kw)
    return ctk.CTkButton(parent, **opts)


def draw_prisma_on_canvas(canvas, lay):
    canvas.delete("all")
    for b in lay["bands"]:
        stroke, fill = pc.STYLE_COLORS[b["style"]]
        canvas.create_rectangle(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], fill=fill, outline=stroke)
        canvas.create_text(b["x"] + b["w"] / 2, b["y"] + b["h"] / 2, text=b["label"], angle=90,
                           font=("Arial", 10, "bold"), fill=stroke)
    for b in lay["boxes"]:
        stroke, fill = pc.STYLE_COLORS[b["style"]]
        canvas.create_rectangle(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], fill=fill, outline=stroke, width=2)
        for i, line in enumerate(b["lines"]):
            canvas.create_text(b["x"] + 12, b["y"] + lay["pad"] + lay["line_h"] * i, text=line, anchor="nw",
                               font=("Arial", 9, "bold" if i == 0 else "normal"), fill=TEXT)
    for x1, y1, x2, y2 in lay["arrows"]:
        canvas.create_line(x1, y1, x2, y2, fill=MUTED2, width=2, arrow=tk.LAST)
    if lay.get("title"):
        canvas.create_text(lay["width"] / 2, 28, text=lay["title"], font=("Arial", 13, "bold"), fill=TEXT)
    canvas.configure(scrollregion=(0, 0, lay["width"], lay["height"]))


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Editor de bloques
# ══════════════════════════════════════════════════════════════════════════════
class BlocksEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, blocks, on_save):
        super().__init__(parent)
        self.title("Editor de Bloques de Cadena de Búsqueda")
        self.geometry("880x700")
        self.configure(fg_color=BG)
        self.blocks = {k: dict(v) for k, v in blocks.items()} or {"B1": {"label": "Bloque 1", "terms": ""}}
        self.on_save = on_save
        self._entries = {}
        self._build()
        make_modal(self, parent)

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🧩  Editor de Bloques", font=("Arial Black", 14), text_color=ACCENT2).pack(anchor="w", padx=24, pady=(12, 0))
        ctk.CTkLabel(hdr, text="Cada bloque = grupo de sinónimos. Un artículo debe cumplir el mínimo de bloques.",
                     font=("Arial", 10), text_color=MUTED2).pack(anchor="w", padx=24)
        help_f = ctk.CTkFrame(self, fg_color="#eff6ff", corner_radius=8, border_color="#bfdbfe", border_width=1)
        help_f.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(help_f, text="💡  Separa con coma. Coincidencia por PALABRA COMPLETA (\"ai\" no coincide con \"main\"). "
                                  "Comodines: monitor* (cualquier sufijo), organi?ation (un carácter). "
                                  "Guiones y espacios son equivalentes. Los bloques vacíos se ignoran.",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=800, justify="left").pack(anchor="w", padx=12, pady=6)
        self._block_frame = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._block_frame.pack(fill="both", expand=True, padx=16, pady=(8, 0))
        self._render_blocks()
        btn_row = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        _ghost_button(btn_row, "➕  Agregar bloque", TEAL, self._add_block, width=160).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="✅  Guardar cambios", height=36, width=160, font=("Arial Bold", 12),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="white", corner_radius=8,
                      command=self._save).pack(side="right", padx=16, pady=10)
        ctk.CTkButton(btn_row, text="Cancelar", height=36, width=100, font=("Arial", 12), fg_color="transparent",
                      hover_color=SURFACE2, text_color=MUTED2, command=self.destroy).pack(side="right")

    def _collect(self):
        """Guarda lo escrito en pantalla antes de volver a dibujar (no se pierden ediciones)."""
        out = {}
        for old_id, e in self._entries.items():
            nid = e["id"].get().strip() or old_id
            out[nid] = {"label": e["label"].get().strip(), "terms": e["terms"].get("1.0", "end").strip()}
        return out

    def _render_blocks(self):
        for w in self._block_frame.winfo_children():
            w.destroy()
        self._entries.clear()
        for idx, (block_id, block) in enumerate(self.blocks.items()):
            color = BLOCK_COLORS[idx % len(BLOCK_COLORS)]
            card = ctk.CTkFrame(self._block_frame, fg_color=SURFACE, corner_radius=10, border_color=color, border_width=1)
            card.pack(fill="x", pady=5)
            header = ctk.CTkFrame(card, fg_color=SURFACE2, corner_radius=8)
            header.pack(fill="x", padx=10, pady=(10, 4))
            ctk.CTkLabel(header, text="ID:", font=("Courier", 10), text_color=MUTED2, width=20).pack(side="left", padx=(10, 2))
            id_e = ctk.CTkEntry(header, width=150, height=30, font=("Courier Bold", 11), fg_color=SURFACE3,
                                border_color=color, text_color=color, corner_radius=6)
            id_e.insert(0, block_id)
            id_e.pack(side="left", padx=(0, 16))
            ctk.CTkLabel(header, text="Etiqueta:", font=("Courier", 10), text_color=MUTED2).pack(side="left")
            lbl_e = ctk.CTkEntry(header, width=320, height=30, font=("Arial", 11), fg_color=SURFACE3,
                                 border_color=BORDER, text_color=TEXT, corner_radius=6)
            lbl_e.insert(0, block.get("label", ""))
            lbl_e.pack(side="left", padx=4)
            ctk.CTkButton(header, text="🗑", width=32, height=30, fg_color="transparent", hover_color=RED_DIM,
                          text_color=RED, font=("Arial", 12), corner_radius=6,
                          command=lambda bid=block_id: self._remove_block(bid)).pack(side="right", padx=8)
            terms_e = ctk.CTkTextbox(card, height=60, font=("Consolas", 11), fg_color=SURFACE2, wrap="word", border_color=BORDER,
                                     border_width=1, text_color=TEXT, corner_radius=6)
            terms_e.insert("1.0", block.get("terms", ""))
            terms_e.pack(fill="x", padx=12, pady=(4, 2))
            n_lbl = ctk.CTkLabel(card, text="", font=("Courier", 9), text_color=MUTED)
            n_lbl.pack(anchor="e", padx=12, pady=(0, 6))

            def upd(_=None, tb=terms_e, lab=n_lbl):
                n = len(pc.parse_terms(tb.get("1.0", "end")))
                lab.configure(text=f"{n} término{'s' if n != 1 else ''}")
            terms_e.bind("<KeyRelease>", upd)
            upd()
            self._entries[block_id] = {"id": id_e, "label": lbl_e, "terms": terms_e}

    def _add_block(self):
        self.blocks = self._collect()
        n = len(self.blocks) + 1
        new_id = f"B{n}"
        while new_id in self.blocks:
            n += 1
            new_id = f"B{n}"
        self.blocks[new_id] = {"label": f"Bloque {n}", "terms": ""}
        self._render_blocks()

    def _remove_block(self, block_id):
        if len(self.blocks) <= 1:
            messagebox.showwarning("Aviso", "Debe haber al menos un bloque.", parent=self)
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar el bloque '{block_id}'?", parent=self):
            current = self._collect()
            ids = list(self._entries)
            pos = ids.index(block_id)
            self.blocks = {k: v for i, (k, v) in enumerate(current.items()) if i != pos}
            self._render_blocks()

    def _save(self):
        ids = [e["id"].get().strip() for e in self._entries.values()]
        if any(not i for i in ids):
            messagebox.showwarning("Aviso", "Todos los bloques necesitan un ID.", parent=self)
            return
        if len(set(ids)) != len(ids):
            messagebox.showwarning("Aviso", "Hay IDs de bloque repetidos.", parent=self)
            return
        self.on_save(self._collect())
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Importar cadena de búsqueda
# ══════════════════════════════════════════════════════════════════════════════
class QueryImportDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_apply):
        super().__init__(parent)
        self.title("Importar cadena de búsqueda (Scopus / WoS)")
        self.geometry("860x640")
        self.configure(fg_color=BG)
        self.on_apply = on_apply
        self.result = None
        _screen_header(self, "🔎  Importar cadena de búsqueda",
                       "Pega la cadena tal como la usaste en Scopus (TITLE-ABS-KEY…) o WoS (TS=…).")
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=10)
        ctk.CTkLabel(body, text="Puedes pegar varias cadenas juntas (p. ej. WoS y Scopus) y la línea «Refine:» de WoS. "
                                "Se aplican bloques, AND NOT, años, tipos de documento (LIMIT-TO DOCTYPE / Document "
                                "Types / DT=) e idiomas (LIMIT-TO LANGUAGE / Languages / LA=).",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=800, justify="left").pack(anchor="w", pady=(0, 6))
        self.query = ctk.CTkTextbox(body, height=200, font=("Consolas", 11), fg_color=SURFACE, border_color=BORDER,
                                    border_width=1, text_color=TEXT, wrap="word")
        self.query.pack(fill="x")
        self.query.insert("1.0", 'TITLE-ABS-KEY ( ( "structural health monitoring" OR shm ) AND ( bridge* OR building* ) '
                                 'AND ( iot OR "wireless sensor network" ) AND NOT ( medical ) ) AND PUBYEAR > 2015')
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkButton(row, text="Analizar", height=34, fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                      font=("Arial Bold", 12), command=self._analyze).pack(side="left")
        self.btn_apply = ctk.CTkButton(row, text="Aplicar a la configuración", height=34, fg_color=GREEN,
                                       hover_color="#15803d", text_color="white", font=("Arial Bold", 12),
                                       state="disabled", command=self._apply)
        self.btn_apply.pack(side="left", padx=8)
        self.preview = scrolledtext.ScrolledText(body, bg=SURFACE2, fg=TEXT, font=("Consolas", 10), relief="flat",
                                                 wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True)
        make_modal(self, parent)

    def _analyze(self):
        try:
            self.result = pc.parse_search_query(_get_text(self.query))
        except Exception as e:
            self.result = None
            self.btn_apply.configure(state="disabled")
            messagebox.showerror("No se pudo analizar", str(e), parent=self)
            return
        r = self.result
        lines = []
        if r.get("n_queries", 1) > 1:
            lines += [f"Se detectaron {r['n_queries']} cadenas; sus bloques se combinaron por posición.", ""]
        lines += [f"Bloques detectados: {len(r['search_blocks'])}  (mínimo requerido = {r['min_blocks']}, todos por AND)", ""]
        for bid, b in r["search_blocks"].items():
            lines += [f"  {bid}  {b['label']}", f"      {b['terms']}", ""]
        lines.append(f"Términos de exclusión (AND NOT): {r['kw_exclude'] or '—'}")
        lines.append(f"Años: {r['year_from'] or '…'} – {r['year_to'] or '…'}")
        lines.append(f"Tipos de documento permitidos: {r['doc_include'] or 'todos'}")
        if r["doc_exclude"]:
            lines.append(f"Tipos de documento excluidos: {r['doc_exclude']}")
        lines.append(f"Idiomas permitidos: {r['languages'] or 'todos'}")
        if r["warnings"]:
            lines += ["", "Advertencias:"] + [f"  ⚠ {w}" for w in r["warnings"]]
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))
        self.preview.configure(state="disabled")
        self.btn_apply.configure(state="normal" if r["search_blocks"] else "disabled")

    def _apply(self):
        if self.result:
            self.on_apply(self.result)
            self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGOS — Presets y bienvenida
# ══════════════════════════════════════════════════════════════════════════════
def _load_json_preset(parent):
    import json
    path = filedialog.askopenfilename(title="Importar configuración JSON",
                                      filetypes=[("JSON", "*.json"), ("Todos", "*.*")], parent=parent)
    if not path:
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict) and "config" in cfg and "provenance" in cfg:   # sidecar de una exportación
            cfg = cfg["config"]
        validate_preset_cfg(cfg)
    except Exception as e:
        messagebox.showerror("Error al importar", f"Formato incorrecto:\n\n{e}", parent=parent)
        return None, None
    return cfg.get("name") or Path(path).stem, cfg


def _save_template(parent):
    import json
    path = filedialog.asksaveasfilename(title="Guardar plantilla", defaultextension=".json",
                                        initialfile="plantilla_revision_prisma", filetypes=[("JSON", "*.json")],
                                        parent=parent)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(PRESET_TEMPLATE, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Plantilla guardada", f"Guardada en:\n{path}", parent=parent)


class PresetDialog(ctk.CTkToplevel):
    def __init__(self, parent, presets, current_cfg, on_load):
        super().__init__(parent)
        self.title("Gestionar Presets de Revisión")
        self.geometry("820x680")
        self.configure(fg_color=BG)
        self.presets, self.current_cfg, self.on_load = presets, current_cfg, on_load
        _screen_header(self, "⚙  Gestionar Presets", "Carga, guarda o exporta configuraciones de revisión")
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=16, pady=10)
        self.list_frame = ctk.CTkScrollableFrame(body, fg_color=SURFACE, corner_radius=12, border_color=BORDER, border_width=1)
        self.list_frame.pack(fill="both", expand=True)
        self._render_list()
        save_row = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        save_row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(save_row, text="💾  Guardar configuración actual como:", font=("Courier", 11),
                     text_color=MUTED2).pack(side="left", padx=12)
        self.name_entry = ctk.CTkEntry(save_row, width=260, height=34, font=("Courier", 12), fg_color=SURFACE3,
                                       border_color=BORDER, text_color=TEXT, placeholder_text="Nombre del preset...")
        self.name_entry.pack(side="left", padx=8)
        ctk.CTkButton(save_row, text="Guardar", height=34, width=100, font=("Arial Bold", 12), fg_color=TEAL,
                      hover_color="#0f766e", text_color="white", corner_radius=8,
                      command=self._save_current).pack(side="left", pady=6)
        io_row = ctk.CTkFrame(body, fg_color="transparent")
        io_row.pack(fill="x", pady=4)
        _ghost_button(io_row, "📂  Importar JSON", TEAL, self._import_json).pack(side="left", padx=(0, 8))
        _ghost_button(io_row, "📤  Exportar actual", CYAN, self._export_current_json).pack(side="left", padx=(0, 8))
        _ghost_button(io_row, "📄  Descargar plantilla", MUTED2, lambda: _save_template(self)).pack(side="left")
        make_modal(self, parent)

    def _render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for name, cfg in self.presets.items():
            is_default = name in DEFAULT_PRESETS
            row = ctk.CTkFrame(self.list_frame, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", padx=8, pady=3)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(info, text=name, font=("Arial Bold", 12), text_color=TEXT, anchor="w").pack(anchor="w")
            desc = cfg.get("description", "")
            yrs = f"{cfg.get('year_from') or '…'}–{cfg.get('year_to') or '…'}"
            ctk.CTkLabel(info, text=f"{desc}  ·  {yrs}" if desc else yrs, font=("Arial", 10),
                         text_color=MUTED2, anchor="w").pack(anchor="w")
            ctk.CTkLabel(row, text="SISTEMA" if is_default else "USUARIO", font=("Courier", 9),
                         text_color=MUTED if is_default else TEAL, fg_color=BORDER if is_default else "#f0fdf4",
                         corner_radius=4, width=70).pack(side="right", padx=(0, 6), pady=8)
            if not is_default:
                ctk.CTkButton(row, text="✕", width=28, height=28, fg_color="transparent", hover_color=RED_DIM,
                              text_color=RED, font=("Arial Bold", 11), corner_radius=6,
                              command=lambda n=name: self._delete_preset(n)).pack(side="right", pady=8)
            ctk.CTkButton(row, text="Cargar →", width=90, height=30, fg_color=ACCENT, hover_color=ACCENT2,
                          text_color="white", font=("Arial Bold", 10), corner_radius=6,
                          command=lambda c=cfg, n=name: self._load(n, c)).pack(side="right", padx=4, pady=8)

    def _load(self, name, cfg):
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
        if name in self.presets and not messagebox.askyesno("Confirmar", f'"{name}" ya existe. ¿Reemplazarlo?', parent=self):
            return
        self.presets[name] = dict(self.current_cfg)
        save_user_presets(self.presets)
        messagebox.showinfo("Guardado", f'Preset "{name}" guardado.', parent=self)
        self._render_list()

    def _delete_preset(self, name):
        if messagebox.askyesno("Confirmar", f'¿Eliminar el preset "{name}"?', parent=self):
            del self.presets[name]
            save_user_presets(self.presets)
            self._render_list()

    def _import_json(self):
        name, cfg = _load_json_preset(self)
        if cfg is None:
            return
        self.presets[name] = cfg
        save_user_presets(self.presets)
        self._load(name, cfg)

    def _export_current_json(self):
        import json
        path = filedialog.asksaveasfilename(title="Exportar configuración actual", defaultextension=".json",
                                            initialfile=safe_name(self.current_cfg.get("name", "mi_revision")),
                                            filetypes=[("JSON", "*.json")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_cfg, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Exportado", f"Guardado en:\n{path}", parent=self)


class WelcomeDialog(ctk.CTkToplevel):
    def __init__(self, parent, presets, on_select, on_open_session):
        super().__init__(parent)
        self.title("Bienvenido — Configurar revisión")
        self.geometry("720x620")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.presets, self.on_select, self.on_open_session = presets, on_select, on_open_session
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._blank_start)
        make_modal(self, parent)

    def _build(self):
        logo = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=100)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text=f"SysReview PRISMA  v{pc.APP_VERSION}", font=("Arial Black", 24),
                     text_color=ACCENT2).pack(pady=(20, 0))
        ctk.CTkLabel(logo, text="Pipeline de Cribado Bibliográfico · PRISMA 2020", font=("Arial", 12),
                     text_color=MUTED2).pack()
        _ghost_button(self, "📂  Abrir proyecto guardado (.prisma)", ACCENT, self._open_session,
                      height=40).pack(fill="x", padx=28, pady=(14, 0))
        ctk.CTkLabel(self, text="…o elige un tema para una revisión nueva:", font=("Arial Bold", 13),
                     text_color=TEXT).pack(anchor="w", padx=28, pady=(12, 6))
        sb = ctk.CTkScrollableFrame(self, height=240, fg_color=SURFACE, corner_radius=12, border_color=BORDER, border_width=1)
        sb.pack(fill="x", padx=28, pady=(0, 12))
        for name, cfg in self.presets.items():
            is_default = name in DEFAULT_PRESETS
            row = ctk.CTkFrame(sb, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkFrame(row, fg_color=ACCENT if is_default else TEAL, width=4, corner_radius=2).pack(side="left", fill="y", padx=(0, 10))
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, pady=8)
            ctk.CTkLabel(info, text=name, font=("Arial Bold", 12), text_color=TEXT, anchor="w").pack(anchor="w")
            desc = cfg.get("description", "")
            yrs = f"{cfg.get('year_from') or '…'}–{cfg.get('year_to') or '…'}"
            ctk.CTkLabel(info, text=f"{desc}  ·  {yrs}" if desc else yrs, font=("Arial", 10), text_color=MUTED2,
                         anchor="w").pack(anchor="w")
            ctk.CTkButton(row, text="Usar →", width=86, height=32, font=("Arial Bold", 10), fg_color=ACCENT,
                          hover_color=ACCENT2, text_color="white", corner_radius=6,
                          command=lambda c=cfg, n=name: self._pick(n, c)).pack(side="right", padx=10, pady=8)
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=28, pady=(0, 8))
        _ghost_button(btn_row, "📂  Cargar configuración JSON...", TEAL, self._import_json,
                      height=40).pack(side="left", fill="x", expand=True, padx=(0, 6))
        _ghost_button(btn_row, "📄  Descargar plantilla JSON", CYAN, lambda: _save_template(self),
                      height=40).pack(side="left", fill="x", expand=True, padx=(6, 0))
        _ghost_button(self, "✦  Empezar desde cero (configuración vacía)", MUTED2, self._blank_start,
                      height=40).pack(fill="x", padx=28, pady=(0, 20))

    def _pick(self, name, cfg):
        self.destroy()
        self.on_select(name, cfg)

    def _blank_start(self):
        self.destroy()
        self.on_select("Nueva revisión", dict(BLANK_CONFIG))

    def _open_session(self):
        self.grab_release()
        if self.on_open_session(parent=self):
            self.destroy()
        else:
            make_modal(self, self.master)

    def _import_json(self):
        name, cfg = _load_json_preset(self)
        if cfg is not None:
            self._pick(name, cfg)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Revisión manual de un artículo (con navegación)
# ══════════════════════════════════════════════════════════════════════════════
class ReviewDialog(ctk.CTkToplevel):
    def __init__(self, app, rids, index=0):
        super().__init__(app)
        self.app = app
        self.rids = list(rids)
        self.i = max(0, min(index, len(self.rids) - 1))
        self.title("Revisión manual")
        self.geometry("1060x820")
        self.minsize(900, 700)
        self.configure(fg_color=BG)
        self.patterns = app.display_patterns()
        self._build()
        self._load()
        make_modal(self, app)

    # ── construcción ─────────────────────────────────────────────────────────
    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self.lbl_pos = ctk.CTkLabel(hdr, text="", font=("Courier Bold", 11), text_color=MUTED2)
        self.lbl_pos.pack(side="right", padx=18)
        self.lbl_title = ctk.CTkLabel(hdr, text="", font=("Arial Bold", 13), text_color=TEXT, anchor="w",
                                      justify="left", wraplength=860)
        self.lbl_title.pack(side="left", padx=18, pady=8, fill="x", expand=True)

        self.meta = ctk.CTkFrame(self, fg_color=SURFACE2, corner_radius=10)
        self.meta.pack(fill="x", padx=14, pady=(8, 4))
        self.meta_vals = {}
        for key, label in [("record_id", "ID"), ("year", "Año"), ("source", "Fuente"), ("doc_type", "Tipo"),
                           ("language", "Idioma"),
                           ("auto", "Decisión automática"), ("Status", "Estado PRISMA")]:
            f = ctk.CTkFrame(self.meta, fg_color="transparent")
            f.pack(side="left", padx=12, pady=6)
            ctk.CTkLabel(f, text=label, font=("Courier", 9), text_color=MUTED).pack(anchor="w")
            v = ctk.CTkLabel(f, text="—", font=("Arial Bold", 11), text_color=ACCENT2, anchor="w")
            v.pack(anchor="w")
            self.meta_vals[key] = v

        tabs = ctk.CTkTabview(self, fg_color=SURFACE, height=380, **TAB_STYLE)
        self._tabs = tabs   # se empaca al final para que el panel de decisión siempre quede visible
        for t in ("Texto", "Cribado automático", "Metadatos"):
            tabs.add(t)
        legend = ctk.CTkFrame(tabs.tab("Texto"), fg_color="transparent")
        legend.pack(fill="x")
        for label, _p, color in [(lab, p, c) for (_t, lab, p, c) in self.patterns]:
            ctk.CTkLabel(legend, text=f" {label} ", fg_color=color, text_color=TEXT, corner_radius=4,
                         font=("Arial", 9)).pack(side="left", padx=2, pady=(0, 4))
        self.txt = self._text_widget(tabs.tab("Texto"), ("Arial", 11))
        self.txt.tag_configure("title", font=("Arial", 13, "bold"))
        self.txt.tag_configure("label", font=("Arial", 10, "bold"), foreground=MUTED2)
        for tag, _lab, _p, color in self.patterns:
            self.txt.tag_configure(tag, background=color)
        if self.patterns:
            self.txt.tag_raise(self.patterns[0][0])
        self.txt_auto = self._text_widget(tabs.tab("Cribado automático"), ("Consolas", 10))
        self.txt_meta = self._text_widget(tabs.tab("Metadatos"), ("Consolas", 10))
        for w in (self.txt_auto, self.txt_meta):
            w.tag_configure("key", foreground=ACCENT2, font=("Consolas", 10, "bold"))

        panel = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=12, border_color=BORDER, border_width=1)
        self.lbl_dup = ctk.CTkLabel(panel, text="", font=("Arial Bold", 11), text_color=MUTED2)
        r1 = ctk.CTkFrame(panel, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(r1, text="Cribado (título/resumen):", font=("Arial Bold", 11), text_color=TEXT,
                     width=190, anchor="w").pack(side="left")
        self.ta_var = tk.StringVar(value="Sin decidir")
        self.seg_ta = ctk.CTkSegmentedButton(r1, values=list(TA_OPTIONS), variable=self.ta_var, font=("Arial", 11),
                                             **SEG_STYLE)
        self.seg_ta.pack(side="left", padx=(0, 10))
        self.cb_ta_reason = ctk.CTkComboBox(r1, values=pc.TA_EXCLUSION_REASONS, width=240, font=("Arial", 11))
        self.cb_ta_reason.set("")
        self.cb_ta_reason.pack(side="left", padx=(0, 8))
        self.note = ctk.CTkEntry(r1, placeholder_text="Nota (opcional)", font=("Arial", 11))
        self.note.pack(side="left", fill="x", expand=True)
        r2 = ctk.CTkFrame(panel, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(4, 10))
        ctk.CTkLabel(r2, text="Texto completo:", font=("Arial Bold", 11), text_color=TEXT, width=190,
                     anchor="w").pack(side="left")
        self.ft_var = tk.StringVar(value="Sin evaluar")
        self.seg_ft = ctk.CTkSegmentedButton(r2, values=list(FT_OPTIONS), variable=self.ft_var, font=("Arial", 11),
                                             **SEG_STYLE_FT)
        self.seg_ft.pack(side="left", padx=(0, 10))
        self.cb_ft_reason = ctk.CTkComboBox(r2, values=pc.FT_EXCLUSION_REASONS, width=240, font=("Arial", 11))
        self.cb_ft_reason.set("")
        self.cb_ft_reason.pack(side="left")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self, text="Atajos:  Ctrl+1 Incluir · Ctrl+2 Excluir · Ctrl+3 Dudoso · Ctrl+0 Sin decidir · "
                                "Ctrl+Enter guardar y siguiente · Ctrl+S guardar · Ctrl+← / → navegar · Esc cerrar",
                     font=("Arial", 9), text_color=MUTED2).pack(side="bottom", pady=(0, 8))
        nav.pack(side="bottom", fill="x", padx=14, pady=(0, 4))
        panel.pack(side="bottom", fill="x", padx=14, pady=(4, 6))
        self._tabs.pack(fill="both", expand=True, padx=14, pady=4)
        ctk.CTkButton(nav, text="◀ Anterior", width=110, height=36, fg_color=SURFACE2, hover_color=SURFACE3,
                      text_color=TEXT, command=lambda: self._move(-1)).pack(side="left")
        ctk.CTkButton(nav, text="Siguiente ▶", width=110, height=36, fg_color=SURFACE2, hover_color=SURFACE3,
                      text_color=TEXT, command=lambda: self._move(1)).pack(side="left", padx=6)
        ctk.CTkButton(nav, text="Cerrar", width=90, height=36, fg_color="transparent", hover_color=SURFACE2,
                      text_color=MUTED2, command=self.destroy).pack(side="right")
        ctk.CTkButton(nav, text="💾 Guardar y siguiente ▶", width=200, height=36, fg_color=ACCENT,
                      hover_color=ACCENT2, text_color="white", font=("Arial Bold", 12),
                      command=lambda: self._save(advance=True)).pack(side="right", padx=6)
        ctk.CTkButton(nav, text="Guardar", width=100, height=36, fg_color=SURFACE2, hover_color=SURFACE3,
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      command=lambda: self._save(advance=False)).pack(side="right")

        for key, label in (("1", "Incluir"), ("2", "Excluir"), ("3", "Dudoso"), ("0", "Sin decidir")):
            self.bind(f"<Control-Key-{key}>", lambda _e, lab=label: self.ta_var.set(lab))
        self.bind("<Control-Return>", lambda _e: self._save(advance=True))
        self.bind("<Control-s>", lambda _e: self._save(advance=False))
        self.bind("<Control-Right>", lambda _e: self._move(1))
        self.bind("<Control-Left>", lambda _e: self._move(-1))
        self.bind("<Escape>", lambda _e: self.destroy())

    @staticmethod
    def _text_widget(parent, font):
        frame = tk.Frame(parent, bg=SURFACE2)
        frame.pack(fill="both", expand=True)
        t = tk.Text(frame, bg=SURFACE2, fg=TEXT, font=font, wrap="word", relief="flat", padx=10, pady=8)
        sb = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        return t

    # ── datos ─────────────────────────────────────────────────────────────────
    def _row(self):
        return self.app.df.loc[self.rids[self.i]]

    def _load(self):
        if not self.rids:
            self.destroy()
            return
        r = self._row()
        self.lbl_pos.configure(text=f"{self.i + 1} / {len(self.rids)}")
        self.lbl_title.configure(text=str(r["title"])[:260] or "(sin título)")
        auto = r["Auto_Decision"]
        vals = {"record_id": r["record_id"], "year": fmt_year(r["year"]), "source": r["source"],
                "doc_type": (r["doc_type"] or "—")[:28], "language": (r["language"] or "—")[:20], "auto": DECISION_LABEL.get(auto, auto) or "—",
                "Status": r["Status"]}
        for k, v in vals.items():
            color = STATUS_STYLE.get(v, (None, ACCENT2))[1] if k == "Status" else ACCENT2
            self.meta_vals[k].configure(text=str(v), text_color=color)

        # Texto con resaltado de coincidencias
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("end", str(r["title"]) + "\n\n", "title")
        self.txt.insert("end", "Keywords: ", "label")
        self.txt.insert("end", (r["keywords"] or "—") + "\n\n")
        self.txt.insert("end", "Abstract\n", "label")
        self.txt.insert("end", (r["abstract"] or "— (sin abstract)") + "\n")
        full = self.txt.get("1.0", "end")
        for tag, _lab, pat, _c in self.patterns:
            for m in pat.finditer(full):
                self.txt.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        self.txt.configure(state="disabled")

        self._fill_kv(self.txt_auto, [
            ("Decisión automática", DECISION_LABEL.get(auto, auto)), ("Etapa", r["Auto_Stage"]),
            ("Razón", r["Auto_Reason"]), ("Coincidencias — obligatorio", r["Matched_Required"]),
            ("Coincidencias — secundario", r["Matched_Secondary"]), ("Coincidencias — exclusión", r["Matched_Exclude"]),
            ("Bloques cumplidos", f"{r['Matched_Blocks']}   ({r['N_Blocks']})"), ("Bloques faltantes", r["Missing_Blocks"]),
            ("Duplicado", f"{r['Is_Duplicate']}  {('de ' + r['Duplicate_Of']) if r['Duplicate_Of'] else ''}  {r['Duplicate_Reason']}"),
            ("Revisor 2", f"{DECISION_LABEL.get(r['TA_Decision_R2'], r['TA_Decision_R2'])}  {r['TA_Reason_R2']}"),
        ])
        self._fill_kv(self.txt_meta, [(c, r[c]) for c in r.index if c not in pc.AUTO_COLS])

        # Panel de decisión
        is_dup = r["Is_Duplicate"] == "Duplicate"
        state = "disabled" if is_dup else "normal"
        for w in (self.seg_ta, self.seg_ft, self.cb_ta_reason, self.cb_ft_reason, self.note):
            w.configure(state=state)
        if is_dup:
            self.lbl_dup.configure(text=f"Registro duplicado de {r['Duplicate_Of']} ({r['Duplicate_Reason']}) — "
                                        "las decisiones se toman sobre el registro conservado.")
            self.lbl_dup.pack(anchor="w", padx=12, pady=(8, 0), before=self.lbl_dup.master.winfo_children()[1])
        else:
            self.lbl_dup.pack_forget()
        inv_ta = {v: k for k, v in TA_OPTIONS.items()}
        inv_ft = {v: k for k, v in FT_OPTIONS.items()}
        self.ta_var.set(inv_ta.get(r["TA_Decision"], "Sin decidir"))
        self.ft_var.set(inv_ft.get(r["FT_Decision"], "Sin evaluar"))
        self.cb_ta_reason.set(r["TA_Reason"])
        self.cb_ft_reason.set(r["FT_Reason"])
        self.note.delete(0, "end")
        if r["TA_Note"]:
            self.note.insert(0, r["TA_Note"])

    @staticmethod
    def _fill_kv(widget, pairs):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for k, v in pairs:
            widget.insert("end", f"{k}:\n", "key")
            widget.insert("end", f"  {'' if v is None or (not isinstance(v, str) and pd.isna(v)) else v}\n\n")
        widget.configure(state="disabled")

    def _save(self, advance):
        r = self._row()
        if r["Is_Duplicate"] == "Duplicate":
            if advance:
                self._move(1)
            return
        ta = TA_OPTIONS[self.ta_var.get()]
        ft = FT_OPTIONS[self.ft_var.get()]
        ta_reason = self.cb_ta_reason.get().strip()
        ft_reason = self.cb_ft_reason.get().strip()
        ta_eff = ta or (pc.INCLUDE if r["Auto_Decision"] == pc.INCLUDE else pc.PENDING)
        if ft and ta_eff != pc.INCLUDE:
            messagebox.showwarning("Texto completo", "Para evaluar el texto completo, el registro debe estar "
                                   "INCLUIDO en el cribado de título/resumen.", parent=self)
            return
        if ft == pc.EXCLUDE and not ft_reason:
            messagebox.showwarning("Razón requerida", "PRISMA 2020 exige la razón de exclusión a texto completo.",
                                   parent=self)
            return
        if ta != pc.EXCLUDE:
            ta_reason = ta_reason if ta == pc.MAYBE else ""
        if ft != pc.EXCLUDE:
            ft_reason = ""
        self.app.set_manual(self.rids[self.i], TA_Decision=ta, TA_Reason=ta_reason,
                            TA_Note=self.note.get().strip(), FT_Decision=ft, FT_Reason=ft_reason)
        if advance and self.i < len(self.rids) - 1:
            self.i += 1
        elif advance:
            messagebox.showinfo("Fin de la lista", "Revisaste el último registro de esta lista.", parent=self)
        self._load()

    def _move(self, step):
        j = self.i + step
        if 0 <= j < len(self.rids):
            self.i = j
            self._load()


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — κ de Cohen
# ══════════════════════════════════════════════════════════════════════════════
class KappaDialog(ctk.CTkToplevel):
    def __init__(self, parent, res, unknown, invalid):
        super().__init__(parent)
        self.title("Acuerdo entre revisores")
        self.geometry("620x460")
        self.configure(fg_color=BG)
        self.res = res
        _screen_header(self, "👥  Acuerdo entre revisores (κ de Cohen)", "Cribado de título/resumen")
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=12)
        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x")
        k = res["kappa"]
        _stat_card(stats, "Registros comparados", str(res["n"]), TEXT)
        _stat_card(stats, "Acuerdo observado", f"{res['agreement'] * 100:.1f}%" if res["agreement"] is not None else "—", ACCENT2)
        _stat_card(stats, "κ de Cohen", f"{k:.3f}" if k is not None else "—", GREEN if (k or 0) >= 0.6 else YELLOW)
        lines = [f"Interpretación (Landis & Koch): {res['interpretation']}",
                 f"Desacuerdos: {len(res['disagreements'])}"]
        if res["r1_from_auto"]:
            lines.append(f"⚠ En {res['r1_from_auto']} registros el revisor 1 no tiene decisión manual; se usó la "
                         "decisión automática (Incluir).")
        if unknown:
            lines.append(f"⚠ {unknown} IDs de la hoja no existen en el proyecto (ignorados).")
        if invalid:
            lines.append(f"⚠ {invalid} filas con decisión no reconocida (usa Incluir / Excluir / Dudoso).")
        ctk.CTkLabel(body, text="\n".join(lines), font=("Arial", 11), text_color=TEXT, justify="left",
                     wraplength=560).pack(anchor="w", pady=14)
        _ghost_button(body, "💾 Exportar desacuerdos (.xlsx)", TEAL, self._export).pack(anchor="w")
        make_modal(self, parent)

    def _export(self):
        if self.res["disagreements"].empty:
            messagebox.showinfo("Sin desacuerdos", "No hay desacuerdos que exportar.", parent=self)
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Desacuerdos_revisores",
                                            filetypes=[("Excel", "*.xlsx")], parent=self)
        if path:
            self.res["disagreements"].map(pc.clean_cell).to_excel(path, index=False)
            messagebox.showinfo("Guardado", f"Guardado en:\n{path}", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# DIÁLOGO — Informe PRISMA
# ══════════════════════════════════════════════════════════════════════════════
class PrismaReportDialog(ctk.CTkToplevel):
    def __init__(self, parent, counts, review_name, cfg, prov):
        super().__init__(parent)
        self.title(f"Informe PRISMA 2020 — {review_name}")
        self.geometry("1080x820")
        self.configure(fg_color=BG)
        self.counts, self.review_name, self.cfg, self.prov = counts, review_name, cfg, prov
        self.layout = pc.prisma_layout(counts, f"Diagrama PRISMA 2020 — {review_name}")
        self.text = pc.build_text_report(counts, review_name, cfg, prov)
        hdr = _screen_header(self, "📋  Informe PRISMA 2020", review_name)
        if counts.get("pending") or counts.get("ft_pending") or counts.get("not_screened"):
            ctk.CTkLabel(hdr, text="⚠ Hay registros pendientes — ver advertencias en el resumen",
                         font=("Arial Bold", 10), text_color=YELLOW).place(relx=1.0, x=-20, y=22, anchor="ne")
        tabs = ctk.CTkTabview(self, fg_color=BG, **TAB_STYLE)
        tabs.pack(fill="both", expand=True, padx=12, pady=8)
        tabs.add("Diagrama de flujo")
        tabs.add("Resumen texto")
        frame = tk.Frame(tabs.tab("Diagrama de flujo"), bg=SURFACE)
        frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        draw_prisma_on_canvas(canvas, self.layout)
        st = scrolledtext.ScrolledText(tabs.tab("Resumen texto"), bg=SURFACE2, fg=TEXT, font=("Consolas", 10),
                                       wrap="none", relief="flat")
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("1.0", self.text)
        st.configure(state="disabled")
        btn_row = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)
        ctk.CTkButton(btn_row, text="📋 Copiar texto", height=36, font=("Arial Bold", 12), fg_color=ACCENT,
                      text_color="white", corner_radius=8, command=self._copy).pack(side="left", padx=(16, 8), pady=10)
        _ghost_button(btn_row, "💾 Guardar .txt", TEAL, self._save_txt).pack(side="left", padx=4)
        _ghost_button(btn_row, "🖼 Exportar SVG", CYAN, self._save_svg).pack(side="left", padx=4)
        _ghost_button(btn_row, "🖼 Exportar PNG", ACCENT2, self._save_png).pack(side="left", padx=4)
        make_modal(self, parent)

    def _ask(self, ext, kind):
        return filedialog.asksaveasfilename(defaultextension=ext, parent=self,
                                            initialfile=f"PRISMA_{safe_name(self.review_name)}",
                                            filetypes=[(kind, f"*{ext}")])

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.text)
        messagebox.showinfo("Copiado", "Informe copiado al portapapeles.", parent=self)

    def _save_txt(self):
        path = self._ask(".txt", "Texto")
        if path:
            Path(path).write_text(self.text, encoding="utf-8")
            pc.write_sidecar(path, self.cfg, self.prov, self.counts)
            messagebox.showinfo("Guardado", f"Informe guardado en:\n{path}", parent=self)

    def _save_svg(self):
        path = self._ask(".svg", "SVG")
        if path:
            Path(path).write_text(pc.layout_to_svg(self.layout), encoding="utf-8")
            messagebox.showinfo("Guardado", f"Diagrama guardado en:\n{path}", parent=self)

    def _save_png(self):
        path = self._ask(".png", "PNG")
        if not path:
            return
        try:
            pc.layout_to_png(self.layout, path)
            messagebox.showinfo("Guardado", f"Diagrama guardado en:\n{path}", parent=self)
        except ImportError:
            messagebox.showerror("Falta Pillow", "Para exportar PNG instala Pillow:\n  pip install pillow\n\n"
                                 "Mientras tanto puedes usar la exportación SVG.", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class SysReviewApp(ctk.CTk):
    def __init__(self, show_welcome=True):
        super().__init__()
        self.title(f"SysReview PRISMA  v{pc.APP_VERSION}  ·  Pipeline de Cribado PRISMA 2020")
        self.geometry("1440x960")
        self.minsize(1120, 780)
        self.configure(fg_color=BG)

        self.presets, preset_warning = load_user_presets()
        self.review_name = tk.StringVar(value="Nueva revisión")
        self.review_description = ""
        self.sources: list[dict] = []        # filas de la pantalla 1: {path, name_var, info, row}
        self.sources_info: list[dict] = []   # info de la última combinación (procedencia)
        self.df: pd.DataFrame | None = None
        self.dedup_stats: dict = {}
        self.last_steps: dict = {}
        self._last_cfg: dict | None = None
        self._search_blocks = dict(BLANK_CONFIG["search_blocks"])
        self._sort = ("record_id", True)
        self._search_job = None
        self._busy = False
        self._dirty = False
        self._session_path = None
        self._uiq: queue.Queue = queue.Queue()

        self._build_ui()
        self._apply_preset("Nueva revisión", dict(BLANK_CONFIG), mark_dirty=False)
        self._update_state()
        self.after(40, self._drain_ui)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if preset_warning:
            self.after(400, lambda: messagebox.showwarning("Presets", preset_warning, parent=self))
        if show_welcome:
            self.after(300, self._show_welcome)

    # ══════════════════════════════════════════════════════════════════════════
    # Hilos: los trabajos pesados corren en segundo plano y SOLO el hilo principal toca Tk
    # ══════════════════════════════════════════════════════════════════════════
    def _post(self, fn, *args):
        self._uiq.put((fn, args))

    def _drain_ui(self):
        try:
            while True:
                fn, args = self._uiq.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(40, self._drain_ui)

    def _bg(self, work, on_ok, on_err):
        if self._busy:
            messagebox.showinfo("Procesando", "Espera a que termine la operación en curso.", parent=self)
            return False
        self._busy = True
        self._update_state()

        def runner():
            try:
                res = work()
            except Exception as e:
                tb = traceback.format_exc()
                self._post(self._finish_bg, on_err, (e, tb))
                return
            self._post(self._finish_bg, on_ok, (res,))
        threading.Thread(target=runner, daemon=True).start()
        return True

    def _finish_bg(self, cb, args):
        self._busy = False
        try:
            cb(*args)
        finally:
            self._update_state()

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
        ctk.CTkLabel(hdr, text=f"  v{pc.APP_VERSION}  ·  PRISMA 2020", font=("Arial", 11),
                     text_color=MUTED2).pack(side="left")

        name_frame = ctk.CTkFrame(hdr, fg_color=SURFACE2, corner_radius=8)
        name_frame.pack(side="right", padx=(0, 12), pady=14)
        ctk.CTkLabel(name_frame, text="Revisión:", font=("Courier", 10), text_color=MUTED).pack(side="left", padx=(10, 4))
        ctk.CTkEntry(name_frame, textvariable=self.review_name, width=220, height=28, font=("Arial Bold", 11),
                     fg_color="transparent", border_width=0, text_color=ACCENT2).pack(side="left", padx=(0, 8))
        for text, color, cmd in [("⚙ Presets", MUTED2, self._open_presets),
                                 ("📋 Informe PRISMA", CYAN, self._show_prisma_report),
                                 ("💾 Guardar", TEAL, self._save_session),
                                 ("📂 Abrir", ACCENT2, self._open_session)]:
            ctk.CTkButton(hdr, text=text, width=110, height=34, font=("Arial Bold", 11), fg_color=SURFACE2,
                          hover_color=SURFACE3, border_color=BORDER, border_width=1, text_color=color,
                          corner_radius=8, command=cmd).pack(side="right", padx=(0, 6), pady=16)
        self.bind("<Control-s>", lambda _e: self._save_session())
        self.bind("<Control-o>", lambda _e: self._open_session())

        main_row = ctk.CTkFrame(self, fg_color=BG)
        main_row.pack(fill="both", expand=True)
        sidebar = ctk.CTkFrame(main_row, fg_color=SURFACE, width=250, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="PIPELINE", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(20, 8))
        self._tab_btns = []
        for num, label, icon, hint in [
            ("1", "Cargar Archivos", "📁", "Scopus, WoS, PubMed, IEEE, RIS, BibTeX, CSV o Excel"),
            ("2", "Deduplicar", "🔗", "DOI, título normalizado y títulos similares"),
            ("3", "Cribado automático", "🔬", "Años, tipos, keywords y bloques de la cadena"),
            ("4", "Revisión y resultados", "📊", "Revisión manual, segundo revisor y exportación"),
        ]:
            btn = ctk.CTkButton(sidebar, text=f"  {icon}  Paso {num} — {label}", anchor="w", height=46,
                                fg_color="transparent", hover_color=SURFACE2, font=("Arial", 12), text_color=MUTED,
                                corner_radius=10, command=lambda n=int(num) - 1: self._show_tab(n))
            btn.pack(fill="x", padx=8, pady=2)
            Tooltip(btn, hint)
            self._tab_btns.append(btn)
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(sidebar, text="RESUMEN RÁPIDO", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 8))
        self.sidebar_stats = {}
        for key, label, color in [("total", "Identificados", MUTED2), ("unique", "Únicos", ACCENT2),
                                  ("pending", "Pendientes", YELLOW), ("included", "Incluidos ✓", GREEN)]:
            row = ctk.CTkFrame(sidebar, fg_color=SURFACE2, corner_radius=8, height=46)
            row.pack(fill="x", padx=8, pady=2)
            row.pack_propagate(False)
            var = tk.StringVar(value="—")
            self.sidebar_stats[key] = var
            ctk.CTkLabel(row, textvariable=var, font=("Arial Black", 17), text_color=color).pack(side="right", padx=12)
            ctk.CTkLabel(row, text=label, font=("Courier", 10), text_color=MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(sidebar, text="PROGRESO", font=("Courier", 10), text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 6))
        self.global_progress = ctk.CTkProgressBar(sidebar, height=8, corner_radius=4, fg_color=SURFACE2,
                                                  progress_color=ACCENT)
        self.global_progress.pack(fill="x", padx=12)
        self.global_progress.set(0)
        self.lbl_progress = ctk.CTkLabel(sidebar, text="Sin datos", font=("Arial", 10), text_color=MUTED2,
                                         justify="left", anchor="w", wraplength=215)
        self.lbl_progress.pack(anchor="w", padx=14, pady=4)
        self.lbl_dirty = ctk.CTkLabel(sidebar, text="", font=("Courier", 9), text_color=ORANGE)
        self.lbl_dirty.pack(anchor="w", padx=14, side="bottom", pady=10)

        self._content = ctk.CTkFrame(main_row, fg_color=BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)
        self._screens = [self._build_screen_load(), self._build_screen_dedup(),
                         self._build_screen_cribar(), self._build_screen_results()]
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
                       "Agrega una o varias exportaciones. El nombre de la fuente se detecta automáticamente y puedes editarlo.")
        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)
        help_frame = ctk.CTkFrame(body, fg_color="#eff6ff", corner_radius=8, border_color="#bfdbfe", border_width=1)
        help_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(help_frame, text="💡  Formatos: CSV (coma o punto y coma) · Excel .xlsx/.xls · LibreOffice .ods · "
                                      "WoS texto tabulado / texto plano / .ciw · RIS · BibTeX · PubMed .nbib · EndNote .enw "
                                      "· IEEE CSV. El formato se detecta por el contenido, aunque la extensión no coincida. "
                                      "Si falta una librería (p. ej. xlrd para .xls), la app ofrece instalarla.",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=1000, justify="left").pack(anchor="w", padx=14, pady=8)

        src_card = _card_frame(body, "FUENTES")
        top = ctk.CTkFrame(src_card, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        ctk.CTkButton(top, text="➕  Agregar archivo(s)…", height=40, font=("Arial Bold", 12), fg_color=ACCENT,
                      hover_color=ACCENT2, text_color="white", corner_radius=10,
                      command=self._add_files).pack(side="left")
        self.lbl_sources_hint = ctk.CTkLabel(top, text="Sin archivos", font=("Courier", 11), text_color=MUTED)
        self.lbl_sources_hint.pack(side="left", padx=14)
        self.sources_frame = ctk.CTkFrame(src_card, fg_color="transparent")
        self.sources_frame.pack(fill="x")

        map_card = _card_frame(body, "MAPEO DE COLUMNAS  (opcional — solo si tus exportaciones usan nombres no estándar)")
        self._col_map = {}
        pairs = [("title", "Title / Article Title"), ("year", "Year / Publication Year"), ("abstract", "Abstract"),
                 ("doi", "DOI"), ("doc_type", "Document Type"), ("authors", "Authors"),
                 ("keywords", "Author Keywords"), ("index_keywords", "Index Keywords / Keywords Plus"),
                 ("journal", "Source title"), ("language", "Language of Original Document / Language")]
        for i in range(0, len(pairs), 3):
            row = ctk.CTkFrame(map_card, fg_color="transparent")
            row.pack(fill="x", pady=2)
            for k, v in pairs[i:i + 3]:
                sub = ctk.CTkFrame(row, fg_color="transparent")
                sub.pack(side="left", fill="x", expand=True, padx=(0, 8))
                ctk.CTkLabel(sub, text=f"{k}:", font=("Courier", 10), text_color=MUTED2, width=110, anchor="w").pack(side="left")
                e = ctk.CTkEntry(sub, height=28, font=("Courier", 11), fg_color=SURFACE2, border_color=BORDER,
                                 text_color=TEXT, placeholder_text=v)
                e.pack(side="left", fill="x", expand=True)
                self._col_map[k] = e

        self.load_stats_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.load_stats_frame.pack(fill="x", pady=10)
        self.btn_combine = ctk.CTkButton(body, text="▶  Combinar y preparar datos", height=50, font=("Arial Black", 14),
                                         fg_color=ACCENT, hover_color=ACCENT2, text_color="white", corner_radius=12,
                                         command=self._run_combine)
        self.btn_combine.pack(fill="x", pady=(0, 10))
        _log_label(body, "LOG DE CARGA")
        self.log_load = _log_area(body, height=8)
        return frame

    def _get_col_map(self):
        return {k: e.get().strip() for k, e in self._col_map.items() if e.get().strip()}

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Agregar exportaciones bibliográficas", filetypes=FILE_TYPES, parent=self)
        if not paths:
            return
        col_map = self._get_col_map()
        known = {s["path"] for s in self.sources}
        new = [p for p in paths if p not in known]
        if not new:
            return

        self._read_and_add(new, col_map)

    def _read_and_add(self, new, col_map):
        def work():
            out = []
            for p in new:
                try:
                    _df, info = pc.read_source(p, None, col_map)
                    out.append((p, info, None, None))
                except pc.MissingDependency as e:
                    out.append((p, None, str(e), e.package))
                except Exception as e:
                    out.append((p, None, str(e), None))
            return out

        def ok(results):
            missing = {}
            for p, info, err, pkg in results:
                if pkg:
                    missing.setdefault(pkg, []).append(p)
                    self._log(self.log_load, f"⚠ {Path(p).name}: {err}\n", YELLOW)
                    continue
                if err:
                    self._log(self.log_load, f"✗ {Path(p).name}: {err}\n", RED)
                    continue
                self._add_source_row(p, info["name"], info)
                miss = f"  ⚠ faltan: {', '.join(info['missing_fields'])}" if info["missing_fields"] else ""
                self._log(self.log_load, f"✓ {info['file']} → {info['name']} ({info['format']}, {info['n']} reg.){miss}\n",
                          YELLOW if miss else GREEN)
            if missing:
                self.after(50, lambda: self._offer_install(
                    list(missing), lambda: self._read_and_add([p for ps in missing.values() for p in ps], col_map)))

        def err(e, tb):
            self._log(self.log_load, f"✗ Error: {e}\n{tb}\n", RED)

        self._log(self.log_load, f"── Leyendo {len(new)} archivo(s)… ──\n", ACCENT2)
        self._bg(work, ok, err)

    def _offer_install(self, packages, retry):
        """Ofrece instalar librerías faltantes con pip (solo con permiso del usuario) y reintenta."""
        names = ", ".join(packages)
        if not messagebox.askyesno("Falta una librería",
                                   f"Para leer este formato se necesita: {names}\n\n¿Instalarla ahora con pip?\n"
                                   f"(Equivale a ejecutar:  pip install {' '.join(packages)})", parent=self):
            self._log(self.log_load, f"ℹ Instala manualmente con:  pip install {' '.join(packages)}\n", MUTED2)
            return
        import importlib
        import subprocess
        import sys

        def work():
            proc = subprocess.run([sys.executable, "-m", "pip", "install", *packages], capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout)[-800:])
            importlib.invalidate_caches()
            return True

        def ok(_):
            self._log(self.log_load, f"✓ Instalado: {names}. Reintentando lectura…\n", GREEN)
            self.after(50, retry)

        def err(e, _tb):
            self._log(self.log_load, f"✗ No se pudo instalar {names}: {e}\n", RED)
            messagebox.showerror("Error al instalar", f"No se pudo instalar {names}.\n\nPrueba en una terminal:\n"
                                 f"  pip install {' '.join(packages)}", parent=self)

        self._log(self.log_load, f"── Instalando {names}… ──\n", ACCENT2)
        self._bg(work, ok, err)

    def _add_source_row(self, path, name, info=None):
        row = ctk.CTkFrame(self.sources_frame, fg_color=SURFACE2, corner_radius=8)
        row.pack(fill="x", pady=2)
        color = SOURCE_COLORS[len(self.sources) % len(SOURCE_COLORS)]
        ctk.CTkFrame(row, fg_color=color, width=5, corner_radius=2).pack(side="left", fill="y", padx=(0, 8))
        name_var = tk.StringVar(value=name)
        ctk.CTkEntry(row, textvariable=name_var, width=150, height=30, font=("Arial Bold", 11), fg_color=SURFACE,
                     border_color=color, text_color=color).pack(side="left", padx=(0, 10), pady=6)
        if info:
            meta = f"{info['file']}  ·  {info['format']}  ·  {info['n']} registros"
            if info.get("missing_fields"):
                meta += f"  ·  ⚠ sin: {', '.join(info['missing_fields'])}"
        else:
            meta = f"{Path(path).name}  ·  (desde proyecto guardado)"
        ctk.CTkLabel(row, text=meta, font=("Courier", 10), text_color=MUTED2, anchor="w").pack(side="left", fill="x", expand=True)
        entry = {"path": path, "name_var": name_var, "info": info, "row": row}
        ctk.CTkButton(row, text="✕", width=30, height=28, fg_color="transparent", hover_color=RED_DIM, text_color=RED,
                      command=lambda: self._remove_source(entry)).pack(side="right", padx=6)
        self.sources.append(entry)
        self._update_state()

    def _remove_source(self, entry):
        entry["row"].destroy()
        self.sources.remove(entry)
        self._update_state()

    def _run_combine(self):
        if not self.sources:
            return
        if self.df is not None and (self.df["TA_Decision"].ne("").any() or self.df["FT_Decision"].ne("").any()):
            if not messagebox.askyesno("Reiniciar proyecto",
                                       "Volver a combinar reinicia el proyecto y se PERDERÁN las decisiones manuales.\n"
                                       "¿Continuar? (Guarda antes el proyecto si quieres conservarlas.)", parent=self):
                return
        names = [s["name_var"].get().strip() or Path(s["path"]).stem for s in self.sources]
        if len(set(names)) != len(names):
            messagebox.showwarning("Nombres repetidos", "Cada fuente debe tener un nombre distinto.", parent=self)
            return
        jobs = [(s["path"], n) for s, n in zip(self.sources, names)]
        col_map = self._get_col_map()

        def work():
            frames, infos = [], []
            for path, name in jobs:
                if not Path(path).exists():
                    raise FileNotFoundError(f"No se encuentra el archivo: {path}")
                df, info = pc.read_source(path, name, col_map)
                frames.append(df)
                infos.append(info)
            return pc.compute_status(pc.combine_sources(frames)), infos

        def ok(res):
            df, infos = res
            self.df, self.sources_info = df, infos
            self.dedup_stats, self.last_steps, self._last_cfg = {}, {}, None
            for w in self.load_stats_frame.winfo_children():
                w.destroy()
            for i, inf in enumerate(infos):
                _stat_card(self.load_stats_frame, inf["name"], str(inf["n"]), SOURCE_COLORS[i % len(SOURCE_COLORS)])
            _stat_card(self.load_stats_frame, "Total identificados", str(len(df)), TEXT)
            self._log(self.log_load, f"\n✅ Combinación exitosa: {len(df)} registros de {len(infos)} fuente(s).\n"
                                     f"➡ Continúa con el Paso 2.\n", GREEN)
            self._reset_screen_stats()
            self._mark_dirty()
            self._refresh_all()

        def err(e, tb):
            self._log(self.log_load, f"✗ Error: {e}\n{tb}\n", RED)

        self._log(self.log_load, "── Combinando fuentes ──\n", ACCENT2)
        self._bg(work, ok, err)

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 2 — DEDUPLICACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_dedup(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "🔗  Paso 2 — Eliminar Duplicados",
                       "DOI normalizado (sin https://doi.org/), título normalizado y, opcionalmente, títulos similares")
        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)
        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 14))
        self.dedup_cards = {
            "total": _stat_card(stats, "Total inicial", "—", MUTED2),
            "duplicates_doi": _stat_card(stats, "Dupl. por DOI", "—", RED),
            "duplicates_title": _stat_card(stats, "Dupl. por título", "—", YELLOW),
            "duplicates_fuzzy": _stat_card(stats, "Títulos similares", "—", ORANGE),
            "unique": _stat_card(stats, "Artículos únicos", "—", GREEN),
        }
        opts = _card_frame(body, "OPCIONES DE DEDUPLICACIÓN")
        r1 = ctk.CTkFrame(opts, fg_color="transparent")
        r1.pack(fill="x", pady=2)
        self.dedup_by_doi = tk.BooleanVar(value=True)
        self.dedup_by_title = tk.BooleanVar(value=True)
        self.dedup_fuzzy = tk.BooleanVar(value=False)
        self.title_sim_var = tk.StringVar(value="Normalizada")
        ctk.CTkCheckBox(r1, text="Por DOI", variable=self.dedup_by_doi, font=("Arial", 11), text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT2).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(r1, text="Por título", variable=self.dedup_by_title, font=("Arial", 11), text_color=TEXT,
                        fg_color=ACCENT, hover_color=ACCENT2).pack(side="left", padx=(0, 10))
        ctk.CTkSegmentedButton(r1, values=["Exacta", "Normalizada"], variable=self.title_sim_var, font=("Arial", 11),
                               **SEG_STYLE).pack(side="left", padx=(0, 30))
        cb = ctk.CTkCheckBox(r1, text="Títulos similares (≥", variable=self.dedup_fuzzy, font=("Arial", 11),
                             text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT2)
        cb.pack(side="left")
        self.fuzzy_thr = _num_entry(r1, 95, width=52)
        ctk.CTkLabel(r1, text="%)", font=("Arial", 11), text_color=TEXT).pack(side="left")
        Tooltip(cb, "Detecta erratas o puntuación distinta entre bases. 95% es conservador; 90% encuentra más pero "
                    "con más falsos positivos.")
        engine = "rapidfuzz (rápido)" if pc.HAS_RAPIDFUZZ else "difflib (instala rapidfuzz para más velocidad)"
        ctk.CTkLabel(opts, text=f"Motor de similitud: {engine}.  Nunca se fusionan por título registros con DOI "
                                "distintos.  De cada grupo se conserva el registro más completo.",
                     font=("Arial", 10), text_color=MUTED2, wraplength=1000, justify="left").pack(anchor="w", pady=(6, 0))
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 14))
        self.btn_dedup = ctk.CTkButton(btn_row, text="▶  Eliminar duplicados", height=46, font=("Arial Black", 13),
                                       fg_color=ACCENT, hover_color=ACCENT2, text_color="white", corner_radius=10,
                                       command=self._run_dedup)
        self.btn_dedup.pack(side="left", padx=(0, 10))
        self.btn_save_flagged = _ghost_button(btn_row, "💾  Exportar todos con banderas", TEAL, self._export_flagged, height=46)
        self.btn_save_flagged.pack(side="left")
        _log_label(body, "LOG DE DEDUPLICACIÓN")
        self.log_dedup = _log_area(body, height=14)
        return frame

    def _run_dedup(self):
        if self.df is None:
            return
        try:
            thr = read_int(self.fuzzy_thr, "Umbral de similitud", 70, 100)
        except ValueError as e:
            messagebox.showerror("Valor inválido", str(e), parent=self)
            return
        if self.df["Auto_Decision"].ne("").any():
            if not messagebox.askyesno("Volver a deduplicar", "Deduplicar de nuevo reinicia el cribado automático "
                                       "(las decisiones manuales se conservan). ¿Continuar?", parent=self):
                return
        params = dict(by_doi=self.dedup_by_doi.get(), by_title=self.dedup_by_title.get(),
                      title_mode="normalized" if self.title_sim_var.get() == "Normalizada" else "exact",
                      fuzzy=self.dedup_fuzzy.get(), threshold=thr)
        df = self.df

        def work():
            return pc.deduplicate(df, **params)

        def ok(res):
            self.df, self.dedup_stats = res
            self._last_cfg, self.last_steps = None, {}
            st = self.dedup_stats
            for k, lbl in self.dedup_cards.items():
                v = st.get(k, 0) + (st.get("duplicates_other", 0) if k == "duplicates_fuzzy" else 0)
                lbl.configure(text=str(v))
            self._log(self.log_dedup,
                      f"\n✅ Deduplicación completada.\n"
                      f"   Total inicial:      {st['total']}\n"
                      f"   DOI idéntico:       {st['duplicates_doi']}\n"
                      f"   Título idéntico:    {st['duplicates_title']}\n"
                      f"   Título similar:     {st['duplicates_fuzzy'] + st['duplicates_other']}"
                      f"{'  (' + st['fuzzy_engine'] + ')' if st['fuzzy_engine'] else ''}\n"
                      f"   Total eliminados:   {st['duplicates_total']}\n"
                      f"   Únicos restantes:   {st['unique']}\n"
                      f"➡ Continúa con el Paso 3.\n", GREEN)
            self._reset_cribar_stats()
            self._mark_dirty()
            self._refresh_all()

        def err(e, tb):
            self._log(self.log_dedup, f"✗ Error: {e}\n{tb}\n", RED)

        self._log(self.log_dedup, "── Iniciando deduplicación"
                                  f"{' (títulos similares: puede tardar)' if params['fuzzy'] else ''} ──\n", ACCENT2)
        self._bg(work, ok, err)

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 3 — CRIBADO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_cribar(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "🔬  Paso 3 — Cribado automático",
                       "Filtra por año, tipo, keywords y bloques. Los casos dudosos se envían a revisión manual en vez de excluirse.")
        outer = ctk.CTkScrollableFrame(frame, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        body = ctk.CTkFrame(outer, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)
        left_col = ctk.CTkFrame(body, fg_color=BG)
        right_col = ctk.CTkFrame(body, fg_color=BG)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10), anchor="n")
        right_col.pack(side="left", fill="both", expand=True, padx=(10, 0), anchor="n")

        cfg = _card_frame(left_col, "CONFIGURACIÓN DEL FILTRO")
        ctk.CTkLabel(cfg, text="Sintaxis: términos separados por coma · palabra completa (\"ai\" ≠ \"main\") · "
                               "comodines monitor* y organi?ation · guion = espacio · sin distinguir acentos.",
                     font=("Arial", 10), text_color="#1d4ed8", wraplength=560, justify="left").pack(anchor="w", pady=(0, 6))
        yr_row = ctk.CTkFrame(cfg, fg_color="transparent")
        yr_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(yr_row, text="Rango de años:", font=("Courier", 11), text_color=MUTED2).pack(side="left")
        self.year_from = _num_entry(yr_row, "")
        ctk.CTkLabel(yr_row, text="  —  ", text_color=MUTED2).pack(side="left")
        self.year_to = _num_entry(yr_row, "")
        ctk.CTkLabel(yr_row, text="   Sin año:", font=("Courier", 11), text_color=MUTED2).pack(side="left")
        self.missing_year_var = tk.StringVar(value=pc.MISSING_YEAR_MODES["review"])
        ctk.CTkSegmentedButton(yr_row, values=list(pc.MISSING_YEAR_MODES.values()), variable=self.missing_year_var,
                               font=("Arial", 10), **SEG_STYLE).pack(side="left", padx=6)

        self.kw_required = _textarea(cfg, "🟠 Bloque OBLIGATORIO — al menos UNO en título/resumen/keywords", 60, ORANGE)
        Tooltip(self.kw_required, "Si ninguno de estos términos aparece → excluido automáticamente. Vacío = sin filtro.")
        self.kw_secondary = _textarea(cfg, "🟢 Bloque SECUNDARIO — al menos UNO", 70, GREEN)
        Tooltip(self.kw_secondary, "Complementa el bloque obligatorio. Vacío = sin filtro.")
        self.kw_exclude = _textarea(cfg, "🔴 Términos de EXCLUSIÓN", 80, RED)
        exc_row = ctk.CTkFrame(cfg, fg_color="transparent")
        exc_row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(exc_row, text="Modo de exclusión:", font=("Courier", 10), text_color=MUTED2).pack(side="left")
        self.exclude_mode_var = tk.StringVar(value=pc.EXCLUDE_MODES["balanced"])
        ctk.CTkOptionMenu(exc_row, values=list(pc.EXCLUDE_MODES.values()), variable=self.exclude_mode_var, width=430,
                          font=("Arial", 10), fg_color=SURFACE2, button_color=SURFACE3, button_hover_color=BORDER,
                          text_color=TEXT).pack(side="left", padx=6)
        self.doc_include = _textarea(cfg, "✅ Tipos de documento PERMITIDOS — vacío = todos (ej. Article, Proceedings Paper)",
                                     40, TEAL)
        Tooltip(self.doc_include, "Solo pasan estos tipos. 'Proceedings Paper' (WoS) y 'Conference Paper' (Scopus) "
                                  "se consideran el mismo tipo. Registros sin tipo no se excluyen.")
        self.doc_exclude = _textarea(cfg, "🚫 Tipos de documento a excluir (coincidencia exacta por tipo)", 40, MUTED2)
        Tooltip(self.doc_exclude, "Se compara cada tipo por separado: 'Article; Proceedings Paper' se excluye si "
                                  "'proceedings paper' está en la lista, pero 'review' no excluye 'Article'.")
        self.languages = _textarea(cfg, "🌐 Idiomas permitidos — vacío = todos (ej. English, Spanish)", 36, CYAN)
        Tooltip(self.languages, "Se usa la columna de idioma de la exportación (Scopus: 'Language of Original "
                                "Document'; WoS: 'Language'). Acepta English/Inglés/eng. Registros sin idioma no se excluyen.")

        blk_hdr = ctk.CTkFrame(cfg, fg_color="transparent")
        blk_hdr.pack(fill="x", pady=(10, 2))
        ctk.CTkLabel(blk_hdr, text="🧩 Bloques de cadena de búsqueda", font=("Courier", 11), text_color=MUTED2).pack(side="left")
        _ghost_button(blk_hdr, "✏ Editar bloques", TEAL, self._open_blocks_editor, height=28, width=120).pack(side="right")
        _ghost_button(blk_hdr, "🔎 Importar cadena", ACCENT2, self._open_query_import, height=28, width=130).pack(side="right", padx=6)
        self.blocks_summary = ctk.CTkFrame(cfg, fg_color=SURFACE2, corner_radius=8)
        self.blocks_summary.pack(fill="x", pady=(0, 8))
        min_row = ctk.CTkFrame(cfg, fg_color="transparent")
        min_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(min_row, text="Bloques mínimos (0 = todos):", font=("Courier", 11), text_color=MUTED2).pack(side="left")
        self.min_blocks_entry = _num_entry(min_row, 0)
        opt_row = ctk.CTkFrame(cfg, fg_color="transparent")
        opt_row.pack(fill="x", pady=(4, 0))
        self.auto_plural_var = tk.BooleanVar(value=True)
        self.near_miss_var = tk.BooleanVar(value=False)
        c1 = ctk.CTkCheckBox(opt_row, text="Plural automático (s/es, y→ies)", variable=self.auto_plural_var,
                             font=("Arial", 11), text_color=TEXT, fg_color=ACCENT)
        c1.pack(side="left", padx=(0, 18))
        c2 = ctk.CTkCheckBox(opt_row, text="A 1 bloque del mínimo → revisión", variable=self.near_miss_var,
                             font=("Arial", 11), text_color=TEXT, fg_color=ACCENT)
        c2.pack(side="left")
        Tooltip(c2, "En lugar de excluir, envía a revisión manual los artículos que cumplen (mínimo − 1) bloques.")

        pipe_card = _card_frame(right_col, "RESULTADO DEL CRIBADO AUTOMÁTICO")
        self.cribar_steps = {}
        for key, name in [("input", "Registros únicos a cribar"), ("year", "Filtro de año"),
                          ("doc_type", "Tipo de documento"), ("language", "Idioma"), ("required", "Bloque obligatorio"),
                          ("secondary", "Bloque secundario"), ("exclude", "Términos de exclusión"),
                          ("blocks", "Bloques de búsqueda"), ("result", "Resultado")]:
            row = ctk.CTkFrame(pipe_card, fg_color=SURFACE2, corner_radius=8)
            row.pack(fill="x", pady=2)
            dot = ctk.CTkLabel(row, text="", width=14, height=14, fg_color=BORDER, corner_radius=7)
            dot.pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=name, font=("Arial Bold", 11), text_color=TEXT, anchor="w", width=170).pack(side="left")
            val = ctk.CTkLabel(row, text="—", font=("Arial", 10), text_color=MUTED, anchor="w", justify="left",
                               wraplength=250)
            val.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)
            self.cribar_steps[key] = (dot, val)
        stats = ctk.CTkFrame(pipe_card, fg_color="transparent")
        stats.pack(fill="x", pady=(10, 0))
        self.cribar_cards = {
            "auto_exc": _stat_card(stats, "Excl. auto", "—", RED),
            "review": _stat_card(stats, "A revisión", "—", YELLOW),
            "include": _stat_card(stats, "Aprobados", "—", GREEN),
        }
        ctk.CTkLabel(pipe_card, text="Incluidos por fuente", font=("Courier", 10), text_color=MUTED2).pack(anchor="w", pady=(10, 2))
        self.bar_canvas = tk.Canvas(pipe_card, height=14, bg=SURFACE3, highlightthickness=0, bd=0)
        self.bar_canvas.pack(fill="x")
        self.lbl_src_split = ctk.CTkLabel(pipe_card, text="—", font=("Courier", 10), text_color=MUTED2, anchor="w",
                                          justify="left")
        self.lbl_src_split.pack(anchor="w", pady=(4, 0))
        self.btn_run = ctk.CTkButton(right_col, text="⚡  Ejecutar cribado automático", height=52, font=("Arial Black", 15),
                                     fg_color=ACCENT, hover_color=ACCENT2, text_color="white", corner_radius=14,
                                     command=self._start_pipeline)
        self.btn_run.pack(fill="x", pady=(4, 4))
        self.btn_go_review = _ghost_button(right_col, "➡  Ir a revisión manual (Paso 4)", GREEN,
                                           lambda: self._show_tab(3), height=42)
        self.btn_go_review.pack(fill="x", pady=(0, 8))
        _log_label(right_col, "LOG DEL CRIBADO")
        self.log_cribar = _log_area(right_col, height=12)
        return frame

    def _refresh_blocks_summary(self):
        for w in self.blocks_summary.winfo_children():
            w.destroy()
        inner = ctk.CTkFrame(self.blocks_summary, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=6)
        for i, (bid, b) in enumerate(self._search_blocks.items()):
            n_terms = len(pc.parse_terms(b.get("terms", "")))
            chip = ctk.CTkFrame(inner, fg_color=SURFACE3, corner_radius=6)
            chip.pack(side="left", padx=3, pady=2)
            ctk.CTkLabel(chip, text=f"{bid} ({n_terms}t)" if n_terms else f"{bid} (vacío)", font=("Courier", 9),
                         text_color=BLOCK_COLORS[i % len(BLOCK_COLORS)] if n_terms else MUTED).pack(padx=8, pady=3)
            Tooltip(chip, f"{b.get('label', bid)}\n{b.get('terms', '')}")

    def _open_blocks_editor(self):
        BlocksEditorDialog(self, self._search_blocks, self._on_blocks_saved)

    def _on_blocks_saved(self, new_blocks):
        self._search_blocks = new_blocks
        self._refresh_blocks_summary()
        try:
            n = int(self.min_blocks_entry.get() or 0)
            n_act = sum(1 for b in new_blocks.values() if pc.parse_terms(b.get("terms", "")))
            if n > n_act:
                self.min_blocks_entry.delete(0, "end")
                self.min_blocks_entry.insert(0, str(n_act))
        except ValueError:
            pass
        self._mark_dirty()

    def _open_query_import(self):
        QueryImportDialog(self, self._apply_query)

    def _apply_query(self, r):
        self._search_blocks = r["search_blocks"]
        self._refresh_blocks_summary()
        self.min_blocks_entry.delete(0, "end")
        self.min_blocks_entry.insert(0, str(r["min_blocks"]))
        if r["year_from"]:
            self.year_from.delete(0, "end")
            self.year_from.insert(0, str(r["year_from"]))
        if r["year_to"]:
            self.year_to.delete(0, "end")
            self.year_to.insert(0, str(r["year_to"]))
        if r["kw_exclude"]:
            merged = pc.parse_terms(_get_text(self.kw_exclude)) + pc.parse_terms(r["kw_exclude"])
            _set_text(self.kw_exclude, ", ".join(dict.fromkeys(merged)))
        msg = f"Se aplicaron {len(r['search_blocks'])} bloques"
        if r["year_from"] or r["year_to"]:
            msg += f", años {r['year_from'] or '…'}–{r['year_to'] or '…'}"
        if r["languages"]:
            _set_text(self.languages, r["languages"])
            msg += f", idiomas: {r['languages']}"
        if r["doc_include"]:
            _set_text(self.doc_include, r["doc_include"])
            msg += f", tipos: {r['doc_include']}"
            # Quita de 'excluir' los tipos que la cadena permite explícitamente (evita contradicciones)
            allowed = set(pc.canon_list(r["doc_include"], "doctype"))
            current = pc.canon_list(_get_text(self.doc_exclude), "doctype")
            removed = [t for t in current if t in allowed]
            if removed:
                _set_text(self.doc_exclude, ", ".join(t for t in current if t not in allowed))
                msg += f".\nSe quitaron de 'tipos a excluir' porque la cadena los permite: {', '.join(removed)}"
        if r["doc_exclude"]:
            merged = pc.canon_list(_get_text(self.doc_exclude), "doctype") + pc.canon_list(r["doc_exclude"], "doctype")
            _set_text(self.doc_exclude, ", ".join(dict.fromkeys(merged)))
        self._mark_dirty()
        msg += "."
        if _get_text(self.kw_required) or _get_text(self.kw_secondary):
            msg += ("\n\nOjo: los campos 'Bloque OBLIGATORIO' y 'Bloque SECUNDARIO' siguen con términos del preset "
                    "y también se aplicarán. Vacíalos si solo quieres usar los criterios de tu cadena.")
        if r["warnings"]:
            msg += "\n\n" + "\n".join("⚠ " + w for w in r["warnings"])
        messagebox.showinfo("Cadena importada", msg, parent=self)

    def _get_config(self) -> dict:
        """Lee la configuración de la pantalla (en el hilo principal). Lanza ValueError si hay datos inválidos."""
        yf = read_int(self.year_from, "Año desde", 1800, 2100, allow_empty=True)
        yt = read_int(self.year_to, "Año hasta", 1800, 2100, allow_empty=True)
        if yf is not None and yt is not None and yf > yt:
            raise ValueError("El año inicial debe ser menor o igual al año final.")
        mb = read_int(self.min_blocks_entry, "Bloques mínimos", 0, 99, allow_empty=True) or 0
        inv_exc = {v: k for k, v in pc.EXCLUDE_MODES.items()}
        inv_my = {v: k for k, v in pc.MISSING_YEAR_MODES.items()}
        return {
            "name": self.review_name.get().strip(),
            "description": self.review_description,
            "year_from": yf, "year_to": yt,
            "kw_required": _get_text(self.kw_required),
            "kw_secondary": _get_text(self.kw_secondary),
            "kw_exclude": _get_text(self.kw_exclude),
            "doc_exclude": _get_text(self.doc_exclude),
            "doc_include": _get_text(self.doc_include),
            "languages": _get_text(self.languages),
            "search_blocks": {k: dict(v) for k, v in self._search_blocks.items()},
            "min_blocks": mb,
            "exclude_mode": inv_exc.get(self.exclude_mode_var.get(), "balanced"),
            "missing_year": inv_my.get(self.missing_year_var.get(), "review"),
            "auto_plural": bool(self.auto_plural_var.get()),
            "review_near_miss": bool(self.near_miss_var.get()),
            "col_map": self._get_col_map(),
        }

    def _start_pipeline(self):
        if self.df is None:
            return
        try:
            cfg = self._get_config()
        except ValueError as e:
            messagebox.showerror("Configuración inválida", str(e), parent=self)
            return
        if not self.df["Is_Duplicate"].ne("").any():
            if not messagebox.askyesno("Sin deduplicar", "Aún no ejecutas la deduplicación (Paso 2). "
                                       "¿Cribar sin eliminar duplicados?", parent=self):
                return
        df = self.df
        self._log(self.log_cribar, "── Iniciando cribado automático ──\n", ACCENT2)

        def work():
            return pc.run_screening(df, cfg)

        def ok(res):
            self.df, steps = res
            self.last_steps, self._last_cfg = steps, cfg
            self._show_steps(steps)
            c = pc.compute_counts(self.df)
            self._log(self.log_cribar,
                      f"✓ Únicos cribados: {steps['input']}\n"
                      f"✓ Año: −{steps['year_out']} fuera de rango, −{steps['year_missing_excluded']} sin año, "
                      f"{steps['year_missing_review']} sin año → revisión\n"
                      f"✓ Tipo de documento: −{steps['doc_type']}   Idioma: −{steps['language']}\n"
                      f"✓ Bloque obligatorio: −{steps['required']}   Secundario: −{steps['secondary']}\n"
                      f"✓ Exclusión: −{steps['exclude_terms']}   → revisión: {steps['exclude_review']}\n"
                      f"✓ Bloques: −{steps['blocks']}   casi cumplen → revisión: {steps['near_miss_review']}\n"
                      f"{'═' * 50}\n✅ Aprobados: {steps['include']}   ·   A revisión manual: {steps['review']}\n"
                      f"   Estado actual (incluye decisiones manuales): {c['included']} incluidos, {c['pending']} pendientes\n"
                      f"➡ Ve al Paso 4 para revisar y exportar.\n", GREEN)
            self._mark_dirty()
            self._refresh_all()

        def err(e, tb):
            self._log(self.log_cribar, f"✗ Error: {e}\n{tb}\n", RED)

        self._bg(work, ok, err)

    def _show_steps(self, s):
        if not s:
            return
        rows = {
            "input": (s["input"], f"{s['input']} registros"),
            "year": (s["year_out"] + s["year_missing_excluded"],
                     f"−{s['year_out']} fuera de rango · −{s['year_missing_excluded']} sin año · "
                     f"{s['year_missing_review']} sin año → revisión"),
            "doc_type": (s["doc_type"], f"−{s['doc_type']}"),
            "language": (s.get("language", 0), f"−{s.get('language', 0)}"),
            "required": (s["required"], f"−{s['required']}"),
            "secondary": (s["secondary"], f"−{s['secondary']}"),
            "exclude": (s["exclude_terms"], f"−{s['exclude_terms']} · {s['exclude_review']} → revisión"),
            "blocks": (s["blocks"], f"−{s['blocks']} · {s['near_miss_review']} casi cumplen → revisión"),
            "result": (None, f"✅ {s['include']} aprobados · 🟡 {s['review']} a revisión"),
        }
        for key, (n, text) in rows.items():
            dot, val = self.cribar_steps[key]
            dot.configure(fg_color=ACCENT2 if key in ("input", "result") else (ORANGE if n else GREEN))
            val.configure(text=text, text_color=TEXT)
        auto_exc = sum(s.get(k, 0) for k in ("year_out", "year_missing_excluded", "doc_type", "language", "required",
                                             "secondary", "exclude_terms", "blocks"))
        self.cribar_cards["auto_exc"].configure(text=str(auto_exc))
        self.cribar_cards["review"].configure(text=str(s["review"]))
        self.cribar_cards["include"].configure(text=str(s["include"]))

    def _reset_cribar_stats(self):
        for dot, val in self.cribar_steps.values():
            dot.configure(fg_color=BORDER)
            val.configure(text="—", text_color=MUTED)
        for lbl in self.cribar_cards.values():
            lbl.configure(text="—")

    def _reset_screen_stats(self):
        for lbl in self.dedup_cards.values():
            lbl.configure(text="—")
        self._reset_cribar_stats()

    def _draw_source_bar(self, by_source: dict):
        self.bar_canvas.update_idletasks()
        w = self.bar_canvas.winfo_width()
        w = w if w > 50 else 400
        self.bar_canvas.delete("all")
        self.bar_canvas.create_rectangle(0, 0, w, 14, fill=BORDER, outline="")
        total = sum(by_source.values())
        x = 0
        parts = []
        for i, (src, n) in enumerate(by_source.items()):
            color = SOURCE_COLORS[i % len(SOURCE_COLORS)]
            if total:
                seg = w * n / total
                self.bar_canvas.create_rectangle(x, 0, x + seg, 14, fill=color, outline="")
                x += seg
            parts.append(f"{src}: {n}")
        self.lbl_src_split.configure(text="   ".join(parts) if parts else "—")

    # ══════════════════════════════════════════════════════════════════════════
    # PANTALLA 4 — REVISIÓN Y RESULTADOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_screen_results(self):
        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        _screen_header(frame, "📊  Paso 4 — Revisión manual y resultados",
                       "Doble clic (o Enter) en una fila para revisarla. Las decisiones manuales prevalecen sobre las automáticas.")
        body = ctk.CTkFrame(frame, fg_color=BG)
        body.pack(fill="both", expand=True, padx=28, pady=10)
        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 10))
        self.res_cards = {
            "identified_total": _stat_card(stats, "Identificados", "—", MUTED2),
            "duplicates_total": _stat_card(stats, "Duplicados", "—", YELLOW),
            "auto_exc": _stat_card(stats, "Excl. automáticos", "—", MUTED2),
            "pending": _stat_card(stats, "Pendientes", "—", YELLOW),
            "manual_exc": _stat_card(stats, "Excl. manuales", "—", RED),
            "included": _stat_card(stats, "Incluidos", "—", GREEN),
        }
        toolbar = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        toolbar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(toolbar, text="🔍", font=("Arial", 14), text_color=MUTED2).pack(side="left", padx=(12, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._schedule_search())
        ctk.CTkEntry(toolbar, textvariable=self.search_var, width=300, height=34, font=("Courier", 12), fg_color=SURFACE3,
                     border_color=BORDER, text_color=TEXT,
                     placeholder_text="Buscar en título, abstract, DOI, autores…").pack(side="left", padx=(0, 10), pady=8)
        self.view_var = tk.StringVar(value="Todos")
        ctk.CTkSegmentedButton(toolbar, values=list(VIEW_FILTERS), variable=self.view_var, font=("Arial", 11),
                               **SEG_STYLE, command=lambda _v: self._refresh_table()).pack(side="left", padx=4)
        ctk.CTkLabel(toolbar, text="Fuente:", font=("Courier", 10), text_color=MUTED2).pack(side="left", padx=(10, 2))
        self.source_var = tk.StringVar(value="Todas")
        self.source_menu = ctk.CTkOptionMenu(toolbar, values=["Todas"], variable=self.source_var, width=130,
                                             fg_color=SURFACE3, button_color=SURFACE3, button_hover_color=BORDER,
                                             text_color=TEXT, command=lambda _v: self._refresh_table())
        self.source_menu.pack(side="left")
        self.lbl_count = ctk.CTkLabel(toolbar, text="", font=("Courier", 10), text_color=MUTED2)
        self.lbl_count.pack(side="right", padx=12)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")   # se empaca ANTES de la tabla: siempre visible
        btn_row.pack(side="bottom", fill="x", pady=(8, 0))
        tree_frame = tk.Frame(body, bg=BG)
        tree_frame.pack(fill="both", expand=True)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("SR.Treeview", background=SURFACE, foreground=TEXT, fieldbackground=SURFACE, rowheight=28,
                        font=("Segoe UI", 9))
        style.configure("SR.Treeview.Heading", background=SURFACE2, foreground=MUTED2, font=("Arial Bold", 9), relief="flat")
        style.map("SR.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        self.tree_cols = [("ID", "record_id", 70), ("Año", "year", 52), ("Título", "title", 430),
                          ("Fuente", "source", 80), ("Auto", "Auto_Decision", 70), ("Manual", "TA_Decision", 120),
                          ("Estado", "Status", 160), ("Razón / bloques", "_reason", 280)]
        self.tree = ttk.Treeview(tree_frame, columns=[c[0] for c in self.tree_cols], show="headings", style="SR.Treeview")
        for col, key, w in self.tree_cols:
            self.tree.heading(col, text=col, command=lambda k=key: self._sort_tree(k))
            self.tree.column(col, width=w, minwidth=40, stretch=(key == "title"))
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        for status, (bg, fg) in STATUS_STYLE.items():
            self.tree.tag_configure(status, background=bg, foreground=fg)
        self.tree.bind("<Double-1>", self._on_row_open)
        self.tree.bind("<Return>", self._on_row_open)

        self.btn_review_pending = ctk.CTkButton(btn_row, text="▶ Revisar pendientes", height=40, font=("Arial Bold", 12),
                                                fg_color=ACCENT, hover_color=ACCENT2, text_color="white",
                                                corner_radius=10, command=self._review_pending)
        self.btn_review_pending.pack(side="left", padx=(0, 6))
        self.result_buttons = [self.btn_review_pending]
        for text, color, cmd in [("Revisar vista actual", ACCENT2, self._review_view),
                                 ("💾 Excel completo (por etapas)", TEXT, self._export_workbook),
                                 ("CSV incluidos", TEAL, self._export_csv_included),
                                 ("RIS incluidos", CYAN, self._export_ris_included),
                                 ("👥 Hoja 2º revisor", MUTED2, self._export_reviewer_sheet),
                                 ("👥 Importar 2º revisor (κ)", GREEN, self._import_reviewer_sheet)]:
            b = _ghost_button(btn_row, text, color, cmd, height=40)
            b.pack(side="left", padx=(0, 6))
            self.result_buttons.append(b)
        return frame

    # ── tabla ─────────────────────────────────────────────────────────────────
    def _schedule_search(self):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._refresh_table)

    def _view_df(self) -> pd.DataFrame:
        if self.df is None:
            return pd.DataFrame()
        d = self.df
        statuses = VIEW_FILTERS.get(self.view_var.get())
        if statuses:
            d = d[d["Status"].isin(statuses)]
        src = self.source_var.get()
        if src != "Todas":
            d = d[d["source"] == src]
        q = self.search_var.get().strip().lower()
        if q:
            mask = pd.Series(False, index=d.index)
            for c in ("title", "abstract", "keywords", "doi", "authors", "record_id", "Matched_Blocks", "TA_Note"):
                mask |= d[c].str.lower().str.contains(q, regex=False)
            d = d[mask]
        key, asc = self._sort
        if key == "_reason":
            key = "Auto_Reason"
        if key in d.columns:
            d = d.sort_values(key, ascending=asc, na_position="last", kind="stable")
        return d

    @staticmethod
    def _row_reason(r) -> str:
        st = r["Status"]
        if st == pc.STATUS_EXC_TA:
            return r["TA_Reason"] or "(manual, sin razón)"
        if st in (pc.STATUS_EXC_FT, pc.STATUS_NOT_RETRIEVED):
            return r["FT_Reason"] or st
        if st == pc.STATUS_DUP:
            return f"{r['Duplicate_Reason']} de {r['Duplicate_Of']}"
        if st in (pc.STATUS_EXC_AUTO, pc.STATUS_PENDING):
            return r["Auto_Reason"] if r["Auto_Decision"] != pc.INCLUDE else (r["TA_Note"] or "Dudoso")
        return f"{r['Matched_Blocks']} ({r['N_Blocks']})" if r["Matched_Blocks"] else r["Auto_Reason"]

    def _row_values(self, r):
        manual = DECISION_LABEL.get(r["TA_Decision"], r["TA_Decision"])
        if r["FT_Decision"]:
            manual += f" · TC: {DECISION_LABEL.get(r['FT_Decision'], r['FT_Decision'])}"
        return (r["record_id"], fmt_year(r["year"]), str(r["title"])[:140], r["source"],
                DECISION_LABEL.get(r["Auto_Decision"], r["Auto_Decision"]), manual, r["Status"],
                self._row_reason(r)[:120])

    def _refresh_table(self):
        self._search_job = None
        self.tree.delete(*self.tree.get_children())
        d = self._view_df()
        for rid, r in d.iterrows():
            self.tree.insert("", "end", iid=rid, values=self._row_values(r), tags=(r["Status"],))
        total = 0 if self.df is None else len(self.df)
        self.lbl_count.configure(text=f"{len(d)} de {total} registros")

    def _sort_tree(self, key):
        cur_key, asc = self._sort
        self._sort = (key, not asc if cur_key == key else True)
        self._refresh_table()

    def _on_row_open(self, _event=None):
        sel = self.tree.selection() or ((self.tree.focus(),) if self.tree.focus() else ())
        if not sel or self.df is None:
            return
        rids = list(self.tree.get_children())
        ReviewDialog(self, rids, rids.index(sel[0]))

    def _review_pending(self):
        if self.df is None:
            return
        rids = self.df.index[self.df["Status"] == pc.STATUS_PENDING].tolist()
        if not rids:
            messagebox.showinfo("Sin pendientes", "No hay registros pendientes de revisión.", parent=self)
            return
        ReviewDialog(self, rids, 0)

    def _review_view(self):
        rids = list(self.tree.get_children())
        if not rids:
            messagebox.showinfo("Vista vacía", "La vista actual no tiene registros.", parent=self)
            return
        ReviewDialog(self, rids, 0)

    def set_manual(self, rid, **values):
        """Guarda una decisión manual (llamado desde ReviewDialog) y actualiza todo."""
        for k, v in values.items():
            self.df.loc[rid, k] = v
        self.df = pc.compute_status(self.df)
        if self.tree.exists(rid):
            r = self.df.loc[rid]
            self.tree.item(rid, values=self._row_values(r), tags=(r["Status"],))
        self._mark_dirty()
        self._refresh_counts()

    def display_patterns(self):
        """Patrones de resaltado (tag, etiqueta, regex, color) según la configuración vigente."""
        cfg = self._last_cfg
        if cfg is None:
            try:
                cfg = self._get_config()
            except ValueError:
                cfg = {}
        cfg = pc.normalize_config(cfg)
        ap = cfg["auto_plural"]
        out = []
        p = pc.compile_terms(pc.parse_terms(cfg["kw_exclude"]), ap, display=True)
        if p:
            out.append(("hl_exc", "Exclusión", p, "#fecaca"))
        p = pc.compile_terms(pc.parse_terms(cfg["kw_required"]), ap, display=True)
        if p:
            out.append(("hl_req", "Obligatorio", p, "#fed7aa"))
        p = pc.compile_terms(pc.parse_terms(cfg["kw_secondary"]), ap, display=True)
        if p:
            out.append(("hl_sec", "Secundario", p, "#bbf7d0"))
        for i, (bid, b) in enumerate(cfg["search_blocks"].items()):
            p = pc.compile_terms(pc.parse_terms(b.get("terms", "")), ap, display=True)
            if p:
                out.append((f"hl_b{i}", bid, p, BLOCK_HL[i % len(BLOCK_HL)]))
        return out

    # ══════════════════════════════════════════════════════════════════════════
    # Estado general
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_all(self):
        sources = ["Todas"] + (sorted(self.df["source"].unique().tolist()) if self.df is not None else [])
        self.source_menu.configure(values=sources)
        if self.source_var.get() not in sources:
            self.source_var.set("Todas")
        self._refresh_counts()
        self._refresh_table()
        self._update_state()

    def _refresh_counts(self):
        if self.df is None:
            for v in self.sidebar_stats.values():
                v.set("—")
            self.global_progress.set(0)
            self.lbl_progress.configure(text="Sin datos")
            return
        c = pc.compute_counts(self.df)
        dedup_done = self.df["Is_Duplicate"].ne("").any()
        screened = self.df["Auto_Decision"].ne("").any()
        self.sidebar_stats["total"].set(str(c["identified_total"]))
        self.sidebar_stats["unique"].set(str(c["unique"]) if dedup_done else "—")
        self.sidebar_stats["pending"].set(str(c["pending"]) if screened else "—")
        self.sidebar_stats["included"].set(str(c["included"]) if screened else "—")
        vals = {"identified_total": c["identified_total"], "duplicates_total": c["duplicates_total"],
                "auto_exc": c["removed_automation"] + c["removed_other"], "pending": c["pending"],
                "manual_exc": c["excluded_screening"] + c["excluded_fulltext"] + c["not_retrieved"],
                "included": c["included"]}
        for k, lbl in self.res_cards.items():
            lbl.configure(text=str(vals[k]) if screened or k == "identified_total" else "—")
        stages = [True, dedup_done, screened, screened and c["pending"] == 0,
                  screened and c["included"] > 0 and c["ft_pending"] == 0]
        done = sum(stages)
        labels = ["Datos cargados", "Duplicados eliminados", "Cribado automático", "Cribado manual completo",
                  "Texto completo evaluado"]
        nxt = next((lab for lab, s in zip(labels, stages) if not s), None)
        self.global_progress.set(done / len(stages))
        self.lbl_progress.configure(text=f"{done}/{len(stages)} etapas" + (f"\nSiguiente: {nxt}" if nxt else "\n✓ Completo")
                                    + (f"\n{c['ft_pending']} incluidos sin evaluar a TC" if screened and c["ft_pending"] else ""))
        self._draw_source_bar(c["included_by_source"] if screened else {})

    def _update_state(self):
        has = self.df is not None and len(self.df) > 0
        screened = has and self.df["Auto_Decision"].ne("").any()
        busy = self._busy

        def st(ok):
            return "normal" if ok and not busy else "disabled"
        self.btn_combine.configure(state=st(bool(self.sources)))
        self.btn_dedup.configure(state=st(has))
        self.btn_save_flagged.configure(state=st(has))
        self.btn_run.configure(state=st(has), text="⏳  Procesando…" if busy else "⚡  Ejecutar cribado automático")
        self.btn_go_review.configure(state=st(screened))
        for b in self.result_buttons:
            b.configure(state=st(screened))
        self.lbl_sources_hint.configure(text=f"{len(self.sources)} archivo(s)" if self.sources else "Sin archivos")

    def _mark_dirty(self, value=True):
        self._dirty = value
        self.lbl_dirty.configure(text="● Cambios sin guardar" if value else "")

    def _log(self, widget, msg, color=None):
        tag = f"c_{color or TEXT}"
        widget.configure(state="normal")
        widget.insert("end", msg, tag)
        widget.tag_configure(tag, foreground=color or TEXT)
        widget.see("end")
        widget.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # Presets
    # ══════════════════════════════════════════════════════════════════════════
    def _show_welcome(self):
        WelcomeDialog(self, self.presets, self._apply_preset, self._open_session)

    def _open_presets(self):
        try:
            cfg = self._get_config()
        except ValueError as e:
            messagebox.showerror("Configuración inválida", f"Corrige la configuración antes de gestionar presets:\n\n{e}",
                                 parent=self)
            return
        PresetDialog(self, self.presets, cfg, self._apply_preset)

    def _apply_preset(self, name, cfg, mark_dirty=True):
        full = dict(BLANK_CONFIG)
        full.update(cfg or {})
        self.review_name.set(name)
        self.review_description = full.get("description", "") or ""

        def put(entry, v):
            entry.delete(0, "end")
            if v not in (None, ""):
                entry.insert(0, str(v))
        put(self.year_from, full.get("year_from"))
        put(self.year_to, full.get("year_to"))
        put(self.min_blocks_entry, full.get("min_blocks", 0))
        for field in ("kw_required", "kw_secondary", "kw_exclude", "doc_exclude", "doc_include", "languages"):
            _set_text(getattr(self, field), full.get(field, ""))
        self._search_blocks = {k: dict(v) for k, v in (full.get("search_blocks") or {}).items()} or \
            dict(BLANK_CONFIG["search_blocks"])
        self._refresh_blocks_summary()
        self.exclude_mode_var.set(pc.EXCLUDE_MODES.get(full.get("exclude_mode"), pc.EXCLUDE_MODES["balanced"]))
        self.missing_year_var.set(pc.MISSING_YEAR_MODES.get(full.get("missing_year"), pc.MISSING_YEAR_MODES["review"]))
        self.auto_plural_var.set(bool(full.get("auto_plural", True)))
        self.near_miss_var.set(bool(full.get("review_near_miss", False)))
        col_map = full.get("col_map") or {}
        for k, e in self._col_map.items():
            e.delete(0, "end")
            if col_map.get(k):
                e.insert(0, str(col_map[k]))
        if mark_dirty:
            self._mark_dirty()

    # ══════════════════════════════════════════════════════════════════════════
    # Proyecto (.prisma)
    # ══════════════════════════════════════════════════════════════════════════
    def _save_session(self, ask=False):
        if self.df is None:
            messagebox.showinfo("Sin datos", "Carga y combina archivos antes de guardar el proyecto.", parent=self)
            return False
        try:
            cfg = self._get_config()
        except ValueError as e:
            messagebox.showerror("Configuración inválida", str(e), parent=self)
            return False
        path = self._session_path
        if ask or not path:
            path = filedialog.asksaveasfilename(title="Guardar proyecto", defaultextension=".prisma",
                                                initialfile=safe_name(self.review_name.get()),
                                                filetypes=[("Proyecto SysReview", "*.prisma")], parent=self)
            if not path:
                return False
        try:
            pc.save_session(path, self.df, cfg, self.review_name.get(), self.sources_info, self.dedup_stats,
                            {"last_steps": self.last_steps, "last_cfg": self._last_cfg})
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e), parent=self)
            return False
        self._session_path = path
        self._mark_dirty(False)
        self.title(f"SysReview PRISMA  v{pc.APP_VERSION}  ·  {Path(path).name}")
        return True

    def _open_session(self, parent=None):
        parent = parent or self
        if self._dirty and self.df is not None:
            ans = messagebox.askyesnocancel("Cambios sin guardar", "¿Guardar el proyecto actual antes de abrir otro?",
                                            parent=parent)
            if ans is None or (ans and not self._save_session()):
                return False
        path = filedialog.askopenfilename(title="Abrir proyecto", filetypes=[("Proyecto SysReview", "*.prisma"),
                                                                             ("Todos", "*.*")], parent=parent)
        if not path:
            return False
        try:
            payload = pc.load_session(path)
        except Exception as e:
            messagebox.showerror("No se pudo abrir", f"{e}", parent=parent)
            return False
        self.df = payload["df"]
        self.sources_info = payload.get("sources", [])
        self.dedup_stats = payload.get("dedup_stats", {})
        extra = payload.get("extra", {}) or {}
        self.last_steps = extra.get("last_steps") or {}
        self._last_cfg = extra.get("last_cfg")
        self._apply_preset(payload.get("review_name", "Revisión"), payload.get("config", {}), mark_dirty=False)
        for s in list(self.sources):
            s["row"].destroy()
        self.sources.clear()
        for inf in self.sources_info:
            self._add_source_row(inf.get("path", inf.get("file", "")), inf.get("name", ""), None)
        for w in self.load_stats_frame.winfo_children():
            w.destroy()
        for i, inf in enumerate(self.sources_info):
            _stat_card(self.load_stats_frame, inf.get("name", "?"), str(inf.get("n", "?")),
                       SOURCE_COLORS[i % len(SOURCE_COLORS)])
        self._reset_screen_stats()
        st = self.dedup_stats
        if st:
            for k, lbl in self.dedup_cards.items():
                lbl.configure(text=str(st.get(k, 0) + (st.get("duplicates_other", 0) if k == "duplicates_fuzzy" else 0)))
        self._show_steps(self.last_steps)
        self._session_path = path
        self._mark_dirty(False)
        self.title(f"SysReview PRISMA  v{pc.APP_VERSION}  ·  {Path(path).name}")
        self._refresh_all()
        self._log(self.log_load, f"📂 Proyecto abierto: {path}  ({len(self.df)} registros, guardado "
                                 f"{payload.get('saved', '?')})\n", ACCENT2)
        self._show_tab(3 if self.df["Auto_Decision"].ne("").any() else 1)
        return True

    def _on_close(self):
        if self._dirty and self.df is not None:
            ans = messagebox.askyesnocancel("Cambios sin guardar", "¿Guardar el proyecto antes de salir?", parent=self)
            if ans is None:
                return
            if ans and not self._save_session():
                return
        self.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # Informe y exportaciones
    # ══════════════════════════════════════════════════════════════════════════
    def _export_cfg(self):
        if self._last_cfg is not None:
            return self._last_cfg
        try:
            return self._get_config()
        except ValueError:
            return {}

    def _provenance(self):
        return pc.build_provenance(self.sources_info, self.dedup_stats)

    def _show_prisma_report(self):
        if self.df is None:
            messagebox.showinfo("Sin datos", "Carga datos y ejecuta el pipeline antes de generar el informe.", parent=self)
            return
        PrismaReportDialog(self, pc.compute_counts(self.df), self.review_name.get(), self._export_cfg(),
                           self._provenance())

    def _ask_save(self, ext, kind, prefix):
        return filedialog.asksaveasfilename(defaultextension=ext, parent=self,
                                            initialfile=f"{prefix}_{safe_name(self.review_name.get())}",
                                            filetypes=[(kind, f"*{ext}")])

    def _run_export(self, fn, path):
        try:
            fn()
        except PermissionError:
            messagebox.showerror("No se pudo guardar", f"El archivo está abierto en otro programa o no hay "
                                 f"permisos:\n{path}", parent=self)
            return
        except Exception as e:
            messagebox.showerror("Error al exportar", f"{e}", parent=self)
            return
        messagebox.showinfo("Exportado", f"Guardado en:\n{path}\n\n(Se guardó también la configuración y "
                            "procedencia en un archivo _config.json junto al archivo cuando aplica.)", parent=self)

    def _export_workbook(self):
        path = self._ask_save(".xlsx", "Excel", "Cribado_PRISMA")
        if path:
            self._run_export(lambda: pc.export_workbook(path, self.df, pc.compute_counts(self.df), self._export_cfg(),
                                                        self._provenance()), path)

    def _export_flagged(self):
        if self.df is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", parent=self,
                                            initialfile=f"Todos_con_banderas_{safe_name(self.review_name.get())}",
                                            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if not path:
            return
        if path.lower().endswith(".csv"):
            self._run_export(lambda: pc.export_csv(path, self.df, self._export_cfg(), self._provenance()), path)
        else:
            self._run_export(lambda: pc.export_workbook(path, self.df, pc.compute_counts(self.df),
                                                        self._export_cfg(), self._provenance()), path)

    def _included(self):
        d = self.df[self.df["Status"] == pc.STATUS_INCLUDED]
        if d.empty:
            messagebox.showinfo("Sin incluidos", "Todavía no hay artículos incluidos.", parent=self)
            return None
        return d

    def _export_csv_included(self):
        d = self._included()
        if d is None:
            return
        path = self._ask_save(".csv", "CSV", "Articulos_Incluidos")
        if path:
            self._run_export(lambda: pc.export_csv(path, d, self._export_cfg(), self._provenance()), path)

    def _export_ris_included(self):
        d = self._included()
        if d is None:
            return
        path = self._ask_save(".ris", "RIS (Zotero, Mendeley, EndNote)", "Articulos_Incluidos")
        if path:
            self._run_export(lambda: pc.export_ris(path, d), path)

    def _export_reviewer_sheet(self):
        sheet = pc.reviewer_sheet(self.df)
        if sheet.empty:
            messagebox.showinfo("Sin registros", "No hay registros que hayan llegado al cribado.", parent=self)
            return
        path = self._ask_save(".xlsx", "Excel", "Hoja_revisor2")
        if not path:
            return

        def write():
            instr = pd.DataFrame({"Instrucciones": [
                "1. Lee título, keywords y abstract de cada registro (hoja 'Cribado').",
                "2. Escribe en 'Decision_R2': Incluir, Excluir o Dudoso.",
                "3. Opcional: razón en 'Reason_R2'.",
                "4. No modifiques la columna 'record_id'.",
                "5. Devuelve el archivo y usa 'Importar 2º revisor (κ)' en SysReview PRISMA.",
                "Las decisiones del revisor 1 NO se incluyen para mantener la evaluación ciega."]})
            with pd.ExcelWriter(path, engine="openpyxl") as xw:
                sheet.to_excel(xw, sheet_name="Cribado", index=False)
                instr.to_excel(xw, sheet_name="Instrucciones", index=False)
        self._run_export(write, path)

    def _import_reviewer_sheet(self):
        path = filedialog.askopenfilename(title="Importar hoja del 2º revisor", parent=self,
                                          filetypes=[("Excel / CSV", "*.xlsx *.csv"), ("Todos", "*.*")])
        if not path:
            return
        try:
            imp, invalid = pc.import_reviewer_sheet(path)
        except Exception as e:
            messagebox.showerror("Error al importar", str(e), parent=self)
            return
        known = imp["record_id"].isin(self.df.index)
        unknown = int((~known).sum())
        imp = imp[known]
        self.df.loc[imp["record_id"].tolist(), "TA_Decision_R2"] = imp["TA_Decision_R2"].tolist()
        self.df.loc[imp["record_id"].tolist(), "TA_Reason_R2"] = imp["TA_Reason_R2"].astype(str).tolist()
        self.df = pc.compute_status(self.df)
        self._mark_dirty()
        self._refresh_all()
        KappaDialog(self, pc.compare_reviewers(self.df), unknown, invalid)


def main():
    app = SysReviewApp()
    app.mainloop()


if __name__ == "__main__":
    main()
