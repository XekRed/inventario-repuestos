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
from database.inventario_db import inicializar_db, InventarioDAO, VentasDAO, DeudoresDAO, CuentasPorPagarDAO  # noqa: E402
from ui.app import (  # noqa: E402
    SearchBar, FormPanel, InventoryTable, DetailModal,
    COLORS, FONT_FAMILY,
)
from ui.proveedores import ProveedoresPage  # noqa: E402

# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

F = FONT_FAMILY   # alias corto

# Colores extra para la sidebar
C_SIDEBAR     = "#13151e"
C_SIDEBAR_BTN = "#1c1f2d"
C_ACTIVE_BTN  = "#2a3a6a"
C_ACTIVE_TEXT = "#4f8ef7"


# ===========================================================================
# Página: Inventario (embebida)
# ===========================================================================

class InventarioPage(ctk.CTkFrame):
    """
    Frame completo de inventario reutilizando FormPanel, SearchBar,
    InventoryTable y DetailModal de ui/app.py.
    """

    def __init__(self, parent, dao: InventarioDAO, es_admin: bool,
                 rol: str, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._dao      = dao
        self._es_admin = es_admin
        self._rol      = rol
        self._all_rows: list[dict] = []
        self._form     = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1 if es_admin else 0, weight=1)

        self._build()
        self._load_inventory()

    # ------------------------------------------------------------------
    def _build(self):
        # ── Barra de búsqueda ─────────────────────────────────────────
        span = 2 if self._es_admin else 1
        self._search_bar = SearchBar(self, on_search_callback=self._on_search)
        self._search_bar.grid(
            row=0, column=0, columnspan=span,
            padx=16, pady=(12, 4), sticky="ew",
        )

        # ── Formulario (solo Admin) ───────────────────────────────────
        if self._es_admin:
            self._form = FormPanel(
                self,
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
        self._table = InventoryTable(self)
        self._table.grid(
            row=1, column=col,
            padx=(8 if self._es_admin else 16, 16),
            pady=(4, 16), sticky="nsew",
        )
        self._table.bind_select(self._on_row_selected)
        self._table.bind_double_click(self._on_row_double_clicked)

        # ── Botones de acción ─────────────────────────────────────────
        self._build_action_buttons()

    def _build_action_buttons(self):
        btn_bar = ctk.CTkFrame(self._table, fg_color="transparent")
        btn_bar.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="e")

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
                btn_bar, text="🗑️ Eliminar",
                width=110, height=32, font=(F, 12),
                fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                text_color="#fff", corner_radius=8,
                command=self._on_delete,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                btn_bar, text="📋 Agregar Similar",
                width=140, height=32, font=(F, 12),
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

    def _on_edit(self):
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
        if not self._es_admin:
            return
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showwarning("Sin selección", "Selecciona un repuesto de la tabla primero.")
            return
        if not messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Eliminar repuesto ID {record_id}?\nEsta acción no se puede deshacer.",
            icon="warning",
        ):
            return
        try:
            self._dao.eliminar(record_id)
            if self._form:
                self._form.clear()
            self._load_inventory()
            messagebox.showinfo("Eliminado", "✅ Repuesto eliminado correctamente.")
        except Exception as e:
            messagebox.showerror("Error al eliminar", str(e))

    def _on_agregar_similar(self):
        """Copia Nombre, Marca y Modelo del producto seleccionado al formulario."""
        if not self._form:
            return
        record_id = self._table.get_selected_id()
        if record_id is None:
            messagebox.showwarning(
                "Sin selección",
                "Selecciona un producto de la tabla para agregar uno similar.",
            )
            return
        record = self._dao.obtener_por_id(record_id)
        if record is None:
            return
        self._form.load_similar(record)
        # Dar foco al campo SKU (el único campo distinto que el usuario debe llenar)
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
            fg_color="#1e3820", hover_color=COLORS["success"],
            text_color=COLORS["success"], corner_radius=10,
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
            ("Total Bs.",     f"Bs. {resumen['total_bs']:,.2f}",  "#f5c518",          "💰"),
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
        ("nombre", "Nombre/Cliente",200, "w"),
        ("telef",  "Teléfono",      120, "center"),
        ("usd",    "Monto USD",     110, "e"),
        ("bs",     "Monto Bs.",     130, "e"),
        ("fecha",  "Fecha",         130, "center"),
        ("limite", "Fecha Límite",  130, "center"),
        ("estado", "Estado",         90, "center"),
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
    """Centro de alertas con diseño premium — stock bajo, deudores vencidos."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_root"], corner_radius=0, **kwargs)
        self._inv_dao = InventarioDAO()
        from database.inventario_db import DeudoresDAO as _DD
        self._deu_dao = _DD()
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    def _build(self):
        # ── Banner superior ─────────────────────────────────────────
        banner = ctk.CTkFrame(self, fg_color="#0a0d1a", corner_radius=0, height=110)
        banner.grid(row=0, column=0, sticky="ew")
        banner.grid_propagate(False)
        banner.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.grid(row=0, column=0, padx=28, pady=0, sticky="nsew")
        inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(inner, text="🔔  Centro de Alertas",
                     font=(F, 26, "bold"), text_color=COLORS["accent"],
                     anchor="w").grid(row=0, column=0, pady=(20, 0), sticky="w")
        ctk.CTkLabel(inner, text="Monitoreo automático de stock bajo y deudas vencidas",
                     font=(F, 12), text_color=COLORS["text_muted"],
                     anchor="w").grid(row=1, column=0, pady=(2, 0), sticky="w")

        btn_f = ctk.CTkFrame(inner, fg_color="transparent")
        btn_f.grid(row=0, column=1, rowspan=2, padx=(0, 0), pady=0, sticky="e")
        ctk.CTkButton(btn_f, text="🔄  Actualizar",
                      font=(F, 12, "bold"), height=38, width=140,
                      fg_color=COLORS["bg_input"], hover_color=COLORS["accent"],
                      text_color=COLORS["accent"], corner_radius=12,
                      command=self.refresh).pack(anchor="e", pady=(20, 0))

        # ── KPI cards (se llenan en refresh) ─────────────────────
        self._kpi_frame = ctk.CTkFrame(self, fg_color="transparent", height=110)
        self._kpi_frame.grid(row=1, column=0, padx=24, pady=(18, 0), sticky="ew")
        self._kpi_frame.grid_propagate(False)
        self._kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # ── Scroll de tarjetas ───────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0)
        self._scroll.grid(row=2, column=0, padx=0, pady=(14, 0), sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

    # ------------------------------------------------------------------
    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        for w in self._kpi_frame.winfo_children():
            w.destroy()

        try:    vencidos   = self._deu_dao.listar_vencidos()
        except: vencidos   = []
        try:    stock_bajo = self._inv_dao.listar_stock_bajo(limite=5)
        except: stock_bajo = []

        n_venc  = len(vencidos)
        n_stock = len(stock_bajo)
        n_sin   = sum(1 for p in stock_bajo if p["cantidad"] == 0)
        n_ok    = max(0, 3 - (1 if n_venc else 0) - (1 if n_stock else 0) - (1 if n_sin else 0))
        total   = n_venc + n_stock

        # ── KPI cards ─────────────────────────────────────────────
        kpis = [
            ("🚨", str(n_venc),  "Deudas Vencidas", "#e05c5c", "#3d1010"),
            ("⚠️",  str(n_stock), "Stock Bajo",       "#e0954a", "#3d2200"),
            ("📦",  str(n_sin),   "Sin Stock",        "#e05c5c" if n_sin else COLORS["text_muted"], "#3d1010" if n_sin else COLORS["bg_card"]),
            ("✅",  "OK" if total == 0 else "—",
             "Todo en orden" if total == 0 else "Hay alertas",
             COLORS["success"] if total == 0 else COLORS["text_muted"],
             "#0d2e1a" if total == 0 else COLORS["bg_card"]),
        ]
        for col, (icono, valor, etiq, color, bg) in enumerate(kpis):
            c = ctk.CTkFrame(self._kpi_frame, fg_color=bg, corner_radius=16)
            c.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")
            c.grid_columnconfigure(1, weight=1)
            # Indicador lateral
            ctk.CTkFrame(c, fg_color=color, width=5, corner_radius=3).grid(
                row=0, column=0, rowspan=3, sticky="nsew", padx=(0,0), pady=0)
            ctk.CTkLabel(c, text=icono, font=(F, 30)).grid(
                row=0, column=1, rowspan=2, padx=(12,8), pady=(14,14))
            ctk.CTkLabel(c, text=valor, font=(F, 28, "bold"),
                         text_color=color, anchor="w").grid(
                row=0, column=2, padx=(0,16), pady=(18,0), sticky="sw")
            ctk.CTkLabel(c, text=etiq, font=(F, 10),
                         text_color=COLORS["text_muted"], anchor="w").grid(
                row=1, column=2, padx=(0,16), pady=(0,14), sticky="nw")

        if total == 0:
            # Banner de todo bien
            ok = ctk.CTkFrame(self._scroll, fg_color="#0d2e1a", corner_radius=20)
            ok.grid(row=0, column=0, padx=32, pady=32, sticky="ew")
            ok.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(ok, text="✅", font=(F, 72)).grid(pady=(32, 8))
            ctk.CTkLabel(ok, text="¡Todo en orden!",
                         font=(F, 26, "bold"), text_color=COLORS["success"]).grid()
            ctk.CTkLabel(ok, text="No hay alertas activas. El stock y los pagos están al día.",
                         font=(F, 13), text_color=COLORS["text_muted"]).grid(pady=(6, 32))
            return

        row = 0

        # ── Deudores Vencidos ───────────────────────────────────
        if vencidos:
            self._seccion(row, f"🚨  Deudas Vencidas  —  {n_venc} pendiente{'s' if n_venc != 1 else ''}",
                          "#e05c5c")
            row += 1
            for d in vencidos:
                dias = d.get("dias_atraso", 0)
                tel  = d.get("telefono") or ""
                urgency = "🔴 URGENTE" if dias > 7 else "⚠️ Vencido"
                self._tarjeta_deuda(
                    row,
                    nombre=d["nombre"],
                    monto_usd=d["monto_deuda_usd"],
                    monto_bs=d["monto_deuda_bs"],
                    dias=dias,
                    limite=d.get("fecha_limite_pago","?"),
                    telefono=tel,
                    urgency=urgency,
                )
                row += 1

        # ── Stock Bajo ─────────────────────────────────────────
        if stock_bajo:
            self._seccion(row, f"⚠️  Stock Bajo  —  {n_stock} producto{'s' if n_stock != 1 else ''}",
                          "#e0954a")
            row += 1
            for p in stock_bajo:
                qty = p["cantidad"]
                self._tarjeta_stock(row, p["nombre"], qty, p.get("sku",""))
                row += 1

    # ------------------------------------------------------------------
    def _seccion(self, row, titulo, color):
        f = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"],
                         corner_radius=10, height=42)
        f.grid(row=row, column=0, padx=24, pady=(20, 8), sticky="ew")
        f.grid_propagate(False)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(f, fg_color=color, width=5, corner_radius=3).grid(
            row=0, column=0, sticky="nsew", padx=(0, 0))
        ctk.CTkLabel(f, text=titulo, font=(F, 13, "bold"),
                     text_color=color, anchor="w").grid(
            row=0, column=1, padx=14, pady=0, sticky="w")

    def _tarjeta_deuda(self, row, nombre, monto_usd, monto_bs, dias, limite, telefono, urgency):
        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"],
                            corner_radius=16)
        card.grid(row=row, column=0, padx=24, pady=5, sticky="ew")
        card.grid_columnconfigure(2, weight=1)

        # Barra lateral roja
        ctk.CTkFrame(card, fg_color="#e05c5c", width=6, corner_radius=4).grid(
            row=0, column=0, rowspan=4, sticky="nsew")

        # Icono + urgencia
        left = ctk.CTkFrame(card, fg_color="transparent", width=64)
        left.grid(row=0, column=1, rowspan=4, padx=(14, 4), pady=18, sticky="n")
        ctk.CTkLabel(left, text="🚨", font=(F, 34)).pack()
        ctk.CTkLabel(left, text=urgency, font=(F, 9, "bold"),
                     text_color="#e05c5c").pack(pady=(4,0))

        # Info
        ctk.CTkLabel(card, text=nombre, font=(F, 15, "bold"),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=2, padx=(8,20), pady=(18,2), sticky="w")
        ctk.CTkLabel(card, text=f"${monto_usd:,.2f} USD  |  Bs. {monto_bs:,.2f}",
                     font=(F, 14, "bold"), text_color="#e05c5c", anchor="w").grid(
            row=1, column=2, padx=(8,20), pady=0, sticky="w")
        ctk.CTkLabel(card, text=f"Vencido hace {dias} día{'s' if dias!=1 else ''}   ·   Límite: {limite}",
                     font=(F, 10), text_color=COLORS["text_muted"], anchor="w").grid(
            row=2, column=2, padx=(8,20), pady=0, sticky="w")
        if telefono:
            ctk.CTkLabel(card, text=f"📱 {telefono}",
                         font=(F, 10), text_color=COLORS["accent"], anchor="w").grid(
                row=3, column=2, padx=(8,20), pady=(0,16), sticky="w")

    def _tarjeta_stock(self, row, nombre, qty, sku):
        urgente = qty == 0
        color   = "#e05c5c" if urgente else "#e0954a"
        bg      = "#2a1010" if urgente else "#2a1800"

        card = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"],
                            corner_radius=16)
        card.grid(row=row, column=0, padx=24, pady=5, sticky="ew")
        card.grid_columnconfigure(2, weight=1)

        ctk.CTkFrame(card, fg_color=color, width=6, corner_radius=4).grid(
            row=0, column=0, rowspan=3, sticky="nsew")

        icono = "📦" if urgente else "⚠️"
        ctk.CTkLabel(card, text=icono, font=(F, 32)).grid(
            row=0, column=1, rowspan=3, padx=(14,8), pady=14)

        ctk.CTkLabel(card, text=nombre, font=(F, 14, "bold"),
                     text_color=COLORS["text_primary"], anchor="w").grid(
            row=0, column=2, padx=(4,20), pady=(16,2), sticky="w")

        # Barra de stock visual
        bar_f = ctk.CTkFrame(card, fg_color="transparent")
        bar_f.grid(row=1, column=2, padx=(4,20), pady=2, sticky="ew")
        bar_f.grid_columnconfigure(1, weight=1)
        lbl_qty = "¡SIN STOCK!" if urgente else f"{qty} unidades"
        ctk.CTkLabel(bar_f, text=lbl_qty, font=(F, 12, "bold"),
                     text_color=color, anchor="w").grid(row=0, column=0, sticky="w")
        bar_bg = ctk.CTkFrame(bar_f, fg_color="#1a1e30", height=8, corner_radius=4)
        bar_bg.grid(row=0, column=1, padx=(12,0), sticky="ew")
        bar_bg.grid_columnconfigure(0, weight=1)
        if not urgente:
            fill_pct = min(1.0, qty / 5.0)
            ctk.CTkFrame(bar_bg, fg_color=color, height=8,
                         corner_radius=4, width=int(fill_pct * 200)).grid(
                row=0, column=0, sticky="w")

        ctk.CTkLabel(card, text=f"SKU: {sku or 'N/A'}" + ("   ·   Reordenar URGENTE" if urgente else ""),
                     font=(F, 10), text_color=COLORS["text_muted"], anchor="w").grid(
            row=2, column=2, padx=(4,20), pady=(0,14), sticky="w")


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
        ("📊",  "Reportes",           "reportes",       False),
        ("🛒",  "Punto de Venta",     "pos",            True),   # abre ventana
        ("📦",  "Inventario",         "inventario",     False),
        ("🏭",  "Proveedores",        "proveedores",    False),
        ("📋",  "Deudores (Fiado)",   "deudores",       False),
        ("🔔",  "Notificaciones",     "notificaciones", False),
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
        self._es_admin       = self._rol == "Admin"

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
            self, fg_color=C_SIDEBAR, corner_radius=0, width=220,
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
        self._sidebar.grid_rowconfigure(7, weight=1)  # push badge al fondo
        self._sidebar.grid_columnconfigure(0, weight=1)

        # Logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color=COLORS["bg_card"], corner_radius=0)
        logo_frame.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            logo_frame, text="⚡ RepuestosDB",
            font=(F, 18, "bold"), text_color=COLORS["accent"],
        ).pack(padx=16, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            logo_frame, text="Sistema de Gestión",
            font=(F, 10), text_color=COLORS["text_muted"],
        ).pack(padx=16, pady=(0, 16), anchor="w")

        # Separador
        ctk.CTkFrame(self._sidebar, fg_color=COLORS["border"], height=1).grid(
            row=1, column=0, sticky="ew", pady=(0, 8),
        )

        # Botones de navegación
        for i, (icono, label, key, is_external) in enumerate(self.NAV_ITEMS):
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"  {icono}  {label}",
                font=(F, 13),
                height=44,
                anchor="w",
                fg_color=C_SIDEBAR_BTN if not is_external else "#1a2a1a",
                hover_color=C_ACTIVE_BTN,
                text_color=COLORS["text_primary"] if not is_external else COLORS["success"],
                corner_radius=10,
                command=lambda k=key: self._navigate(k),
            )
            btn.grid(row=i + 2, column=0, padx=10, pady=3, sticky="ew")
            if not is_external:
                self._nav_buttons[key] = btn

        # Badge de usuario (parte baja del sidebar)
        rol_color = COLORS["accent"] if self._rol == "Admin" else COLORS["success"]
        badge = ctk.CTkFrame(self._sidebar, fg_color=COLORS["bg_card"], corner_radius=12)
        badge.grid(row=8, column=0, padx=10, pady=(0, 16), sticky="sew")

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
            PuntoDeVentaWindow(parent=self, on_venta_procesada_callback=_on_pos_closed)
            return

        # Actualizar estado visual de los botones
        for nav_key, btn in self._nav_buttons.items():
            if nav_key == key:
                btn.configure(fg_color=C_ACTIVE_BTN, text_color=C_ACTIVE_TEXT,
                              font=(F, 13, "bold"))
            else:
                btn.configure(fg_color=C_SIDEBAR_BTN, text_color=COLORS["text_primary"],
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
        elif key == "proveedores":
            self._pages["proveedores"].refresh()
        elif key == "notificaciones":
            self._pages["notificaciones"].refresh()
            # Resetear badge al ver las notificaciones
            if "notificaciones" in self._nav_buttons:
                self._nav_buttons["notificaciones"].configure(
                    text=f"  🔔  Notificaciones"
                )

        self._active_key = key

    def _refresh_notif_badge(self):
        """
        Cuenta alertas activas y actualiza el botón del sidebar con un badge rojo.
        Se llama al iniciar sesión y cada vez que cambia una página relevante.
        """
        try:
            inv_dao = InventarioDAO()
            stock_bajo = inv_dao.listar_stock_bajo(limite=5)
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
                text_color=COLORS["text_primary"],
            )
