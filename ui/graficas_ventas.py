# -*- coding: utf-8 -*-
"""
ui/graficas_ventas.py
=====================
Ventana con gráficas de ventas en canvas puro (sin matplotlib).
Muestra: ventas de hoy por hora, esta semana por día, este mes por día.
"""

import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.app import COLORS as _AC, FONT_FAMILY

FONT = FONT_FAMILY
C = {
    "bg":      _AC["bg_root"],
    "card":    _AC["bg_card"],
    "input":   _AC["bg_input"],
    "border":  _AC["border"],
    "accent":  _AC["accent"],
    "success": _AC["success"],
    "text":    _AC["text_primary"],
    "muted":   _AC["text_muted"],
}


class GraficasVentasWindow(ctk.CTkToplevel):
    """Ventana flotante con gráficas de ventas Diaria / Semanal / Mensual."""

    TABS = [("hoy", "📅 Hoy (por hora)"),
            ("semana", "📆 Esta semana"),
            ("mes", "🗓️ Este mes")]

    def __init__(self, parent, dao, tasa_actual: float = 1.0):
        super().__init__(parent)
        self._dao   = dao
        self._tasa  = tasa_actual
        self._tab   = "hoy"

        self.title("📊 Gráficas de Ventas")
        self.geometry("860x560")
        self.minsize(700, 460)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()
        self._center()
        self._build()
        self._dibujar()

    def _center(self):
        self.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        w, h = 860, 560
        self.geometry(f"{w}x{h}+{px + (pw-w)//2}+{py + (ph-h)//2}")

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="ew")
        hdr.grid_columnconfigure(len(self.TABS), weight=1)

        ctk.CTkLabel(hdr, text="Gráficas de Ventas", font=(FONT, 18, "bold"),
                     text_color=C["accent"]).grid(row=0, column=0, padx=(0, 24))

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for col, (key, label) in enumerate(self.TABS, start=1):
            btn = ctk.CTkButton(
                hdr, text=label, width=160, height=32, font=(FONT, 11, "bold"),
                fg_color=C["accent"] if key == self._tab else C["input"],
                hover_color=C["border"], text_color="#fff" if key == self._tab else C["muted"],
                corner_radius=8, command=lambda k=key: self._switch_tab(k),
            )
            btn.grid(row=0, column=col, padx=4)
            self._tab_btns[key] = btn

        # ── Canvas de la gráfica ─────────────────────────────────────────
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        card.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(card, bg=C["card"], highlightthickness=0)
        self._canvas.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        self._canvas.bind("<Configure>", lambda _: self._dibujar())

    def _switch_tab(self, key: str):
        self._tab = key
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(fg_color=C["accent"], text_color="#fff")
            else:
                btn.configure(fg_color=C["input"], text_color=C["muted"])
        self._dibujar()

    def _get_data(self) -> tuple[list[str], list[float], str]:
        """Devuelve (etiquetas, valores_usd, titulo) según el tab activo."""
        ventas = self._dao.listar_ventas()
        hoy    = date.today()

        if self._tab == "hoy":
            # Por hora (0-23)
            totals = defaultdict(float)
            for v in ventas:
                try:
                    dt = datetime.fromisoformat(v["fecha"])
                    if dt.date() == hoy:
                        totals[dt.hour] += float(v.get("total_usd", 0))
                except Exception:
                    pass
            labels = [f"{h:02d}h" for h in range(0, 24)]
            values = [totals.get(h, 0.0) for h in range(0, 24)]
            # Only keep up to current hour + 1
            cur_h = datetime.now().hour
            labels = labels[:cur_h + 2]
            values = values[:cur_h + 2]
            titulo = f"Ventas de hoy ({hoy.strftime('%d/%m/%Y')}) — por hora"

        elif self._tab == "semana":
            # Lunes a domingo de la semana actual
            lunes = hoy - timedelta(days=hoy.weekday())
            dias_nombre = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            totals = defaultdict(float)
            for v in ventas:
                try:
                    dt = datetime.fromisoformat(v["fecha"])
                    if lunes <= dt.date() <= lunes + timedelta(days=6):
                        totals[(dt.date() - lunes).days] += float(v.get("total_usd", 0))
                except Exception:
                    pass
            labels = [f"{dias_nombre[i]}\n{(lunes + timedelta(days=i)).strftime('%d')}" for i in range(7)]
            values = [totals.get(i, 0.0) for i in range(7)]
            titulo = f"Semana {lunes.strftime('%d/%m')} — {(lunes+timedelta(days=6)).strftime('%d/%m/%Y')}"

        else:  # mes
            import calendar
            primer_dia = hoy.replace(day=1)
            ultimo_dia = hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1])
            totals = defaultdict(float)
            for v in ventas:
                try:
                    dt = datetime.fromisoformat(v["fecha"])
                    if primer_dia <= dt.date() <= ultimo_dia:
                        totals[dt.day] += float(v.get("total_usd", 0))
                except Exception:
                    pass
            num_days = calendar.monthrange(hoy.year, hoy.month)[1]
            labels = [str(d) for d in range(1, num_days + 1)]
            values = [totals.get(d, 0.0) for d in range(1, num_days + 1)]
            titulo = f"Mes de {hoy.strftime('%B %Y')}"

        return labels, values, titulo

    def _dibujar(self):
        """Dibuja la gráfica de barras en el canvas."""
        self._canvas.delete("all")
        W = self._canvas.winfo_width()
        H = self._canvas.winfo_height()
        if W < 50 or H < 50:
            return

        labels, values, titulo = self._get_data()
        if not labels:
            return

        # Márgenes
        mx_l, mx_r, my_t, my_b = 60, 20, 50, 50

        # Título
        self._canvas.create_text(W // 2, 22, text=titulo, font=(FONT, 12, "bold"),
                                  fill=C["text"], anchor="center")

        max_val = max(values) if values else 1
        if max_val == 0:
            max_val = 1

        area_w = W - mx_l - mx_r
        area_h = H - my_t - my_b
        n = len(labels)
        bar_w = max(4, area_w // n - 4)

        # Líneas de referencia
        for pct in [0, 0.25, 0.5, 0.75, 1.0]:
            y = my_t + area_h - int(pct * area_h)
            ref_val = max_val * pct
            self._canvas.create_line(mx_l, y, W - mx_r, y,
                                      fill=C["border"], dash=(3, 5))
            self._canvas.create_text(mx_l - 6, y,
                                      text=f"${ref_val:.0f}",
                                      font=(FONT, 8), fill=C["muted"], anchor="e")

        # Barras
        accent_hex = C["accent"]
        for i, (lbl, val) in enumerate(zip(labels, values)):
            x0 = mx_l + i * (area_w // n) + 2
            x1 = x0 + bar_w
            bar_h = int((val / max_val) * area_h)
            y1 = my_t + area_h
            y0 = y1 - bar_h

            # Color dinámico: más alto = más brillante
            ratio = val / max_val if max_val > 0 else 0
            r_hex = C["success"] if ratio > 0.6 else (C["accent"] if ratio > 0.2 else C["input"])

            if bar_h > 0:
                self._canvas.create_rectangle(x0, y0, x1, y1, fill=r_hex, outline="", width=0)

            # Etiqueta encima de la barra
            if val > 0:
                self._canvas.create_text((x0 + x1) // 2, y0 - 8,
                                          text=f"${val:.0f}", font=(FONT, 7, "bold"),
                                          fill=C["text"], anchor="s")

            # Etiqueta del eje X
            self._canvas.create_text((x0 + x1) // 2, y1 + 12,
                                      text=lbl, font=(FONT, 7),
                                      fill=C["muted"], anchor="n")

        # Eje Y
        self._canvas.create_line(mx_l, my_t, mx_l, my_t + area_h, fill=C["border"], width=1)
        # Eje X
        self._canvas.create_line(mx_l, my_t + area_h, W - mx_r, my_t + area_h,
                                   fill=C["border"], width=1)
