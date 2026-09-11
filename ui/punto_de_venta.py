"""
ui/punto_de_venta.py
====================
Pantalla de Punto de Venta (POS).

Features:
  - Buscador de productos en tiempo real
  - Carrito con columna de descuento % por item
  - Botón "Dar a Fiado" con panel inline (sin popups)
  - Tasa del dólar configurable
  - Totales en USD y VES
"""

import json
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import InventarioDAO, VentasDAO, DeudoresDAO, ClientesDAO, CombosDAO  # noqa: E402

ROOT_DIR   = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)
TASA_FILE  = CONFIG_DIR / "tasa.json"

from ui.app import COLORS as _AC, FONT_FAMILY  # noqa: E402

FONT = FONT_FAMILY

C = {
    "bg":        _AC["bg_root"],
    "card":      _AC["bg_card"],
    "sidebar":   _AC.get("bg_sidebar", _AC["bg_root"]),
    "input":     _AC["bg_input"],
    "border":    _AC["border"],
    "accent":    _AC["accent"],
    "accent_h":  _AC["accent_hover"],
    "success":   _AC["success"],
    "success_h": _AC["success"],
    "warning":   "#e0954a",
    "danger":    _AC["danger"],
    "text":      _AC["text_primary"],
    "muted":     _AC["text_muted"],
    "row_even":  _AC["row_even"],
    "row_odd":   _AC["row_odd"],
    "row_sel":   _AC["row_selected"],
    "gold":      "#f5c518",
}


# ---------------------------------------------------------------------------
# Tasa
# ---------------------------------------------------------------------------

def cargar_tasa() -> float:
    try:
        if TASA_FILE.exists():
            data = json.loads(TASA_FILE.read_text(encoding="utf-8"))
            return float(data.get("tasa", 1.0))
    except (json.JSONDecodeError, ValueError):
        pass
    return 1.0


def guardar_tasa(tasa: float) -> None:
    TASA_FILE.write_text(
        json.dumps({"tasa": tasa}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ===========================================================================
# TasaPanel
# ===========================================================================

class TasaPanel(ctk.CTkFrame):
    def __init__(self, parent, on_change=None, **kwargs):
        super().__init__(parent, fg_color=C["card"], corner_radius=12, **kwargs)
        self._on_change = on_change
        self._build()
        self._cargar()

    def _build(self):
        self.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(self, text="💱  Tasa del Dólar (Bs/USD):",
                     font=(FONT, 13, "bold"), text_color=C["text"]).grid(
            row=0, column=0, padx=(16, 8), pady=14)
        self._var = ctk.StringVar(value="1.00")
        self._entry = ctk.CTkEntry(self, textvariable=self._var, width=130, height=36,
                                    font=(FONT, 14, "bold"), fg_color=C["input"],
                                    border_color=C["border"], text_color=C["gold"],
                                    corner_radius=8, justify="center")
        self._entry.grid(row=0, column=1, padx=(0, 10), pady=14)
        self._entry.bind("<Return>", lambda _: self._on_guardar())
        ctk.CTkButton(self, text="💾 Guardar", width=100, height=36,
                      font=(FONT, 12, "bold"), fg_color=C["accent"],
                      hover_color=C["accent_h"], corner_radius=8,
                      command=self._on_guardar).grid(row=0, column=2, padx=(0, 8), pady=14, sticky="w")
        # Botón link al monitor BCV
        def _abrir_bcv():
            import webbrowser
            webbrowser.open("https://xekred.github.io/dolar-bcv-monitor/")
        ctk.CTkButton(self, text="🌐 Ver precio BCV", width=140, height=36,
                      font=(FONT, 11), fg_color="#0a1628",
                      hover_color=C["accent"], text_color=C["accent"],
                      border_width=1, border_color=C["accent"],
                      corner_radius=8, command=_abrir_bcv).grid(
            row=0, column=3, padx=(0, 8), pady=14, sticky="w")
        self._lbl_estado = ctk.CTkLabel(self, text="", font=(FONT, 11), text_color=C["success"])
        self._lbl_estado.grid(row=0, column=4, padx=(0, 16), pady=14)

    def _cargar(self):
        self._var.set(f"{cargar_tasa():.2f}")

    def _on_guardar(self):
        try:
            tasa = float(self._var.get().replace(",", "."))
            if tasa <= 0:
                raise ValueError
        except ValueError:
            self._lbl_estado.configure(text="⚠ Valor inválido", text_color=C["danger"])
            return
        guardar_tasa(tasa)
        self._var.set(f"{tasa:.2f}")
        self._lbl_estado.configure(text="✓ Guardado", text_color=C["success"])
        self.after(2500, lambda: self._lbl_estado.configure(text=""))
        if self._on_change:
            self._on_change(tasa)

    def get_tasa(self) -> float:
        try:
            return float(self._var.get().replace(",", "."))
        except ValueError:
            return 1.0


# ===========================================================================
# ProductSearch
# ===========================================================================

class ProductSearch(ctk.CTkFrame):
    def __init__(self, parent, dao: InventarioDAO, on_add, **kwargs):
        super().__init__(parent, fg_color=C["sidebar"], corner_radius=0, **kwargs)
        self._dao    = dao
        from database.inventario_db import CombosDAO
        self._combos_dao = CombosDAO()
        self._on_add = on_add
        self._resultados: list[dict] = []
        self._build()
        self._buscar("")

    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="🛍️  Productos", font=(FONT, 14, "bold"),
                     text_color=C["text"], anchor="w").grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w")

        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._buscar(self._search_var.get()))
        ctk.CTkEntry(search_frame, textvariable=self._search_var,
                     placeholder_text="🔍  Buscar por nombre o SKU…",
                     font=(FONT, 12), height=36, fg_color=C["input"],
                     border_color=C["border"], text_color=C["text"],
                     corner_radius=8).grid(row=0, column=0, sticky="ew")

        list_frame = tk.Frame(self, bg=C["card"])
        list_frame.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                    bg=C["card"], fg=C["text"],
                                    selectbackground=C["row_sel"],
                                    selectforeground=C["text"],
                                    font=(FONT, 11), relief="flat",
                                    borderwidth=0, highlightthickness=0,
                                    activestyle="none")
        scrollbar.config(command=self._listbox.yview)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._listbox.bind("<Double-1>", self._on_listbox_double_click)

        self._info_frame = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=10)
        self._info_frame.grid(row=3, column=0, padx=10, pady=(0, 8), sticky="ew")
        self._info_frame.grid_columnconfigure(0, weight=1)
        self._info_frame.grid_columnconfigure(1, weight=0)

        self._lbl_nombre = ctk.CTkLabel(self._info_frame, text="Selecciona un producto",
                                         font=(FONT, 12, "bold"), text_color=C["muted"],
                                         wraplength=175, anchor="w", justify="left")
        self._lbl_nombre.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        self._lbl_precio = ctk.CTkLabel(self._info_frame, text="", font=(FONT, 11),
                                         text_color=C["success"], anchor="w")
        self._lbl_precio.grid(row=1, column=0, padx=12, pady=(0, 2), sticky="w")
        self._lbl_stock  = ctk.CTkLabel(self._info_frame, text="", font=(FONT, 11),
                                         text_color=C["muted"], anchor="w")
        self._lbl_stock.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")

        # Imagen del producto
        self._lbl_img = ctk.CTkLabel(self._info_frame, text="", width=90, height=90,
                                      fg_color=C["input"], corner_radius=8)
        self._lbl_img.grid(row=0, column=1, rowspan=3, padx=(4, 10), pady=8, sticky="ne")

        self._listbox.bind("<<ListboxSelect>>", self._on_select)


        qty_frame = ctk.CTkFrame(self, fg_color="transparent")
        qty_frame.grid(row=4, column=0, padx=10, pady=(0, 14), sticky="ew")
        qty_frame.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(qty_frame, text="Cant:", font=(FONT, 12), text_color=C["muted"]).grid(
            row=0, column=0, padx=(0, 6))
            
        self._qty_var = ctk.StringVar(value="1")
        
        ctk.CTkButton(qty_frame, text="-", width=34, height=38, font=(FONT, 16, "bold"), 
                      fg_color=C["input"], hover_color=C["border"], text_color=C["text"], 
                      command=self._dec_qty).grid(row=0, column=1, padx=(0, 2))
                      
        ctk.CTkEntry(qty_frame, textvariable=self._qty_var, width=50, height=38,
                     font=(FONT, 14, "bold"), fg_color=C["card"], border_color=C["border"],
                     text_color=C["text"], corner_radius=0, justify="center").grid(
            row=0, column=2)
            
        ctk.CTkButton(qty_frame, text="+", width=34, height=38, font=(FONT, 16, "bold"), 
                      fg_color=C["input"], hover_color=C["border"], text_color=C["text"], 
                      command=self._inc_qty).grid(row=0, column=3, padx=(2, 10), sticky="w")

        ctk.CTkButton(qty_frame, text="➕ Agregar", font=(FONT, 13, "bold"),
                      height=38, width=120, fg_color=C["success"], hover_color=C["success_h"],
                      text_color="#fff", corner_radius=8,
                      command=self._agregar_seleccionado).grid(
            row=0, column=4, sticky="e")

    def _dec_qty(self):
        try:
            v = int(self._qty_var.get())
            if v > 1: self._qty_var.set(str(v - 1))
        except ValueError:
            self._qty_var.set("1")

    def _inc_qty(self):
        try:
            v = int(self._qty_var.get())
            self._qty_var.set(str(v + 1))
        except ValueError:
            self._qty_var.set("1")

    def _buscar(self, termino: str):
        termino = termino.strip().lower()
        
        # Productos regulares
        if termino:
            prods = [
                r for r in self._dao.listar_todos()
                if termino in r["nombre"].lower()
                or termino in (r["marca"] or "").lower()
                or termino in (r["sku"] or "").lower()
            ]
        else:
            prods = [r for r in self._dao.listar_todos() if r["cantidad"] > 0]
            
        for p in prods:
            p["is_combo"] = False
            
        # Combos
        combos = []
        for c in self._combos_dao.listar():
            if not termino or termino in c["nombre"].lower():
                c["is_combo"] = True
                combos.append(c)

        self._resultados = combos + prods
        
        self._listbox.delete(0, "end")
        for i, r in enumerate(self._resultados):
            if r.get("is_combo"):
                self._listbox.insert("end", f"  🎁 {r['nombre']} (-{r['descuento']:.0f}%)")
                self._listbox.itemconfig(i, {'fg': C["gold"]})
            else:
                stock_tag = "" if r["cantidad"] > 0 else "  ⚠️ SIN STOCK"
                self._listbox.insert("end", f"  {r['nombre']}{stock_tag}")
                if r["cantidad"] <= 0:
                    self._listbox.itemconfig(i, {'fg': C["danger"]})

    def _on_select(self, _event=None):
        sel = self._listbox.curselection()
        if not sel: return
        r = self._resultados[sel[0]]
        self._mostrar_r(r)

    def _mostrar_r(self, r):
        if r.get("is_combo"):
            self._lbl_nombre.configure(text=f"🎁 {r['nombre']}", text_color=C["gold"])
            self._lbl_precio.configure(text=f"Precio combo: ${r['precio_final']:.2f} USD")
            self._lbl_stock.configure(text=f"({r['num_items']} productos)")
            self._lbl_img.configure(image="", text="COMBO")
            if hasattr(self._lbl_img, '_image_ref'):
                self._lbl_img._image_ref = None
            return

        self._lbl_nombre.configure(
            text=f"{r['nombre']}  —  {r['marca']} {r['modelo']}",
            text_color=C["text"])
        self._lbl_precio.configure(text=f"Precio venta: ${r['precio_venta']:.2f} USD")
        self._lbl_stock.configure(text=f"Stock disponible: {r['cantidad']} unidades")
        # Mostrar imagen del producto si existe
        img_ruta = r.get("imagen_ruta") or ""
        if img_ruta and Path(img_ruta).exists():
            try:
                from PIL import Image as PILImage, ImageTk
                pil_img = PILImage.open(img_ruta).convert("RGBA")
                pil_img.thumbnail((120, 120))
                tk_img = ImageTk.PhotoImage(pil_img)
                self._lbl_img.configure(image=tk_img, text="")
                self._lbl_img._image_ref = tk_img  # evitar GC
            except Exception:
                self._lbl_img.configure(image="", text="N/A")
                self._lbl_img._image_ref = None
        else:
            self._lbl_img.configure(image="", text="N/A")
            self._lbl_img._image_ref = None

    def _on_listbox_double_click(self, event=None):
        sel = self._listbox.curselection()
        if not sel: return
        r = self._resultados[sel[0]]
        
        if r.get("is_combo"):
            from database.inventario_db import CombosDAO
            detalles = CombosDAO().obtener_detalle_completo(r["id"])
            if detalles:
                popup = ctk.CTkToplevel(self.winfo_toplevel())
                popup.title("Contenido del Combo")
                popup.geometry("350x300")
                popup.configure(fg_color=C["bg"])
                popup.grab_set()
                popup.transient(self.winfo_toplevel())
                
                # Center popup
                px = self.winfo_toplevel().winfo_rootx()
                py = self.winfo_toplevel().winfo_rooty()
                pw = self.winfo_toplevel().winfo_width()
                ph = self.winfo_toplevel().winfo_height()
                x = px + (pw - 350) // 2
                y = py + (ph - 300) // 2
                popup.geometry(f"350x300+{x}+{y}")
                
                ctk.CTkLabel(popup, text=f"🎁 {detalles['nombre']}", font=(FONT, 16, "bold"),
                             text_color=C["gold"]).pack(pady=(20, 10))
                             
                scroll = ctk.CTkScrollableFrame(popup, fg_color="transparent")
                scroll.pack(fill="both", expand=True, padx=20, pady=10)
                
                for item in detalles["items"]:
                    ctk.CTkLabel(scroll, text=f"• {item['nombre']} (x{item['cantidad']})",
                                 font=(FONT, 13), text_color=C["text"], anchor="w").pack(fill="x", pady=2)
                
                ctk.CTkButton(popup, text="Cerrar", fg_color=C["input"], text_color=C["text"],
                              hover_color=C["border"], command=popup.destroy).pack(pady=15)
        else:
            self._agregar_seleccionado()

    def mostrar_info_id(self, p_id: int):
        for r in self._dao.listar_todos():
            if r["id"] == p_id:
                self._mostrar_r(r)
                break

    def _agregar_seleccionado(self):
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un producto o combo de la lista primero.")
            return
        r = self._resultados[sel[0]]
        try:
            qty = int(self._qty_var.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "La cantidad debe ser mayor a 0")
            return
            
        if not r.get("is_combo") and r["cantidad"] <= 0:
            messagebox.showwarning("Sin stock", "No hay stock de este producto.")
            return

        self._on_add(r, qty)
        self._qty_var.set("1")


# ===========================================================================
# CartPanel  —  Carrito con descuentos + Fiado
# ===========================================================================

class CartPanel(ctk.CTkFrame):
    """
    Panel de carrito de venta.
    - Columna 'Desc.%' editable al seleccionar un item (barra inferior).
    - Botón '💳 Dar a Fiado' que despliega un panel inline.
    - Total USD respeta los descuentos individuales.
    """

    COLS = [
        ("nombre",   "Producto",   200, "w"),
        ("sku",      "SKU",         90, "center"),
        ("precio",   "P. Unit.",    80, "e"),
        ("qty",      "Cant.",       50, "center"),
        ("subtotal", "Subtotal",   100, "e"),
    ]

    def __init__(self, parent, tasa_callback, on_venta_procesada=None, on_cart_select=None, **kwargs):
        super().__init__(parent, fg_color=C["card"], corner_radius=12, **kwargs)
        self._items: list[dict] = []
        self._get_tasa           = tasa_callback
        self._on_venta_procesada = on_venta_procesada
        self._on_cart_select     = on_cart_select
        self._ventas_dao         = VentasDAO()
        self._deudores_dao       = DeudoresDAO()
        self._clientes_dao       = ClientesDAO()
        self._suggest_win        = None  # ventana flotante de sugerencias
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Datos del cliente ─────────────────────────────────────────
        cf = ctk.CTkFrame(self, fg_color=C["input"], corner_radius=10)
        cf.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")
        cf.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(cf, text="👤 Cliente:", font=(FONT, 12, "bold"), text_color=C["muted"]).grid(
            row=0, column=0, padx=(12, 6), pady=10)
        self._entry_nombre = ctk.CTkEntry(cf, font=(FONT, 12), height=34, fg_color=C["card"],
                                           border_color=C["border"], text_color=C["text"], corner_radius=8)
        self._entry_nombre.insert(0, "N/A")
        self._entry_nombre.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")
        ctk.CTkLabel(cf, text="🪪 Cédula/RIF:", font=(FONT, 12, "bold"), text_color=C["muted"]).grid(
            row=0, column=2, padx=(0, 6))
        self._entry_cedula = ctk.CTkEntry(cf, font=(FONT, 12), height=34, width=150,
                                           fg_color=C["card"], border_color=C["border"],
                                           text_color=C["text"], corner_radius=8)
        self._entry_cedula.insert(0, "N/A")
        self._entry_cedula.grid(row=0, column=3, padx=(0, 12), pady=10, sticky="ew")

        # Auto-clear N/A behavior + autocomplete
        def _on_focus_in(event):
            w = event.widget
            if w.get() == "N/A":
                w.delete(0, "end")
        def _on_focus_out(event):
            w = event.widget
            if not w.get().strip():
                w.insert(0, "N/A")
            self.after(200, self._hide_suggestions)

        self._entry_nombre.bind("<FocusIn>", _on_focus_in)
        self._entry_nombre.bind("<FocusOut>", _on_focus_out)
        self._entry_cedula.bind("<FocusIn>", _on_focus_in)
        self._entry_cedula.bind("<FocusOut>", _on_focus_out)

        # Autocomplete bindings
        self._entry_cedula.bind("<KeyRelease>",
            lambda e: self._on_buscar_cliente(self._entry_cedula.get(), "cedula"))
        self._entry_nombre.bind("<KeyRelease>",
            lambda e: self._on_buscar_cliente(self._entry_nombre.get(), "nombre"))

        # ── Encabezado ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=1, column=0, padx=14, pady=(6, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="🧾  Carrito de Venta", font=(FONT, 14, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="🗑️ Vaciar", width=90, height=30, font=(FONT, 11),
                      fg_color=C["input"], hover_color=C["border"], text_color=C["danger"],
                      corner_radius=8, command=self._on_vaciar).grid(row=0, column=1, sticky="e")

        # ── Tabla ─────────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=C["card"])
        tree_frame.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Cart.Treeview", background=C["card"], foreground=C["text"],
                         fieldbackground=C["card"], rowheight=34, font=(FONT, 11), borderwidth=0)
        style.configure("Cart.Treeview.Heading", background=C["input"], foreground=C["muted"],
                         font=(FONT, 10, "bold"), borderwidth=0, relief="flat")
        style.map("Cart.Treeview",
                  background=[("selected", C["row_sel"])],
                  foreground=[("selected", C["text"])])

        col_ids = [c[0] for c in self.COLS]
        self._tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings",
                                   style="Cart.Treeview", selectmode="browse")
        for col_id, heading, width, anchor in self.COLS:
            self._tree.heading(col_id, text=heading, anchor=anchor)
            self._tree.column(col_id, width=width, anchor=anchor, minwidth=30,
                              stretch=(col_id == "nombre"))
        self._tree.tag_configure("even",    background=C["row_even"])
        self._tree.tag_configure("odd",     background=C["row_odd"])
        self._tree.tag_configure("sel_row", background=C["row_selected"], foreground=C["text_primary"])
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=v_scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self._tree.bind("<Double-1>", self._on_editar_precio_inline)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # ── Hint rapido ───────────────────────────────────────────────
        hint = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=8)
        hint.grid(row=3, column=0, padx=14, pady=(0, 2), sticky="ew")
        ctk.CTkLabel(hint, text="📝 Clic en Precio o Cantidad para editar  │  Doble-clic en Nombre para quitar",
                     font=(FONT, 10), text_color=C["muted"]).grid(row=0, column=0, padx=12, pady=5, sticky="w")

        # ── Totales + botones ─────────────────────────────────────────
        self._build_totales()

        # ── Panel de Fiado (hidden) ───────────────────────────────────
        self._build_fiado_panel()

    def _build_totales(self):
        tf = ctk.CTkFrame(self, fg_color=C["input"], corner_radius=12)
        tf.grid(row=4, column=0, padx=14, pady=(0, 8), sticky="ew")
        tf.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(tf, text="Items en carrito:", font=(FONT, 11), text_color=C["muted"], anchor="w").grid(
            row=0, column=0, padx=(18, 4), pady=(12, 2), sticky="w")
        self._lbl_items = ctk.CTkLabel(tf, text="0", font=(FONT, 13, "bold"), text_color=C["text"], anchor="w")
        self._lbl_items.grid(row=0, column=1, padx=4, pady=(12, 2), sticky="w")

        ctk.CTkLabel(tf, text="TOTAL USD:", font=(FONT, 15, "bold"), text_color=C["muted"], anchor="e").grid(
            row=1, column=0, padx=(18, 8), pady=(4, 4), sticky="e")
        self._lbl_usd = ctk.CTkLabel(tf, text="$0.00", font=(FONT, 24, "bold"), text_color=C["success"], anchor="w")
        self._lbl_usd.grid(row=1, column=1, pady=(4, 4), sticky="w")

        sep = ctk.CTkFrame(tf, fg_color=C["border"], width=2)
        sep.grid(row=0, column=2, rowspan=3, padx=8, pady=8, sticky="ns")

        ctk.CTkLabel(tf, text="TOTAL Bs (VES):", font=(FONT, 11, "bold"), text_color=C["muted"], anchor="w").grid(
            row=0, column=3, padx=(8, 18), pady=(12, 2), sticky="w")
        self._lbl_ves = ctk.CTkLabel(tf, text="Bs. 0.00", font=(FONT, 18, "bold"), text_color=C["gold"], anchor="w")
        self._lbl_ves.grid(row=1, column=3, padx=(8, 18), pady=(4, 4), sticky="w")
        self._lbl_tasa_info = ctk.CTkLabel(tf, text="Tasa: Bs. 1.00 / USD", font=(FONT, 9), text_color=C["muted"])
        self._lbl_tasa_info.grid(row=2, column=3, padx=(8, 18), pady=(0, 12), sticky="w")

        btn_row = ctk.CTkFrame(tf, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=4, padx=18, pady=(0, 12), sticky="ew")
        btn_row.grid_columnconfigure((1, 2, 3), weight=1)

        self._combo_metodo = ctk.CTkOptionMenu(
            btn_row, values=["Punto", "Efectivo", "Divisa", "Pago Móvil"],
            font=(FONT, 13, "bold"), fg_color=C["card"], button_color=C["border"], button_hover_color=C["muted"],
            text_color=C["text"], corner_radius=10, height=42, width=120, state="disabled"
        )
        self._combo_metodo.set("Punto")
        self._combo_metodo.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_confirmar = ctk.CTkButton(
            btn_row, text="✅  Confirmar", font=(FONT, 13, "bold"), height=42,
            fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#fff", corner_radius=10, state="disabled",
            command=self._on_confirmar_simple)
        self._btn_confirmar.grid(row=0, column=1, padx=(0, 6), sticky="ew")

        self._btn_multi_pago = ctk.CTkButton(
            btn_row, text="🧾 Dividir", font=(FONT, 13, "bold"), height=42,
            fg_color=C["input"], hover_color=C["border"],
            text_color=C["text"], corner_radius=10, state="disabled",
            command=self._on_confirmar)
        self._btn_multi_pago.grid(row=0, column=2, padx=(0, 6), sticky="ew")

        self._btn_fiado = ctk.CTkButton(
            btn_row, text="💳  Crédito", font=(FONT, 13, "bold"), height=42,
            fg_color="#2a1a0a", hover_color=C["warning"],
            text_color=C["warning"], corner_radius=10, state="disabled",
            command=self._on_abrir_fiado)
        self._btn_fiado.grid(row=0, column=3, padx=(0, 0), sticky="ew")

    def _build_fiado_panel(self):
        """Panel inline — se grid/grid_remove sin popups."""
        self._fiado_frame = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=12)
        self._fiado_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(self._fiado_frame, text="💳  Datos de Crédito",
                     font=(FONT, 14, "bold"), text_color=C["warning"]).grid(
            row=0, column=0, columnspan=4, padx=16, pady=(14, 8), sticky="w")

        ctk.CTkLabel(self._fiado_frame, text="Nombre *", font=(FONT, 11), text_color=C["muted"]).grid(
            row=1, column=0, padx=(16, 6), pady=4, sticky="w")
        self._fiado_nombre = ctk.CTkEntry(self._fiado_frame, placeholder_text="Nombre del deudor",
                                           font=(FONT, 12), height=34, fg_color=C["input"],
                                           border_color=C["border"], text_color=C["text"], corner_radius=8)
        self._fiado_nombre.grid(row=1, column=1, padx=(0, 16), pady=4, sticky="ew")

        ctk.CTkLabel(self._fiado_frame, text="Teléfono", font=(FONT, 11), text_color=C["muted"]).grid(
            row=1, column=2, padx=(0, 6), pady=4, sticky="w")
        self._fiado_tel = ctk.CTkEntry(self._fiado_frame, placeholder_text="04XX-XXXXXXX",
                                        font=(FONT, 12), height=34, width=150,
                                        fg_color=C["input"], border_color=C["border"],
                                        text_color=C["text"], corner_radius=8)
        self._fiado_tel.grid(row=1, column=3, padx=(0, 16), pady=4, sticky="ew")

        ctk.CTkLabel(self._fiado_frame, text="Fecha límite *", font=(FONT, 11), text_color=C["muted"]).grid(
            row=2, column=0, padx=(16, 6), pady=(4, 8), sticky="w")
        from tkcalendar import DateEntry
        self._fiado_fecha = DateEntry(
            self._fiado_frame, width=12,
            background=C.get("accent", "#2563eb"), foreground='white', borderwidth=2,
            date_pattern='yyyy-mm-dd', font=("Segoe UI", 11)
        )
        self._fiado_fecha.grid(row=2, column=1, padx=(0, 16), pady=(4, 8), sticky="ew")

        self._fiado_lbl_error = ctk.CTkLabel(self._fiado_frame, text="", font=(FONT, 10), text_color=C["danger"])
        self._fiado_lbl_error.grid(row=2, column=2, columnspan=2, padx=(0, 16), pady=(4, 8), sticky="w")

        btn_f = ctk.CTkFrame(self._fiado_frame, fg_color="transparent")
        btn_f.grid(row=3, column=0, columnspan=4, padx=16, pady=(0, 14), sticky="ew")
        btn_f.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btn_f, text="✅  Confirmar Crédito", font=(FONT, 12, "bold"), height=38,
                      fg_color=C["warning"], hover_color="#c97a2a",
                      text_color="#0a0a0a", corner_radius=10,
                      command=self._on_confirmar_fiado).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(btn_f, text="✖  Cancelar", font=(FONT, 12), height=38,
                      fg_color=C["input"], hover_color=C["border"],
                      text_color=C["muted"], corner_radius=10,
                      command=self._on_cerrar_fiado).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def agregar(self, record: dict, qty: int):
        # Combo o producto normal
        is_combo = record.get("is_combo", False)
        for item in self._items:
            if item["id"] == record["id"] and item.get("is_combo") == is_combo:
                item["qty"] += qty
                self._refresh_table()
                return
        
        precio = record.get("precio_venta", 0.0)
        p_base = precio
        if is_combo:
            precio = record.get("precio_final", 0.0)
            p_base = record.get("precio_base", 0.0)
            
        self._items.append({
            "id":           record["id"],
            "sku":          record.get("sku", "COMBO" if is_combo else ""),
            "nombre":       record.get("nombre", ""),
            "precio_venta": precio,
            "precio_base":  p_base,
            "qty":          qty,
            "is_combo":     is_combo,
        })
        self._refresh_table()

    def get_items(self) -> list:
        return list(self._items)

    def get_total_usd(self) -> float:
        return sum(
            item["precio_venta"] * item["qty"]
            for item in self._items
        )

    def get_cliente_info(self) -> tuple:
        nombre = self._entry_nombre.get().strip()
        if not nombre or nombre == "N/A": nombre = "N/A"
        cedula = self._entry_cedula.get().strip()
        if not cedula or cedula == "N/A": cedula = "N/A"
        return nombre, cedula

    def clear(self):
        self._items.clear()
        self._refresh_table()

    def update_tasa(self, tasa: float):
        self._refresh_totals(tasa)

    # ------------------------------------------------------------------
    # Autocomplete de clientes
    # ------------------------------------------------------------------

    def _on_buscar_cliente(self, termino: str, campo: str):
        """Busca clientes y muestra sugerencias flotantes debajo del entry."""
        t = termino.strip()
        if not t or t == "N/A" or len(t) < 2:
            self._hide_suggestions()
            return
        resultados = self._clientes_dao.buscar(t, limite=8)
        if not resultados:
            self._hide_suggestions()
            return
        self._show_suggestions(resultados)

    def _show_suggestions(self, clientes: list):
        """Muestra un panel flotante con las sugerencias de clientes."""
        self._hide_suggestions()
        # Calcular posicion
        win = tk.Toplevel(self.winfo_toplevel())
        win.overrideredirect(True)
        win.configure(bg=C["card"])
        win.attributes("-topmost", True)
        self._suggest_win = win

        x = self._entry_cedula.winfo_rootx()
        y = self._entry_cedula.winfo_rooty() + self._entry_cedula.winfo_height() + 2
        win.geometry(f"+{x}+{y}")

        for i, cl in enumerate(clientes):
            bg = C["input"] if i % 2 == 0 else C["card"]
            btn = tk.Button(
                win,
                text=f"  {cl['cedula']}   {cl['nombre']}",
                bg=bg, fg=C["text"], relief="flat",
                font=(FONT, 11), anchor="w", cursor="hand2",
                activebackground=C["row_sel"], activeforeground=C["text"],
                command=lambda c=cl: self._seleccionar_cliente(c),
            )
            btn.pack(fill="x", padx=0, pady=0)

    def _hide_suggestions(self):
        if self._suggest_win and self._suggest_win.winfo_exists():
            self._suggest_win.destroy()
        self._suggest_win = None

    def _seleccionar_cliente(self, cliente: dict):
        """Rellena los campos de cliente al seleccionar una sugerencia."""
        self._entry_cedula.delete(0, "end")
        self._entry_cedula.insert(0, cliente["cedula"])
        self._entry_nombre.delete(0, "end")
        self._entry_nombre.insert(0, cliente["nombre"])
        self._hide_suggestions()

    # ------------------------------------------------------------------
    # Lógica interna
    # ------------------------------------------------------------------

    def _refresh_table(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for i, item in enumerate(self._items):
            precio   = item["precio_venta"]
            subtotal = precio * item["qty"]
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert("", "end", iid=str(i), tags=(tag,), values=(
                item["nombre"],
                item["sku"],
                f"${precio:.2f}",
                item["qty"],
                f"${subtotal:.2f}",
            ))
        self._refresh_totals(self._get_tasa())

    def _refresh_totals(self, tasa: float):
        total_usd = self.get_total_usd()
        total_ves = total_usd * tasa
        n_items   = sum(i["qty"] for i in self._items)
        self._lbl_items.configure(text=str(n_items))
        self._lbl_usd.configure(text=f"${total_usd:,.2f}")
        self._lbl_ves.configure(text=f"Bs. {total_ves:,.2f}")
        self._lbl_tasa_info.configure(text=f"Tasa: Bs. {tasa:,.2f} / USD")
        state = "normal" if self._items else "disabled"
        self._btn_confirmar.configure(state=state)
        self._btn_fiado.configure(state=state)
        if hasattr(self, "_btn_multi_pago"):
            self._btn_multi_pago.configure(state=state)
            self._combo_metodo.configure(state=state)

    def _on_tree_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
            item = self._items[idx]
            if getattr(self, "_on_cart_select", None):
                self._on_cart_select(item["id"])
        except Exception:
            pass

    def _on_editar_precio_inline(self, event=None):
        """
        Doble-clic en una celda del carrito:
          #1 (nombre) / #2 (sku)  -> quitar item
          #3 (precio) / #5 (sub)  -> editar precio unitario
          #4 (qty)                -> editar cantidad
        Un Entry nativo aparece flotante sobre la celda para edición directa.
        """
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        col = self._tree.identify_column(event.x) if event else ""

        # ── Quitar item ──────────────────────────────
        if col in ("", "#1", "#2"):
            self._items.pop(idx)
            self._refresh_table()
            return

        is_qty   = col == "#4"
        is_total = col == "#5"

        # ── Obtener bbox de la celda para posicionar el Entry ─────────
        bbox = self._tree.bbox(sel[0], col)
        if not bbox:
            return
        cell_x, cell_y, cell_w, cell_h = bbox
        tree_rx = self._tree.winfo_rootx()
        tree_ry = self._tree.winfo_rooty()

        # ── Entry flotante nativo ─────────────────────────────────────
        if is_qty:
            init_val = str(item["qty"])
            txt_color = C["success"]
        elif is_total:
            init_val = f"{item['precio_venta'] * item['qty']:.2f}"
            txt_color = C["gold"]
        else:  # precio unitario
            init_val = f"{item['precio_venta']:.2f}"
            txt_color = C["gold"]

        popup = tk.Toplevel(self.winfo_toplevel())
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        ew = max(cell_w, 80)
        popup.geometry(f"{ew}x{cell_h}+{tree_rx + cell_x}+{tree_ry + cell_y}")
        popup.configure(bg=C["input"])

        var = tk.StringVar(value=init_val)
        entry = tk.Entry(popup, textvariable=var, justify="center",
                         font=(FONT, 12, "bold"),
                         bg=C["input"], fg=txt_color,
                         insertbackground=txt_color,
                         relief="flat", bd=2,
                         highlightthickness=2,
                         highlightcolor=C["accent"],
                         highlightbackground=C["accent"])
        entry.pack(fill="both", expand=True)
        entry.select_range(0, "end")
        entry.focus_force()

        tasa = self._get_tasa()

        def _commit(raw: str):
            raw = raw.strip()
            is_pct = False
            pct_val = 0.0
            
            if not is_qty and raw.endswith("%"):
                is_pct = True
                try:
                    pct_val = float(raw[:-1].strip().replace(",", "."))
                    if pct_val < 0 or pct_val > 100:
                        raise ValueError
                except ValueError:
                    popup.destroy()
                    return
            else:
                try:
                    val = float(raw.replace(",", "."))
                    if val < 0:
                        raise ValueError
                except ValueError:
                    popup.destroy()
                    return

            if is_qty:
                new_qty = max(1, int(val))
                item["qty"] = new_qty
            elif is_pct:
                base = item.get("precio_base", item["precio_venta"])
                item["precio_venta"] = base * (1 - (pct_val / 100))
            elif is_total:
                # total ÷ qty = precio unitario
                unit = val / item["qty"] if item["qty"] > 0 else 0
                item["precio_venta"] = unit
            else:
                item["precio_venta"] = val
                
            popup.destroy()
            self._refresh_table()
            try:
                self._tree.selection_set(str(idx))
            except Exception:
                pass

        entry.bind("<Return>",  lambda _: _commit(var.get()))
        entry.bind("<Escape>",  lambda _: popup.destroy())
        entry.bind("<FocusOut>", lambda _: _commit(var.get()))

    def _on_vaciar(self):
        if not self._items:
            return
        if messagebox.askyesno("Vaciar carrito", "¿Seguro que deseas vaciar el carrito?"):
            self.clear()

    # ------------------------------------------------------------------
    # Fiado
    # ------------------------------------------------------------------

    def _on_abrir_fiado(self):
        self._fiado_nombre.delete(0, "end")
        nombre_cliente = self._entry_nombre.get().strip()
        if nombre_cliente and nombre_cliente != "N/A":
            self._fiado_nombre.insert(0, nombre_cliente)
        self._fiado_tel.delete(0, "end")
        self._fiado_fecha.delete(0, "end")
        self._fiado_lbl_error.configure(text="")
        self._fiado_frame.grid(row=5, column=0, padx=14, pady=(0, 14), sticky="ew")

    def _on_cerrar_fiado(self):
        self._fiado_frame.grid_remove()

    def _on_confirmar_fiado(self):
        nombre_deudor = self._fiado_nombre.get().strip()
        telefono      = self._fiado_tel.get().strip()
        fecha_limite  = self._fiado_fecha.get().strip()

        if not nombre_deudor:
            self._fiado_lbl_error.configure(text="⚠ El nombre es obligatorio.")
            return
        if not fecha_limite:
            self._fiado_lbl_error.configure(text="⚠ La fecha límite es obligatoria.")
            return

        _, cedula = self.get_cliente_info()
        total_usd = self.get_total_usd()
        tasa      = self._get_tasa()
        total_bs  = total_usd * tasa

        try:
            self._ventas_dao.registrar_venta(
                nombre_cliente=nombre_deudor,
                cedula_cliente=cedula,
                total_usd=total_usd,
                total_bs=total_bs,
                items=self._items,
            )
            self._deudores_dao.crear_deuda(
                nombre=nombre_deudor,
                telefono=telefono,
                monto_usd=total_usd,
                monto_bs=total_bs,
                fecha_limite_pago=fecha_limite,
            )
        except ValueError as e:
            self._fiado_lbl_error.configure(text=f"⚠ {e}")
            return
        except Exception as e:
            self._fiado_lbl_error.configure(text=f"⚠ Error: {e}")
            return

        self._on_cerrar_fiado()
        self.clear()
        self._entry_nombre.delete(0, "end")
        self._entry_nombre.insert(0, "N/A")
        self._entry_cedula.delete(0, "end")
        self._entry_cedula.insert(0, "N/A")
        messagebox.showinfo(
            "Crédito registrado",
            f"✅ Deuda de {nombre_deudor} registrada.\n"
            f"Monto: ${total_usd:,.2f} USD  |  Fecha límite: {fecha_limite}",
        )
        if self._on_venta_procesada:
            self._on_venta_procesada()

    # ------------------------------------------------------------------
    # Venta normal
    # ------------------------------------------------------------------

    def _on_confirmar_simple(self):
        if not self._items: return
        total_usd = self.get_total_usd()
        tasa = self._get_tasa()
        metodo = self._combo_metodo.get()
        if metodo == "Divisa":
            metodo_pago_str = f"Divisa: ${total_usd:,.2f}"
        else:
            total_bs = total_usd * tasa
            metodo_pago_str = f"{metodo}: Bs.{total_bs:,.0f}"
        self._ejecutar_venta(metodo_pago_str)

    def _on_confirmar(self):
        """Modal con switch USD/Bs por método. La suma no necesita ser exacta."""
        if not self._items:
            return

        total_usd = self.get_total_usd()
        tasa = self._get_tasa()
        total_bs  = total_usd * tasa

        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title("Forma de Pago")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.focus_force()

        frame = ctk.CTkFrame(win, fg_color=C["bg"])
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            frame,
            text=f"Total: ${total_usd:,.2f} USD  /  Bs. {total_bs:,.2f}",
            font=(FONT, 14, "bold"), text_color=C["success"],
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            frame,
            text=f"💡 Tasa: Bs. {tasa:,.2f} / USD  —  El monto no debe ser exacto",
            font=(FONT, 10), text_color=C["muted"],
        ).pack(pady=(0, 10))

        METODOS = ["Punto", "Efectivo", "Divisa", "Pago Móvil"]

        # Por cada método guardamos: {moneda: StringVar('USD'|'Bs'), entry: CTkEntry}
        metodo_data: dict[str, dict] = {}

        for metodo in METODOS:
            row = ctk.CTkFrame(frame, fg_color=C["card"], corner_radius=10)
            row.pack(fill="x", pady=4)
            row.grid_columnconfigure(1, weight=1)

            # Nombre del método
            ctk.CTkLabel(row, text=metodo, width=110, anchor="w",
                         font=(FONT, 12, "bold"), text_color=C["text"]).grid(
                row=0, column=0, padx=(12, 4), pady=8)

            # Entry de monto
            en = ctk.CTkEntry(row, width=140, height=34,
                               font=(FONT, 13), fg_color=C["input"],
                               border_color=C["border"], text_color=C["gold"],
                               corner_radius=8, justify="right",
                               placeholder_text="0")
            en.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

            if metodo == "Divisa":
                moneda_var = ctk.StringVar(value="USD")
                ctk.CTkLabel(row, text="USD", width=52, anchor="center",
                             font=(FONT, 11, "bold"), text_color=C["success"]).grid(
                    row=0, column=2, padx=(4, 12), pady=8)
            else:
                moneda_var = ctk.StringVar(value="Bs")
                ctk.CTkLabel(row, text="Bs.", width=52, anchor="center",
                             font=(FONT, 11, "bold"), text_color=C["gold"]).grid(
                    row=0, column=2, padx=(4, 12), pady=8)

            metodo_data[metodo] = {"moneda": moneda_var, "entry": en}

            # Pre-rellenar Punto con el total en Bs
            if metodo == "Punto":
                en.insert(0, f"{total_bs:.2f}")

        lbl_info = ctk.CTkLabel(frame, text="", font=(FONT, 10), text_color=C["muted"])
        lbl_info.pack(pady=(4, 0))
        lbl_error = ctk.CTkLabel(frame, text="", font=(FONT, 11), text_color=C["danger"])
        lbl_error.pack()

        def _procesar():
            pagos = []
            for m, data in metodo_data.items():
                txt = data["entry"].get().strip().replace(",", ".")
                if not txt:
                    continue
                try:
                    val = float(txt)
                    if val < 0: raise ValueError
                except ValueError:
                    lbl_error.configure(text=f"⚠️ Valor inválido en '{m}'")
                    return
                if val > 0:
                    moneda = data["moneda"].get()  # 'USD' o 'Bs'
                    if moneda == "USD":
                        usd_val = val
                        if m == "Divisa":
                            pagos.append(f"{m}: ${usd_val:,.2f}")
                        else:
                            bs_val  = val * tasa
                            pagos.append(f"{m}: ${usd_val:,.2f} / Bs.{bs_val:,.0f}")
                    else:
                        bs_val  = val
                        usd_val = val / tasa if tasa > 0 else 0
                        pagos.append(f"{m}: Bs.{bs_val:,.0f} / ${usd_val:,.2f}")

            if not pagos:
                lbl_error.configure(text="⚠️ Ingresa al menos un monto.")
                return

            metodo_pago_str = " | ".join(pagos)
            win.destroy()
            self._ejecutar_venta(metodo_pago_str)

        ctk.CTkButton(
            frame, text="✅  Confirmar Pago",
            font=(FONT, 13, "bold"), height=42,
            fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#fff", corner_radius=10,
            command=_procesar,
        ).pack(fill="x", pady=(10, 0))

        # Tamaño dinámico + seguridad
        win.update_idletasks()
        w = 430
        h = 440  # Tamaño fijo para evitar cortes
        px = self.winfo_toplevel().winfo_rootx()
        py = self.winfo_toplevel().winfo_rooty()
        pw = self.winfo_toplevel().winfo_width()
        ph = self.winfo_toplevel().winfo_height()
        win.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

    def _ejecutar_venta(self, metodo_pago_str: str):
        """Procesa la venta con el string de metodo(s) de pago ya validado."""
        nombre, cedula = self.get_cliente_info()
        total_usd = self.get_total_usd()
        tasa      = self._get_tasa()
        total_bs  = total_usd * tasa

        try:
            self._ventas_dao.registrar_venta(
                nombre_cliente=nombre,
                cedula_cliente=cedula,
                total_usd=total_usd,
                total_bs=total_bs,
                items=self._items,
                metodo_pago=metodo_pago_str,
            )
        except ValueError as e:
            messagebox.showerror("Error de stock", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error de base de datos", str(e))
            return

        # Guardar / actualizar cliente en la tabla clientes para futuro autocompletado
        try:
            if cedula and cedula not in ("N/A", "S/C"):
                self._clientes_dao.upsert(cedula, nombre)
        except Exception:
            pass

        self.clear()
        self._entry_nombre.delete(0, "end")
        self._entry_nombre.insert(0, "N/A")
        self._entry_cedula.delete(0, "end")
        self._entry_cedula.insert(0, "N/A")
        if self._on_venta_procesada:
            self._on_venta_procesada()


# ===========================================================================
# PuntoDeVentaWindow
# ===========================================================================

class PuntoDeVentaWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_venta_procesada_callback=None):
        super().__init__(parent)
        self._dao = InventarioDAO()
        self._dashboard_callback = on_venta_procesada_callback
        self._setup_window()
        self._build()

    def _setup_window(self):
        self.title("⚡ RepuestosDB — Punto de Venta")
        self.geometry("1160x760")
        self.minsize(960, 600)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()
        self.update_idletasks()
        px = self.master.winfo_rootx()
        py = self.master.winfo_rooty()
        pw = self.master.winfo_width()
        ph = self.master.winfo_height()
        x = px + (pw - 1160) // 2
        y = py + (ph - 760)  // 2
        self.geometry(f"1160x760+{x}+{y}")

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 0), sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="🛒  Punto de Venta", font=(FONT, 20, "bold"),
                     text_color=C["accent"]).grid(row=0, column=0, padx=(4, 16), sticky="w")
        self._tasa_panel = TasaPanel(top, on_change=self._on_tasa_changed)
        self._tasa_panel.grid(row=0, column=1, padx=(0, 4), sticky="e")

        self._search = ProductSearch(self, dao=self._dao, on_add=self._on_add_to_cart)
        self._search.grid(row=1, column=0, padx=(16, 8), pady=(10, 16), sticky="nsew")
        self._search.configure(width=300)

        self._cart = CartPanel(self, tasa_callback=self._tasa_panel.get_tasa,
                                on_venta_procesada=self._on_venta_procesada,
                                on_cart_select=self._on_cart_select)
        self._cart.grid(row=1, column=1, padx=(0, 16), pady=(10, 16), sticky="nsew")

    def _on_cart_select(self, p_id):
        self._search.mostrar_info_id(p_id)

    def _on_add_to_cart(self, record: dict, qty: int):
        if not record.get("is_combo") and record.get("cantidad", 0) <= 0:
            messagebox.showwarning("Sin stock",
                                   f"«{record['nombre']}» no tiene unidades disponibles en inventario.")
            return
            
        if record.get("is_combo"):
            from database.inventario_db import CombosDAO
            detalles = CombosDAO().obtener_detalle_completo(record["id"])
            if detalles:
                p_base = detalles.get("precio_base", 1.0)
                if p_base <= 0: p_base = 1.0
                factor = record.get("precio_final", 1.0) / p_base
                for c_item in detalles["items"]:
                    prod_record = {
                        "id": c_item["producto_id"],
                        "sku": c_item.get("sku", ""),
                        "nombre": f"{c_item['nombre']} ({detalles['nombre']})",
                        "precio_venta": c_item["precio_venta"] * factor,
                        "precio_base": c_item["precio_venta"], # original product price
                        "is_combo": False,
                    }
                    self._cart.agregar(prod_record, c_item["cantidad"] * qty)
        else:
            self._cart.agregar(record, qty)

    def _on_tasa_changed(self, nueva_tasa: float):
        self._cart.update_tasa(nueva_tasa)

    def _on_venta_procesada(self):
        """Notifica al dashboard y cierra la ventana."""
        if self._dashboard_callback:
            self._dashboard_callback()
        self.destroy()
