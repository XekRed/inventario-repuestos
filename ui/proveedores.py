# -*- coding: utf-8 -*-
import os, sys, shutil, datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import get_connection

BASE_DIR    = Path(__file__).resolve().parent.parent
LOGOS_DIR   = BASE_DIR / "logos"
PEDIDOS_DIR = BASE_DIR / "pedidos_img"
LOGOS_DIR.mkdir(exist_ok=True)
PEDIDOS_DIR.mkdir(exist_ok=True)

COLORS = {
    "bg":        "#0d0f1a", "card":      "#13172a", "input":     "#1a1e30",
    "border":    "#2a2e45", "accent":    "#4f8ef7", "accent_h":  "#3a70d4",
    "success":   "#2ecc71", "success_h": "#27ae60", "gold":      "#f0a500",
    "danger":    "#e05c5c", "text":      "#e8eaf6", "muted":     "#6b7099",
    "row_even":  "#13172a", "row_odd":   "#181c2e", "row_sel":   "#2a3a6a",
}
FONT = "Inter"


# ---------------------------------------------------------------------------
# DAOs
# ---------------------------------------------------------------------------

class ProveedoresDAO:
    def crear(self, nombre, ruta_logo=""):
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO proveedores (nombre, ruta_logo) VALUES (?, ?)",
                (nombre.strip(), ruta_logo))
            conn.commit()
            return cur.lastrowid

    def listar(self):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, nombre, ruta_logo FROM proveedores ORDER BY nombre"
            ).fetchall()
            return [dict(r) for r in rows]

    def eliminar(self, pid):
        with get_connection() as conn:
            conn.execute("DELETE FROM proveedores WHERE id = ?", (pid,))
            conn.commit()


class PedidosDAO:
    def crear(self, proveedor_id, ruta_imagen, items):
        fecha = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO pedidos (proveedor_id, fecha, ruta_imagen) VALUES (?, ?, ?)",
                (proveedor_id, fecha, ruta_imagen))
            pid = cur.lastrowid
            for it in items:
                conn.execute(
                    "INSERT INTO pedido_items (pedido_id, codigo, nombre, tipo, cantidad, unidad)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, it.get("codigo",""), it["nombre"],
                     it.get("tipo",""), it["cantidad"], it.get("unidad","Unidad")))
            conn.commit()
            return pid

    def listar(self):
        with get_connection() as conn:
            sql = ("SELECT p.id, pr.nombre AS proveedor, p.fecha, p.ruta_imagen"
                   " FROM pedidos p"
                   " JOIN proveedores pr ON pr.id = p.proveedor_id"
                   " ORDER BY p.fecha DESC")
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    def listar_items(self, pedido_id):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT codigo, nombre, tipo, cantidad, unidad"
                " FROM pedido_items WHERE pedido_id = ?", (pedido_id,)).fetchall()
            return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Generador PNG con Pillow
# ---------------------------------------------------------------------------

def generar_imagen_pedido(nombre_empresa, logo_empresa_ruta,
                          nombre_proveedor, logo_proveedor_ruta, items, ruta_salida):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("Pillow no instalado. Ejecuta: pip install Pillow")

    W = 900; ROW_H = 34; HEADER_H = 160; FOOTER_H = 80
    TABLE_HEADER_H = 40; TABLE_BODY_H = max(len(items), 1) * ROW_H + 20
    H = HEADER_H + TABLE_HEADER_H + TABLE_BODY_H + FOOTER_H + 40

    img  = Image.new("RGB", (W, H), "#0d0f1a")
    draw = ImageDraw.Draw(img)

    def _font(size, bold=False):
        candidates = (["arialbd.ttf","Arial Bold.ttf","DejaVuSans-Bold.ttf"]
                      if bold else ["arial.ttf","Arial.ttf","DejaVuSans.ttf"])
        for name in candidates:
            try: return ImageFont.truetype(name, size)
            except Exception: pass
        return ImageFont.load_default()

    f_title = _font(28, bold=True); f_sub = _font(14)
    f_hdr   = _font(13, bold=True); f_body = _font(12)
    f_foot  = _font(16, bold=True)

    y = 20; logo_offset = 0
    if logo_empresa_ruta and Path(logo_empresa_ruta).exists():
        try:
            logo = Image.open(logo_empresa_ruta).convert("RGBA")
            logo.thumbnail((80, 80))
            img.paste(logo, (30, y), logo)
            logo_offset = logo.width + 16
        except Exception: pass

    draw.text((30 + logo_offset, y + 4),  nombre_empresa,       font=f_title, fill="#4f8ef7")
    draw.text((30 + logo_offset, y + 40), "Pedido de Repuestos", font=f_sub,   fill="#6b7099")
    fecha_str = datetime.datetime.now().strftime("%d/%m/%Y")
    draw.text((30 + logo_offset, y + 60), f"Fecha: {fecha_str}",  font=f_sub,   fill="#6b7099")
    draw.rectangle([(30, HEADER_H - 12), (W - 30, HEADER_H - 10)], fill="#2a2e45")

    COLS = [("Codigo",120),("Nombre",280),("Tipo",120),("Cantidad",90),("Unidad",110)]
    y_th = HEADER_H + 4; x_cur = 30
    draw.rectangle([(25, y_th - 4), (W - 25, y_th + TABLE_HEADER_H - 4)], fill="#1a1e30")
    for col_name, col_w in COLS:
        draw.text((x_cur + 6, y_th + 8), col_name, font=f_hdr, fill="#f0a500")
        x_cur += col_w

    y_row = y_th + TABLE_HEADER_H
    for i, item in enumerate(items):
        bg = "#13172a" if i % 2 == 0 else "#181c2e"
        draw.rectangle([(25, y_row), (W - 25, y_row + ROW_H)], fill=bg)
        x_cur = 30
        vals = [item.get("codigo",""), item.get("nombre",""), item.get("tipo",""),
                str(item.get("cantidad","")), item.get("unidad","")]
        for val, (_, cw) in zip(vals, COLS):
            while val and draw.textlength(val, font=f_body) > cw - 12:
                val = val[:-1]
            draw.text((x_cur + 6, y_row + 8), val, font=f_body, fill="#e8eaf6")
            x_cur += cw
        y_row += ROW_H

    draw.rectangle([(30, y_row + 4), (W - 30, y_row + 6)], fill="#2a2e45")
    
    logo_p_offset = 0
    if logo_proveedor_ruta and Path(logo_proveedor_ruta).exists():
        try:
            logo_p = Image.open(logo_proveedor_ruta).convert("RGBA")
            logo_p.thumbnail((50, 50))
            img.paste(logo_p, (30, H - FOOTER_H + 10), logo_p)
            logo_p_offset = 60
        except Exception: pass
        
    draw.text((30 + logo_p_offset, H - FOOTER_H + 35),
              nombre_proveedor,
              font=f_foot, fill="#2ecc71", anchor="lm")
    img.save(str(ruta_salida), "PNG")


# ---------------------------------------------------------------------------
# Treeview estilizado
# ---------------------------------------------------------------------------

def _make_tree(parent, cols, style_name):
    frame = tk.Frame(parent, bg=COLORS["card"])
    frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
    frame.pack(fill="both", expand=True)
    s = ttk.Style()
    s.configure(style_name, background=COLORS["card"], foreground=COLORS["text"],
                fieldbackground=COLORS["card"], rowheight=30, font=(FONT,11), borderwidth=0)
    s.configure(f"{style_name}.Heading", background=COLORS["input"],
                foreground=COLORS["muted"], font=(FONT,10,"bold"), relief="flat")
    s.map(style_name, background=[("selected",COLORS["row_sel"])],
          foreground=[("selected",COLORS["text"])])
    tree = ttk.Treeview(frame, columns=[c[0] for c in cols],
                        show="headings", style=style_name, selectmode="browse")
    for cid, heading, width, anchor in cols:
        tree.heading(cid, text=heading, anchor=anchor)
        tree.column(cid, width=width, anchor=anchor, minwidth=40)
    tree.tag_configure("even", background=COLORS["row_even"])
    tree.tag_configure("odd",  background=COLORS["row_odd"])
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew"); vsb.grid(row=0, column=1, sticky="ns")
    tree._frame = frame
    return tree


# ===========================================================================
# ProveedoresPage
# ===========================================================================

class ProveedoresPage(ctk.CTkFrame):

    EMPRESA_NOMBRE = "RepuestosDB"
    EMPRESA_LOGO   = ""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self._dao_prov     = ProveedoresDAO()
        self._dao_ped      = PedidosDAO()
        self._logo_tmp     = ""
        self._pedido_items = []
        self._prov_nombres = {}
        self._card_images  = []   # mantener referencias a fotos
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="Modulo de Proveedores",
                     font=(FONT, 20, "bold"), text_color=COLORS["accent"],
                     anchor="w").pack(padx=20, pady=(14,12), anchor="w")

        self._tabs = ctk.CTkTabview(
            self, fg_color=COLORS["card"],
            segmented_button_fg_color=COLORS["input"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_h"],
            segmented_button_unselected_color=COLORS["input"],
            segmented_button_unselected_hover_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=12)
        self._tabs.grid(row=1, column=0, padx=16, pady=(0,16), sticky="nsew")
        self._tabs.add("Proveedores")
        self._tabs.add("Hacer Pedido")
        self._tabs.add("Historial")
        self._build_tab_proveedores(self._tabs.tab("Proveedores"))
        self._build_tab_pedido(self._tabs.tab("Hacer Pedido"))
        self._build_tab_historial(self._tabs.tab("Historial"))

    # =======================================================================
    # PESTANA 1: Proveedores  -  Cards con logo + Formulario de registro
    # =======================================================================

    def _build_tab_proveedores(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # -- Formulario de registro (izquierda) --
        form = ctk.CTkFrame(parent, fg_color=COLORS["input"], corner_radius=12, width=260)
        form.grid(row=0, column=0, padx=(0,12), pady=0, sticky="nsew")
        form.grid_propagate(False)

        ctk.CTkLabel(form, text="Nuevo Proveedor",
                     font=(FONT,14,"bold"), text_color=COLORS["accent"]
                     ).pack(anchor="w", padx=16, pady=(16,10))
        ctk.CTkLabel(form, text="Nombre *", font=(FONT,11),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=16)
        self._prov_nombre = ctk.CTkEntry(
            form, height=36, font=(FONT,12), placeholder_text="Nombre del proveedor",
            fg_color=COLORS["card"], border_color=COLORS["border"],
            text_color=COLORS["text"], corner_radius=8)
        self._prov_nombre.pack(fill="x", padx=16, pady=(2,12))

        ctk.CTkLabel(form, text="Logo (opcional)", font=(FONT,11),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=16)
        self._lbl_logo = ctk.CTkLabel(form, text="Sin logo seleccionado",
                                       font=(FONT,10), text_color=COLORS["muted"],
                                       wraplength=220, anchor="w")
        self._lbl_logo.pack(anchor="w", padx=16, pady=(2,4))
        ctk.CTkButton(form, text="Cargar Logo", height=34,
                      font=(FONT,12), fg_color=COLORS["border"],
                      hover_color=COLORS["accent"], text_color=COLORS["text"],
                      corner_radius=8, command=self._cargar_logo_proveedor,
                      ).pack(fill="x", padx=16, pady=(0,16))

        self._prov_lbl_err = ctk.CTkLabel(form, text="", font=(FONT,10),
                                           text_color=COLORS["danger"])
        self._prov_lbl_err.pack(padx=16)
        ctk.CTkButton(form, text="Guardar Proveedor", height=40,
                      font=(FONT,13,"bold"), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_h"], text_color="#fff",
                      corner_radius=10, command=self._guardar_proveedor,
                      ).pack(fill="x", padx=16, pady=(8,0))
        ctk.CTkButton(form, text="Eliminar Seleccionado", height=36,
                      font=(FONT,12), fg_color="#3a0a0a",
                      hover_color=COLORS["danger"], text_color=COLORS["danger"],
                      corner_radius=10, command=self._eliminar_proveedor,
                      ).pack(fill="x", padx=16, pady=(8,16))

        # -- Grid de cards con logo (derecha) --
        right = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hdr2 = ctk.CTkFrame(right, fg_color="transparent")
        hdr2.grid(row=0, column=0, padx=14, pady=(12,6), sticky="ew")
        hdr2.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr2, text="Proveedores",
                     font=(FONT,13,"bold"), text_color=COLORS["text"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr2, text="Haz clic en un proveedor para iniciar un pedido",
                     font=(FONT,10), text_color=COLORS["muted"],
                     anchor="e").grid(row=0, column=1, sticky="e")

        self._cards_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", corner_radius=0)
        self._cards_scroll.grid(row=1, column=0, padx=8, pady=(0,8), sticky="nsew")
        self._cards_scroll.grid_columnconfigure((0,1,2,3), weight=1)

        self._load_proveedores()

    def _cargar_logo_proveedor(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona un logo",
            filetypes=[("Imagenes","*.png *.jpg *.jpeg *.webp *.bmp"),("Todos","*.*")])
        if ruta:
            self._logo_tmp = ruta
            self._lbl_logo.configure(text=Path(ruta).name, text_color=COLORS["success"])

    def _guardar_proveedor(self):
        nombre = self._prov_nombre.get().strip()
        if not nombre:
            self._prov_lbl_err.configure(text="El nombre es obligatorio.")
            return
        dest_logo = ""
        if self._logo_tmp and Path(self._logo_tmp).exists():
            ext  = Path(self._logo_tmp).suffix
            dest = LOGOS_DIR / f"prov_{nombre.replace(' ','_')}{ext}"
            shutil.copy2(self._logo_tmp, dest)
            dest_logo = str(dest)
        try:
            self._dao_prov.crear(nombre, dest_logo)
        except Exception as e:
            self._prov_lbl_err.configure(text=f"Error: {e}")
            return
        self._prov_nombre.delete(0, "end")
        self._lbl_logo.configure(text="Sin logo seleccionado", text_color=COLORS["muted"])
        self._logo_tmp = ""
        self._prov_lbl_err.configure(text="")
        self._load_proveedores()
        self._refresh_combobox()

    def _eliminar_proveedor(self):
        if not hasattr(self, "_selected_prov_id") or not self._selected_prov_id:
            messagebox.showwarning("Sin seleccion", "Haz clic en un proveedor primero.")
            return
        nombre = self._selected_prov_nombre
        if messagebox.askyesno("Confirmar", f"Eliminar '{nombre}'?"):
            self._dao_prov.eliminar(self._selected_prov_id)
            self._selected_prov_id   = None
            self._selected_prov_nombre = ""
            self._load_proveedores()
            self._refresh_combobox()

    def _load_proveedores(self):
        # Limpiar cards anteriores
        for w in self._cards_scroll.winfo_children():
            w.destroy()
        self._card_images.clear()

        provs = self._dao_prov.listar()
        self._selected_prov_id     = None
        self._selected_prov_nombre = ""

        if not provs:
            ctk.CTkLabel(self._cards_scroll,
                         text="No hay proveedores registrados.\nAgrega uno usando el formulario.",
                         font=(FONT,13), text_color=COLORS["muted"],
                         ).grid(row=0, column=0, columnspan=4, padx=20, pady=40)
            return

        for i, p in enumerate(provs):
            col = i % 4
            row = i // 4
            self._crear_card_proveedor(p, row, col)

    def _crear_card_proveedor(self, p, row, col):
        card = ctk.CTkFrame(self._cards_scroll, fg_color=COLORS["input"],
                            corner_radius=14, cursor="hand2")
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # Logo
        logo_label = ctk.CTkLabel(card, text="", width=80, height=80,
                                   fg_color=COLORS["card"], corner_radius=10)
        logo_label.grid(row=0, column=0, padx=12, pady=(14,6))

        ruta_logo = p.get("ruta_logo","") or ""
        if ruta_logo and Path(ruta_logo).exists():
            try:
                from PIL import Image as PILImg, ImageTk
                pil = PILImg.open(ruta_logo).convert("RGBA")
                pil.thumbnail((80, 80))
                tk_img = ImageTk.PhotoImage(pil)
                logo_label.configure(image=tk_img, fg_color="transparent")
                self._card_images.append(tk_img)
            except Exception:
                logo_label.configure(text="🏭", font=(FONT,32), fg_color="transparent")
        else:
            logo_label.configure(text="🏭", font=(FONT,32), fg_color="transparent")

        # Nombre
        ctk.CTkLabel(card, text=p["nombre"],
                     font=(FONT,11,"bold"), text_color=COLORS["text"],
                     wraplength=110, anchor="center").grid(
            row=1, column=0, padx=8, pady=(0,4))

        # Boton pedido
        btn_ped = ctk.CTkButton(card, text="Hacer Pedido", height=28,
                                 font=(FONT,10,"bold"), fg_color=COLORS["accent"],
                                 hover_color=COLORS["accent_h"], text_color="#fff",
                                 corner_radius=8,
                                 command=lambda _p=p: self._iniciar_pedido_desde_card(_p))
        btn_ped.grid(row=2, column=0, padx=10, pady=(2,12), sticky="ew")

        # Click en card selecciona
        for widget in (card, logo_label):
            widget.bind("<Button-1>", lambda e, _p=p: self._seleccionar_proveedor(_p))

    def _seleccionar_proveedor(self, p):
        self._selected_prov_id     = p["id"]
        self._selected_prov_nombre = p["nombre"]

    def _iniciar_pedido_desde_card(self, p):
        self._selected_prov_id     = p["id"]
        self._selected_prov_nombre = p["nombre"]
        self._refresh_combobox()
        if p["nombre"] in self._prov_nombres:
            self._combo_prov.set(p["nombre"])
        self._tabs.set("Hacer Pedido")

    # =======================================================================
    # PESTANA 2: Hacer Pedido
    # =======================================================================

    def _build_tab_pedido(self, parent):
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(parent, fg_color=COLORS["input"], corner_radius=10)
        top.grid(row=0, column=0, sticky="ew", pady=(0,10))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top, text="Proveedor:", font=(FONT,13,"bold"),
                     text_color=COLORS["muted"]).grid(row=0, column=0, padx=(16,8), pady=12)
        self._combo_prov = ctk.CTkComboBox(
            top, values=[], height=36, font=(FONT,12),
            fg_color=COLORS["card"], border_color=COLORS["border"],
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_h"],
            dropdown_fg_color=COLORS["card"], dropdown_text_color=COLORS["text"],
            text_color=COLORS["text"], corner_radius=8, state="readonly")
        self._combo_prov.grid(row=0, column=1, padx=(0,16), pady=12, sticky="ew")
        self._refresh_combobox()

        # Formulario de item
        item_f = ctk.CTkFrame(parent, fg_color=COLORS["input"], corner_radius=10)
        item_f.grid(row=1, column=0, sticky="ew", pady=(0,10))

        # Codigo (pequeno), Nombre (pequeno), Tipo (mas grande), Cantidad
        fields = [
            ("Codigo",   "_ped_codigo",    90, "Cod."),
            ("Nombre",   "_ped_nombre",   160, "Nombre del repuesto"),
            ("Tipo",     "_ped_tipo",     250, "Tipo / Categoria / Descripcion"),
            ("Cantidad", "_ped_cantidad",  60, "1"),
        ]
        self._entries_list = []
        for col_i, (lbl, attr, w, ph) in enumerate(fields):
            ctk.CTkLabel(item_f, text=lbl, font=(FONT,11),
                         text_color=COLORS["muted"]).grid(
                row=0, column=col_i*2,
                padx=(14 if col_i==0 else 4, 2), pady=(10,2), sticky="w")

            en = ctk.CTkEntry(item_f, width=w, height=34, font=(FONT,12),
                              placeholder_text=ph, fg_color=COLORS["card"],
                              border_color=COLORS["border"], text_color=COLORS["text"],
                              corner_radius=8)
            en.grid(row=0, column=col_i*2+1, padx=(0,4), pady=(10,2))
            
            def _make_keyrelease(en_ref, attr_name):
                def _on_key(e):
                    # ignore navigation keys
                    if e.keysym in ("Return", "Tab", "Left", "Right", "Up", "Down", "Shift_L", "Shift_R"):
                        return
                    val = en_ref.get()
                    if not val: return
                    if attr_name == "_ped_codigo":
                        new_val = val.upper()
                    else:
                        new_val = val[0].upper() + val[1:]
                    if val != new_val:
                        idx = en_ref._entry.index("insert")
                        en_ref.delete(0, "end")
                        en_ref.insert(0, new_val)
                        en_ref._entry.icursor(idx)
                return _on_key

            if attr != "_ped_cantidad":
                en.bind("<KeyRelease>", _make_keyrelease(en, attr))

            self._entries_list.append(en)
            setattr(self, attr, en)

        # Configurar saltos con Enter
        for i in range(len(self._entries_list) - 1):
            self._entries_list[i].bind("<Return>", lambda e, nxt=self._entries_list[i+1]: nxt.focus())


        ctk.CTkLabel(item_f, text="Unidad", font=(FONT,11),
                     text_color=COLORS["muted"]).grid(
            row=0, column=8, padx=(4,2), pady=(10,2), sticky="w")
        self._ped_unidad = ctk.CTkComboBox(
            item_f, values=["Unidad","Caja","Rollo"],
            width=90, height=34, font=(FONT,12),
            fg_color=COLORS["card"], border_color=COLORS["border"],
            button_color=COLORS["accent"], button_hover_color=COLORS["accent_h"],
            dropdown_fg_color=COLORS["card"], dropdown_text_color=COLORS["text"],
            text_color=COLORS["text"], corner_radius=8, state="readonly")
        self._ped_unidad.set("Unidad")
        self._ped_unidad.grid(row=0, column=9, padx=(0,6), pady=(10,2))

        self._ped_lbl_err = ctk.CTkLabel(item_f, text="", font=(FONT,10),
                                          text_color=COLORS["danger"])
        self._ped_lbl_err.grid(row=1, column=0, columnspan=10, padx=14, pady=(2,4), sticky="w")
        btn_anadir = ctk.CTkButton(item_f, text="Añadir", height=34, width=70,
                      font=(FONT,12,"bold"), fg_color=COLORS["success"],
                      hover_color=COLORS["success_h"], text_color="#fff",
                      corner_radius=8, command=self._anadir_item)
        btn_anadir.grid(row=0, column=10, padx=(4,8), pady=(10,2), sticky="ew")
        
        # Add return binding to cantidad to trigger Anadir
        self._ped_cantidad.bind("<Return>", lambda e: self._anadir_item())

        # Treeview temporal
        ped_f = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        ped_f.grid(row=2, column=0, sticky="nsew")
        ped_f.grid_rowconfigure(1, weight=1)
        ped_f.grid_columnconfigure(0, weight=1)

        lbl_row = ctk.CTkFrame(ped_f, fg_color="transparent")
        lbl_row.grid(row=0, column=0, padx=14, pady=(10,4), sticky="ew")
        lbl_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lbl_row, text="Items del pedido",
                     font=(FONT,13,"bold"), text_color=COLORS["text"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        btn_row = ctk.CTkFrame(lbl_row, fg_color="transparent")
        btn_row.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btn_row, text="Quitar", width=80, height=28,
                      font=(FONT,11), fg_color="#3a0a0a",
                      hover_color=COLORS["danger"], text_color=COLORS["danger"],
                      corner_radius=8, command=self._quitar_item,
                      ).pack(side="left", padx=(0,4))
        ctk.CTkButton(btn_row, text="Limpiar", width=80, height=28,
                      font=(FONT,11), fg_color=COLORS["border"],
                      hover_color=COLORS["danger"], text_color=COLORS["muted"],
                      corner_radius=8, command=self._limpiar_pedido,
                      ).pack(side="left", padx=(0,4))
        ctk.CTkButton(btn_row, text="Generar Pedido (PNG)", width=160, height=28,
                      font=(FONT,11,"bold"), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_h"], text_color="#fff",
                      corner_radius=8, command=self._generar_pedido,
                      ).pack(side="left")

        tw = ctk.CTkFrame(ped_f, fg_color=COLORS["card"], corner_radius=0)
        tw.grid(row=1, column=0, padx=12, pady=(0,12), sticky="nsew")
        tw.grid_rowconfigure(0, weight=1); tw.grid_columnconfigure(0, weight=1)
        self._ped_tree = _make_tree(tw, cols=[
            ("#",        "#",         30,  "center"),
            ("codigo",   "Codigo",    80,  "w"),
            ("nombre",   "Nombre",   240,  "w"),
            ("tipo",     "Tipo",     250,  "w"),
            ("cantidad", "Cant.",     60,  "center"),
            ("unidad",   "Unidad",    80,  "center"),
        ], style_name="Ped.Treeview")
        self._ped_tree.bind("<Double-1>", self._on_ped_tree_double_click)

    def _refresh_combobox(self):
        provs = self._dao_prov.listar()
        self._prov_nombres = {p["nombre"]: p for p in provs}
        nombres = list(self._prov_nombres.keys())
        self._combo_prov.configure(values=nombres)
        if nombres: self._combo_prov.set(nombres[0])
        else:       self._combo_prov.set("")

    def _anadir_item(self):
        self._ped_lbl_err.configure(text="")
        nombre = self._ped_nombre.get().strip()
        if not nombre:
            self._ped_lbl_err.configure(text="El nombre es obligatorio.")
            return
        cant_str = self._ped_cantidad.get().strip()
        if not cant_str:
            cant_str = "1"
        try:
            cantidad = int(cant_str)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self._ped_lbl_err.configure(text="La cantidad debe ser un numero entero positivo.")
            return
        self._pedido_items.append({
            "codigo":   self._ped_codigo.get().strip(),
            "nombre":   nombre,
            "tipo":     self._ped_tipo.get().strip(),
            "cantidad": cantidad,
            "unidad":   self._ped_unidad.get(),
        })
        self._refresh_ped_tree()
        for attr in ("_ped_codigo","_ped_nombre","_ped_tipo","_ped_cantidad"):
            getattr(self, attr).delete(0, "end")
        self._ped_unidad.set("Unidad")

    def _on_ped_tree_double_click(self, _event=None):
        sel = self._ped_tree.selection()
        if not sel: return
        idx = int(sel[0])
        item = self._pedido_items.pop(idx)
        self._ped_codigo.delete(0, "end"); self._ped_codigo.insert(0, item["codigo"])
        self._ped_nombre.delete(0, "end"); self._ped_nombre.insert(0, item["nombre"])
        self._ped_tipo.delete(0, "end"); self._ped_tipo.insert(0, item["tipo"])
        self._ped_cantidad.delete(0, "end"); self._ped_cantidad.insert(0, str(item["cantidad"]))
        self._ped_unidad.set(item["unidad"])
        self._refresh_ped_tree()
        self._ped_codigo.focus()

    def _refresh_ped_tree(self):
        for row in self._ped_tree.get_children():
            self._ped_tree.delete(row)
        for i, item in enumerate(self._pedido_items):
            tag = "even" if i % 2 == 0 else "odd"
            self._ped_tree.insert("","end", iid=str(i), tags=(tag,), values=(
                i+1, item["codigo"], item["nombre"],
                item["tipo"], item["cantidad"], item["unidad"]))

    def _quitar_item(self):
        sel = self._ped_tree.selection()
        if sel:
            self._pedido_items.pop(int(sel[0]))
            self._refresh_ped_tree()

    def _limpiar_pedido(self):
        if not self._pedido_items: return
        if messagebox.askyesno("Limpiar","Limpiar todos los items?"):
            self._pedido_items.clear()
            self._refresh_ped_tree()

    def _generar_pedido(self):
        nombre_prov = self._combo_prov.get().strip()
        if not nombre_prov or nombre_prov not in self._prov_nombres:
            messagebox.showwarning("Sin proveedor","Selecciona un proveedor valido.")
            return
        if not self._pedido_items:
            messagebox.showwarning("Sin items","Aniade al menos un repuesto.")
            return
        prov_data = self._prov_nombres[nombre_prov]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_png  = PEDIDOS_DIR / f"pedido_{prov_data['id']}_{timestamp}.png"
        try:
            generar_imagen_pedido(
                nombre_empresa=self.EMPRESA_NOMBRE,
                logo_empresa_ruta=self.EMPRESA_LOGO,
                nombre_proveedor=nombre_prov,
                logo_proveedor_ruta=prov_data.get("ruta_logo", ""),
                items=self._pedido_items,
                ruta_salida=ruta_png)
        except RuntimeError as e:
            messagebox.showerror("Error de Pillow", str(e)); return
        except Exception as e:
            messagebox.showerror("Error al generar imagen", str(e)); return
        try:
            self._dao_ped.crear(prov_data["id"], str(ruta_png), self._pedido_items)
        except Exception as e:
            messagebox.showerror("Error BD", str(e)); return
        self._pedido_items.clear()
        self._refresh_ped_tree()
        self._load_historial()
        messagebox.showinfo("Pedido generado", f"Imagen guardada en:\n{ruta_png}")
        try: os.startfile(str(ruta_png))
        except Exception: pass

    # =======================================================================
    # PESTANA 3: Historial
    # =======================================================================

    def _build_tab_historial(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0,8))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Historial de Pedidos",
                     font=(FONT,14,"bold"), text_color=COLORS["text"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(top, text="Clic en un pedido para ver detalle   |   Doble-clic para abrir imagen",
                     font=(FONT,10), text_color=COLORS["muted"],
                     anchor="e").grid(row=0, column=1, sticky="e")
        ctk.CTkButton(top, text="Actualizar", width=100, height=28,
                      font=(FONT,11), fg_color=COLORS["border"],
                      hover_color=COLORS["accent"], text_color=COLORS["text"],
                      corner_radius=8, command=self._load_historial,
                      ).grid(row=0, column=2, padx=(8,0), sticky="e")

        tw = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        tw.grid(row=1, column=0, sticky="nsew")
        tw.grid_rowconfigure(0, weight=1); tw.grid_columnconfigure(0, weight=1)
        self._hist_tree = _make_tree(tw, cols=[
            ("id",        "ID",         60,  "center"),
            ("proveedor", "Proveedor",  220, "w"),
            ("fecha",     "Fecha",      180, "center"),
            ("ruta",      "Archivo",    380, "w"),
        ], style_name="Hist.Treeview")
        self._hist_tree.bind("<Double-1>",   self._on_historial_dobleclick)
        self._hist_tree.bind("<<TreeviewSelect>>", self._on_historial_select)
        self._load_historial()

    def _load_historial(self):
        for row in self._hist_tree.get_children():
            self._hist_tree.delete(row)
        for i, ped in enumerate(self._dao_ped.listar()):
            tag = "even" if i % 2 == 0 else "odd"
            self._hist_tree.insert("","end", iid=str(ped["id"]), tags=(tag,),
                                   values=(ped["id"], ped["proveedor"],
                                           ped["fecha"].replace("T","  "),
                                           ped["ruta_imagen"]))

    def _on_historial_select(self, _event=None):
        sel = self._hist_tree.selection()
        if not sel: return
        pedido_id = int(sel[0])
        items = self._dao_ped.listar_items(pedido_id)
        self._mostrar_detalle_pedido(pedido_id, items)

    def _mostrar_detalle_pedido(self, pedido_id, items):
        win = ctk.CTkToplevel(self.winfo_toplevel())
        win.title(f"Detalle del Pedido #{pedido_id}")
        win.resizable(True, True)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.focus_force()

        frame = ctk.CTkFrame(win, fg_color=COLORS["bg"])
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text=f"Pedido #{pedido_id} — Lista de items",
                     font=(FONT,15,"bold"), text_color=COLORS["accent"],
                     anchor="w").grid(row=0, column=0, pady=(0,12), sticky="w")

        tw_f = ctk.CTkFrame(frame, fg_color=COLORS["card"], corner_radius=10)
        tw_f.grid(row=1, column=0, sticky="nsew")
        tw_f.grid_rowconfigure(0, weight=1); tw_f.grid_columnconfigure(0, weight=1)

        tree = _make_tree(tw_f, cols=[
            ("#",        "#",        30,  "center"),
            ("codigo",   "Codigo",   90,  "w"),
            ("nombre",   "Nombre",  220,  "w"),
            ("tipo",     "Tipo",    100,  "w"),
            ("cantidad", "Cant.",    60,  "center"),
            ("unidad",   "Unidad",   80,  "center"),
        ], style_name="Det.Treeview")

        for i, it in enumerate(items):
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("","end", tags=(tag,), values=(
                i+1, it["codigo"], it["nombre"],
                it["tipo"], it["cantidad"], it["unidad"]))

        ctk.CTkButton(frame, text="Cerrar", height=36,
                      font=(FONT,12,"bold"), fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_h"], text_color="#fff",
                      corner_radius=10, command=win.destroy,
                      ).grid(row=2, column=0, pady=(12,0), sticky="ew")

        win.update_idletasks()
        w, h = 680, 400
        px = self.winfo_toplevel().winfo_rootx()
        py = self.winfo_toplevel().winfo_rooty()
        pw = self.winfo_toplevel().winfo_width()
        ph = self.winfo_toplevel().winfo_height()
        win.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")

    def _on_historial_dobleclick(self, _event=None):
        sel = self._hist_tree.selection()
        if not sel: return
        ruta = self._hist_tree.item(sel[0], "values")[3]
        if not ruta or not Path(ruta).exists():
            messagebox.showwarning("No encontrado", f"Archivo no existe:\n{ruta}")
            return
        try: os.startfile(ruta)
        except Exception as e: messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_proveedores()
        self._refresh_combobox()
        self._load_historial()
