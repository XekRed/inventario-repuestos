"""
ui/historial_ventas.py
======================
Ventana de Historial de Ventas.

Muestra todas las ventas realizadas en una tabla.
Al hacer clic en una venta se muestran los productos que llevó ese cliente.
"""

import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import VentasDAO  # noqa: E402

# ---------------------------------------------------------------------------
# Paleta (idéntica al resto del proyecto)
# ---------------------------------------------------------------------------
FONT = "Segoe UI"

C = {
    "bg":       "#0f1117",
    "card":     "#1c1f2b",
    "input":    "#252836",
    "border":   "#2e3246",
    "accent":   "#4f8ef7",
    "success":  "#3ecf8e",
    "warning":  "#e0954a",
    "danger":   "#e05c5c",
    "text":     "#e8eaf0",
    "muted":    "#8b91a7",
    "row_even": "#1c1f2b",
    "row_odd":  "#212438",
    "row_sel":  "#2a3a6a",
    "gold":     "#f5c518",
}


# ===========================================================================
# HistorialVentasWindow
# ===========================================================================

class HistorialVentasWindow(ctk.CTkToplevel):
    """
    Ventana de historial de ventas. Se abre como Toplevel desde InventarioApp.

    Layout:
      ┌──────────────────────────────────────────────────────────────────────┐
      │  Título                                    [🔄 Actualizar]          │
      ├──────────────────────────────┬───────────────────────────────────────┤
      │  Tabla de Ventas (izquierda) │  Detalles de la venta (derecha)       │
      └──────────────────────────────┴───────────────────────────────────────┘
    """

    COLS_VENTAS = [
        ("id",             "# Venta",    70,  "center"),
        ("fecha",          "Fecha",      155, "w"),
        ("nombre_cliente", "Cliente",    160, "w"),
        ("cedula_cliente", "Cédula/RIF", 110, "center"),
        ("total_usd",      "Total USD",  100, "e"),
        ("total_bs",       "Total Bs.",  120, "e"),
        ("metodo_pago",    "Método Pago",190, "w"),
    ]

    COLS_DETALLE = [
        ("nombre_producto", "Producto",      220, "w"),
        ("cantidad",        "Cant.",          60, "center"),
        ("precio_unitario", "Precio Unit.",  120, "e"),
        ("subtotal",        "Subtotal",      120, "e"),
    ]

    def __init__(self, parent, tasa_actual: float = 1.0):
        super().__init__(parent)
        self._dao         = VentasDAO()
        self._tasa_actual = tasa_actual   # para incluirla en el PDF
        self._setup_window()
        self._build()
        self._cargar_ventas()

    # ------------------------------------------------------------------
    # Configuración de ventana
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.title("📋 RepuestosDB — Historial de Ventas")
        self.geometry("1150x680")
        self.minsize(900, 500)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()

        self.update_idletasks()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        x  = px + (pw - 1150) // 2
        y  = py + (ph - 680)  // 2
        self.geometry(f"1150x680+{x}+{y}")

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        # ── Top bar ──────────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 8), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top,
            text="📋  Historial de Ventas",
            font=(FONT, 20, "bold"),
            text_color=C["accent"],
        ).grid(row=0, column=0, padx=(4, 16), sticky="w")

        ctk.CTkButton(
            top,
            text="🔄  Actualizar",
            width=120,
            height=34,
            font=(FONT, 12, "bold"),
            fg_color=C["input"],
            hover_color=C["border"],
            text_color=C["accent"],
            corner_radius=8,
            command=self._cargar_ventas,
        ).grid(row=0, column=2, padx=(0, 6), sticky="e")

        ctk.CTkButton(
            top,
            text="📄  Reporte del Día",
            width=160,
            height=34,
            font=(FONT, 12, "bold"),
            fg_color="#1e3820",
            hover_color=C["success"],
            text_color=C["success"],
            corner_radius=8,
            command=self._generar_reporte,
        ).grid(row=0, column=3, sticky="e")

        # ── Panel izquierdo: lista de ventas ─────────────────────────
        left = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        left.grid(row=1, column=0, padx=(16, 6), pady=(0, 16), sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="Ventas registradas",
            font=(FONT, 13, "bold"),
            text_color=C["text"],
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        self._lbl_total_ventas = ctk.CTkLabel(
            left, text="",
            font=(FONT, 11), text_color=C["muted"], anchor="e",
        )
        self._lbl_total_ventas.grid(row=0, column=1, padx=14, pady=(12, 6), sticky="e")

        self._ventas_tree = self._make_treeview(
            left,
            cols=self.COLS_VENTAS,
            style_name="Ventas.Treeview",
        )
        self._ventas_tree._frame.grid(
            row=1, column=0, columnspan=2,
            in_=left, padx=14, pady=(0, 14), sticky="nsew")
        self._ventas_tree.bind("<<TreeviewSelect>>", self._on_venta_seleccionada)

        # ── Panel derecho: detalle de la venta seleccionada ──────────
        right = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        right.grid(row=1, column=1, padx=(0, 16), pady=(0, 16), sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right,
            text="Detalle de la venta seleccionada",
            font=(FONT, 13, "bold"),
            text_color=C["text"],
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        # Info del cliente
        self._lbl_cliente_info = ctk.CTkLabel(
            right,
            text="Selecciona una venta para ver su detalle",
            font=(FONT, 11),
            text_color=C["muted"],
            anchor="w",
            wraplength=360,
        )
        self._lbl_cliente_info.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

        # Tabla de detalles
        self._detalle_tree = self._make_treeview(
            right,
            cols=self.COLS_DETALLE,
            style_name="Detalle.Treeview",
        )
        self._detalle_tree._frame.grid(
            row=2, column=0, in_=right, padx=14, pady=(0, 8), sticky="nsew")

        # Totales del detalle
        self._lbl_total_detalle = ctk.CTkLabel(
            right,
            text="",
            font=(FONT, 14, "bold"),
            text_color=C["success"],
            anchor="e",
        )
        self._lbl_total_detalle.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="e")

    # ------------------------------------------------------------------
    # Helper: crear Treeview con scroll
    # ------------------------------------------------------------------

    def _make_treeview(self, parent, cols: list, style_name: str) -> ttk.Treeview:
        frame = tk.Frame(parent, bg=C["card"])
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # Estilo
        style = ttk.Style()
        style.configure(
            style_name,
            background=C["card"],
            foreground=C["text"],
            fieldbackground=C["card"],
            rowheight=32,
            font=(FONT, 11),
            borderwidth=0,
        )
        style.configure(
            f"{style_name}.Heading",
            background=C["input"],
            foreground=C["muted"],
            font=(FONT, 10, "bold"),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            style_name,
            background=[("selected", C["row_sel"])],
            foreground=[("selected", C["text"])],
        )

        col_ids = [c[0] for c in cols]
        tree = ttk.Treeview(
            frame,
            columns=col_ids,
            show="headings",
            style=style_name,
            selectmode="browse",
        )
        for col_id, heading, width, anchor in cols:
            tree.heading(col_id, text=heading, anchor=anchor)
            tree.column(col_id, width=width, anchor=anchor,
                        minwidth=30, stretch=(col_id in ("nombre_cliente", "nombre_producto", "metodo_pago")))

        tree.tag_configure("even", background=C["row_even"])
        tree.tag_configure("odd",  background=C["row_odd"])

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Store frame reference on tree so caller can place it
        tree._frame = frame
        return tree

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------

    def _cargar_ventas(self):
        """Carga (o recarga) la tabla principal con todas las ventas."""
        for row in self._ventas_tree.get_children():
            self._ventas_tree.delete(row)

        ventas = self._dao.listar_ventas()
        for i, v in enumerate(ventas):
            fecha = v["fecha"].replace("T", "  ") if "T" in v["fecha"] else v["fecha"]
            tag   = "even" if i % 2 == 0 else "odd"
            self._ventas_tree.insert(
                "", "end",
                iid=str(v["id"]),
                tags=(tag,),
                values=(
                    v["id"],
                    fecha,
                    v["nombre_cliente"],
                    v["cedula_cliente"],
                    f"${v['total_usd']:,.2f}",
                    f"Bs. {v['total_bs']:,.2f}",
                    v.get("metodo_pago", "Punto"),
                ),
            )

        n = len(ventas)
        self._lbl_total_ventas.configure(text=f"{n} venta{'s' if n != 1 else ''}")

        # Limpiar detalle
        self._limpiar_detalle()

    def _on_venta_seleccionada(self, _event=None):
        """Carga el detalle de la venta que el usuario seleccionó."""
        sel = self._ventas_tree.selection()
        if not sel:
            return
        id_venta = int(sel[0])

        # Buscar info del cliente en los valores de la fila
        valores = self._ventas_tree.item(sel[0], "values")
        # valores: (id, fecha, nombre_cliente, cedula_cliente, total_usd, total_bs, metodo_pago)
        nombre, cedula, total_usd, total_bs = valores[2], valores[3], valores[4], valores[5]
        metodo = valores[6] if len(valores) > 6 else "Punto"
        self._lbl_cliente_info.configure(
            text=(
                f"👤  {nombre}   |   🪪  {cedula}\n"
                f"💵  {total_usd}   |   💰  {total_bs}\n"
                f"💳  Pago: {metodo}"
            ),
            text_color=C["text"],
        )

        # Cargar detalles
        for row in self._detalle_tree.get_children():
            self._detalle_tree.delete(row)

        detalles = self._dao.obtener_detalles_venta(id_venta)
        total = 0.0
        for i, d in enumerate(detalles):
            tag = "even" if i % 2 == 0 else "odd"
            self._detalle_tree.insert(
                "", "end",
                iid=str(d["id"]),
                tags=(tag,),
                values=(
                    d["nombre_producto"],
                    d["cantidad"],
                    f"${d['precio_unitario']:,.2f}",
                    f"${d['subtotal']:,.2f}",
                ),
            )
            total += d["subtotal"]

        self._lbl_total_detalle.configure(
            text=f"TOTAL:  ${total:,.2f} USD",
        )

    def _limpiar_detalle(self):
        """Vacía la tabla de detalle y resetea las etiquetas."""
        for row in self._detalle_tree.get_children():
            self._detalle_tree.delete(row)
        self._lbl_cliente_info.configure(
            text="Selecciona una venta para ver su detalle",
            text_color=C["muted"],
        )
        self._lbl_total_detalle.configure(text="")

    def _generar_reporte(self):
        """Genera el PDF del Reporte de Cierre de Día y lo abre."""
        import tkinter.messagebox as mb
        import subprocess
        import os
        from utils.reporte_pdf import generar_reporte_dia

        try:
            resumen = self._dao.resumen_dia()
            ventas  = self._dao.listar_ventas_del_dia()
        except Exception as e:
            mb.showerror("Error de base de datos", str(e))
            return

        if resumen["total_ventas"] == 0:
            mb.showinfo(
                "Sin ventas hoy",
                "No hay ventas registradas para el día de hoy.\n"
                "Realiza al menos una venta antes de generar el reporte.",
            )
            return

        try:
            ruta = generar_reporte_dia(
                resumen=resumen,
                ventas=ventas,
                tasa_bs=self._tasa_actual,
            )
        except Exception as e:
            mb.showerror("Error al generar PDF", str(e))
            return

        respuesta = mb.askyesno(
            "✅ Reporte generado",
            f"El reporte fue guardado en:\n\n{ruta}\n\n¿Deseas abrirlo ahora?",
        )
        if respuesta:
            try:
                os.startfile(str(ruta))          # Windows: abre con el visor PDF predeterminado
            except Exception:
                subprocess.Popen(["xdg-open", str(ruta)])  # Linux / fallback
