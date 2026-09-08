"""
ui/app.py
=========
Interfaz de Usuario principal del Sistema de Gestión de Inventario.
Construida con CustomTkinter para un aspecto moderno y profesional.

Estructura:
  - InventarioApp   → Ventana raíz y orquestación
  - SearchBar       → Barra de búsqueda en tiempo real
  - FormPanel       → Panel izquierdo (formulario de alta / edición)
  - InventoryTable  → Panel derecho (tabla Treeview)
  - DetailModal     → Ventana modal de detalle con visor de imagen
"""

import sys
import shutil
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from PIL import Image, ImageTk

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Ruta al módulo de base de datos (un nivel arriba: /database/)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import inicializar_db, InventarioDAO  # noqa: E402
from utils.analisis import calcular_analisis_inversion             # noqa: E402

# ---------------------------------------------------------------------------
# Tema y paleta de colores
# ---------------------------------------------------------------------------
import json as _json

_THEME_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "theme.json"

# Paletas completas disponibles (sincronizadas con dashboard.py)
_PALETAS = {
    "Claro Azul": {
        "bg_root": "#f0f4ff", "bg_sidebar": "#e8edf8", "bg_card": "#ffffff",
        "bg_input": "#e2e8f7", "accent": "#2563eb", "accent_hover": "#1d4ed8",
        "danger": "#dc2626", "danger_hover": "#b91c1c",
        "success": "#16a34a", "text_primary": "#1e293b", "text_muted": "#64748b",
        "border": "#c7d2e8", "row_even": "#f0f4ff", "row_odd": "#e8edf8",
        "row_selected": "#bfdbfe",
    },
    "Claro Morado": {
        "bg_root": "#f5f0ff", "bg_sidebar": "#ede8ff", "bg_card": "#ffffff",
        "bg_input": "#e9e0ff", "accent": "#7c3aed", "accent_hover": "#6d28d9",
        "danger": "#dc2626", "danger_hover": "#b91c1c",
        "success": "#16a34a", "text_primary": "#1e1b4b", "text_muted": "#6d28d9",
        "border": "#d8b4fe", "row_even": "#f5f0ff", "row_odd": "#ede8ff",
        "row_selected": "#ddd6fe",
    },
    "Claro Celeste": {
        "bg_root": "#f0faff", "bg_sidebar": "#e0f4ff", "bg_card": "#ffffff",
        "bg_input": "#d0ebff", "accent": "#0284c7", "accent_hover": "#0369a1",
        "danger": "#dc2626", "danger_hover": "#b91c1c",
        "success": "#16a34a", "text_primary": "#0c1a2e", "text_muted": "#0369a1",
        "border": "#bae6fd", "row_even": "#f0faff", "row_odd": "#e0f4ff",
        "row_selected": "#bae6fd",
    },
    "Oscuro Azul": {
        "bg_root": "#0f1117", "bg_sidebar": "#16181f", "bg_card": "#1c1f2b",
        "bg_input": "#252836", "accent": "#4f8ef7", "accent_hover": "#3a6fd8",
        "danger": "#e05c5c", "danger_hover": "#c94a4a",
        "success": "#3ecf8e", "text_primary": "#e8eaf0", "text_muted": "#8b91a7",
        "border": "#2e3246", "row_even": "#1c1f2b", "row_odd": "#212438",
        "row_selected": "#2a3a6a",
    },
    "Oscuro Morado": {
        "bg_root": "#0e0a14", "bg_sidebar": "#130e1c", "bg_card": "#1a1525",
        "bg_input": "#221c30", "accent": "#9b59b6", "accent_hover": "#7d3c98",
        "danger": "#e05c5c", "danger_hover": "#c94a4a",
        "success": "#3ecf8e", "text_primary": "#e8e0f0", "text_muted": "#9b7cc0",
        "border": "#3a2a50", "row_even": "#1a1525", "row_odd": "#221c30",
        "row_selected": "#2d1a4a",
    },
    "Oscuro Verde": {
        "bg_root": "#0a1210", "bg_sidebar": "#0d1a15", "bg_card": "#111d18",
        "bg_input": "#172419", "accent": "#3ecf8e", "accent_hover": "#27ae60",
        "danger": "#e05c5c", "danger_hover": "#c94a4a",
        "success": "#4f8ef7", "text_primary": "#e0f0e8", "text_muted": "#7ab89a",
        "border": "#1e3828", "row_even": "#111d18", "row_odd": "#172419",
        "row_selected": "#1a3a28",
    },
    "Oscuro Dorado": {
        "bg_root": "#130f08", "bg_sidebar": "#1a1508", "bg_card": "#1e190f",
        "bg_input": "#28220e", "accent": "#f0a500", "accent_hover": "#c8880a",
        "danger": "#e05c5c", "danger_hover": "#c94a4a",
        "success": "#3ecf8e", "text_primary": "#f5ecd8", "text_muted": "#b89050",
        "border": "#3a2c0a", "row_even": "#1e190f", "row_odd": "#28220e",
        "row_selected": "#3a2c0a",
    },
    "Oscuro Rojo": {
        "bg_root": "#130a0a", "bg_sidebar": "#1a0e0e", "bg_card": "#1f1212",
        "bg_input": "#2a1818", "accent": "#e05c5c", "accent_hover": "#c04040",
        "danger": "#f0a500", "danger_hover": "#c88800",
        "success": "#3ecf8e", "text_primary": "#f0e0e0", "text_muted": "#c08080",
        "border": "#3a1010", "row_even": "#1f1212", "row_odd": "#2a1818",
        "row_selected": "#3a1010",
    },
}

_DEFAULT_TEMA = "Claro Azul"

def _leer_nombre_tema() -> str:
    try:
        with open(_THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            return _json.load(f).get("tema", _DEFAULT_TEMA)
    except Exception:
        return _DEFAULT_TEMA

def _construir_colors(nombre_tema: str) -> dict:
    paleta = _PALETAS.get(nombre_tema, _PALETAS[_DEFAULT_TEMA])
    return {
        "bg_root":      paleta["bg_root"],
        "bg_sidebar":   paleta.get("bg_sidebar", paleta["bg_root"]),
        "bg_card":      paleta["bg_card"],
        "bg_input":     paleta["bg_input"],
        "accent":       paleta["accent"],
        "accent_hover": paleta["accent_hover"],
        "danger":       paleta["danger"],
        "danger_hover": paleta.get("danger_hover", paleta["danger"]),
        "success":      paleta["success"],
        "text_primary": paleta["text_primary"],
        "text_muted":   paleta["text_muted"],
        "border":       paleta["border"],
        "row_even":     paleta["row_even"],
        "row_odd":      paleta["row_odd"],
        "row_selected": paleta["row_selected"],
    }

# Aplicar modo claro u oscuro según el tema seleccionado
_TEMA_ACTUAL = _leer_nombre_tema()
_ES_CLARO    = _TEMA_ACTUAL.startswith("Claro")
ctk.set_appearance_mode("Light" if _ES_CLARO else "Dark")
ctk.set_default_color_theme("blue")

COLORS = _construir_colors(_TEMA_ACTUAL)

FONT_FAMILY = "Segoe UI"


# ===========================================================================
# Componente: Barra de Búsqueda
# ===========================================================================

class SearchBar(ctk.CTkFrame):
    """Barra superior de búsqueda en tiempo real."""

    def __init__(self, parent, on_search_callback, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            **kwargs,
        )
        self._callback = on_search_callback
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # Icono de lupa (emoji como placeholder ligero)
        lupa = ctk.CTkLabel(
            self,
            text="🔍",
            font=(FONT_FAMILY, 16),
            text_color=COLORS["text_muted"],
        )
        lupa.grid(row=0, column=0, padx=(14, 6), pady=10)

        # Variable y Entry de búsqueda
        self._var = ctk.StringVar()
        self._var.trace_add("write", lambda *_: self._callback(self._var.get()))

        entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            placeholder_text="Buscar por nombre o código SKU…",
            font=(FONT_FAMILY, 13),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=38,
            corner_radius=8,
        )
        entry.grid(row=0, column=1, padx=(0, 14), pady=10, sticky="ew")

    def clear(self):
        self._var.set("")


# ===========================================================================
# Componente: Panel Izquierdo — Formulario
# ===========================================================================

class FormPanel(ctk.CTkFrame):
    """
    Panel izquierdo con el formulario de alta/edición de repuestos.
    Expone:
      - get_data()         → dict con los valores actuales del formulario
      - load_data(record)  → carga un dict en los campos (modo edición)
      - clear()            → limpia todos los campos
      - set_edit_mode(id)  → activa botones de edición con el ID cargado
    """

    # Campos del formulario en orden de aparición
    FIELDS = [
        ("nombre",         "Nombre *",                       "Ej: Resistencia calefactora"),
        ("modelo",         "Modelo",                         "(N/A)"),
        ("marca",          "Marca",                          "(N/A)"),
        ("precio_entrada", "Precio Entrada * (USD)",          "0.00"),
        ("precio_venta",   "Precio Venta *",                  "0.00"),
        ("cantidad",       "Cantidad *",                      "0"),
        ("stock_minimo",   "Avisar si stock baja de ↓",       "5"),
        ("sku",            "Código / SKU *",                  "Ej: TERM-TX200-GNC"),
        ("ubicacion",      "Ubicación",                       "Ej: Estante A-1"),
    ]

    # Valores por defecto al abrir formulario nuevo
    _DEFAULTS = {
        "modelo": "(N/A)",
        "marca":  "(N/A)",
    }

    # Campos que DEBEN estar llenos y válidos para habilitar el botón
    _REQUIRED_NUMERIC = {"precio_entrada", "precio_venta", "cantidad", "stock_minimo"}
    _REQUIRED_TEXT    = {"nombre", "sku"}

    def __init__(self, parent, dao: InventarioDAO, refresh_callback, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=0,
            **kwargs,
        )
        self._dao = dao
        self._refresh  = refresh_callback
        self._edit_id: int | None = None
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._vars:    dict[str, ctk.StringVar] = {}
        self._desc_box: ctk.CTkTextbox | None = None
        self._img_ruta = ""
        self._tasa = self._cargar_tasa_local()
        self._ignore_trace = False
        self._build()

    def _cargar_tasa_local(self):
        tasa_file = Path(__file__).resolve().parent.parent / "config" / "tasa.json"
        try:
            if tasa_file.exists():
                return float(json.loads(tasa_file.read_text(encoding="utf-8")).get("tasa", 1.0))
        except Exception:
            pass
        return 1.0

        self._apply_defaults()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # ── Encabezado ────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        header.grid(row=0, column=0, padx=14, pady=(14, 0), sticky="ew")

        ctk.CTkLabel(
            header,
            text="➕  Nuevo Repuesto",
            font=(FONT_FAMILY, 15, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(padx=14, pady=10, anchor="w")

        # ── Área de scroll con campos ──────────────────────────────────
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        scroll.grid(row=1, column=0, padx=14, pady=8, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, (key, label, placeholder) in enumerate(self.FIELDS):
            self._add_labeled_entry(scroll, i, key, label, placeholder)

        # Campo Descripción (multilinea)
        row_desc = len(self.FIELDS) * 2
        ctk.CTkLabel(
            scroll,
            text="Descripción",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=row_desc, column=0, padx=4, pady=(10, 2), sticky="w")

        self._desc_box = ctk.CTkTextbox(
            scroll,
            height=80,
            font=(FONT_FAMILY, 12),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text_primary"],
            corner_radius=8,
        )
        self._desc_box.grid(row=row_desc + 1, column=0, padx=4, pady=(0, 6), sticky="ew")

        # ── Imagen ──────────────────────────────────────────────
        img_f = ctk.CTkFrame(scroll, fg_color="transparent")
        img_f.grid(row=row_desc + 2, column=0, padx=4, pady=10, sticky="ew")
        self._lbl_img = ctk.CTkLabel(img_f, text="Sin imagen", text_color=COLORS["text_muted"])
        self._lbl_img.pack(side="left", padx=10)
        ctk.CTkButton(img_f, text="🖼️ Cargar Imagen", width=120, height=28,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["accent"],
                      command=self._cargar_imagen).pack(side="right", padx=10)

        # ── Botones de acción ──────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._btn_save = ctk.CTkButton(
            btn_frame,
            text="💾  Guardar",
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=COLORS["bg_input"],        # gris por defecto = deshabilitado visualmente
            hover_color=COLORS["bg_input"],
            text_color=COLORS["text_muted"],
            height=40,
            corner_radius=10,
            state="disabled",                   # <─ deshabilitado al inicio
            command=self._on_save,
        )
        self._btn_save.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self._btn_cancel = ctk.CTkButton(
            btn_frame,
            text="✖  Cancelar",
            font=(FONT_FAMILY, 13),
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            height=40,
            corner_radius=10,
            command=self.clear,
        )
        self._btn_cancel.grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _add_labeled_entry(self, parent, row, key, label, placeholder):
        ctk.CTkLabel(
            parent,
            text=label,
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=row * 2, column=0, padx=4, pady=(10, 2), sticky="w")

        var = ctk.StringVar()
        var.trace_add("write", lambda *_: self._validate())
        self._vars[key] = var

        entry = ctk.CTkEntry(
            parent, textvariable=var, placeholder_text=placeholder,
            font=(FONT_FAMILY, 12), fg_color=COLORS["bg_input"],
            border_color=COLORS["border"], text_color=COLORS["text_primary"],
            height=36, corner_radius=8
        )
        entry.grid(row=row * 2 + 1, column=0, padx=4, pady=(0, 2), sticky="ew")
        self._entries[key] = entry

    # ------------------------------------------------------------------
    # Validación en tiempo real
    # ------------------------------------------------------------------



    def _cargar_imagen(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Imagen del Producto",
            filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg")]
        )
        if ruta:
            self._img_ruta = ruta
            self._lbl_img.configure(text=Path(ruta).name)

    def _validate(self):
        """
        Revisa los campos obligatorios cada vez que el usuario escribe.
        Si todo es válido habilita el botón (azul); si no, lo deshabilita (gris).
        Sin ventanas emergentes de error.
        """
        vals = {k: v.get().strip() for k, v in self._vars.items()}

        # Campos de texto requeridos
        for key in self._REQUIRED_TEXT:
            if not vals.get(key, ""):
                self._set_btn_disabled()
                return

        # Campos numéricos requeridos
        for key in self._REQUIRED_NUMERIC:
            raw = vals.get(key, "")
            if not raw:
                self._set_btn_disabled()
                return
            try:
                val = float(raw)
                if key == "cantidad" and int(val) != val:
                    self._set_btn_disabled()
                    return
                if val < 0:
                    self._set_btn_disabled()
                    return
            except ValueError:
                self._set_btn_disabled()
                return

        # Todo OK → habilitar botón en azul celeste
        self._btn_save.configure(
            state="normal",
            fg_color="#38bdf8",        # azul celeste brillante
            hover_color="#0ea5e9",
            text_color="#0a1628",
        )

    def _set_btn_disabled(self):
        self._btn_save.configure(
            state="disabled",
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_input"],
            text_color=COLORS["text_muted"],
        )

    def _apply_defaults(self):
        """Establece los valores por defecto para Marca y Modelo."""
        for key, default_val in self._DEFAULTS.items():
            if key in self._entries:
                self._entries[key].delete(0, "end")
                self._entries[key].insert(0, default_val)

    # ------------------------------------------------------------------
    # Lógica de negocio del formulario
    # ------------------------------------------------------------------

    def _on_save(self):
        """Valida y guarda (CREATE o UPDATE)."""
        data = self.get_data()
        if data is None:
            return  # la validación ya mostró el error

        try:
            if self._edit_id is None:
                self._dao.crear(**data)
                messagebox.showinfo("Éxito", "✅ Repuesto agregado correctamente.")
            else:
                self._dao.actualizar(self._edit_id, **data)
                messagebox.showinfo("Éxito", "✅ Repuesto actualizado correctamente.")
        except ValueError as e:
            messagebox.showerror("Error de validación", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))
            return

        self.clear()
        self._refresh()

    def get_data(self) -> dict | None:
        """
        Lee y valida los campos del formulario.
        Devuelve un dict listo para pasar al DAO, o None si hay error.
        Sin ventanas emergentes — la validación visual ya lo gestionó.
        """
        values = {key: entry.get().strip() for key, entry in self._entries.items()}
        values["descripcion"] = self._desc_box.get("1.0", "end").strip()
        
        # Copiar imagen si existe y es nueva (ruta absoluta)
        if hasattr(self, "_img_ruta") and self._img_ruta and Path(self._img_ruta).is_absolute():
            import uuid
            img_dir = Path(__file__).resolve().parent.parent / "inventario_img"
            img_dir.mkdir(exist_ok=True)
            ext = Path(self._img_ruta).suffix
            new_name = f"img_{uuid.uuid4().hex[:8]}{ext}"
            dest = img_dir / new_name
            try:
                shutil.copy2(self._img_ruta, dest)
                values["imagen_ruta"] = f"inventario_img/{new_name}"
            except Exception as e:
                print(f"Error copiando imagen: {e}")
                values["imagen_ruta"] = self._img_ruta # fallback
        elif hasattr(self, "_img_ruta") and self._img_ruta:
            values["imagen_ruta"] = self._img_ruta # ya era relativa

        # Asegurarse de que campos requeridos estén llenos
        for campo in list(self._REQUIRED_TEXT) + list(self._REQUIRED_NUMERIC):
            if not values.get(campo, ""):
                return None

        # Parsear numéricos (ya validados, pero segúros)
        try:
            values["precio_entrada"] = float(values["precio_entrada"])
            values["precio_venta"]   = float(values["precio_venta"])
            values["cantidad"]       = int(float(values["cantidad"]))
            values["stock_minimo"]   = max(0, int(float(values.get("stock_minimo", 5))))
        except ValueError:
            return None

        if values["precio_entrada"] < 0 or values["precio_venta"] < 0 or values["cantidad"] < 0:
            return None

        return values

    def load_data(self, record: dict):
        """Rellena el formulario con los datos de un registro para editar."""
        mapping = {
            "nombre":         record.get("nombre", ""),
            "modelo":         record.get("modelo", "") or "(N/A)",
            "marca":          record.get("marca",  "") or "(N/A)",
            "precio_entrada": str(record.get("precio_entrada", "")),
            "precio_venta":   str(record.get("precio_venta", "")),
            "cantidad":       str(record.get("cantidad", "")),
            "stock_minimo":   str(record.get("stock_minimo", 5)),
            "sku":            record.get("sku", ""),
            "ubicacion":      record.get("ubicacion", "") or "",
        }
        self._img_ruta = record.get("imagen_ruta", "")
        if self._img_ruta:
            self._lbl_img.configure(text=Path(self._img_ruta).name)
        else:
            self._lbl_img.configure(text="Sin imagen")
        for key, val in mapping.items():
            entry = self._entries[key]
            entry.delete(0, "end")
            entry.insert(0, val)

        self._desc_box.delete("1.0", "end")
        self._desc_box.insert("1.0", record.get("descripcion", "") or "")
        self._validate()  # recalcular estado del botón

    def load_similar(self, record: dict):
        """
        Carga Nombre, Marca y Modelo de un producto existente para crear
        uno similar. Limpia los demás campos numéricos.
        """
        self.clear()   # resetea todo a defaults
        for key in ("nombre", "marca", "modelo"):
            val = record.get(key, "") or self._DEFAULTS.get(key, "")
            self._entries[key].delete(0, "end")
            self._entries[key].insert(0, val)
        self._validate()

    def set_edit_mode(self, record_id: int):
        self._edit_id = record_id
        self._btn_save.configure(text="✏️  Actualizar")

    def clear(self):
        """Limpia todos los campos y vuelve al modo creación con valores por defecto."""
        for entry in self._entries.values():
            entry.delete(0, "end")
        self._desc_box.delete("1.0", "end")
        self._edit_id = None
        self._img_ruta = ""
        if hasattr(self, "_lbl_img"):
            self._lbl_img.configure(text="Sin imagen")
        self._tasa = self._cargar_tasa_local() # refrescar por si acaso

        self._btn_save.configure(text="💾  Guardar")
        self._apply_defaults()   # restaurar (N/A) en marca y modelo
        self._set_btn_disabled()  # volver a estado gris


# ===========================================================================
# Componente: Panel Derecho — Tabla de Inventario
# ===========================================================================

class InventoryTable(ctk.CTkFrame):
    """
    Panel derecho con la tabla (Treeview) del inventario.
    Expone:
      - refresh(rows)              → recarga la tabla con la lista dada
      - get_selected_id()          → devuelve el ID de la fila seleccionada
      - bind_select(callback)      → callback al seleccionar una fila
    """

    COLUMNS = [
        ("id",             "ID",             50,  "center"),
        ("sku",            "SKU / Código",   140, "w"),
        ("nombre",         "Nombre",         200, "w"),
        ("marca",          "Marca",          110, "w"),
        ("modelo",         "Modelo",         110, "w"),
        ("precio_entrada", "P. Entrada",     90,  "e"),
        ("precio_venta",   "P. Venta",       90,  "e"),
        ("cantidad",       "Stock",          70,  "center"),
        ("ubicacion",      "Ubicación",      110, "w"),
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=12,
            **kwargs,
        )
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # ── Encabezado de la tabla ─────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")

        ctk.CTkLabel(
            header,
            text="📦  Inventario de Repuestos",
            font=(FONT_FAMILY, 15, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        self._count_label = ctk.CTkLabel(
            header,
            text="0 repuestos",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text_muted"],
        )
        self._count_label.pack(side="right")

        # ── Treeview con scroll ────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=COLORS["bg_card"])
        tree_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Estilo personalizado del Treeview (via ttk.Style)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Inventory.Treeview",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card"],
            rowheight=34,
            font=(FONT_FAMILY, 12),
            borderwidth=0,
        )
        style.configure(
            "Inventory.Treeview.Heading",
            background=COLORS["bg_input"],
            foreground=COLORS["text_muted"],
            font=(FONT_FAMILY, 11, "bold"),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Inventory.Treeview",
            background=[("selected", COLORS["row_selected"])],
            foreground=[("selected", COLORS["text_primary"])],
        )
        style.map(
            "Inventory.Treeview.Heading",
            background=[("active", COLORS["border"])],
        )

        col_ids = [c[0] for c in self.COLUMNS]
        self._tree = ttk.Treeview(
            tree_frame,
            columns=col_ids,
            show="headings",
            style="Inventory.Treeview",
            selectmode="browse",
        )

        # Configurar columnas
        for col_id, heading, width, anchor in self.COLUMNS:
            self._tree.heading(col_id, text=heading, anchor=anchor)
            self._tree.column(col_id, width=width, anchor=anchor, minwidth=40, stretch=(col_id == "nombre"))

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical",   command=self._tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # Tags para filas alternas
        self._tree.tag_configure("even", background=COLORS["row_even"])
        self._tree.tag_configure("odd",  background="#212438")
        self._tree.tag_configure("out_of_stock", foreground="#e05c5c")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def refresh(self, rows: list[dict]):
        """Limpia e inserta las filas dadas en la tabla."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        for i, row in enumerate(rows):
            if row.get("cantidad", 0) <= 0:
                tag = "out_of_stock"
            else:
                tag = "even" if i % 2 == 0 else "odd"
                
            values = (
                row["id"],
                row.get("sku", ""),
                row.get("nombre", ""),
                row.get("marca", ""),
                row.get("modelo", ""),
                f"${row.get('precio_entrada', 0):.2f}",
                f"${row.get('precio_venta', 0):.2f}",
                row.get("cantidad", 0),
                row.get("ubicacion", "") or "—",
            )
            self._tree.insert("", "end", iid=str(row["id"]), values=values, tags=(tag,))


        self._count_label.configure(text=f"{len(rows)} repuesto(s)")

    def get_selected_id(self) -> int | None:
        sel = self._tree.selection()
        return int(sel[0]) if sel else None

    def bind_select(self, callback):
        self._tree.bind("<<TreeviewSelect>>", callback)

    def bind_double_click(self, callback):
        self._tree.bind("<Double-1>", callback)


# ===========================================================================
# Ventana Modal: DetailModal
# ===========================================================================

IMG_DIR = Path(__file__).resolve().parent.parent / "imagenes_repuestos"
IMG_DIR.mkdir(exist_ok=True)

_PLACEHOLDER_SIZE = (260, 260)  # tamaño del placeholder cuando no hay imagen
_DISPLAY_SIZE     = (260, 260)  # tamaño máximo de imagen mostrada


class DetailModal(ctk.CTkToplevel):
    """
    Ventana modal que muestra todos los detalles de un repuesto
    y permite cargar / cambiar su imagen.

    Args:
        parent:       Ventana padre.
        record:       dict con todos los campos del repuesto.
        dao:          Instancia de InventarioDAO para persistir la imagen.
        on_updated:   Callback opcional para refrescar la tabla tras cambiar imagen.
    """

    def __init__(
        self,
        parent,
        record: dict,
        dao: "InventarioDAO",
        on_updated=None,
        rol: str = "Admin",
    ):
        super().__init__(parent)
        self._record     = record
        self._dao        = dao
        self._on_updated = on_updated
        self._es_admin   = (rol == "Admin")
        self._photo: ImageTk.PhotoImage | None = None  # referencia para evitar GC

        self._setup_window()
        self._build()
        self._load_image(record.get("imagen_ruta"))

    # ------------------------------------------------------------------
    # Configuración de la ventana
    # ------------------------------------------------------------------

    def _setup_window(self):
        nombre = self._record.get("nombre", "Detalle")
        self.title(f"📋 {nombre}")
        self.geometry("720x500")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_root"])
        self.grab_set()           # bloquea la ventana padre
        self.focus_force()

        # Centrar relativo al padre
        self.update_idletasks()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        x = px + (pw - 720) // 2
        y = py + (ph - 500) // 2
        self.geometry(f"720x500+{x}+{y}")

    # ------------------------------------------------------------------
    # Construcción del layout
    # ------------------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(0, weight=0)  # columna imagen
        self.grid_columnconfigure(1, weight=1)  # columna detalles
        self.grid_rowconfigure(0, weight=1)

        self._build_image_panel()
        self._build_detail_panel()

    # ── Panel izquierdo: imagen ────────────────────────────────────────
    def _build_image_panel(self):
        img_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            width=300,
        )
        img_frame.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ns")
        img_frame.grid_propagate(False)
        img_frame.grid_rowconfigure(1, weight=1)
        img_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            img_frame,
            text="🖼️  Foto del Producto",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="w")

        # Canvas donde se renderiza la imagen
        self._img_canvas = tk.Canvas(
            img_frame,
            width=_DISPLAY_SIZE[0],
            height=_DISPLAY_SIZE[1],
            bg=COLORS["bg_input"],
            highlightthickness=0,
        )
        self._img_canvas.grid(row=1, column=0, padx=14, pady=(0, 10))
        self._draw_placeholder()

        # Botón cargar imagen — solo para Admin
        if self._es_admin:
            ctk.CTkButton(
                img_frame,
                text="📁  Cargar / Cambiar Imagen",
                font=(FONT_FAMILY, 12, "bold"),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                height=38,
                corner_radius=10,
                command=self._on_load_image,
            ).grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        else:
            ctk.CTkLabel(
                img_frame,
                text="🔒  Solo lectura",
                font=(FONT_FAMILY, 11),
                text_color=COLORS["text_muted"],
            ).grid(row=2, column=0, padx=14, pady=(0, 14))

    # ── Panel derecho: detalles ────────────────────────────────────────
    def _build_detail_panel(self):
        detail_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_card"],
            corner_radius=14,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        detail_frame.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")
        detail_frame.grid_columnconfigure(0, weight=1)

        r = self._record
        fields = [
            ("SKU / Código",    r.get("sku",            "—")),
            ("Nombre",          r.get("nombre",         "—")),
            ("Marca",           r.get("marca",          "—")),
            ("Modelo",          r.get("modelo",         "—")),
            ("Precio Entrada",  f"${r.get('precio_entrada', 0):.2f}"),
            ("Precio Venta",    f"${r.get('precio_venta',   0):.2f}"),
            ("Stock",           str(r.get("cantidad",   0))),
            ("Ubicación",       r.get("ubicacion",      "—") or "—"),
            ("Creado en",       r.get("creado_en",      "—")),
            ("Actualizado en",  r.get("actualizado_en", "—")),
        ]

        ctk.CTkLabel(
            detail_frame,
            text="📋  Información del Repuesto",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(14, 10), sticky="w")

        for i, (label, value) in enumerate(fields, start=1):
            row_f = ctk.CTkFrame(detail_frame, fg_color=COLORS["bg_input"], corner_radius=8)
            row_f.grid(row=i, column=0, padx=10, pady=3, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_f,
                text=label,
                font=(FONT_FAMILY, 11),
                text_color=COLORS["text_muted"],
                width=120,
                anchor="w",
            ).grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")

            ctk.CTkLabel(
                row_f,
                text=str(value),
                font=(FONT_FAMILY, 12, "bold"),
                text_color=COLORS["text_primary"],
                anchor="w",
                wraplength=200,
            ).grid(row=0, column=1, padx=(0, 10), pady=8, sticky="w")

        # Descripción
        desc = r.get("descripcion", "") or "Sin descripción."
        desc_row = len(fields) + 1

        ctk.CTkLabel(
            detail_frame,
            text="Descripción",
            font=(FONT_FAMILY, 11),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=desc_row, column=0, padx=12, pady=(12, 2), sticky="w")

        ctk.CTkLabel(
            detail_frame,
            text=desc,
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text_primary"],
            anchor="nw",
            wraplength=280,
            justify="left",
        ).grid(row=desc_row + 1, column=0, padx=12, pady=(0, 14), sticky="w")

        # ── Sección: Análisis de Inversión ────────────────────────────
        self._build_analysis_section(detail_frame, desc_row + 2)

    # ── Análisis de Inversión ──────────────────────────────────────────
    def _build_analysis_section(self, parent, start_row: int):
        """
        Renderiza las tres métricas de rentabilidad dentro del panel
        de detalles usando `calcular_analisis_inversion`.
        """
        r = self._record
        analisis = calcular_analisis_inversion(
            precio_entrada=r.get("precio_entrada", 0),
            precio_venta=r.get("precio_venta", 0),
        )

        # ── Encabezado de sección ──────────────────────────────────────
        ctk.CTkLabel(
            parent,
            text="📊  Análisis de Inversión",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=start_row, column=0, padx=12, pady=(14, 6), sticky="w")

        # Separador visual
        sep = ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1)
        sep.grid(row=start_row + 1, column=0, padx=10, pady=(0, 10), sticky="ew")

        if not analisis.valido:
            ctk.CTkLabel(
                parent,
                text=f"⚠️  {analisis.error}",
                font=(FONT_FAMILY, 11),
                text_color="#e0954a",
            ).grid(row=start_row + 2, column=0, padx=12, pady=(0, 14), sticky="w")
            return

        # ── Tarjeta 1: Margen de Ganancia Bruta ───────────────────────
        self._metric_card(
            parent,
            row=start_row + 2,
            icono="📈",
            titulo="Margen de Ganancia Bruta",
            valor=f"{analisis.margen_bruto_pct:.1f} %",
            subtitulo="(precio_venta − costo) / precio_venta × 100",
            color_valor=analisis.indicador_color,
        )

        # ── Tarjeta 2: Ganancia Neta por unidad ───────────────────────
        self._metric_card(
            parent,
            row=start_row + 3,
            icono="💵",
            titulo="Ganancia Neta por Unidad",
            valor=f"${analisis.ganancia_neta_und:.2f}",
            subtitulo="precio_venta − precio_entrada",
            color_valor=COLORS["success"],
        )

        # ── Tarjeta 3: Indicador de rentabilidad ──────────────────────
        badge_frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_input"],
            corner_radius=10,
            border_width=2,
            border_color=analisis.indicador_color,
        )
        badge_frame.grid(
            row=start_row + 4, column=0,
            padx=10, pady=(4, 16), sticky="ew",
        )
        badge_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            badge_frame,
            text=analisis.indicador_emoji,
            font=("Segoe UI Emoji", 20),
        ).grid(row=0, column=0, padx=(14, 8), pady=12)

        ctk.CTkLabel(
            badge_frame,
            text=analisis.indicador_texto,
            font=(FONT_FAMILY, 13, "bold"),
            text_color=analisis.indicador_color,
            anchor="w",
        ).grid(row=0, column=1, pady=12, sticky="w")

    @staticmethod
    def _metric_card(
        parent,
        row: int,
        icono: str,
        titulo: str,
        valor: str,
        subtitulo: str,
        color_valor: str,
    ):
        """Renderiza una tarjeta de métrica con icono, título, valor y subtítulo."""
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_input"], corner_radius=10)
        card.grid(row=row, column=0, padx=10, pady=4, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # Icono
        ctk.CTkLabel(
            card,
            text=icono,
            font=("Segoe UI Emoji", 18),
        ).grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=10)

        # Título
        ctk.CTkLabel(
            card,
            text=titulo,
            font=(FONT_FAMILY, 10),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 14), pady=(10, 0), sticky="w")

        # Valor principal
        ctk.CTkLabel(
            card,
            text=valor,
            font=(FONT_FAMILY, 18, "bold"),
            text_color=color_valor,
            anchor="w",
        ).grid(row=1, column=1, padx=(0, 14), pady=(0, 2), sticky="w")

        # Subtítulo/fórmula
        ctk.CTkLabel(
            card,
            text=subtitulo,
            font=(FONT_FAMILY, 9),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).grid(row=2, column=1, padx=(0, 14), pady=(0, 8), sticky="w")

    # ------------------------------------------------------------------
    # Manejo de imágenes
    # ------------------------------------------------------------------

    def _draw_placeholder(self):
        """Dibuja un ícono de placeholder cuando no hay imagen."""
        self._img_canvas.delete("all")
        cx, cy = _DISPLAY_SIZE[0] // 2, _DISPLAY_SIZE[1] // 2
        self._img_canvas.create_rectangle(
            10, 10, _DISPLAY_SIZE[0] - 10, _DISPLAY_SIZE[1] - 10,
            outline=COLORS["border"], dash=(6, 4), width=2,
        )
        self._img_canvas.create_text(
            cx, cy - 20, text="🖼️", font=("Segoe UI Emoji", 40), fill=COLORS["text_muted"]
        )
        self._img_canvas.create_text(
            cx, cy + 30, text="Sin imagen", font=(FONT_FAMILY, 12), fill=COLORS["text_muted"]
        )

    def _load_image(self, ruta: str | None):
        """Carga y muestra la imagen almacenada en `ruta`."""
        if not ruta:
            self._draw_placeholder()
            return
        ruta_path = Path(ruta)
        # Ruta absoluta o relativa a la raíz del proyecto
        if not ruta_path.is_absolute():
            ruta_path = Path(__file__).resolve().parent.parent / ruta_path
        if not ruta_path.exists():
            self._draw_placeholder()
            return
        try:
            img = Image.open(ruta_path).convert("RGBA")
            img.thumbnail(_DISPLAY_SIZE, Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self._img_canvas.delete("all")
            cx = _DISPLAY_SIZE[0] // 2
            cy = _DISPLAY_SIZE[1] // 2
            self._img_canvas.create_image(cx, cy, image=self._photo, anchor="center")
        except Exception as exc:
            self._draw_placeholder()
            messagebox.showwarning("Imagen no válida", f"No se pudo cargar la imagen:\n{exc}")

    def _on_load_image(self):
        """
        Abre el explorador de archivos, copia la imagen a /imagenes_repuestos
        y actualiza el campo imagen_ruta en la base de datos.
        """
        ruta_src = filedialog.askopenfilename(
            title="Seleccionar imagen del producto",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp"), ("Todos", "*.*")],
            parent=self,
        )
        if not ruta_src:
            return  # usuario canceló

        src = Path(ruta_src)
        sku_safe = str(self._record.get("sku", f"id_{self._record['id']}")).replace("/", "-")
        dest = IMG_DIR / f"{sku_safe}{src.suffix.lower()}"

        try:
            shutil.copy2(src, dest)
        except OSError as e:
            messagebox.showerror("Error al copiar", f"No se pudo copiar la imagen:\n{e}")
            return

        # Guardar ruta relativa a la raíz del proyecto en la BD
        ruta_relativa = str(dest.relative_to(Path(__file__).resolve().parent.parent))
        try:
            self._dao.actualizar(self._record["id"], imagen_ruta=ruta_relativa)
            self._record["imagen_ruta"] = ruta_relativa
        except Exception as e:
            messagebox.showerror("Error al guardar", f"No se pudo actualizar la base de datos:\n{e}")
            return

        self._load_image(ruta_relativa)
        messagebox.showinfo("Imagen guardada", "✅ Imagen cargada y guardada correctamente.")

        if self._on_updated:
            self._on_updated()


# ===========================================================================
# Ventana Principal: InventarioApp
# ===========================================================================

class InventarioApp(ctk.CTk):
    """
    Ventana raíz de la aplicación.

    Args:
        usuario_info (dict): {id, usuario, rol} devuelto por UsuariosDAO.
                             El rol determina qué controles se muestran:
                             - 'Admin'    → acceso completo.
                             - 'Empleado' → solo lectura (sin formulario ni botones de cambio).

    Layout (Admin):
      ┌──────────────────────────────────────────────────────┐
      │  Barra de búsqueda (top)                             │
      ├──────────────┬───────────────────────────────────────┐
      │  FormPanel   │  InventoryTable                       │
      └──────────────┴───────────────────────────────────────┘

    Layout (Empleado):
      ┌──────────────────────────────────────────────────────┐
      │  Barra de búsqueda (top)                             │
      ├──────────────────────────────────────────────────────┤
      │  InventoryTable (ancho completo)                      │
      └──────────────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()
        self._dao = InventarioDAO()
        self._all_rows: list[dict] = []      # caché de todos los registros

        # Ocultamos la ventana principal mientras ocurre el login
        self.withdraw()

        from ui.login import LoginWindow
        self.login = LoginWindow(self)
        self.login.protocol("WM_DELETE_WINDOW", self._on_login_closed)

    def _on_login_success(self, usuario_info: dict):
        """Callback llamado desde LoginWindow cuando las credenciales son correctas."""
        self.login.destroy()
        
        # Datos del usuario autenticado
        self._usuario_nombre: str = usuario_info.get("usuario", "")
        self._rol:            str = usuario_info.get("rol", "Empleado")
        self._es_admin:       bool = self._rol == "Admin"
        self._form = None                    # solo existe si es Admin

        self._configure_window()
        self._build_layout()
        self._load_inventory()
        self.deiconify()                     # Mostramos la ventana principal

    def _on_login_closed(self):
        """Si el usuario cierra la ventana de login con la 'X'."""
        self.destroy()

    # ------------------------------------------------------------------
    # Configuración de la ventana
    # ------------------------------------------------------------------

    def _configure_window(self):
        self.title("⚡ Sistema de Inventario — Repuestos Electrodomésticos")
        self.geometry("1280x760")
        self.minsize(960, 600)
        self.configure(fg_color=COLORS["bg_root"])

        # Centrar en pantalla
        self.update_idletasks()
        w, h = 1280, 760
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Construcción del layout principal
    # ------------------------------------------------------------------

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=0)  # título / top bar
        self.grid_rowconfigure(1, weight=0)  # search bar
        self.grid_rowconfigure(2, weight=1)  # contenido principal
        self.grid_columnconfigure(1, weight=1)  # tabla siempre expande

        if self._es_admin:
            self.grid_columnconfigure(0, weight=0)  # sidebar (Admin)
        else:
            self.grid_columnconfigure(0, weight=0, minsize=0)  # sin sidebar

        # ── Top bar ────────────────────────────────────────────────
        self._build_top_bar()

        # ── Search bar ────────────────────────────────────────────────
        self._search_bar = SearchBar(
            self,
            on_search_callback=self._on_search,
        )
        self._search_bar.grid(
            row=1, column=0, columnspan=2,
            padx=16, pady=(0, 12), sticky="ew",
        )

        # ── Form panel (izquierda) ─────────────────────────────────────
        self._form = FormPanel(
            self,
            dao=self._dao,
            refresh_callback=self._load_inventory,
        )
        self._form.grid(
            row=2, column=0,
            padx=(16, 8), pady=(0, 16), sticky="nsew",
        )
        self._form.configure(width=280)

        # ── Inventory table (derecha) ──────────────────────────────────
        self._table = InventoryTable(self)
        self._table.grid(
            row=2, column=1,
            padx=(0, 16), pady=(0, 16), sticky="nsew",
        )
        self._table.bind_select(self._on_row_selected)
        self._table.bind_double_click(self._on_row_double_clicked)

        # ── Botones de acción sobre la tabla ──────────────────────────
        self._build_action_buttons()


    def _build_top_bar(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        # Logo / título
        ctk.CTkLabel(
            top,
            text="⚡ RepuestosDB",
            font=(FONT_FAMILY, 22, "bold"),
            text_color=COLORS["accent"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top,
            text="Sistema de Gestión de Inventario — Offline First",
            font=(FONT_FAMILY, 12),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=1, padx=16, sticky="w")

        # Badge de usuario y rol (columna derecha)
        rol_color = "#4f8ef7" if self._rol == "Admin" else "#3ecf8e"
        badge = ctk.CTkFrame(top, fg_color=COLORS["bg_input"],
                             corner_radius=8,
                             border_width=2, border_color=rol_color)
        badge.grid(row=0, column=2, padx=(0, 10), sticky="e")

        ctk.CTkLabel(
            badge,
            text=f"  {self._usuario_nombre}  [{self._rol}]  ",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=rol_color,
        ).pack(padx=8, pady=6)

        # Botón Punto de Venta — visible para todos los roles
        ctk.CTkButton(
            top,
            text="🛒  Punto de Venta",
            width=150,
            height=34,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color="#2a3a6a",
            hover_color=COLORS["accent"],
            text_color=COLORS["accent"],
            corner_radius=10,
            command=self._open_pos,
        ).grid(row=0, column=3, padx=(0, 4), sticky="e")

        # Botón Historial de Ventas
        ctk.CTkButton(
            top,
            text="📋  Historial",
            width=130,
            height=34,
            font=(FONT_FAMILY, 13, "bold"),
            fg_color="#1e2e1e",
            hover_color=COLORS["success"],
            text_color=COLORS["success"],
            corner_radius=10,
            command=self._open_historial,
        ).grid(row=0, column=4, padx=(0, 4), sticky="e")

    def _build_action_buttons(self):
        """Botones de acción sobre la tabla. Editar/Eliminar solo para Admin."""
        btn_bar = ctk.CTkFrame(self._table, fg_color="transparent")
        btn_bar.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="e")

        # Ver Detalle — disponible para todos los roles
        ctk.CTkButton(
            btn_bar,
            text="🔍 Ver Detalle",
            width=120,
            height=32,
            font=(FONT_FAMILY, 12),
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            text_color=COLORS["success"],
            corner_radius=8,
            command=self._on_row_double_clicked,
        ).pack(side="left", padx=(0, 8))

        if self._es_admin:
            # Editar — solo Admin
            ctk.CTkButton(
                btn_bar,
                text="✏️ Editar",
                width=100,
                height=32,
                font=(FONT_FAMILY, 12),
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["border"],
                text_color=COLORS["accent"],
                corner_radius=8,
                command=self._on_edit,
            ).pack(side="left", padx=(0, 8))

            # Eliminar — solo Admin
            ctk.CTkButton(
                btn_bar,
                text="🗑️ Eliminar",
                width=110,
                height=32,
                font=(FONT_FAMILY, 12),
                fg_color=COLORS["danger"],
                hover_color=COLORS["danger_hover"],
                text_color="#fff",
                corner_radius=8,
                command=self._on_delete,
            ).pack(side="left")

    # ------------------------------------------------------------------
    # Lógica de eventos
    # ------------------------------------------------------------------

    def _load_inventory(self):
        """Recarga todos los registros desde la BD y refresca la tabla."""
        try:
            self._all_rows = self._dao.listar_todos()
            self._table.refresh(self._all_rows)
            # Reaplicar filtro si hay texto en la barra
        except Exception as e:
            messagebox.showerror("Error de base de datos", str(e))

    def _on_search(self, termino: str):
        """Filtra la tabla en tiempo real con el texto de búsqueda."""
        termino = termino.strip().lower()
        if not termino:
            self._table.refresh(self._all_rows)
            return

        filtrados = [
            r for r in self._all_rows
            if termino in r["nombre"].lower()
            or termino in (r["sku"] or "").lower()
        ]
        self._table.refresh(filtrados)

    def _on_row_selected(self, _event=None):
        """Resalta visualmente la selección (el form se llena sólo con Editar)."""
        pass  # selección simple — el doble clic abre el modal de detalle

    def _open_pos(self):
        """Abre la ventana del Punto de Venta."""
        from ui.punto_de_venta import PuntoDeVentaWindow  # import diferido
        PuntoDeVentaWindow(parent=self)

    def _open_historial(self):
        """Abre la ventana del Historial de Ventas."""
        from ui.historial_ventas import HistorialVentasWindow  # import diferido
        HistorialVentasWindow(parent=self)

    def _on_row_double_clicked(self, _event=None):
        """Abre el DetailModal al hacer doble clic en una fila."""
        record_id = self._table.get_selected_id()
        if record_id is None:
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            return
        DetailModal(
            parent=self,
            record=record,
            dao=self._dao,
            on_updated=self._load_inventory,
            rol=self._rol,
        )

    def _on_edit(self):
        """Carga el registro seleccionado en el formulario para edición."""
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showwarning("Sin selección", "Selecciona un repuesto de la tabla primero.")
            return

        record = self._dao.obtener_por_id(record_id)
        if record is None:
            messagebox.showerror("Error", "No se encontró el registro seleccionado.")
            return

        self._form.load_data(record)
        self._form.set_edit_mode(record_id)

    def _on_delete(self):
        """Elimina el registro seleccionado previa confirmación. Solo Admin."""
        if not self._es_admin:
            return
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showwarning("Sin selección", "Selecciona un repuesto de la tabla primero.")
            return

        confirm = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Está seguro de eliminar el repuesto ID {record_id}?\n"
            "Esta acción no se puede deshacer.",
            icon="warning",
        )
        if not confirm:
            return

        try:
            self._dao.eliminar(record_id)
            if self._form:
                self._form.clear()
            self._load_inventory()
            messagebox.showinfo("Eliminado", "✅ Repuesto eliminado correctamente.")
        except Exception as e:
            messagebox.showerror("Error al eliminar", str(e))


# ===========================================================================
# Punto de entrada
# ===========================================================================

if __name__ == "__main__":
    inicializar_db()
    app = InventarioApp()
    app.mainloop()
