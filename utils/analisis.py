"""
utils/analisis.py
=================
Funciones de análisis financiero para el módulo de inventario.
Son funciones puras (sin efectos secundarios ni dependencias externas),
fáciles de testear de forma aislada.
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constantes de umbrales de rentabilidad
# ---------------------------------------------------------------------------

UMBRAL_BAJO:  float = 30.0   # % — por debajo de esto se considera bajo margen
UMBRAL_MEDIO: float = 50.0   # % — entre UMBRAL_BAJO y aquí es margen estándar


# ---------------------------------------------------------------------------
# Tipos de datos de resultado
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AnalisisInversion:
    """
    Resultado inmutable del análisis de inversión de un repuesto.

    Atributos:
        margen_bruto_pct  : Margen de ganancia bruta (%).
                            Fórmula: (venta − entrada) / venta × 100
        ganancia_neta_und : Ganancia neta por unidad (dinero).
                            Fórmula: precio_venta − precio_entrada
        indicador_texto   : Etiqueta textual del nivel de rentabilidad.
        indicador_emoji   : Emoji representativo del nivel.
        indicador_color   : Color hex sugerido para la UI.
        indicador_nivel   : Nivel como cadena ('bajo' | 'estandar' | 'alto').
        valido            : False si los datos de entrada son inválidos.
        error             : Mensaje de error, sólo cuando valido=False.
    """
    margen_bruto_pct:   float
    ganancia_neta_und:  float
    indicador_texto:    str
    indicador_emoji:    str
    indicador_color:    str
    indicador_nivel:    str          # 'bajo' | 'estandar' | 'alto'
    valido:             bool = True
    error:              str  = ""


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def calcular_analisis_inversion(
    precio_entrada: float,
    precio_venta:   float,
) -> AnalisisInversion:
    """
    Calcula el análisis de inversión de un repuesto dado su precio
    de entrada (costo) y precio de venta.

    Args:
        precio_entrada: Costo de adquisición del repuesto (debe ser > 0).
        precio_venta:   Precio al que se vende el repuesto (debe ser > precio_entrada).

    Returns:
        AnalisisInversion con todos los métricas calculadas.

    Notas sobre la fórmula del margen bruto:
        Se usa el margen sobre ventas (método estándar contable):
            margen = (venta - costo) / venta × 100
        Esto es distinto al "markup" que divide sobre el costo.
    """
    # ── Validaciones ──────────────────────────────────────────────────
    try:
        precio_entrada = float(precio_entrada)
        precio_venta   = float(precio_venta)
    except (TypeError, ValueError):
        return AnalisisInversion(
            margen_bruto_pct=0, ganancia_neta_und=0,
            indicador_texto="Datos inválidos", indicador_emoji="❓",
            indicador_color="#8b91a7", indicador_nivel="bajo",
            valido=False, error="Los precios deben ser valores numéricos.",
        )

    if precio_entrada <= 0:
        return AnalisisInversion(
            margen_bruto_pct=0, ganancia_neta_und=0,
            indicador_texto="Precio de entrada inválido", indicador_emoji="❓",
            indicador_color="#8b91a7", indicador_nivel="bajo",
            valido=False, error="El precio de entrada debe ser mayor a 0.",
        )

    if precio_venta <= 0:
        return AnalisisInversion(
            margen_bruto_pct=0, ganancia_neta_und=0,
            indicador_texto="Precio de venta inválido", indicador_emoji="❓",
            indicador_color="#8b91a7", indicador_nivel="bajo",
            valido=False, error="El precio de venta debe ser mayor a 0.",
        )

    # ── Cálculos ──────────────────────────────────────────────────────
    ganancia_neta_und = round(precio_venta - precio_entrada, 4)
    margen_bruto_pct  = round((ganancia_neta_und / precio_venta) * 100, 2)

    # ── Clasificación del indicador ───────────────────────────────────
    if margen_bruto_pct < UMBRAL_BAJO:
        indicador_texto  = "Revisar precio de proveedor"
        indicador_emoji  = "⚠️"
        indicador_color  = "#e0954a"   # naranja / advertencia
        indicador_nivel  = "bajo"
    elif margen_bruto_pct <= UMBRAL_MEDIO:
        indicador_texto  = "Rentabilidad Estándar"
        indicador_emoji  = "✅"
        indicador_color  = "#4f8ef7"   # azul / estándar
        indicador_nivel  = "estandar"
    else:
        indicador_texto  = "Alta Rentabilidad"
        indicador_emoji  = "🚀"
        indicador_color  = "#3ecf8e"   # verde / excelente
        indicador_nivel  = "alto"

    return AnalisisInversion(
        margen_bruto_pct=margen_bruto_pct,
        ganancia_neta_und=ganancia_neta_und,
        indicador_texto=indicador_texto,
        indicador_emoji=indicador_emoji,
        indicador_color=indicador_color,
        indicador_nivel=indicador_nivel,
    )
