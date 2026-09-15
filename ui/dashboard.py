"""
ui/dashboard.py
===============
Ventana principal del Sistema de Gestión de Inventario.

Arquitectura:
  - DashboardApp   → Ventana raíz con sidebar y sistema de páginas
  - InventarioPage → Frame embebido con todo el CRUD de inventario
  - ReportesPage   → Frame con estadísticas del día e historial
  - PlaceholderPage→ Frame genérico "en construcción"

Navegación:
  - Inventario, Proveedores, Deudores, Reportes, Notificaciones → frames embebidos
  - Punto de Venta → abre ventana nueva (PuntoDeVentaWindow)
"""

import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import inicializar_db, InventarioDAO, VentasDAO, DeudoresDAO, CuentasPorPagarDAO, EmpresasDAO  # noqa: E402
from ui.app import (  # noqa: E402
    SearchBar, FormPanel, InventoryTable, DetailModal,
    COLORS, FONT_FAMILY,
)
from ui.proveedores import ProveedoresPage  # noqa: E402
from utils.updater import abrir_actualizador, abrir_rollback, get_local_version, check_for_release_cached  # noqa: E402

# ---------------------------------------------------------------------------
# Tema — se aplica al arrancar según lo guardado en config/theme.json
# ---------------------------------------------------------------------------
from ui.app import _PALETAS, _leer_nombre_tema, _construir_colors, _TEMAS_CLAROS  # noqa: E402

_TEMA_DASH   = _leer_nombre_tema()
_ES_CLARO_D  = _TEMA_DASH in _TEMAS_CLAROS
ctk.set_appearance_mode("Light" if _ES_CLARO_D else "Dark")
ctk.set_default_color_theme("blue")

F = FONT_FAMILY   # alias corto





# ===========================================================================
# CombosPanel
# ===========================================================================

class CombosPanel(ctk.CTkFrame):
    """Panel de gestión de combos embebido en la pestaña Combos de InventarioPage."""

    def __init__(self, parent, dao: InventarioDAO, es_admin: bool, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dao = dao
        self._es_admin = es_admin
        from database.inventario_db import CombosDAO
        self._combos_dao = CombosDAO()
        self._pending_items: list[dict] = []   # items in current form
        self._selected_combo_id: int | None = None
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._build()

    def _build(self):
        # ── Left: combo list ─────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        left.grid(row=0, column=0, padx=(16, 0), pady=16, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.configure(width=260)

        ctk.CTkLabel(left, text="🎁  Combos registrados",
                     font=(F, 14, "bold"), text_color=COLORS["text_primary"]
                     ).grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")

        import tkinter as _tk
        self._combo_listbox = _tk.Listbox(
            left, bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectbackground=COLORS["row_selected"], selectforeground=COLORS["text_primary"],
            font=(F, 11), relief="flat", borderwidth=0, highlightthickness=0,
            activestyle="none"
        )
        self._combo_listbox.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self._combo_listbox.bind("<<ListboxSelect>>", self._on_combo_select)

        if self._es_admin:
            ctk.CTkButton(left, text="🗑️ Eliminar Combo", height=32,
                          fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                          text_color="#fff", font=(F, 12), corner_radius=8,
                          command=self._on_eliminar).grid(
                row=2, column=0, padx=8, pady=(0, 8), sticky="ew")

        # ── Right: form + detail ──────────────────────────────────────
        right = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_root"], corner_radius=0)
        right.grid(row=0, column=1, padx=16, pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        if self._es_admin:
            self._build_combo_form(right)

        # Detail area
        self._detail_frame = ctk.CTkFrame(right, fg_color=COLORS["bg_card"], corner_radius=10)
        self._detail_frame.grid(row=10, column=0, sticky="ew", pady=(8, 0))
        self._detail_frame.grid_columnconfigure(0, weight=1)
        self._lbl_detail = ctk.CTkLabel(
            self._detail_frame, text="← Selecciona un combo para ver su contenido",
            font=(F, 12), text_color=COLORS["text_muted"], wraplength=400
        )
        self._lbl_detail.pack(padx=16, pady=16, anchor="w")

    def _build_combo_form(self, parent):
        form = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=10)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="➕ Nuevo Combo", font=(F, 14, "bold"),
                     text_color=COLORS["text_primary"]).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="w")

        for r, (lbl, attr) in enumerate([
            ("Nombre *", "_cnombre"), ("Descripción", "_cdesc")
        ], start=1):
            ctk.CTkLabel(form, text=lbl, font=(F, 11), text_color=COLORS["text_muted"]
                         ).grid(row=r, column=0, padx=(14, 6), pady=4, sticky="w")
            entry = ctk.CTkEntry(form, height=32, font=(F, 12),
                                 fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                 text_color=COLORS["text_primary"], corner_radius=8)
            entry.grid(row=r, column=1, padx=(0, 14), pady=4, sticky="ew")
            setattr(self, attr, entry)

        ctk.CTkLabel(form, text="Descuento %", font=(F, 11), text_color=COLORS["text_muted"]
                     ).grid(row=3, column=0, padx=(14, 6), pady=4, sticky="w")
        self._cdesc_pct = ctk.CTkEntry(form, height=32, width=80, font=(F, 12),
                                       fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                                       text_color=COLORS["accent"], corner_radius=8)
        self._cdesc_pct.insert(0, "0")
        self._cdesc_pct.grid(row=3, column=1, padx=(0, 14), pady=4, sticky="w")

        # ── Product picker ────────────────────────────────────────────
        ctk.CTkLabel(form, text="Productos del combo", font=(F, 12, "bold"),
                     text_color=COLORS["text_primary"]).grid(
            row=4, column=0, columnspan=2, padx=14, pady=(12, 4), sticky="w")

        picker_row = ctk.CTkFrame(form, fg_color="transparent")
        picker_row.grid(row=5, column=0, columnspan=2, padx=14, pady=(0, 4), sticky="ew")
        picker_row.grid_columnconfigure(0, weight=1)

        self._picker_var = ctk.StringVar()
        self._picker_var.trace_add("write", lambda *_: self._filter_picker())
        ctk.CTkEntry(picker_row, textvariable=self._picker_var,
                     placeholder_text="🔍 Buscar producto...", height=30,
                     font=(F, 11), fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                     text_color=COLORS["text_primary"], corner_radius=8
                     ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._pick_qty_var = ctk.StringVar(value="1")
        ctk.CTkEntry(picker_row, textvariable=self._pick_qty_var, width=50, height=30,
                     font=(F, 12), fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                     text_color=COLORS["text_primary"], corner_radius=8, justify="center"
                     ).grid(row=0, column=1, padx=(0, 6))

        ctk.CTkButton(picker_row, text="+ Agregar", height=30, width=90, font=(F, 11),
                      fg_color=COLORS["success"], hover_color=COLORS["success"],
                      text_color="#fff", corner_radius=8,
                      command=self._on_add_item_picker).grid(row=0, column=2)

        import tkinter as _tk
        self._all_products = []
        self._picker_box = _tk.Listbox(
            form, bg=COLORS["bg_input"], fg=COLORS["text_primary"],
            selectbackground=COLORS["accent"], selectforeground="#fff",
            font=(F, 10), relief="flat", borderwidth=0, highlightthickness=0,
            height=5, activestyle="none"
        )
        self._picker_box.grid(row=6, column=0, columnspan=2, padx=14, pady=(0, 4), sticky="ew")

        # ── Pending items list ────────────────────────────────────────
        ctk.CTkLabel(form, text="Items añadidos:", font=(F, 11, "bold"),
                     text_color=COLORS["text_primary"]).grid(
            row=7, column=0, columnspan=2, padx=14, pady=(6, 2), sticky="w")

        self._items_frame = ctk.CTkFrame(form, fg_color=COLORS["bg_input"], corner_radius=8)
        self._items_frame.grid(row=8, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="ew")
        self._items_frame.grid_columnconfigure(0, weight=1)
        self._lbl_empty_items = ctk.CTkLabel(
            self._items_frame, text="Sin productos aún",
            font=(F, 10), text_color=COLORS["text_muted"]
        )
        self._lbl_empty_items.grid(padx=8, pady=6)

        ctk.CTkButton(form, text="💾 Guardar Combo", height=36, font=(F, 13, "bold"),
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      text_color="#fff", corner_radius=8,
                      command=self._on_guardar_combo).grid(
            row=9, column=0, columnspan=2, padx=14, pady=(4, 12), sticky="ew")

        self._refresh_products()

    def _refresh_products(self):
        self._all_products = self._dao.listar_todos()
        self._filter_picker()

    def _filter_picker(self):
        if not hasattr(self, '_picker_box'): return
        term = self._picker_var.get().strip().lower()
        self._picker_box.delete(0, "end")
        for p in self._all_products:
            if not term or term in p["nombre"].lower() or term in (p["sku"] or "").lower():
                self._picker_box.insert("end", f"  [{p['sku']}] {p['nombre']}")

    def _get_picker_product(self):
        sel = self._picker_box.curselection()
        if not sel: return None
        term = self._picker_var.get().strip().lower()
        visible = [p for p in self._all_products
                   if not term or term in p["nombre"].lower() or term in (p["sku"] or "").lower()]
        idx = sel[0]
        return visible[idx] if idx < len(visible) else None

    def _on_add_item_picker(self):
        prod = self._get_picker_product()
        if not prod: return
        try:
            qty = max(1, int(self._pick_qty_var.get()))
        except ValueError:
            qty = 1
        # Update quantity if already exists
        for item in self._pending_items:
            if item["producto_id"] == prod["id"]:
                item["cantidad"] += qty
                self._refresh_items_display()
                return
        self._pending_items.append({
            "producto_id": prod["id"],
            "nombre":      prod["nombre"],
            "precio_venta": prod["precio_venta"],
            "cantidad":    qty,
        })
        self._refresh_items_display()

    def _refresh_items_display(self):
        for w in self._items_frame.winfo_children():
            w.destroy()
        if not self._pending_items:
            ctk.CTkLabel(self._items_frame, text="Sin productos aún",
                         font=(F, 10), text_color=COLORS["text_muted"]).grid(padx=8, pady=6)
            return
        for i, item in enumerate(self._pending_items):
            row_f = ctk.CTkFrame(self._items_frame, fg_color="transparent")
            row_f.grid(row=i, column=0, padx=6, pady=2, sticky="ew")
            row_f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row_f,
                         text=f"  {item['nombre']}  ×{item['cantidad']}  = ${item['precio_venta']*item['cantidad']:.2f}",
                         font=(F, 10), text_color=COLORS["text_primary"], anchor="w"
                         ).grid(row=0, column=0, sticky="w")
            idx = i
            ctk.CTkButton(row_f, text="✖", width=24, height=20, font=(F, 10),
                          fg_color=COLORS["danger"], text_color="#fff", corner_radius=4,
                          command=lambda x=idx: self._remove_item(x)
                          ).grid(row=0, column=1, padx=(4, 0))

    def _remove_item(self, idx):
        if 0 <= idx < len(self._pending_items):
            self._pending_items.pop(idx)
            self._refresh_items_display()

    def _on_guardar_combo(self):
        nombre = self._cnombre.get().strip()
        desc   = self._cdesc.get().strip()
        try:
            pct = max(0.0, min(100.0, float(self._cdesc_pct.get().strip() or "0")))
        except ValueError:
            pct = 0.0
        if not nombre:
            from tkinter import messagebox
            messagebox.showwarning("Datos incompletos", "El nombre del combo es requerido.")
            return
        if not self._pending_items:
            from tkinter import messagebox
            messagebox.showwarning("Sin productos", "Agrega al menos un producto al combo.")
            return
        try:
            self._combos_dao.crear(nombre=nombre, descripcion=desc, descuento=pct,
                                   items=self._pending_items)
            self._cnombre.delete(0, "end")
            self._cdesc.delete(0, "end")
            self._cdesc_pct.delete(0, "end")
            self._cdesc_pct.insert(0, "0")
            self._pending_items.clear()
            self._refresh_items_display()
            self.refresh()
        except ValueError as e:
            from tkinter import messagebox
            messagebox.showerror("Error", str(e))

    def _on_combo_select(self, _event=None):
        sel = self._combo_listbox.curselection()
        if not sel or not hasattr(self, '_combos_list'): return
        self._selected_combo_id = self._combos_list[sel[0]]["id"]
        combo = self._combos_dao.obtener_detalle_completo(self._selected_combo_id)
        if not combo: return
        for w in self._detail_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail_frame,
                     text=f"🎁 {combo['nombre']}  —  {combo['descuento']:.0f}% desc.  —  ${combo['precio_final']:.2f} USD",
                     font=(F, 13, "bold"), text_color=COLORS["accent"]
                     ).pack(padx=14, pady=(10, 4), anchor="w")
        if combo.get("descripcion"):
            ctk.CTkLabel(self._detail_frame, text=combo["descripcion"],
                         font=(F, 11), text_color=COLORS["text_muted"]
                         ).pack(padx=14, pady=(0, 6), anchor="w")
        for it in combo["items"]:
            ctk.CTkLabel(self._detail_frame,
                         text=f"  • {it['nombre']}  ×{it['cantidad']}  = ${it['precio_venta']*it['cantidad']:.2f}",
                         font=(F, 11), text_color=COLORS["text_primary"]
                         ).pack(padx=14, pady=1, anchor="w")
        ctk.CTkLabel(self._detail_frame,
                     text=f"\n  Precio base: ${combo['precio_base']:.2f}  →  Con {combo['descuento']:.0f}% desc: ${combo['precio_final']:.2f}",
                     font=(F, 11, "bold"), text_color=COLORS["success"]
                     ).pack(padx=14, pady=(4, 10), anchor="w")

    def _on_eliminar(self):
        if self._selected_combo_id is None: return
        from tkinter import messagebox
        if messagebox.askyesno("Eliminar Combo", "¿Eliminar este combo?"):
            self._combos_dao.eliminar(self._selected_combo_id)
            self._selected_combo_id = None
            self.refresh()

    def refresh(self):
        self._combos_list = self._combos_dao.listar()
        self._combo_listbox.delete(0, "end")
        for c in self._combos_list:
            self._combo_listbox.insert(
                "end",
                f"  🎁 {c['nombre']}  ({c['num_items']} prod.)  -{c['descuento']:.0f}%  ${c['precio_final']:.2f}"
            )
        if hasattr(self, '_all_products'):
            self._refresh_products()
        for w in self._detail_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail_frame, text="← Selecciona un combo para ver su contenido",
                     font=(F, 12), text_color=COLORS["text_muted"]
                     ).pack(padx=16, pady=16, anchor="w")


# ===========================================================================
# Página: Inventario (embebida)
# ===========================================================================

class InventarioPage(ctk.CTkFrame):
    """
    Frame completo de inventario reutilizando FormPanel, SearchBar,
    InventoryTable y DetailModal de ui/app.py.
    Incluye pestaña de Combos.
    """

    def __init__(self, parent, dao: InventarioDAO, es_admin: bool,
                 rol: str, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dao      = dao
        self._es_admin = es_admin
        self._rol      = rol
        self._all_rows: list[dict] = []
        self._form     = None
        self._active_tab = "inventario"

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build()
        self._load_inventory()

    # ------------------------------------------------------------------
    def _build(self):
        # ── Tab bar ───────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=44)
        tab_bar.grid(row=0, column=0, sticky="ew")
        tab_bar.grid_propagate(False)
        tab_bar.grid_columnconfigure(2, weight=1)

        self._btn_tab_inv = ctk.CTkButton(
            tab_bar, text="📦  Inventario", width=140, height=34,
            font=(F, 12, "bold"), fg_color=COLORS["accent"], text_color="#fff",
            hover_color=COLORS["accent_hover"], corner_radius=8,
            command=lambda: self._switch_tab("inventario")
        )
        self._btn_tab_inv.grid(row=0, column=0, padx=(10, 4), pady=5)

        self._btn_tab_combo = ctk.CTkButton(
            tab_bar, text="🎁  Combos", width=120, height=34,
            font=(F, 12), fg_color=COLORS["bg_input"], text_color=COLORS["text_muted"],
            hover_color=COLORS["border"], corner_radius=8,
            command=lambda: self._switch_tab("combos")
        )
        self._btn_tab_combo.grid(row=0, column=1, padx=(0, 4), pady=5)

        # ── Content area ─────────────────────────────────────────────
        self._frame_inv   = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._frame_inv.grid(row=1, column=0, sticky="nsew")
        self._frame_inv.grid_rowconfigure(1, weight=1)
        self._frame_inv.grid_columnconfigure(1 if self._es_admin else 0, weight=1)

        self._frame_combo = CombosPanel(self, dao=self._dao, es_admin=self._es_admin)
        self._frame_combo.grid(row=1, column=0, sticky="nsew")
        self._frame_combo.grid_remove()

        # ── Build inventory frame contents ────────────────────────────
        self._build_inventory_frame()

    def _switch_tab(self, tab: str):
        self._active_tab = tab
        if tab == "inventario":
            self._frame_combo.grid_remove()
            self._frame_inv.grid()
            self._btn_tab_inv.configure(fg_color=COLORS["accent"], text_color="#fff")
            self._btn_tab_combo.configure(fg_color=COLORS["bg_input"], text_color=COLORS["text_muted"])
        else:
            self._frame_inv.grid_remove()
            self._frame_combo.grid()
            self._btn_tab_combo.configure(fg_color=COLORS["accent"], text_color="#fff")
            self._btn_tab_inv.configure(fg_color=COLORS["bg_input"], text_color=COLORS["text_muted"])
            self._frame_combo.refresh()

    def _build_inventory_frame(self):
        # ── Barra de búsqueda ─────────────────────────────────────────
        span = 2 if self._es_admin else 1
        self._search_bar = SearchBar(self._frame_inv, on_search_callback=self._on_search)
        self._search_bar.grid(
            row=0, column=0, columnspan=span,
            padx=16, pady=(12, 2), sticky="ew",
        )

        # ── Inicializar filtro de rubro ───────────────────────────────
        from database.inventario_db import AreasDAO
        self._areas_dao_page = AreasDAO()
        self._rubro_var = ctk.StringVar(value="Todos los rubros")

        # ── Formulario (solo Admin) ───────────────────────────────────
        self._frame_inv.grid_rowconfigure(1, weight=1)
        if self._es_admin:
            self._form = FormPanel(
                self._frame_inv,
                dao=self._dao,
                refresh_callback=self._load_inventory,
            )
            self._form.grid(
                row=1, column=0,
                padx=(16, 0), pady=(4, 16), sticky="nsew",
            )
            self._form.configure(width=300)

        # ── Tabla de inventario ───────────────────────────────────────
        col = 1 if self._es_admin else 0
        self._table = InventoryTable(self._frame_inv)
        self._table.grid(
            row=1, column=col,
            padx=(8 if self._es_admin else 16, 16),
            pady=(4, 16), sticky="nsew",
        )
        self._table.bind_select(self._on_row_selected)
        self._table.bind_double_click(self._on_row_double_clicked)

        # ── Botones de acción ─────────────────────────────────────────
        self._build_action_buttons()

    def _get_rubro_values(self) -> list:
        areas = self._areas_dao_page.listar()
        return ["Todos los rubros"] + [a["nombre"] for a in areas]

    def _on_rubro_filter_change(self):
        self._apply_combined_filter()

    def _reset_rubro_filter(self):
        self._rubro_var.set("Todos los rubros")
        self._apply_combined_filter()

    def _apply_combined_filter(self):
        termino = self._search_bar._var.get().strip().lower()
        rubro = self._rubro_var.get()
        rows = self._all_rows
        if rubro and rubro != "Todos los rubros":
            rows = [r for r in rows if (r.get("area_nombre") or "") == rubro]
        if termino:
            rows = [r for r in rows
                    if termino in r["nombre"].lower()
                    or termino in (r["sku"] or "").lower()]
        self._table.refresh(rows)

    def _build_action_buttons(self):
        btn_bar = ctk.CTkFrame(self._table, fg_color="transparent")
        btn_bar.grid(row=0, column=0, padx=16, pady=(10, 4), sticky="ew")

        # ── Selector de rubro (izquierda del btn_bar) ──────────────────
        ctk.CTkLabel(btn_bar, text="📂", font=(F, 14),
                     text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 4))
        rubro_values = self._get_rubro_values()
        self._rubro_filter_combo = ctk.CTkOptionMenu(
            btn_bar,
            variable=self._rubro_var,
            values=rubro_values,
            font=(F, 11),
            width=160,
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent"],
            corner_radius=8,
            command=lambda _: self._on_rubro_filter_change(),
        )
        self._rubro_filter_combo.pack(side="left", padx=(0, 4))

        # Separador visual
        ctk.CTkFrame(btn_bar, fg_color=COLORS["border"], width=1, height=28
                     ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_bar, text="🔍 Ver Detalle",
            width=120, height=32, font=(F, 12),
            fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
            text_color=COLORS["success"], corner_radius=8,
            command=self._on_row_double_clicked,
        ).pack(side="left", padx=(0, 8))

        if self._es_admin:
            ctk.CTkButton(
                btn_bar, text="✏️ Editar",
                width=100, height=32, font=(F, 12),
                fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                text_color=COLORS["accent"], corner_radius=8,
                command=self._on_edit,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_bar, text="📥 Abastecer",
                width=110, height=32, font=(F, 12),
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                text_color="#ffffff", corner_radius=8,
                command=self._on_abastecer,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_bar, text="🗑️ Eliminar",
                width=110, height=32, font=(F, 12),
                fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                text_color="#fff", corner_radius=8,
                command=self._on_delete,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_bar, text="📋 Similar",
                width=100, height=32, font=(F, 12),
                fg_color="#1e2e1e", hover_color=COLORS["success"],
                text_color=COLORS["success"], corner_radius=8,
                command=self._on_agregar_similar,
            ).pack(side="left")

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------

    def _load_inventory(self):
        try:
            self._all_rows = self._dao.listar_todos()
            self._table.refresh(self._all_rows)
        except Exception as e:
            messagebox.showerror("Error de base de datos", str(e))

    def _on_search(self, termino: str):
        self._apply_combined_filter()

    def _on_row_selected(self, _event=None):
        pass

    def _on_row_double_clicked(self, _event=None):
        record_id = self._table.get_selected_id()
        if record_id is None:
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            return
        DetailModal(
            parent=self.winfo_toplevel(),
            record=record,
            dao=self._dao,
            on_updated=self._load_inventory,
            rol=self._rol,
        )

    def _on_new_product(self):
        FormModal(self.winfo_toplevel(), self._dao, self._load_inventory)

    def _on_edit(self):
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showinfo("Editar", "Selecciona un producto de la lista primero.")
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            messagebox.showerror("Error", "No se pudo obtener el producto seleccionado.")
            return
        try:
            self._form.load_data(record)
            self._form.set_edit_mode(record_id)
        except Exception as e:
            messagebox.showerror("Error al cargar", f"No se pudo cargar el producto:\n{e}")

    def _on_delete(self):
        if not self._es_admin:
            return
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showinfo("Eliminar", "Selecciona un producto de la lista primero.")
            return
        record = self._dao.obtener_por_id(record_id)
        nombre = record.get("nombre", f"ID {record_id}") if record else f"ID {record_id}"
        if not messagebox.askyesno("Confirmar eliminación",
                                    f"¿Eliminar '{nombre}'? Esta acción no se puede deshacer."):
            return
        try:
            self._dao.eliminar(record_id)
            if hasattr(self, '_form') and self._form:
                self._form.clear()
            self._load_inventory()
        except Exception as e:
            messagebox.showerror("Error al eliminar", str(e))

    def _on_agregar_similar(self):
        """Carga un producto como base para crear uno similar."""
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showinfo("Similar", "Selecciona un producto de la lista primero.")
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            messagebox.showerror("Error", "No se pudo obtener el producto.")
            return
        try:
            self._form.load_similar(record)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar similar:\n{e}")

    def _on_abastecer(self):
        record_id = self._table.get_selected_id()
        if record_id is None:
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            return
            
        popup = ctk.CTkToplevel(self)
        popup.title("Abastecer: " + record["nombre"])
        popup.geometry("300x350")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        
        ctk.CTkLabel(popup, text="Cantidad actual: " + str(record["cantidad"]), font=(F, 12, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(popup, text="Costo actual: $" + f"{record['precio_entrada']:.2f}", font=(F, 12)).pack(pady=5)
        
        ctk.CTkLabel(popup, text="Cantidad Entrante:", font=(F, 12)).pack(pady=(10, 0))
        entry_qty = ctk.CTkEntry(popup, font=(F, 12), justify="center")
        entry_qty.pack(pady=5)
        entry_qty.insert(0, "0")
        
        ctk.CTkLabel(popup, text="Precio Compra (Unidad) $:", font=(F, 12)).pack(pady=(10, 0))
        entry_cost = ctk.CTkEntry(popup, font=(F, 12), justify="center")
        entry_cost.pack(pady=5)
        entry_cost.insert(0, "0.00")
        
        def save():
            try:
                q = int(entry_qty.get())
                c = float(entry_cost.get())
                if q <= 0: return
                old_q = record["cantidad"]
                old_c = record["precio_entrada"]
                old_v = record.get("precio_venta", 0.0)
                
                # Calcular el porcentaje de ganancia original (markup)
                if old_c > 0:
                    markup = old_v / old_c
                else:
                    markup = 1.0
                
                # Nuevo costo promedio ponderado
                new_q = old_q + q
                new_c = ((old_q * old_c) + (q * c)) / new_q
                
                # Nuevo precio de venta respetando el markup
                new_v = new_c * markup
                
                self._dao.actualizar(record_id, cantidad=new_q, precio_entrada=new_c, precio_venta=new_v)
                self._load_inventory()
                popup.destroy()
            except ValueError:
                pass
                
        ctk.CTkButton(popup, text="Guardar", command=save, fg_color=COLORS["success"], hover_color=COLORS["success"]).pack(pady=20)

    def _on_agregar_similar(self):
        record_id = self._table.get_selected_id()
        if record_id is None:
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            return
        self._form.load_similar(record)
        try:
            self._form._entries["sku"].focus()
        except Exception:
            pass


# ===========================================================================
# Página: Reportes y Estadísticas (embebida)
# ===========================================================================

class ReportesPage(ctk.CTkFrame):
    """Frame con KPIs del día, acceso al historial y generación de PDF."""

    def __init__(self, parent, tasa_actual: float = 1.0, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dao         = VentasDAO()
        self._tasa_actual = tasa_actual
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Título ────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        hdr.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="📊  Reportes y Estadísticas",
            font=(F, 22, "bold"), text_color=COLORS["accent"],
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        ctk.CTkLabel(
            hdr, text="Resumen del día actual y acceso al historial completo.",
            font=(F, 12), text_color=COLORS["text_muted"], anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        # Botones de acción
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=0, column=1, rowspan=2, padx=16, pady=12, sticky="e")

        ctk.CTkButton(
            btn_frame, text="📋  Ver Historial Completo",
            font=(F, 12, "bold"), height=38, width=200,
            fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
            text_color=COLORS["accent"], corner_radius=10,
            command=self._abrir_historial,
        ).pack(pady=(0, 8))

        ctk.CTkButton(
            btn_frame, text="🏁  Realizar Cierre de Día (PDF)",
            font=(F, 12, "bold"), height=38, width=200,
            fg_color=COLORS["success"], hover_color=COLORS["accent"],
            text_color="#ffffff", corner_radius=10,
            command=self._generar_pdf,
        ).pack()

        # ── Área de KPIs (se rellena al mostrar la página) ───────────
        self._kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self._kpi_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._kpi_frame.grid_rowconfigure(1, weight=1)

        self.refresh()

    def refresh(self):
        """Recarga los KPIs con datos actuales de la BD."""
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        try:
            resumen = self._dao.resumen_dia()
        except Exception:
            return
        self._draw_kpis(resumen)
        self._draw_top_productos(resumen.get("productos", []))

    def _draw_kpis(self, resumen: dict):
        cards = [
            ("Ventas hoy",    str(resumen["total_ventas"]),       COLORS["accent"],   "🧾"),
            ("Total USD",     f"${resumen['total_usd']:,.2f}",    COLORS["success"],  "💵"),
            ("Total Bs.",     f"Bs. {resumen['total_bs']:,.2f}",  COLORS["accent"],          "💰"),
        ]
        for col, (titulo, valor, color, icono) in enumerate(cards):
            card = ctk.CTkFrame(self._kpi_frame, fg_color=COLORS["bg_card"], corner_radius=16)
            card.grid(row=0, column=col, padx=8, pady=8, sticky="ew")

            ctk.CTkLabel(card, text=icono, font=(F, 34)).pack(pady=(20, 4))
            ctk.CTkLabel(card, text=valor, font=(F, 26, "bold"), text_color=color).pack()
            ctk.CTkLabel(card, text=titulo, font=(F, 12), text_color=COLORS["text_muted"]).pack(pady=(2, 20))

    def _draw_top_productos(self, productos: list):
        if not productos:
            ctk.CTkLabel(
                self._kpi_frame,
                text="No hay ventas registradas hoy.",
                font=(F, 14), text_color=COLORS["text_muted"],
            ).grid(row=1, column=0, columnspan=3, pady=40)
            return

        lista_frame = ctk.CTkFrame(self._kpi_frame, fg_color=COLORS["bg_card"], corner_radius=16)
        lista_frame.grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="nsew")
        lista_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            lista_frame, text="🏆  Productos más vendidos hoy",
            font=(F, 14, "bold"), text_color=COLORS["text_primary"], anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(14, 8), sticky="w")

        for i, p in enumerate(productos[:10]):
            row_frame = ctk.CTkFrame(
                lista_frame,
                fg_color=COLORS["row_even"] if i % 2 == 0 else COLORS["row_odd"],
                corner_radius=8,
            )
            row_frame.grid(row=i + 1, column=0, padx=16, pady=2, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_frame, text=f"  {i+1:02d}.  {p['nombre_producto']}",
                font=(F, 12), text_color=COLORS["text_primary"], anchor="w",
            ).grid(row=0, column=0, padx=8, pady=8, sticky="w")
            ctk.CTkLabel(
                row_frame,
                text=f"Qty: {p['cantidad_total']}   |   ${p['subtotal']:,.2f}",
                font=(F, 11), text_color=COLORS["text_muted"], anchor="e",
            ).grid(row=0, column=1, padx=12, pady=8, sticky="e")

    def _abrir_historial(self):
        from ui.historial_ventas import HistorialVentasWindow
        HistorialVentasWindow(parent=self.winfo_toplevel(), tasa_actual=self._tasa_actual)

    def _generar_pdf(self):
        if not messagebox.askyesno("Cierre de Día", "¿Estás seguro de que deseas realizar el cierre de día? Se generará un reporte en PDF de todas las transacciones de hoy."):
            return
        import os
        from utils.reporte_pdf import generar_reporte_dia
        try:
            resumen = self._dao.resumen_dia()
            ventas  = self._dao.listar_ventas_del_dia()
        except Exception as e:
            messagebox.showerror("Error de base de datos", str(e))
            return
        if resumen["total_ventas"] == 0:
            messagebox.showinfo("Sin ventas", "No hay ventas registradas hoy para realizar el cierre.")
            return
        try:
            ruta = generar_reporte_dia(resumen=resumen, ventas=ventas, tasa_bs=self._tasa_actual)
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e))
            return
        if messagebox.askyesno("✅ Cierre de Día completado", f"Se ha generado y guardado tu comprobante en:\n{ruta}\n\n¿Deseas abrir el PDF ahora?"):
            try:
                os.startfile(str(ruta))
            except Exception:
                pass


# ===========================================================================
# Página: Placeholder genérico
# ===========================================================================

class PlaceholderPage(ctk.CTkFrame):
    """Pantalla de 'próximamente' para secciones en construcción."""

    def __init__(self, parent, icono: str, titulo: str, descripcion: str, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=20)
        card.grid(padx=60, pady=60, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text=icono,    font=(F, 72)).pack(pady=(0, 8))
        ctk.CTkLabel(inner, text=titulo,   font=(F, 28, "bold"), text_color=COLORS["text_primary"]).pack()
        ctk.CTkLabel(inner, text=descripcion, font=(F, 14), text_color=COLORS["text_muted"],
                     wraplength=500).pack(pady=(8, 0))

        ctk.CTkLabel(
            inner, text="🚧  Esta sección estará disponible próximamente",
            font=(F, 13), text_color=COLORS["accent"],
        ).pack(pady=(24, 0))


# ===========================================================================
# Página: Deudores (Fiado)
# ===========================================================================
class DeudoresPage(ctk.CTkFrame):
    """
    Página unificada de deudas:
    - Deudas de clientes (fiado) - icono 🟢
    - Nuestras deudas (cuentas por pagar) - icono 🟥
    - Filtro Pendientes / Pagadas
    - Tarjeta de información al seleccionar
    - Botón para agregar nuestras deudas
    """

    COLS = [
        ("tipo",   "Tipo",          60,  "center"),
        ("nombre", "Nombre/Cliente",140, "w"),
        ("telef",  "Teléfono",      135, "center"),
        ("usd",    "Monto USD",     120, "e"),
        ("bs",     "Monto Bs.",     140, "e"),
        ("fecha",  "Fecha",         140, "center"),
        ("limite", "Fecha Límite",  140, "center"),
        ("estado", "Estado",         95, "center"),
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dao_deu  = DeudoresDAO()
        self._dao_cpp  = CuentasPorPagarDAO()
        self._rows: list[dict] = []   # filas combinadas con campo __source
        self._selected_row: dict | None = None
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()
        self._load()

    # ------------------------------------------------------------------
    def _build(self):
        from tkinter import ttk as _ttk

        # ── Encabezado ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="📋  Deudas",
                     font=(F, 20, "bold"), text_color=COLORS["text_primary"]).grid(
            row=0, column=0, padx=20, pady=(14, 2), sticky="w")
        ctk.CTkLabel(hdr,
                     text="🟢 = Clientes que nos deben  │  🟥 = Nuestras deudas por pagar",
                     font=(F, 11), text_color=COLORS["text_muted"], anchor="w").grid(
            row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        # Filtro de estado
        self._filtro_var = ctk.StringVar(value="Pendientes")
        seg = ctk.CTkSegmentedButton(
            hdr,
            values=["Pendientes", "Pagadas"],
            variable=self._filtro_var,
            command=lambda _: self._load(),
            font=(F, 12, "bold"),
            height=36,
        )
        seg.grid(row=0, column=1, padx=16, pady=14, sticky="e")

        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(0, 16), pady=14)

        ctk.CTkButton(btn_frame, text="🔄  Actualizar",
                      font=(F, 12, "bold"), height=36, width=130,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                      text_color=COLORS["accent"], corner_radius=10,
                      command=self._load).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_frame, text="➕  Agregar Pago Pendiente",
                      font=(F, 12, "bold"), height=36, width=200,
                      fg_color="#2a1010", hover_color="#4a2020",
                      text_color="#e05c5c", corner_radius=10,
                      command=self._on_agregar_pago_pendiente).pack(side="left", padx=(0, 8))

        self._btn_pagar = ctk.CTkButton(
            btn_frame, text="✅  Marcar Pagada",
            font=(F, 12, "bold"), height=36, width=160,
            fg_color="#1e3820", hover_color=COLORS["success"],
            text_color=COLORS["success"], corner_radius=10,
            state="disabled",
            command=self._on_marcar_pagada)
        self._btn_pagar.pack(side="left")

        # ── Tabla ───────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=COLORS["bg_root"])
        tree_frame.grid(row=1, column=0, padx=16, pady=(12, 16), sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        style = _ttk.Style()
        style.configure("Deudores.Treeview",
                         background=COLORS["bg_card"],
                         foreground=COLORS["text_primary"],
                         fieldbackground=COLORS["bg_card"],
                         rowheight=36, font=(F, 12), borderwidth=0)
        style.configure("Deudores.Treeview.Heading",
                         background=COLORS["bg_input"],
                         foreground=COLORS["text_muted"],
                         font=(F, 11, "bold"), borderwidth=0, relief="flat")
        style.map("Deudores.Treeview",
                  background=[("selected", COLORS["row_selected"])],
                  foreground=[("selected", COLORS["text_primary"])])

        col_ids = [c[0] for c in self.COLS]
        self._tree = _ttk.Treeview(tree_frame, columns=col_ids, show="headings",
                                    style="Deudores.Treeview", selectmode="browse")
        for col_id, heading, width, anchor in self.COLS:
            self._tree.heading(col_id, text=heading, anchor=anchor)
            self._tree.column(col_id, width=width, anchor=anchor,
                              minwidth=30, stretch=(col_id == "nombre"))

        self._tree.tag_configure("cobrar_p",  foreground="#3ecf8e")
        self._tree.tag_configure("cobrar_ok", foreground="#3ecf8e", background=COLORS["row_even"])
        self._tree.tag_configure("pagar_p",   foreground="#e05c5c")
        self._tree.tag_configure("pagar_ok",  foreground="#e05c5c", background=COLORS["row_odd"])
        self._tree.tag_configure("even",      background=COLORS["row_even"])
        self._tree.tag_configure("odd",       background=COLORS["row_odd"])

        v_scroll = _ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=v_scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", self._on_double_click)

    # ------------------------------------------------------------------
    def _load(self):
        estado = "Pendiente" if self._filtro_var.get() == "Pendientes" else "Pagada"
        self._rows.clear()
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._btn_pagar.configure(state="disabled")
        self._selected_row = None

        try:
            deu_list = self._dao_deu.listar_deudores()
            cpp_list = self._dao_cpp.listar_todas()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Filtrar por estado y combinar
        for r in deu_list:
            if r["estado"] == estado:
                r["__source"] = "cobrar"
                self._rows.append(r)
        for r in cpp_list:
            if r["estado"] == estado:
                r["__source"] = "pagar"
                self._rows.append(r)

        for i, r in enumerate(self._rows):
            src = r["__source"]
            icono = "🟢" if src == "cobrar" else "🟥"
            tag   = "cobrar_p" if src == "cobrar" else "pagar_p"

            if src == "cobrar":
                fecha  = (r.get("fecha_venta") or "")[:10] or "—"
                limite = r.get("fecha_limite_pago") or "—"
                monto_usd = r.get("monto_deuda_usd", 0)
                monto_bs  = r.get("monto_deuda_bs", 0)
                telef = r.get("telefono") or "—"
            else:
                fecha  = (r.get("fecha") or "")[:10] or "—"
                limite = "—"
                monto_usd = r.get("monto_usd", 0)
                monto_bs  = r.get("monto_bs", 0)
                telef = r.get("telefono") or "—"

            self._tree.insert("", "end", iid=str(i), tags=(tag,), values=(
                icono,
                r["nombre"],
                telef,
                f"${monto_usd:,.2f}",
                f"Bs. {monto_bs:,.2f}",
                fecha,
                limite,
                r["estado"],
            ))

    # ------------------------------------------------------------------
    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            self._btn_pagar.configure(state="disabled")
            self._selected_row = None
            return
        idx = int(sel[0])
        r = self._rows[idx]
        self._selected_row = r
        # Solo habilitar "Marcar Pagada" si está pendiente
        if r["estado"] == "Pendiente":
            self._btn_pagar.configure(state="normal")
        else:
            self._btn_pagar.configure(state="disabled")

    def _on_double_click(self, _event=None):
        """Muestra una tarjeta con la información detallada del registro."""
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        r = self._rows[idx]
        self._mostrar_tarjeta(r)

    def _mostrar_tarjeta(self, r: dict):
        src = r["__source"]
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("Información")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.focus_force()

        card = ctk.CTkFrame(win, fg_color=COLORS["bg_card"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=24, pady=24)

        if src == "cobrar":
            titulo = f"🟢 Deuda de Cliente: {r['nombre']}"
            lineas = [
                ("Nombre",       r.get("nombre", "")),
                ("Teléfono",     r.get("telefono") or "—"),
                ("Monto USD",    f"${r.get('monto_deuda_usd', 0):,.2f}"),
                ("Monto Bs.",    f"Bs. {r.get('monto_deuda_bs', 0):,.2f}"),
                ("Fecha Venta",  (r.get("fecha_venta") or "")[:10] or "—"),
                ("Fecha Límite", r.get("fecha_limite_pago") or "—"),
                ("Estado",       r.get("estado", "")),
            ]
        else:
            titulo = f"🟥 Pago Pendiente: {r['nombre']}"
            lineas = [
                ("Nombre",       r.get("nombre", "")),
                ("Descripción",  r.get("descripcion") or "—"),
                ("Banco",        r.get("banco") or "—"),
                ("Cédula",       r.get("cedula") or "—"),
                ("Teléfono",     r.get("telefono") or "—"),
                ("Monto USD",    f"${r.get('monto_usd', 0):,.2f}"),
                ("Monto Bs.",    f"Bs. {r.get('monto_bs', 0):,.2f}"),
                ("Estado",       r.get("estado", "")),
            ]

        ctk.CTkLabel(card, text=titulo, font=(F, 15, "bold"),
                     text_color=COLORS["text_primary"]).pack(padx=20, pady=(20, 12), anchor="w")

        for etiqueta, valor in lineas:
            fila = ctk.CTkFrame(card, fg_color="transparent")
            fila.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(fila, text=etiqueta + ":", width=130, anchor="w",
                         font=(F, 12), text_color=COLORS["text_muted"]).pack(side="left")
            ctk.CTkLabel(fila, text=valor, anchor="w",
                         font=(F, 12, "bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=(8, 0))

        ctk.CTkButton(card, text="Cerrar", height=36,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["border"],
                      text_color=COLORS["text_muted"], corner_radius=10,
                      command=win.destroy).pack(padx=20, pady=(16, 20), fill="x")

        win.update_idletasks()
        w, h = win.winfo_reqwidth() + 60, win.winfo_reqheight() + 60
        px = self.winfo_toplevel().winfo_rootx()
        py = self.winfo_toplevel().winfo_rooty()
        pw = self.winfo_toplevel().winfo_width()
        ph = self.winfo_toplevel().winfo_height()
        win.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

    # ------------------------------------------------------------------
    def _on_marcar_pagada(self):
        if not self._selected_row:
            return
        r = self._selected_row
        if r["estado"] != "Pendiente":
            return
        if not messagebox.askyesno(
            "Confirmar pago",
            f"¿Marcar la deuda de {r['nombre']} como Pagada?",
        ):
            return
        try:
            if r["__source"] == "cobrar":
                self._dao_deu.marcar_pagada(r["id"])
            else:
                self._dao_cpp.marcar_pagada(r["id"])
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        messagebox.showinfo("Pagado", f"✅ Deuda de {r['nombre']} marcada como Pagada.")
        self._load()

    # ------------------------------------------------------------------
    def _on_agregar_pago_pendiente(self):
        """Abre un formulario para registrar una nueva deuda propia (cuenta por pagar)."""
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("➕ Agregar Pago Pendiente")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.focus_force()

        frame = ctk.CTkFrame(win, fg_color=COLORS["bg_card"], corner_radius=16)
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(frame, text="🟥 Nueva Deuda Propia",
                     font=(F, 15, "bold"), text_color="#e05c5c").pack(anchor="w", pady=(0, 14))

        campos = [
            ("Nombre *",           "nombre"),
            ("Descripción",         "descripcion"),
            ("Banco",               "banco"),
            ("Cédula",             "cedula"),
            ("Teléfono",           "telefono"),
            ("Monto USD *",         "monto_usd"),
            ("Monto Bs. *",         "monto_bs"),
        ]
        entries: dict[str, ctk.CTkEntry] = {}
        for label, key in campos:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=160, anchor="w",
                         font=(F, 12), text_color=COLORS["text_muted"]).pack(side="left")
            en = ctk.CTkEntry(row, width=220, height=34, font=(F, 12),
                              fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                              text_color=COLORS["text_primary"], corner_radius=8)
            en.pack(side="left", padx=(8, 0))
            entries[key] = en

        lbl_err = ctk.CTkLabel(frame, text="", font=(F, 11), text_color="#e05c5c")
        lbl_err.pack(pady=(4, 0))

        def _guardar():
            nom = entries["nombre"].get().strip()
            if not nom:
                lbl_err.configure(text="⚠️ El nombre es obligatorio.")
                return
            try:
                monto_usd = float(entries["monto_usd"].get().strip().replace(",", ".") or "0")
                monto_bs  = float(entries["monto_bs"].get().strip().replace(",", ".") or "0")
            except ValueError:
                lbl_err.configure(text="⚠️ Los montos deben ser números.")
                return
            try:
                self._dao_cpp.crear(
                    nombre=nom,
                    descripcion=entries["descripcion"].get().strip(),
                    banco=entries["banco"].get().strip(),
                    cedula=entries["cedula"].get().strip(),
                    telefono=entries["telefono"].get().strip(),
                    monto_usd=monto_usd,
                    monto_bs=monto_bs,
                )
                win.destroy()
                self._filtro_var.set("Pendientes")
                self._load()
            except Exception as e:
                lbl_err.configure(text=f"⚠️ Error: {e}")

        ctk.CTkButton(frame, text="💾  Guardar",
                      font=(F, 13, "bold"), height=40,
                      fg_color="#e05c5c", hover_color="#c04040",
                      text_color="#fff", corner_radius=10,
                      command=_guardar).pack(fill="x", pady=(14, 0))

        win.update_idletasks()
        w = max(win.winfo_reqwidth() + 80, 450)
        h = win.winfo_reqheight() + 60
        px = self.winfo_toplevel().winfo_rootx()
        py = self.winfo_toplevel().winfo_rooty()
        pw = self.winfo_toplevel().winfo_width()
        ph = self.winfo_toplevel().winfo_height()
        win.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

    def refresh(self):
        self._load()



# ===========================================================================
# Página: Notificaciones  (diseño premium)
# ===========================================================================

class NotificacionesPage(ctk.CTkFrame):
    """Centro de alertas — stock bajo y deudores vencidos."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._inv_dao = InventarioDAO()
        from database.inventario_db import DeudoresDAO as _DD
        self._deu_dao = _DD()
        self._dismissed: set = set()   # IDs/nombres de alertas descartadas
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()
        self.refresh()

    def _build(self):
        # Top bar
        topbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=70)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)
        topbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(topbar, text="🔔  Centro de Alertas",
                     font=(F, 20, "bold"), text_color=COLORS["accent"]
                     ).grid(row=0, column=0, padx=24, pady=22, sticky="w")
        ctk.CTkLabel(topbar, text="Monitoreo de stock bajo y deudas vencidas",
                     font=(F, 11), text_color=COLORS["text_muted"]
                     ).grid(row=0, column=1, padx=4, pady=22, sticky="w")
        ctk.CTkButton(topbar, text="✔  Marcar todas leídas",
                      font=(F, 12, "bold"), height=34, width=180,
                      fg_color="#1e3820", hover_color=COLORS["success"],
                      text_color=COLORS["success"], corner_radius=8,
                      command=self._marcar_todas_leidas
                      ).grid(row=0, column=2, padx=(0, 8), pady=18)
        ctk.CTkButton(topbar, text="🔄  Actualizar",
                      font=(F, 12, "bold"), height=34, width=130,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["accent"],
                      text_color=COLORS["accent"], corner_radius=8,
                      command=self._actualizar_todo
                      ).grid(row=0, column=3, padx=20, pady=18)

        # KPI row
        self._kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_row.grid(row=1, column=0, padx=16, pady=12, sticky="ew")
        self._kpi_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Scrollable alerts
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"])
        self._scroll.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

    def _actualizar_todo(self):
        """Recarga datos sin conservar las alertas descartadas."""
        self._dismissed.clear()
        self.refresh()

    def _marcar_todas_leidas(self):
        """Descarta todas las alertas visibles (no las borra de la BD)."""
        try:    vencidos   = self._deu_dao.listar_vencidos()
        except: vencidos   = []
        try:    stock_bajo = self._inv_dao.listar_stock_bajo()
        except: stock_bajo = []
        for d in vencidos:
            self._dismissed.add(f"deu_{d['id']}")
        for p in stock_bajo:
            self._dismissed.add(f"sku_{p.get('sku', p['nombre'])}")
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        for w in self._kpi_row.winfo_children():
            w.destroy()

        try:    vencidos_raw   = self._deu_dao.listar_vencidos()
        except: vencidos_raw   = []
        try:    stock_raw      = self._inv_dao.listar_stock_bajo()
        except: stock_raw      = []

        # Filtrar los descartados
        vencidos   = [d for d in vencidos_raw   if f"deu_{d['id']}"                        not in self._dismissed]
        stock_bajo = [p for p in stock_raw       if f"sku_{p.get('sku', p['nombre'])}" not in self._dismissed]

        n_venc  = len(vencidos)
        n_stock = len(stock_bajo)
        n_sin   = sum(1 for p in stock_bajo if p["cantidad"] == 0)
        total   = n_venc + n_stock

        # KPI mini-cards (se basan en datos reales, no filtrados)
        n_venc_total  = len(vencidos_raw)
        n_stock_total = len(stock_raw)
        kpis = [
            ("🚨", str(n_venc_total),  "Deudas\nVencidas",  "#e05c5c", "#2d0e0e"),
            ("⚠️",  str(n_stock_total), "Stock\nBajo",        "#e0954a", "#2d1800"),
            ("📦",  str(sum(1 for p in stock_raw if p["cantidad"] == 0)),   "Sin\nStock",
             "#e05c5c" if any(p["cantidad"] == 0 for p in stock_raw) else COLORS["text_muted"],
             "#2d0e0e" if any(p["cantidad"] == 0 for p in stock_raw) else COLORS["bg_card"]),
            ("✅",  "OK" if total == 0 else f"{total} activas",
             "Todo al día" if total == 0 else "Pendientes",
             COLORS["success"] if total == 0 else COLORS["text_muted"],
             "#0a2218" if total == 0 else COLORS["bg_card"]),
        ]
        for col, (icono, valor, etiq, color, bg) in enumerate(kpis):
            c = ctk.CTkFrame(self._kpi_row, fg_color=bg, corner_radius=12)
            c.grid(row=0, column=col, padx=5, pady=4, sticky="nsew")
            c.grid_columnconfigure(0, weight=1)
            top_f = ctk.CTkFrame(c, fg_color="transparent")
            top_f.pack(fill="x", padx=12, pady=(12, 4))
            ctk.CTkLabel(top_f, text=icono, font=(F, 22)).pack(side="left")
            ctk.CTkLabel(top_f, text=valor, font=(F, 24, "bold"),
                         text_color=color).pack(side="right")
            ctk.CTkFrame(c, fg_color=color, height=2, corner_radius=1).pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(c, text=etiq, font=(F, 10), text_color=COLORS["text_muted"],
                         justify="center").pack(padx=12, pady=(2, 10))

        # Verificar actualización disponible (en background, no bloquea UI)
        try:
            import threading as _t
            def _check_update_bg():
                result = check_for_release_cached()
                if result.get("has_update"):
                    self.after(0, self._show_update_banner, result["latest_tag"])
            _t.Thread(target=_check_update_bg, daemon=True).start()
        except Exception:
            pass

        # Empty state
        if total == 0:
            empty = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=16)
            empty.grid(row=0, column=0, padx=24, pady=24, sticky="ew")
            empty.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(empty, text="✅", font=(F, 60)).grid(pady=(28, 6))
            ctk.CTkLabel(empty, text="¡Todo en orden!",
                         font=(F, 22, "bold"), text_color=COLORS["success"]).grid()
            if self._dismissed:
                ctk.CTkLabel(empty, text=f"{len(self._dismissed)} alerta(s) marcada(s) como leída(s).",
                             font=(F, 11), text_color=COLORS["text_muted"]).grid(pady=(2, 4))
            ctk.CTkLabel(empty, text="No hay alertas activas. El stock y los pagos están al día.",
                         font=(F, 12), text_color=COLORS["text_muted"]).grid(pady=(4, 28))
            return

        row_i = 0

        if vencidos:
            self._section_header(row_i, f"🚨  Deudas Vencidas ({n_venc})", "#e05c5c")
            row_i += 1
            for d in vencidos:
                dias = d.get("dias_atraso", 0)
                self._deuda_card(row_i, d["id"], d["nombre"], d["monto_deuda_usd"],
                                 d["monto_deuda_bs"], dias,
                                 d.get("fecha_limite_pago", "?"), d.get("telefono", ""))
                row_i += 1

        if stock_bajo:
            self._section_header(row_i, f"⚠️  Stock Bajo ({n_stock} productos)", "#e0954a")
            row_i += 1
            for p in stock_bajo:
                self._stock_card(row_i, p["nombre"], p["cantidad"], p.get("sku", ""), p.get("stock_minimo", 5))

                row_i += 1

    def _dismiss(self, key: str):
        """Descarta una alerta individual por su clave."""
        self._dismissed.add(key)
        self.refresh()

    def _show_update_banner(self, tag: str):
        """Inserta banner de actualización disponible en el scroll de alertas."""
        try:
            banner = ctk.CTkFrame(self._scroll, fg_color="#0a1e3a", corner_radius=14)
            banner.grid(row=999, column=0, padx=24, pady=(0, 12), sticky="ew")
            banner.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(banner, text="🚀", font=(F, 28)).grid(
                row=0, column=0, padx=(16, 10), pady=16, sticky="w")
            info_f = ctk.CTkFrame(banner, fg_color="transparent")
            info_f.grid(row=0, column=1, pady=16, sticky="w")
            ctk.CTkLabel(info_f, text=f"Nueva versión {tag} disponible",
                         font=(F, 14, "bold"), text_color="#4f8ef7",
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(info_f, text="Ve a Configuración → Actualizaciones para instalarla.",
                         font=(F, 11), text_color=COLORS["text_muted"],
                         anchor="w").pack(anchor="w")
        except Exception:
            pass

    def _section_header(self, row, titulo, color):
        bg = "#2d0e0e" if color == "#e05c5c" else "#2d1800"
        f = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=8)
        f.grid(row=row, column=0, padx=16, pady=(16, 4), sticky="ew")
        ctk.CTkLabel(f, text=titulo, font=(F, 13, "bold"),
                     text_color=color, anchor="w").pack(padx=16, pady=10, anchor="w")

    def _deuda_card(self, row, deu_id, nombre, usd, bs, dias, limite, telefono):
        key = f"deu_{deu_id}"
        c = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=12)
        c.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        c.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(c, fg_color="#e05c5c", width=4, corner_radius=2).grid(
            row=0, column=0, rowspan=3, sticky="nsew")
        ctk.CTkLabel(c, text=nombre, font=(F, 14, "bold"),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=1, padx=14, pady=(12, 2), sticky="w")
        ctk.CTkLabel(c, text=f"💵 ${usd:,.2f}  |  Bs. {bs:,.2f}",
                     font=(F, 12, "bold"), text_color="#e05c5c", anchor="w").grid(
            row=1, column=1, padx=14, pady=0, sticky="w")
        info = f"Vencido hace {dias} día{'s' if dias!=1 else ''}  ·  Límite: {limite}"
        if telefono:
            info += f"  ·  📱 {telefono}"
        ctk.CTkLabel(c, text=info, font=(F, 10), text_color=COLORS["text_muted"],
                     anchor="w").grid(row=2, column=1, padx=14, pady=(0, 12), sticky="w")
        badge_frame = ctk.CTkFrame(c, fg_color="transparent")
        badge_frame.grid(row=0, column=2, rowspan=3, padx=14, pady=8, sticky="e")
        ctk.CTkLabel(badge_frame, text="🔴 URGENTE" if dias > 7 else "⚠️ Vencida",
                     font=(F, 10, "bold"),
                     text_color="#e05c5c" if dias > 7 else "#e0954a").pack(anchor="e")
        ctk.CTkButton(badge_frame, text="✔ Leído", height=24, width=70,
                      font=(F, 10), fg_color="#1e2e1e", hover_color="#2a3a2a",
                      text_color=COLORS["success"], corner_radius=6,
                      command=lambda k=key: self._dismiss(k)).pack(anchor="e", pady=(4, 0))

    def _stock_card(self, row, nombre, qty, sku, stock_minimo=5):
        key = f"sku_{sku or nombre}"
        urgente = qty == 0
        color   = "#e05c5c" if urgente else "#e0954a"
        c = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=12)
        c.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        c.grid_columnconfigure(2, weight=1)
        ctk.CTkFrame(c, fg_color=color, width=4, corner_radius=2).grid(
            row=0, column=0, rowspan=2, sticky="nsew")
        ctk.CTkLabel(c, text="📦" if urgente else "⚠️", font=(F, 20)).grid(
            row=0, column=1, rowspan=2, padx=(12, 6), pady=12)
        ctk.CTkLabel(c, text=nombre, font=(F, 14, "bold"),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=2, padx=4, pady=(12, 2), sticky="w")
        status = "¡SIN STOCK!" if urgente else f"{qty} unidades disponibles"
        umbral_txt = f"  ·  Umbral: {stock_minimo} uds."
        ctk.CTkLabel(c, text=f"{status}  ·  SKU: {sku or 'N/A'}{umbral_txt}",
                     font=(F, 11), text_color=color, anchor="w").grid(
            row=1, column=2, padx=4, pady=(0, 12), sticky="w")
        badge_frame = ctk.CTkFrame(c, fg_color="transparent")
        badge_frame.grid(row=0, column=3, rowspan=2, padx=14, pady=8, sticky="e")
        ctk.CTkLabel(badge_frame, text="🚨 REORDENAR" if urgente else "📉 Stock bajo",
                     font=(F, 10, "bold"), text_color=color).pack(anchor="e")
        ctk.CTkButton(badge_frame, text="✔ Leído", height=24, width=70,
                      font=(F, 10), fg_color="#1e2e1e", hover_color="#2a3a2a",
                      text_color=COLORS["success"], corner_radius=6,
                      command=lambda k=key: self._dismiss(k)).pack(anchor="e", pady=(4, 0))


# ===========================================================================
# Aplicación Principal: DashboardApp
# ===========================================================================

class DashboardApp(ctk.CTk):
    """
    Ventana raíz del sistema. Gestiona el login y el dashboard con sidebar.

    Flujo:
      1. Se muestra LoginWindow modal.
      2. Si el login es exitoso, se construye el dashboard.
      3. El sidebar navega entre páginas embebidas (o abre POS como ventana).
    """

    NAV_ITEMS = [
        ("📊",  "Reportes",           "reportes",         False, False),
        ("🛒",  "Punto de Venta",     "pos",              True,  False),   # abre ventana
        ("📦",  "Inventario",         "inventario",       False, False),
        ("🏭",  "Proveedores",        "proveedores",      False, False),
        ("📋",  "Deudores",           "deudores",         False, False),
        ("💸",  "Gastos Diarios",     "gastos_diarios",   False, True),   # próximamente
        ("🔔",  "Notificaciones",     "notificaciones",   False, False),
        ("⚙️",  "Configuración",      "configuracion",    False, False),
    ]

    def __init__(self):
        super().__init__()
        self._dao          = InventarioDAO()
        self._active_key   = None
        self._pages: dict  = {}
        self._nav_buttons: dict = {}

        # Ocultar mientras llega el login
        self.withdraw()
        from ui.login import LoginWindow
        self._login_win = LoginWindow(self)
        self._login_win.protocol("WM_DELETE_WINDOW", self._on_login_closed)

    # ------------------------------------------------------------------
    # Callbacks de login
    # ------------------------------------------------------------------

    def _on_login_success(self, usuario_info: dict):
        self._login_win.destroy()
        self._usuario_nombre = usuario_info.get("usuario", "")
        self._rol            = usuario_info.get("rol", "Empleado")
        self._empresa_id     = usuario_info.get("empresa_id")
        self._es_admin       = self._rol == "Admin"

        # SuperAdmin: abre panel propio, no el dashboard normal
        if self._rol == "SuperAdmin":
            from ui.superadmin import SuperAdminPanel
            self.deiconify()
            self.withdraw()
            panel = SuperAdminPanel(self)
            panel.protocol("WM_DELETE_WINDOW", self._on_login_closed)
            return

        self._setup_window()
        self._build_dashboard()
        self.deiconify()
        self._navigate("reportes")
        # Escanear BD y mostrar badge de alertas en el sidebar
        self.after(500, self._refresh_notif_badge)

    def _on_login_closed(self):
        self.destroy()

    # ------------------------------------------------------------------
    # Configuración de ventana
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.title("⚡ RepuestosDB — Sistema de Gestión")
        self.geometry("1360x780")
        self.minsize(1000, 620)
        self.configure(fg_color=COLORS["bg_root"])
        # Maximizar ventana
        try:
            self.state('zoomed')
        except Exception:
            # Fallback a fullscreen si no soporta zoomed
            self.attributes("-fullscreen", True)

    # ------------------------------------------------------------------
    # Construcción del dashboard
    # ------------------------------------------------------------------

    def _build_dashboard(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Sidebar ───────────────────────────────────────────────────
        self._sidebar = ctk.CTkFrame(
            self, fg_color=COLORS["sidebar"], corner_radius=0, width=220,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._build_sidebar()

        # ── Área de contenido ─────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color=COLORS["bg_root"], corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # ── Crear todas las páginas embebidas (ocultas por defecto) ───
        self._build_pages()

    def _build_sidebar(self):
        self._sidebar.grid_rowconfigure(9, weight=1)  # push badge al fondo
        self._sidebar.grid_columnconfigure(0, weight=1)

        # Logo / branding de la empresa
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color=COLORS["bg_card"], corner_radius=0)
        logo_frame.grid(row=0, column=0, sticky="ew")

        empresa = None
        if hasattr(self, "_empresa_id") and self._empresa_id:
            try:
                empresa = EmpresasDAO().obtener_por_id(self._empresa_id)
            except Exception:
                empresa = None

        if empresa:
            nombre_sidebar = empresa["nombre"]
            ruta_logo = empresa.get("ruta_logo", "")
            if ruta_logo and Path(ruta_logo).exists():
                try:
                    from PIL import Image
                    img = Image.open(ruta_logo).convert("RGBA")
                    img.thumbnail((32, 32))
                    ctk_img = ctk.CTkImage(img, size=(32, 32))
                    lbl_logo = ctk.CTkLabel(logo_frame, image=ctk_img, text="",
                                            font=(F, 18, "bold"), text_color=COLORS["accent"])
                    lbl_logo.pack(side="left", padx=(16, 6), pady=(16, 4))
                    lbl_logo._ctk_ref = ctk_img
                except Exception:
                    pass
        else:
            nombre_sidebar = "RepuestosDB"

        ctk.CTkLabel(
            logo_frame, text=nombre_sidebar,
            font=(F, 16, "bold"), text_color=COLORS["accent"],
        ).pack(padx=16, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            logo_frame, text="Sistema de Gestion",
            font=(F, 10), text_color=COLORS["text_muted"],
        ).pack(padx=16, pady=(0, 16), anchor="w")

        # Separador
        ctk.CTkFrame(self._sidebar, fg_color=COLORS["border"], height=1).grid(
            row=1, column=0, sticky="ew", pady=(0, 8),
        )

        # Botones de navegación
        for i, (*nav_data, is_coming_soon) in enumerate(self.NAV_ITEMS):
            icono, label, key, is_external = nav_data
            if is_coming_soon:
                # Botón deshabilitado con estilo "próximamente"
                btn = ctk.CTkButton(
                    self._sidebar,
                    text=f"  {icono}  {label}  🔒",
                    font=(F, 13),
                    height=44,
                    anchor="w",
                    fg_color="transparent",
                    hover_color=COLORS["sidebar_btn"],
                    text_color=COLORS["border"],
                    corner_radius=10,
                    state="disabled",
                    command=lambda: None,
                )
            else:
                btn = ctk.CTkButton(
                    self._sidebar,
                    text=f"  {icono}  {label}",
                    font=(F, 13),
                    height=44,
                    anchor="w",
                    fg_color=COLORS["sidebar_btn"] if not is_external else "#1a2a1a",
                    hover_color=COLORS["sidebar_active"],
                    text_color=COLORS.get("sidebar_text", "#e0e0e0") if not is_external else COLORS["success"],
                    corner_radius=10,
                    command=lambda k=key: self._navigate(k),
                )
            btn.grid(row=i + 2, column=0, padx=10, pady=3, sticky="ew")
            if not is_external and not is_coming_soon:
                self._nav_buttons[key] = btn

        # Badge de usuario (parte baja del sidebar)
        rol_color = COLORS["accent"] if self._rol == "Admin" else COLORS["success"]
        badge = ctk.CTkFrame(self._sidebar, fg_color=COLORS["bg_card"], corner_radius=12)
        badge.grid(row=10, column=0, padx=10, pady=(0, 16), sticky="sew")

        ctk.CTkLabel(
            badge, text=f"👤  {self._usuario_nombre}",
            font=(F, 12, "bold"), text_color=COLORS["text_primary"], anchor="w",
        ).pack(padx=14, pady=(12, 2), anchor="w")

        ctk.CTkLabel(
            badge, text=self._rol,
            font=(F, 11), text_color=rol_color, anchor="w",
        ).pack(padx=14, pady=(0, 12), anchor="w")

    def _build_pages(self):
        """Crea todos los frames de página y los oculta."""
        self._pages["inventario"] = InventarioPage(
            self._content,
            dao=self._dao,
            es_admin=self._es_admin,
            rol=self._rol,
        )
        self._pages["proveedores"] = ProveedoresPage(self._content)
        self._pages["deudores"] = DeudoresPage(self._content)
        self._pages["reportes"] = ReportesPage(self._content)
        self._pages["notificaciones"] = NotificacionesPage(self._content)
        self._pages["configuracion"] = ConfiguracionPage(self._content, self)

        # Colocar todos en el mismo slot y ocultarlos
        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------

    def _navigate(self, key: str):
        """Cambia la página activa o abre el POS como ventana."""
        if key == "pos":
            from ui.punto_de_venta import PuntoDeVentaWindow
            def _on_pos_closed():
                # Actualizar estadísticas al volver del POS
                if "reportes" in self._pages:
                    self._pages["reportes"].refresh()
                if "inventario" in self._pages:
                    self._pages["inventario"]._load_inventory()
                if "notificaciones" in self._pages:
                    self._pages["notificaciones"].refresh()
                self.after(100, self._refresh_notif_badge)
            PuntoDeVentaWindow(parent=self, on_venta_procesada_callback=_on_pos_closed)
            return

        # Actualizar estado visual de los botones
        for nav_key, btn in self._nav_buttons.items():
            if nav_key == key:
                btn.configure(fg_color=COLORS["sidebar_active"], text_color=COLORS["sidebar_active_text"],
                              font=(F, 13, "bold"))
            else:
                btn.configure(fg_color=COLORS["sidebar_btn"], text_color=COLORS.get("sidebar_text", "#e0e0e0"),
                              font=(F, 13))

        # Ocultar página actual y mostrar la nueva
        if self._active_key and self._active_key in self._pages:
            self._pages[self._active_key].grid_remove()

        self._pages[key].grid()

        # Refrescar datos según la sección
        if key == "reportes":
            self._pages["reportes"].refresh()
        elif key == "deudores":
            self._pages["deudores"].refresh()
            # Actualizar el badge de alertas (puede haber cambiado alguna deuda)
            self.after(100, self._refresh_notif_badge)
        elif key == "proveedores":
            self._pages["proveedores"].refresh()
        elif key == "notificaciones":
            self._pages["notificaciones"].refresh()
            # Resetear badge al ver las notificaciones
            if "notificaciones" in self._nav_buttons:
                self._nav_buttons["notificaciones"].configure(
                    text="  🔔  Notificaciones",
                    text_color=COLORS["text_primary"],
                )

        self._active_key = key

    def _refresh_notif_badge(self):
        """
        Cuenta alertas activas y actualiza el botón del sidebar con un badge rojo.
        Se llama al iniciar sesión y cada vez que cambia una página relevante.
        """
        try:
            inv_dao = InventarioDAO()
            stock_bajo = inv_dao.listar_stock_bajo()
        except Exception:
            stock_bajo = []
        try:
            deu_dao = DeudoresDAO()
            vencidos = deu_dao.listar_vencidos()
        except Exception:
            vencidos = []

        total = len(stock_bajo) + len(vencidos)

        if "notificaciones" not in self._nav_buttons:
            return

        btn = self._nav_buttons["notificaciones"]
        if total > 0:
            btn.configure(
                text=f"  🔔  Notificaciones  🔴 {total}",
                text_color="#e05c5c",
            )
        else:
            btn.configure(
                text="  🔔  Notificaciones",
                text_color=COLORS.get("sidebar_text", "#e0e0e0"),
            )


# ===========================================================================
# Página: Configuración (temas, apariencia, actualizaciones)
# ===========================================================================

# Paletas de temas disponibles (sincronizadas con app.py)
TEMAS = {}
for _tn, _tp in _PALETAS.items():
    TEMAS[_tn] = {
        "accent":              _tp["accent"],
        "accent_hover":        _tp["accent_hover"],
        "success":             _tp["success"],
        "danger":              _tp["danger"],
        "bg_root":             _tp["bg_root"],
        "bg_card":             _tp["bg_card"],
        "bg_input":            _tp["bg_input"],
        "sidebar":             _tp.get("sidebar", _tp.get("bg_sidebar", _tp["bg_root"])),
        "sidebar_btn":         _tp.get("sidebar_btn", _tp.get("bg_input", _tp["bg_root"])),
        "sidebar_active":      _tp.get("sidebar_active", _tp["accent"]),
        "sidebar_active_text": _tp.get("sidebar_active_text", "#ffffff"),
    }

THEME_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "theme.json"


def _cargar_tema_guardado() -> str:
    return _leer_nombre_tema()


def _guardar_tema(nombre: str):
    try:
        import json
        THEME_CONFIG_PATH.parent.mkdir(exist_ok=True)
        with open(THEME_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"tema": nombre}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class ConfiguracionPage(ctk.CTkFrame):
    """Página de configuración: temas, apariencia, actualizaciones."""

    def __init__(self, parent, dashboard_ref, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dash = dashboard_ref
        self._tema_actual = _cargar_tema_guardado()
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # ── Banner ────────────────────────────────────────────────────
        banner = ctk.CTkFrame(self, fg_color="#0a0d1a", corner_radius=0, height=110)
        banner.grid(row=0, column=0, sticky="ew")
        banner.grid_propagate(False)
        banner.grid_columnconfigure(0, weight=1)
        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.grid(row=0, column=0, padx=28, pady=0, sticky="nsew")
        inner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(inner, text="⚙️  Configuración del Sistema",
                     font=(F, 26, "bold"), text_color=COLORS["accent"],
                     anchor="w").grid(row=0, column=0, pady=(20, 0), sticky="w")
        ctk.CTkLabel(inner, text="Temas de color, apariencia y actualizaciones del programa",
                     font=(F, 12), text_color=COLORS["text_muted"],
                     anchor="w").grid(row=1, column=0, pady=(2, 0), sticky="w")

        # ── Scroll ────────────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_temas()
        self._build_apariencia()
        self._build_actualizaciones()
        self._build_rollback()
        self._build_info()

    # ------------------------------------------------------------------
    def _build_temas(self):
        self._seccion(self._scroll, 0, "🎨  Temas de Color")

        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=16)
        card.grid(row=1, column=0, padx=28, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(tuple(range(len(TEMAS))), weight=1)

        ctk.CTkLabel(card, text="Selecciona un tema de color. Se aplicará al reiniciar el programa.",
                     font=(F, 11), text_color=COLORS["text_muted"],
                     anchor="w").grid(row=0, column=0, columnspan=len(TEMAS),
                                      padx=20, pady=(16, 12), sticky="w")

        self._tema_btns: dict[str, ctk.CTkButton] = {}
        for col, (nombre, paleta) in enumerate(TEMAS.items()):
            es_actual = (nombre == self._tema_actual)
            # Muestra un mini preview del tema como botón
            btn_frame = ctk.CTkFrame(card,
                                     fg_color=paleta["bg_card"],
                                     corner_radius=12,
                                     border_width=3,
                                     border_color=paleta["accent"] if es_actual else paleta["bg_input"])
            btn_frame.grid(row=1, column=col, padx=8, pady=(0, 16), sticky="nsew")
            btn_frame.grid_columnconfigure(0, weight=1)

            # Mini sidebar
            ctk.CTkFrame(btn_frame, fg_color=paleta["sidebar"],
                         width=16, corner_radius=0).grid(
                row=0, column=0, rowspan=4, sticky="nsw")

            # Accent bar
            ctk.CTkFrame(btn_frame, fg_color=paleta["accent"],
                         height=4, corner_radius=2).grid(
                row=0, column=0, padx=(20, 8), pady=(12, 4), sticky="ew")

            ctk.CTkLabel(btn_frame, text=nombre, font=(F, 11, "bold"),
                         text_color=paleta["accent"], anchor="center").grid(
                row=1, column=0, padx=(20, 8), pady=(0, 4), sticky="ew")

            ctk.CTkLabel(btn_frame,
                         text="✓ Activo" if es_actual else "",
                         font=(F, 10), text_color=paleta["success"],
                         anchor="center").grid(row=2, column=0, padx=(20, 8), sticky="ew")

            ctk.CTkButton(btn_frame, text="Aplicar",
                          height=28, font=(F, 11, "bold"),
                          fg_color=paleta["accent"], hover_color=paleta["accent_hover"],
                          text_color="#fff", corner_radius=8,
                          command=lambda n=nombre: self._aplicar_tema(n)).grid(
                row=3, column=0, padx=(20, 8), pady=(4, 12), sticky="ew")

            self._tema_btns[nombre] = btn_frame

        # ── Banner de reinicio ─────────────────────────────────────────
        restart_bar = ctk.CTkFrame(card, fg_color="#1a2a0a", corner_radius=10)
        restart_bar.grid(row=2, column=0, columnspan=len(TEMAS), padx=16, pady=(0, 16), sticky="ew")
        restart_bar.grid_columnconfigure(0, weight=1)
        tema_guardado = _cargar_tema_guardado()
        ctk.CTkLabel(
            restart_bar,
            text=f"✅ Tema seleccionado: «{tema_guardado}»  —  Reinicia el programa para aplicar los cambios de color.",
            font=(F, 11), text_color="#3ecf8e", anchor="w",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        ctk.CTkButton(
            restart_bar,
            text="🔄  Reiniciar ahora",
            font=(F, 12, "bold"), height=34, width=160,
            fg_color="#1e3820", hover_color="#3ecf8e",
            text_color="#3ecf8e", corner_radius=8,
            command=self._reiniciar_app,
        ).grid(row=0, column=1, padx=(0, 16), pady=10)

    def _aplicar_tema(self, nombre: str):
        _guardar_tema(nombre)
        self._tema_actual = nombre
        # Rebuild cards to update checkmarks
        for w in self._scroll.winfo_children():
            w.destroy()
        self._build_temas()
        self._build_apariencia()
        self._build_actualizaciones()
        self._build_rollback()
        self._build_info()

    def _reiniciar_app(self):
        """Guarda estado y reinicia el proceso para aplicar el nuevo tema."""
        import subprocess, sys, os
        script = Path(__file__).resolve().parent.parent / "main.py"
        try:
            self.winfo_toplevel().destroy()
        except Exception:
            pass
        subprocess.Popen([sys.executable, str(script)], cwd=str(script.parent))
        sys.exit(0)

    # ------------------------------------------------------------------
    def _build_apariencia(self):
        self._seccion(self._scroll, 4, "🖥️  Apariencia")

        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=16)
        card.grid(row=5, column=0, padx=28, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # Modo claro/oscuro
        fila = ctk.CTkFrame(card, fg_color=COLORS["bg_input"], corner_radius=8)
        fila.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew", columnspan=2)
        fila.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fila, text="Modo de interfaz", font=(F, 12),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=0, padx=16, pady=12, sticky="w")
        modo_actual = ctk.get_appearance_mode()
        modo_var = ctk.StringVar(value=modo_actual)
        seg = ctk.CTkSegmentedButton(
            fila, values=["Dark", "Light", "System"],
            variable=modo_var, font=(F, 11),
            command=lambda v: ctk.set_appearance_mode(v),
            height=32,
        )
        seg.grid(row=0, column=1, padx=16, pady=12, sticky="e")

        # Escala de la interfaz
        fila2 = ctk.CTkFrame(card, fg_color="transparent", corner_radius=8)
        fila2.grid(row=1, column=0, padx=12, pady=4, sticky="ew", columnspan=2)
        fila2.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fila2, text="Escala de la interfaz", font=(F, 12),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=0, padx=16, pady=12, sticky="w")
        escala_var = ctk.StringVar(value="100%")
        escala_seg = ctk.CTkSegmentedButton(
            fila2, values=["80%", "90%", "100%", "110%", "120%"],
            variable=escala_var, font=(F, 11),
            command=lambda v: ctk.set_widget_scaling(int(v.replace("%", "")) / 100),
            height=32,
        )
        escala_seg.grid(row=0, column=1, padx=16, pady=12, sticky="e")

        # Animaciones
        fila3 = ctk.CTkFrame(card, fg_color=COLORS["bg_input"], corner_radius=8)
        fila3.grid(row=2, column=0, padx=12, pady=4, sticky="ew", columnspan=2)
        fila3.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fila3, text="Radio de esquinas", font=(F, 12),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=0, padx=16, pady=12, sticky="w")
        radio_var = ctk.StringVar(value="Redondeado")
        ctk.CTkSegmentedButton(
            fila3, values=["Cuadrado", "Redondeado", "Muy redondeado"],
            variable=radio_var, font=(F, 11),
            command=self._cambiar_radio,
            height=32,
        ).grid(row=0, column=1, padx=16, pady=12, sticky="e")

        # Sidebar compacta
        fila4 = ctk.CTkFrame(card, fg_color="transparent", corner_radius=8)
        fila4.grid(row=3, column=0, padx=12, pady=(4, 12), sticky="ew", columnspan=2)
        fila4.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fila4, text="Tamaño de fuente global", font=(F, 12),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=0, padx=16, pady=12, sticky="w")
        font_var = ctk.StringVar(value="Normal")
        ctk.CTkSegmentedButton(
            fila4, values=["Pequeño", "Normal", "Grande"],
            variable=font_var, font=(F, 11),
            command=lambda v: ctk.set_widget_scaling({"Pequeño": 0.9, "Normal": 1.0, "Grande": 1.15}.get(v, 1.0)),
            height=32,
        ).grid(row=0, column=1, padx=16, pady=12, sticky="e")

    def _cambiar_radio(self, valor: str):
        radios = {"Cuadrado": 0, "Redondeado": 8, "Muy redondeado": 20}
        r = radios.get(valor, 8)
        ctk.set_default_color_theme("blue")  # reset base
        # CustomTkinter no expone API directa; mostramos tip
        from tkinter import messagebox
        messagebox.showinfo("Consejo", f"Radio {valor} ({r}px) guardado.\nSe aplicará al reiniciar.")

    # ------------------------------------------------------------------
    def _build_actualizaciones(self):
        self._seccion(self._scroll, 6, "⬇️  Actualizaciones Automáticas")

        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=16)
        card.grid(row=7, column=0, padx=28, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="🚀", font=(F, 52)).grid(
            row=0, column=0, rowspan=3, padx=(24, 16), pady=24, sticky="n")

        ctk.CTkLabel(card, text="Actualización desde GitHub",
                     font=(F, 16, "bold"), text_color=COLORS["text_primary"],
                     anchor="w").grid(row=0, column=1, padx=(0, 20), pady=(24, 2), sticky="w")

        local_v = get_local_version()
        ctk.CTkLabel(card, text=f"Versión instalada actualmente: {local_v}",
                     font=(F, 12), text_color=COLORS["text_muted"],
                     anchor="w").grid(row=1, column=1, padx=(0, 20), pady=0, sticky="w")

        ctk.CTkLabel(card,
                     text="El programa comprobará si hay una nueva versión disponible en GitHub.\n"
                          "Si existe, descargará los cambios y se reiniciará automáticamente.",
                     font=(F, 11), text_color=COLORS["text_muted"],
                     anchor="w", justify="left").grid(
            row=2, column=1, padx=(0, 20), pady=(4, 0), sticky="w")

        ctk.CTkButton(
            card, text="🔍  Buscar Actualizaciones",
            font=(F, 13, "bold"), height=42, width=220,
            fg_color=COLORS["accent"], hover_color="#3a6fd8",
            text_color="#fff", corner_radius=12,
            command=self._on_buscar_actualizacion,
        ).grid(row=3, column=0, columnspan=2, padx=24, pady=(12, 8), sticky="w")

    # ------------------------------------------------------------------
    def _build_rollback(self):
        self._seccion(self._scroll, 10, "⏪  Rollback — Deshacer Última Actualización")

        card = ctk.CTkFrame(self._scroll, fg_color="#1a0505", corner_radius=16,
                             border_width=1, border_color="#4a1010")
        card.grid(row=11, column=0, padx=28, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="⏪", font=(F, 48)).grid(
            row=0, column=0, rowspan=2, padx=(24, 16), pady=20, sticky="n")

        from utils.updater import _load_rollback_tag
        prev_tag = _load_rollback_tag()
        prev_txt = prev_tag if prev_tag else "No hay versión anterior guardada"

        ctk.CTkLabel(card, text="Botón de Pánico — Rollback",
                     font=(F, 15, "bold"), text_color="#e05c5c",
                     anchor="w").grid(row=0, column=1, padx=(0, 20), pady=(20, 2), sticky="w")
        ctk.CTkLabel(card, text=f"Versión anterior disponible: {prev_txt}\n"
                                 "Revierte el código al estado anterior. Datos y configuración intactos.",
                     font=(F, 11), text_color=COLORS["text_muted"],
                     anchor="w", justify="left").grid(
            row=1, column=1, padx=(0, 20), pady=(0, 20), sticky="w")

        ctk.CTkButton(
            card, text="🔴  Deshacer última actualización (Rollback)",
            font=(F, 13, "bold"), height=42,
            fg_color="#b91c1c", hover_color="#991b1b",
            text_color="#fff", corner_radius=12,
            state="normal" if prev_tag else "disabled",
            command=self._on_rollback,
        ).grid(row=2, column=0, columnspan=2, padx=24, pady=(0, 24), sticky="w")

    # ------------------------------------------------------------------
    def _build_info(self):
        self._seccion(self._scroll, 8, "ℹ️  Información del Sistema")

        info_card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"], corner_radius=16)
        info_card.grid(row=9, column=0, padx=28, pady=(0, 28), sticky="ew")
        info_card.grid_columnconfigure(1, weight=1)

        import sys as _sys, platform
        local_v = get_local_version()
        info_items = [
            ("Versión del sistema",    local_v),
            ("Repositorio",            "github.com/XekRed/inventario-repuestos"),
            ("Python",                 _sys.version.split()[0]),
            ("Sistema Operativo",      platform.system() + " " + platform.release()),
            ("Tema activo",            self._tema_actual),
        ]
        for i, (label, val) in enumerate(info_items):
            row_f = ctk.CTkFrame(info_card,
                                  fg_color=COLORS["bg_input"] if i % 2 == 0 else "transparent",
                                  corner_radius=8)
            row_f.grid(row=i, column=0, padx=12, pady=2, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_f, text=label, font=(F, 12), text_color=COLORS["text_muted"],
                         anchor="w").grid(row=0, column=0, padx=16, pady=10, sticky="w")
            ctk.CTkLabel(row_f, text=val, font=(F, 12, "bold"), text_color=COLORS["text_primary"],
                         anchor="e").grid(row=0, column=1, padx=16, pady=10, sticky="e")

        ctk.CTkFrame(info_card, fg_color="transparent", height=8).grid(
            row=len(info_items), column=0)

    # ------------------------------------------------------------------
    def _seccion(self, parent, row, titulo):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, padx=28, pady=(20, 8), sticky="ew")
        ctk.CTkLabel(f, text=titulo, font=(F, 14, "bold"),
                     text_color=COLORS["accent"], anchor="w").pack(side="left")

    def _on_buscar_actualizacion(self):
        abrir_actualizador(self._dash)

    def _on_rollback(self):
        abrir_rollback(self._dash)
