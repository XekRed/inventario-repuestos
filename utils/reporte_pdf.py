"""
utils/reporte_pdf.py
====================
Generación del Reporte de Cierre de Día en PDF.

Usa la librería `fpdf2` (instalar con: pip install fpdf2).

Función principal:
    generar_reporte_dia(resumen, ventas) -> Path

    Crea el PDF en la carpeta /reportes del proyecto y devuelve la ruta.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF, XPos, YPos

if TYPE_CHECKING:
    pass  # solo para type hints; no importa nada que no esté disponible

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ROOT_DIR     = Path(__file__).resolve().parent.parent
REPORTES_DIR = ROOT_DIR / "reportes"
REPORTES_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Colores (R, G, B)
# ---------------------------------------------------------------------------
COLOR_BG_HEADER  = (15,  17,  23)   # #0f1117 — fondo oscuro del encabezado
COLOR_ACCENT     = (79, 142, 247)   # #4f8ef7 — azul acento
COLOR_SUCCESS    = (62, 207, 142)   # #3ecf8e — verde éxito
COLOR_GOLD       = (245, 197, 24)   # #f5c518 — dorado (moneda)
COLOR_TEXT_DARK  = (30,  30,  40)   # texto oscuro sobre fondo blanco
COLOR_TEXT_LIGHT = (232, 234, 240)  # texto claro sobre fondo oscuro
COLOR_ROW_A      = (240, 242, 250)  # fila par
COLOR_ROW_B      = (255, 255, 255)  # fila impar
COLOR_BORDER     = (200, 204, 220)  # borde de tabla


# ===========================================================================
# Clase PDF personalizada
# ===========================================================================

class ReportePDF(FPDF):
    """Extiende FPDF con encabezado y pie de página automáticos."""

    def __init__(self, nombre_empresa: str = "RepuestosDB", fecha: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._nombre_empresa = nombre_empresa
        self._fecha_reporte  = fecha
        self.set_margins(left=18, top=18, right=18)
        self.set_auto_page_break(auto=True, margin=20)

    # ------------------------------------------------------------------
    # Encabezado de página
    # ------------------------------------------------------------------
    def header(self):
        # Banda superior oscura
        self.set_fill_color(*COLOR_BG_HEADER)
        self.rect(0, 0, 210, 28, style="F")

        # Logo / Nombre
        self.set_text_color(*COLOR_ACCENT)
        self.set_font("Helvetica", "B", 16)
        self.set_xy(18, 8)
        self.cell(0, 8, f"{self._nombre_empresa}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Sub-título
        self.set_text_color(*COLOR_TEXT_LIGHT)
        self.set_font("Helvetica", "", 9)
        self.set_x(18)
        self.cell(0, 5, "Sistema de Gestión de Inventario - Reporte de Cierre de Día",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Línea separadora (acento)
        self.set_draw_color(*COLOR_ACCENT)
        self.set_line_width(0.5)
        self.line(0, 28, 210, 28)

        self.ln(8)   # espacio después del encabezado

    # ------------------------------------------------------------------
    # Pie de página
    # ------------------------------------------------------------------
    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(1)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 155, 170)
        self.cell(0, 5,
                  f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Página {self.page_no()}",
                  align="C")


# ===========================================================================
# Función pública
# ===========================================================================

def generar_reporte_dia(
    resumen: dict,
    ventas:  list[dict],
    tasa_bs: float = 1.0,
) -> Path:
    """
    Genera el PDF del Reporte de Cierre de Día.

    Args:
        resumen: dict devuelto por VentasDAO.resumen_dia().
        ventas:  list de ventas del día (VentasDAO.listar_ventas_del_dia()).
        tasa_bs: Tasa del dólar usada en el cierre (informativa).

    Returns:
        Path: Ruta absoluta al archivo PDF generado.
    """
    fecha      = resumen.get("fecha", datetime.now().strftime("%Y-%m-%d"))
    fecha_disp = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d de %B de %Y")

    pdf = ReportePDF(nombre_empresa="RepuestosDB", fecha=fecha)
    pdf.add_page()

    # ── Título del reporte ────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*COLOR_BG_HEADER)
    pdf.cell(0, 10, "Reporte de Cierre de Día", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(0, 6, fecha_disp, align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # ── Tarjetas de resumen ───────────────────────────────────────────
    _draw_summary_cards(pdf, resumen, tasa_bs)
    pdf.ln(8)

    # ── Tabla de productos vendidos ───────────────────────────────────
    if resumen.get("productos"):
        _draw_productos_table(pdf, resumen["productos"])
        pdf.ln(8)

    # ── Tabla de transacciones del día ────────────────────────────────
    if ventas:
        _draw_ventas_table(pdf, ventas)

    # ── Guardar ───────────────────────────────────────────────────────
    nombre_archivo = f"reporte_{fecha}.pdf"
    ruta           = REPORTES_DIR / nombre_archivo
    pdf.output(str(ruta))
    return ruta


# ===========================================================================
# Helpers de dibujo
# ===========================================================================

def _draw_summary_cards(pdf: ReportePDF, resumen: dict, tasa_bs: float):
    """Dibuja 3 tarjetas con los KPIs principales."""
    cards = [
        ("Transacciones",  str(resumen["total_ventas"]),         COLOR_ACCENT),
        ("Total USD",      f"${resumen['total_usd']:,.2f}",      COLOR_SUCCESS),
        ("Total Bs (VES)", f"Bs. {resumen['total_bs']:,.2f}",    COLOR_GOLD),
    ]

    card_w  = 54
    card_h  = 26
    gap     = 5
    start_x = pdf.get_x()
    y       = pdf.get_y()

    for i, (titulo, valor, color) in enumerate(cards):
        x = start_x + i * (card_w + gap)

        # Fondo de la tarjeta
        pdf.set_fill_color(245, 247, 255)
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.6)
        pdf.rect(x, y, card_w, card_h, style="FD", round_corners=True, corner_radius=3)

        # Barra de color superior (decorativa)
        pdf.set_fill_color(*color)
        pdf.rect(x, y, card_w, 3, style="F")

        # Título
        pdf.set_xy(x, y + 4)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*color)
        pdf.cell(card_w, 5, titulo.upper(), align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Valor
        pdf.set_x(x)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*COLOR_TEXT_DARK)
        pdf.cell(card_w, 10, valor, align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Etiqueta de tasa (abajo de las tarjetas)
    pdf.set_xy(start_x, y + card_h + 2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(130, 135, 150)
    pdf.cell(0, 5, f"Tasa de referencia: Bs. {tasa_bs:,.2f} / USD",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _table_header(pdf: ReportePDF, cols: list[tuple]):
    """
    Dibuja la fila de encabezado de una tabla.
    cols: [(texto, ancho, alineación), ...]
    """
    pdf.set_fill_color(*COLOR_BG_HEADER)
    pdf.set_text_color(*COLOR_TEXT_LIGHT)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.set_line_width(0.2)
    for texto, ancho, alin in cols:
        pdf.cell(ancho, 8, texto, border=1, align=alin, fill=True)
    pdf.ln()


def _table_row(pdf: ReportePDF, valores: list[tuple], row_idx: int):
    """
    Dibuja una fila de datos con filas alternas.
    valores: [(texto, ancho, alineación), ...]
    """
    fill_color = COLOR_ROW_A if row_idx % 2 == 0 else COLOR_ROW_B
    pdf.set_fill_color(*fill_color)
    pdf.set_text_color(*COLOR_TEXT_DARK)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.set_line_width(0.1)
    for texto, ancho, alin in valores:
        pdf.cell(ancho, 7, str(texto), border=1, align=alin, fill=True)
    pdf.ln()


def _draw_productos_table(pdf: ReportePDF, productos: list[dict]):
    """Tabla de productos vendidos agrupados."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*COLOR_BG_HEADER)
    pdf.cell(0, 7, "Productos Vendidos", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.set_line_width(0.8)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 174, pdf.get_y())
    pdf.ln(3)

    cols = [
        ("Producto",            110, "L"),
        ("Cant. Total",          30, "C"),
        ("Subtotal USD",         34, "R"),
    ]
    _table_header(pdf, cols)

    total_general = 0.0
    for i, prod in enumerate(productos):
        _table_row(pdf, [
            (prod["nombre_producto"],       110, "L"),
            (str(prod["cantidad_total"]),    30, "C"),
            (f"${prod['subtotal']:,.2f}",    34, "R"),
        ], i)
        total_general += prod["subtotal"]

    # Fila de total
    pdf.set_fill_color(*COLOR_BG_HEADER)
    pdf.set_text_color(*COLOR_SUCCESS)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.cell(110 + 30, 8, "TOTAL GENERAL", border=1, align="R", fill=True)
    pdf.cell(34,        8, f"${total_general:,.2f}", border=1, align="R", fill=True)
    pdf.ln()


def _draw_ventas_table(pdf: ReportePDF, ventas: list[dict]):
    """Tabla con todas las transacciones individuales del día."""
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*COLOR_BG_HEADER)
    pdf.cell(0, 7, "Transacciones del Día", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.set_line_width(0.8)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 174, pdf.get_y())
    pdf.ln(3)

    cols = [
        ("# Venta",   18, "C"),
        ("Hora",       22, "C"),
        ("Cliente",    72, "L"),
        ("Cédula",     32, "C"),
        ("Total USD",  30, "R"),
    ]
    _table_header(pdf, cols)

    for i, v in enumerate(ventas):
        # Extraer hora de la fecha ISO
        try:
            hora = v["fecha"].split("T")[1][:5] if "T" in v["fecha"] else v["fecha"]
        except Exception:
            hora = ""

        _table_row(pdf, [
            (str(v["id"]),             18, "C"),
            (hora,                      22, "C"),
            (v["nombre_cliente"][:35], 72, "L"),
            (v["cedula_cliente"],       32, "C"),
            (f"${v['total_usd']:,.2f}", 30, "R"),
        ], i)
