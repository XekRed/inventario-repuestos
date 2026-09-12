# -*- coding: utf-8 -*-
"""
ui/estadisticas_rentabilidad.py
================================
Ventana con estadísticas de rentabilidad por producto.

Muestra:
  - Tabla: Producto | Unidades Vendidas | P.Costo | P.Venta | Margen % | Ganancia Total
  - Ordena por Margen % o Ganancia Total
  - Mensaje de datos insuficientes si < 5 ventas
"""

import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from collections import defaultdict

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.app import COLORS as _AC, FONT_FAMILY
from database.inventario_db import InventarioDAO

FONT = FONT_FAMILY
C = {
    "bg":       _AC["bg_root"],
    "card":     _AC["bg_card"],
    "input":    _AC["bg_input"],
    "border":   _AC["border"],
    "accent":   _AC["accent"],
    "success":  _AC["success"],
    "danger":   _AC["danger"],
    "text":     _AC["text_primary"],
    "muted":    _AC["text_muted"],
    "row_even": _AC["row_even"],
    "row_odd":  _AC["row_odd"],
    "row_sel":  _AC["row_selected"],
}

MIN_VENTAS = 5  # mínimo de ventas para mostrar estadísticas


class EstadisticasRentabilidadWindow(ctk.CTkToplevel):
    """Ventana de estadísticas de rentabilidad por producto."""

    COLS = [
        ("producto",       "Producto",            220, "w"),
        ("unidades",       "Unid. Vendidas",       100, "center"),
        ("precio_costo",   "Costo (USD)",           90, "e"),
        ("precio_venta",   "Precio Venta (USD)",   110, "e"),
        ("margen_pct",     "Margen %",              90, "center"),
        ("ganancia_total", "Ganancia Total (USD)", 140, "e"),
    ]

    def __init__(self, parent, ventas_dao):
        super().__init__(parent)
        self._ventas_dao = ventas_dao
        self._inv_dao    = InventarioDAO()
        self._sort_key   = "ganancia_total"
        self._sort_asc   = False

        self.title("📈 Estadísticas de Rentabilidad")
        self.geometry("900x580")
        self.minsize(750, 480)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()
        self._center()
        self._build()
        self._cargar()

    def _center(self):
        self.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        w, h = 900, 580
        self.geometry(f"{w}x{h}+{px + (pw-w)//2}+{py + (ph-h)//2}")

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
        hdr.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(hdr, text="📈  Rentabilidad por Producto",
                     font=(FONT, 18, "bold"), text_color=C["accent"]).grid(
            row=0, column=0, padx=(0, 16))

        ctk.CTkLabel(hdr, text="Ordenar por:", font=(FONT, 11),
                     text_color=C["muted"]).grid(row=0, column=1, padx=(0, 6))

        self._sort_var = ctk.StringVar(value="Ganancia Total ↓")
        ctk.CTkOptionMenu(
            hdr, variable=self._sort_var,
            values=["Ganancia Total ↓", "Ganancia Total ↑",
                    "Margen % ↓", "Margen % ↑",
                    "Unidades Vendidas ↓", "Unidades Vendidas ↑"],
            font=(FONT, 11), fg_color=C["input"], text_color=C["text"],
            button_color=C["accent"], button_hover_color=C["border"],
            corner_radius=8, width=200,
            command=lambda _: self._cargar(),
        ).grid(row=0, column=2, padx=(0, 8), sticky="w")

        ctk.CTkButton(
            hdr, text="🔄 Actualizar", width=110, height=32, font=(FONT, 11),
            fg_color=C["input"], hover_color=C["border"], text_color=C["accent"],
            corner_radius=8, command=self._cargar,
        ).grid(row=0, column=3, padx=(0, 0))

        # ── Tabla ────────────────────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        card.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Rent.Treeview",
                         background=C["card"], foreground=C["text"],
                         fieldbackground=C["card"], rowheight=32,
                         font=(FONT, 11), borderwidth=0)
        style.configure("Rent.Treeview.Heading",
                         background=C["input"], foreground=C["muted"],
                         font=(FONT, 10, "bold"), borderwidth=0, relief="flat")
        style.map("Rent.Treeview",
                   background=[("selected", C["row_sel"])],
                   foreground=[("selected", C["text"])])

        col_ids = [c[0] for c in self.COLS]
        self._tree = ttk.Treeview(card, columns=col_ids, show="headings",
                                   style="Rent.Treeview", selectmode="browse")
        for col_id, heading, width, anchor in self.COLS:
            self._tree.heading(col_id, text=heading, anchor=anchor)
            self._tree.column(col_id, width=width, anchor=anchor,
                               minwidth=40, stretch=(col_id == "producto"))

        self._tree.tag_configure("even",  background=C["row_even"])
        self._tree.tag_configure("odd",   background=C["row_odd"])
        self._tree.tag_configure("high",  background="#1a3a20", foreground=C["success"])
        self._tree.tag_configure("low",   background="#2a1a1a", foreground=C["danger"])

        vsb = ttk.Scrollbar(card, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns", pady=8)

        # ── Pie de pantalla ──────────────────────────────────────────────
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")
        self._lbl_resumen = ctk.CTkLabel(
            foot, text="", font=(FONT, 11, "bold"), text_color=C["muted"])
        self._lbl_resumen.pack(side="left")

    def _cargar(self):
        """Carga y calcula estadísticas de rentabilidad."""
        for row in self._tree.get_children():
            self._tree.delete(row)

        ventas = self._ventas_dao.listar_ventas()
        if len(ventas) < MIN_VENTAS:
            self._lbl_resumen.configure(
                text=f"⚠  Aún no hay suficientes datos para estadísticas "
                     f"({len(ventas)} venta(s) registradas — se necesitan al menos {MIN_VENTAS}).",
                text_color=C["danger"],
            )
            return

        # Calcular ventas por producto
        prod_ventas: dict[str, dict] = {}  # nombre_producto -> {unidades, subtotal, id_producto}
        for venta in ventas:
            try:
                detalles = self._ventas_dao.obtener_detalles_venta(venta["id"])
            except Exception:
                continue
            for d in detalles:
                nombre = d.get("nombre_producto", "?")
                pid    = d.get("id_producto", 0)
                if nombre not in prod_ventas:
                    prod_ventas[nombre] = {"unidades": 0, "subtotal": 0.0, "id": pid}
                prod_ventas[nombre]["unidades"] += d.get("cantidad", 0)
                prod_ventas[nombre]["subtotal"] += float(d.get("subtotal", 0))

        # Obtener precio de costo para cada producto
        todos = self._inv_dao.listar_todos()
        costo_map = {p["nombre"]: float(p.get("precio_entrada", 0)) for p in todos}

        rows_data = []
        for nombre, data in prod_ventas.items():
            unidades = data["unidades"]
            subtotal = data["subtotal"]
            costo_u  = costo_map.get(nombre, 0.0)
            precio_v = (subtotal / unidades) if unidades > 0 else 0.0
            ganancia = subtotal - (costo_u * unidades)
            margen   = ((precio_v - costo_u) / precio_v * 100) if precio_v > 0 else 0.0
            rows_data.append({
                "producto":       nombre,
                "unidades":       unidades,
                "precio_costo":   costo_u,
                "precio_venta":   precio_v,
                "margen_pct":     margen,
                "ganancia_total": ganancia,
            })

        # Ordenar
        sort_opt = self._sort_var.get()
        key_map = {
            "Ganancia Total": "ganancia_total",
            "Margen %":       "margen_pct",
            "Unidades Vendidas": "unidades",
        }
        sort_field = "ganancia_total"
        asc = False
        for label, field in key_map.items():
            if label in sort_opt:
                sort_field = field
                asc = "↑" in sort_opt
                break
        rows_data.sort(key=lambda r: r[sort_field], reverse=not asc)

        # Insertar filas
        max_ganancia = max((r["ganancia_total"] for r in rows_data), default=1)
        for i, r in enumerate(rows_data):
            margen = r["margen_pct"]
            if margen >= 40 and r["ganancia_total"] > 0:
                tag = "high"
            elif margen < 10 or r["ganancia_total"] < 0:
                tag = "low"
            else:
                tag = "even" if i % 2 == 0 else "odd"

            margen_str = f"{margen:+.1f}%" if margen != 0 else "0%"
            self._tree.insert("", "end", tags=(tag,), values=(
                r["producto"],
                r["unidades"],
                f"${r['precio_costo']:.2f}",
                f"${r['precio_venta']:.2f}",
                margen_str,
                f"${r['ganancia_total']:,.2f}",
            ))

        total_productos = len(rows_data)
        total_ganancia  = sum(r["ganancia_total"] for r in rows_data)
        margen_prom     = sum(r["margen_pct"] for r in rows_data) / total_productos if total_productos else 0

        self._lbl_resumen.configure(
            text=(f"{total_productos} producto(s)  |  "
                  f"Ganancia total: ${total_ganancia:,.2f} USD  |  "
                  f"Margen promedio: {margen_prom:.1f}%  |  "
                  f"🟢 Alto margen (≥40%)  🔴 Bajo margen (<10%)"),
            text_color=C["muted"],
        )
