# -*- coding: utf-8 -*-
import datetime
from pathlib import Path

from fpdf import FPDF, XPos, YPos

ROOT_DIR = Path(__file__).resolve().parent.parent
FACTURAS_DIR = ROOT_DIR / "facturas"
FACTURAS_DIR.mkdir(exist_ok=True)

# Colores basados en la imagen
COLOR_HEADER_BG = (243, 232, 243) # Púrpura claro para el encabezado de la tabla
COLOR_HEADER_TEXT = (74, 20, 140) # Texto púrpura oscuro
COLOR_TEXT = (0, 0, 0)
COLOR_LINE = (200, 200, 200)

class FacturaPDF(FPDF):
    def __init__(self, empresa_nombre="Cero Grados", empresa_dir="", empresa_tel="", empresa_rif="", logo_ruta=""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)
        self.empresa_nombre = empresa_nombre
        self.empresa_dir = empresa_dir
        self.empresa_tel = empresa_tel
        self.empresa_rif = empresa_rif
        self.logo_ruta = logo_ruta

    def header(self):
        # Logo - resolve relative paths from project root
        logo_ok = False
        if self.logo_ruta:
            logo_path = Path(self.logo_ruta)
            if not logo_path.is_absolute():
                logo_path = ROOT_DIR / logo_path
            if logo_path.exists():
                try:
                    self.image(str(logo_path), x=15, y=12, h=24)
                    logo_ok = True
                except Exception:
                    pass

        # Textos de empresa alineados a la derecha
        # If logo was placed on left, set y to align with it
        if logo_ok:
            self.set_y(12)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(0, 0, 0)
        self.cell(0, 9, self.empresa_nombre, new_x=XPos.RIGHT, new_y=YPos.NEXT, align="R")

        self.set_font("Helvetica", "", 10)
        if self.empresa_dir:
            self.cell(0, 5, self.empresa_dir, new_x=XPos.RIGHT, new_y=YPos.NEXT, align="R")
        if self.empresa_tel:
            self.cell(0, 5, f"Telf: {self.empresa_tel}", new_x=XPos.RIGHT, new_y=YPos.NEXT, align="R")
        if self.empresa_rif:
            self.cell(0, 5, f"R.I.F: {self.empresa_rif}", new_x=XPos.RIGHT, new_y=YPos.NEXT, align="R")

        # Ensure we are below the logo height
        if logo_ok and self.get_y() < 38:
            self.set_y(38)
        self.ln(6)


def generar_factura_venta(venta: dict, detalles: list, empresa_data: dict, tasa_usd: float) -> str:
    """
    Genera el PDF de la factura/recibo.
    venta: dict con id, fecha, nombre_cliente, cedula_cliente, total_usd, total_bs, metodo_pago
    detalles: list de dicts con nombre_producto, cantidad, precio_unitario, subtotal (y opcionalmente sku)
    empresa_data: dict con nombre, telefono, direccion, rif, ruta_logo
    tasa_usd: float
    """
    pdf = FacturaPDF(
        empresa_nombre=empresa_data.get("nombre", "Empresa"),
        empresa_dir=empresa_data.get("direccion", ""),
        empresa_tel=empresa_data.get("telefono", ""),
        empresa_rif=empresa_data.get("rif", ""),
        logo_ruta=empresa_data.get("ruta_logo", "")
    )
    pdf.add_page()
    
    # ── BLOQUE DE CLIENTE ──────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COLOR_TEXT)
    pdf.set_draw_color(*COLOR_LINE)
    pdf.set_line_width(0.2)
    
    # Borde exterior bloque
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    
    # Primera linea: Cliente, Recibo, Fecha
    pdf.cell(70, 8, f"CLIENTE: {venta.get('nombre_cliente', 'General').upper()}", border=0)
    pdf.cell(50, 8, f"RECIBO: #{venta.get('id', '')}", border=0, align="C")
    
    # Formatear fecha
    try:
        dt = datetime.datetime.fromisoformat(venta.get("fecha", ""))
        fecha_str = dt.strftime("%d/%m/%Y")
    except Exception:
        fecha_str = venta.get("fecha", "")
        
    pdf.cell(0, 8, f"FECHA: {fecha_str}", border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Segunda linea: Dirección y Teléfono
    pdf.cell(120, 8, f"DIRECCIÓN: -", border=0) # Asumimos vacío si no hay en db
    cedula = venta.get("cedula_cliente", "S/C")
    pdf.cell(0, 8, f"CÉDULA/RIF: {cedula}", border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    y_end = pdf.get_y()
    
    # Dibujar cuadro alrededor de los datos del cliente
    pdf.rect(x_start, y_start, 180, y_end - y_start)
    
    pdf.ln(5)
    
    # ── TABLA DE PRODUCTOS ─────────────────────────────────────────
    # Configuración de columnas
    cols = [
        ("CANTIDAD", 25, "C"),
        ("DESCRIPCIÓN", 75, "L"),
        ("SKU", 35, "C"),
        ("PRECIO USD", 25, "C"),
        ("TOTAL USD", 20, "C")
    ]
    
    # Encabezado
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*COLOR_HEADER_BG)
    pdf.set_text_color(*COLOR_HEADER_TEXT)
    
    for header, width, align in cols:
        pdf.cell(width, 10, header, border=0, align=align, fill=True)
    pdf.ln(10)
    
    # Cuerpo
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*COLOR_TEXT)
    
    total_items = 0
    for item in detalles:
        c = item.get("cantidad", 0)
        p = float(item.get("precio_unitario", 0.0))
        s = float(item.get("subtotal", c * p))
        sku = item.get("sku", "-")
        
        pdf.cell(cols[0][1], 8, f"{c} Und.", border=0, align=cols[0][2])
        
        # Limitar tamaño de nombre
        nombre = str(item.get("nombre_producto", ""))
        if len(nombre) > 35: nombre = nombre[:32] + "..."
        pdf.cell(cols[1][1], 8, nombre, border=0, align=cols[1][2])
        
        pdf.cell(cols[2][1], 8, sku, border=0, align=cols[2][2])
        pdf.cell(cols[3][1], 8, f"{p:.2f}", border=0, align=cols[3][2])
        pdf.cell(cols[4][1], 8, f"{s:.2f}", border=0, align=cols[4][2], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        total_items += 1
        
    # Línea inferior de la tabla
    pdf.set_draw_color(*COLOR_LINE)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    
    # ── PIE (TOTALES) ──────────────────────────────────────────────
    pdf.ln(2)
    y_footer_start = pdf.get_y()
    
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(70, 8, f"TOTAL DE ITEMS: {total_items}", border=0)
    
    # Subtotal
    pdf.cell(85, 8, "SUBTOTAL USD:", border=0, align="R")
    total_usd = float(venta.get("total_usd", 0.0))
    pdf.cell(0, 8, f"{total_usd:.2f}", border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Total USD
    pdf.cell(70, 8, "", border=0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(85, 8, "TOTAL USD:", border=0, align="R")
    pdf.cell(0, 8, f"{total_usd:.2f}", border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Total BS
    pdf.cell(70, 8, "", border=0)
    pdf.cell(85, 8, "TOTAL BS:", border=0, align="R")
    total_bs = float(venta.get("total_bs", total_usd * tasa_usd))
    pdf.cell(0, 8, f"{total_bs:.2f}", border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Observaciones
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*COLOR_HEADER_TEXT)
    
    y_obs = pdf.get_y() + 5
    pdf.set_xy(15, y_obs)
    pdf.cell(35, 8, "Observaciones", border=1, align="L")
    pdf.cell(0, 8, "", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # Cuadro total
    pdf.rect(15, y_footer_start, 180, (y_obs - y_footer_start) + 8)
    
    # Salvar
    fecha_seg = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = FACTURAS_DIR / f"factura_{venta.get('id', 'gen')}_{fecha_seg}.pdf"
    pdf.output(str(out_file))
    
    return str(out_file)
