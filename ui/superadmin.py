"""
ui/superadmin.py
================
Panel de control exclusivo para el SuperAdmin.
"""

import shutil
import sys
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import EmpresasDAO, UsuariosDAO, get_connection  # noqa: E402

FONT = "Segoe UI"
ROOT_DIR  = Path(__file__).resolve().parent.parent
LOGOS_DIR = ROOT_DIR / "logos"
LOGOS_DIR.mkdir(exist_ok=True)

C = {
    "bg":       "#0b0d14",
    "card":     "#1c1f2b",
    "input":    "#252836",
    "border":   "#2e3246",
    "accent":   "#4f8ef7",
    "accent_h": "#3a6fd8",
    "danger":   "#e05c5c",
    "success":  "#3ecf8e",
    "text":     "#e8eaf0",
    "muted":    "#8b91a7",
    "gold":     "#f5c518",
    "sidebar":  "#13151e",
}

ROL_COLOR = {"SuperAdmin": "#f5c518", "Admin": "#4f8ef7", "Empleado": "#3ecf8e"}


class SuperAdminPanel(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._dao_emp  = EmpresasDAO()
        self._dao_usr  = UsuariosDAO()
        self._logo_tmp = ""
        self._selected_emp_id = None
        self._empresa_map = {}
        self._setup_window()
        self._build()

    def _setup_window(self):
        self.title("Panel SuperAdmin - Gestion del Sistema")
        self.resizable(True, True)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()
        W, H = 1100, 700
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - W) // 2
        y = (sh - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")
        self.minsize(900, 580)

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0, height=70)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Panel de SuperAdmin",
                     font=(FONT, 22, "bold"), text_color=C["gold"], anchor="w",
                     ).grid(row=0, column=0, padx=24, pady=(14, 0), sticky="w")
        ctk.CTkLabel(hdr, text="Gestiona empresas, usuarios y licencias del sistema.",
                     font=(FONT, 11), text_color=C["muted"], anchor="w",
                     ).grid(row=1, column=0, padx=24, pady=(0, 10), sticky="w")

        self._tabs = ctk.CTkTabview(
            self, fg_color=C["card"],
            segmented_button_fg_color=C["input"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_h"],
            segmented_button_unselected_color=C["input"],
            segmented_button_unselected_hover_color=C["border"],
            text_color=C["text"], corner_radius=0,
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._tabs.add("Empresas")
        self._tabs.add("Usuarios")
        self._tabs.add("Mi Cuenta")

        self._build_tab_empresas(self._tabs.tab("Empresas"))
        self._build_tab_usuarios(self._tabs.tab("Usuarios"))
        self._build_tab_cuenta(self._tabs.tab("Mi Cuenta"))

    # ================================================================
    # TAB: Empresas
    # ================================================================

    def _build_tab_empresas(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        form = ctk.CTkFrame(parent, fg_color=C["input"], corner_radius=12, width=300)
        form.grid(row=0, column=0, padx=(0, 12), pady=0, sticky="nsew")
        form.grid_propagate(False)

        ctk.CTkLabel(form, text="Registrar Empresa",
                     font=(FONT, 14, "bold"), text_color=C["accent"]).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(form, text="Nombre *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._emp_nombre = ctk.CTkEntry(form, height=34, font=(FONT, 12),
            placeholder_text="Ej: Repuestos El Exito",
            fg_color=C["card"], border_color=C["border"], text_color=C["text"], corner_radius=8)
        self._emp_nombre.pack(fill="x", padx=16, pady=(2, 10))

        ctk.CTkLabel(form, text="Logo", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._emp_logo_preview = ctk.CTkLabel(form, text="Sin logo", width=100, height=60,
            fg_color=C["card"], corner_radius=10, font=(FONT, 10), text_color=C["muted"])
        self._emp_logo_preview.pack(pady=(4, 0))
        ctk.CTkButton(form, text="Cargar Logo", height=32, font=(FONT, 12),
            fg_color=C["border"], hover_color=C["accent"], text_color=C["text"],
            corner_radius=8, command=self._cargar_logo_empresa).pack(fill="x", padx=16, pady=(4, 12))

        self._emp_lbl_err = ctk.CTkLabel(form, text="", font=(FONT, 10), text_color=C["danger"])
        self._emp_lbl_err.pack(padx=16)

        ctk.CTkButton(form, text="Registrar Empresa", height=40,
            font=(FONT, 13, "bold"), fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#fff", corner_radius=10, command=self._guardar_empresa).pack(fill="x", padx=16, pady=(6, 0))
        ctk.CTkButton(form, text="Eliminar Seleccionada", height=34,
            font=(FONT, 11), fg_color="#3a0a0a", hover_color=C["danger"],
            text_color=C["danger"], corner_radius=10, command=self._eliminar_empresa).pack(fill="x", padx=16, pady=(8, 16))

        right = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="Empresas Registradas", font=(FONT, 13, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        self._emp_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent", corner_radius=0)
        self._emp_scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self._emp_scroll.grid_columnconfigure(0, weight=1)
        self._refresh_empresas()

    def _cargar_logo_empresa(self):
        ruta = filedialog.askopenfilename(title="Logo",
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos", "*.*")])
        if ruta:
            self._logo_tmp = ruta
            try:
                from PIL import Image
                img = Image.open(ruta).convert("RGBA")
                img.thumbnail((80, 60))
                ctk_img = ctk.CTkImage(img, size=(80, 60))
                self._emp_logo_preview.configure(image=ctk_img, text="")
                self._emp_logo_preview._ctk_ref = ctk_img
            except Exception:
                self._emp_logo_preview.configure(text=Path(ruta).name)

    def _guardar_empresa(self):
        nombre = self._emp_nombre.get().strip()
        if not nombre:
            self._emp_lbl_err.configure(text="El nombre es obligatorio.")
            return
        ruta_logo = ""
        if self._logo_tmp and Path(self._logo_tmp).exists():
            ext = Path(self._logo_tmp).suffix
            safe = nombre.replace(" ", "_")
            dest = LOGOS_DIR / f"empresa_{safe}{ext}"
            shutil.copy2(self._logo_tmp, dest)
            ruta_logo = str(dest)
        try:
            self._dao_emp.crear(nombre, ruta_logo)
        except Exception as e:
            self._emp_lbl_err.configure(text=f"Error: {e}")
            return
        self._emp_nombre.delete(0, "end")
        self._logo_tmp = ""
        self._emp_logo_preview.configure(image=None, text="Sin logo")
        self._emp_lbl_err.configure(text="")
        self._refresh_empresas()
        self._refresh_empresa_combo()
        messagebox.showinfo("Listo", f"Empresa '{nombre}' registrada correctamente.")

    def _eliminar_empresa(self):
        if not self._selected_emp_id:
            messagebox.showwarning("Seleccion", "Haz clic en una empresa primero.")
            return
        if messagebox.askyesno("Confirmar", "Eliminar esta empresa? Los usuarios seran desvinculados."):
            self._dao_emp.eliminar(self._selected_emp_id)
            self._selected_emp_id = None
            self._refresh_empresas()
            self._refresh_empresa_combo()

    def _refresh_empresas(self):
        for w in self._emp_scroll.winfo_children():
            w.destroy()
        empresas = self._dao_emp.listar()
        if not empresas:
            ctk.CTkLabel(self._emp_scroll, text="No hay empresas registradas.",
                         font=(FONT, 12), text_color=C["muted"]).pack(pady=30)
            return
        for emp in empresas:
            self._crear_empresa_card(emp)

    def _crear_empresa_card(self, emp):
        es_sel = (emp["id"] == self._selected_emp_id)
        card = ctk.CTkFrame(self._emp_scroll, fg_color=C["input"], corner_radius=12, cursor="hand2",
                            border_width=2, border_color=C["accent"] if es_sel else C["border"])
        card.pack(fill="x", padx=4, pady=4)
        card.grid_columnconfigure(1, weight=1)
        logo_lbl = ctk.CTkLabel(card, text="[emp]", font=(FONT, 10), width=60, height=50)
        logo_lbl.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=10)
        ruta = emp.get("ruta_logo", "")
        if ruta and Path(ruta).exists():
            try:
                from PIL import Image
                img = Image.open(ruta).convert("RGBA")
                img.thumbnail((48, 48))
                ctk_img = ctk.CTkImage(img, size=(48, 48))
                logo_lbl.configure(image=ctk_img, text="")
                logo_lbl._ctk_ref = ctk_img
            except Exception:
                pass
        ctk.CTkLabel(card, text=emp["nombre"], font=(FONT, 13, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=1, padx=4, pady=(10, 2), sticky="w")
        estado = "Activa" if emp["licencia_activa"] else "Inactiva"
        ctk.CTkLabel(card, text=f"ID: {emp['id']}  |  Licencia: {estado}",
                     font=(FONT, 10), text_color=C["muted"], anchor="w").grid(row=1, column=1, padx=4, pady=(0, 10), sticky="w")
        for w in (card, logo_lbl):
            w.bind("<Button-1>", lambda e, _id=emp["id"]: self._seleccionar_empresa(_id))

    def _seleccionar_empresa(self, emp_id):
        self._selected_emp_id = emp_id
        self._refresh_empresas()

    # ================================================================
    # TAB: Usuarios
    # ================================================================

    def _build_tab_usuarios(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        form = ctk.CTkFrame(parent, fg_color=C["input"], corner_radius=12, width=300)
        form.grid(row=0, column=0, padx=(0, 12), pady=0, sticky="nsew")
        form.grid_propagate(False)

        ctk.CTkLabel(form, text="Crear Usuario",
                     font=(FONT, 14, "bold"), text_color=C["accent"]).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(form, text="Usuario *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._usr_usuario = ctk.CTkEntry(form, height=32, font=(FONT, 12), placeholder_text="nombre_usuario",
            fg_color=C["card"], border_color=C["border"], text_color=C["text"], corner_radius=8)
        self._usr_usuario.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(form, text="Contrasena *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._usr_contrasena = ctk.CTkEntry(form, height=32, font=(FONT, 12), placeholder_text="contrasena",
            fg_color=C["card"], border_color=C["border"], text_color=C["text"], corner_radius=8, show="*")
        self._usr_contrasena.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(form, text="Rol *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._usr_rol = ctk.CTkComboBox(form, values=["Admin", "Empleado"], height=32, font=(FONT, 12),
            fg_color=C["card"], border_color=C["border"], button_color=C["accent"],
            button_hover_color=C["accent_h"], dropdown_fg_color=C["card"],
            dropdown_text_color=C["text"], text_color=C["text"], corner_radius=8, state="readonly")
        self._usr_rol.set("Empleado")
        self._usr_rol.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(form, text="Empresa asignada", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=16)
        self._usr_empresa_combo = ctk.CTkComboBox(form, values=[""], height=32, font=(FONT, 12),
            fg_color=C["card"], border_color=C["border"], button_color=C["accent"],
            button_hover_color=C["accent_h"], dropdown_fg_color=C["card"],
            dropdown_text_color=C["text"], text_color=C["text"], corner_radius=8, state="readonly")
        self._usr_empresa_combo.pack(fill="x", padx=16, pady=(2, 8))
        self._refresh_empresa_combo()

        self._usr_lbl_err = ctk.CTkLabel(form, text="", font=(FONT, 10), text_color=C["danger"])
        self._usr_lbl_err.pack(padx=16)
        ctk.CTkButton(form, text="Crear Usuario", height=40, font=(FONT, 13, "bold"),
            fg_color=C["accent"], hover_color=C["accent_h"], text_color="#fff",
            corner_radius=10, command=self._crear_usuario).pack(fill="x", padx=16, pady=(6, 16))

        right = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hdr_row = ctk.CTkFrame(right, fg_color="transparent")
        hdr_row.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        hdr_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr_row, text="Usuarios del Sistema", font=(FONT, 13, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr_row, text="Actualizar", width=100, height=28, font=(FONT, 11),
            fg_color=C["border"], hover_color=C["accent"], text_color=C["text"],
            corner_radius=8, command=self._refresh_usuarios).grid(row=0, column=1, sticky="e")

        self._usr_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent", corner_radius=0)
        self._usr_scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self._usr_scroll.grid_columnconfigure(0, weight=1)
        self._refresh_usuarios()

    def _refresh_empresa_combo(self):
        empresas = self._dao_emp.listar()
        self._empresa_map = {e["nombre"]: e["id"] for e in empresas}
        nombres = list(self._empresa_map.keys())
        if hasattr(self, "_usr_empresa_combo"):
            opciones = nombres if nombres else ["Sin empresa"]
            self._usr_empresa_combo.configure(values=opciones)
            self._usr_empresa_combo.set(opciones[0])

    def _crear_usuario(self):
        self._usr_lbl_err.configure(text="")
        usuario    = self._usr_usuario.get().strip()
        contrasena = self._usr_contrasena.get()
        rol        = self._usr_rol.get()
        emp_nombre = self._usr_empresa_combo.get()
        if not usuario or not contrasena:
            self._usr_lbl_err.configure(text="Usuario y contrasena son obligatorios.")
            return
        if len(contrasena) < 4:
            self._usr_lbl_err.configure(text="Minimo 4 caracteres en la contrasena.")
            return
        empresa_id = self._empresa_map.get(emp_nombre)
        try:
            self._dao_usr.crear_usuario(usuario, contrasena, rol, empresa_id)
        except ValueError as e:
            self._usr_lbl_err.configure(text=str(e))
            return
        except Exception as e:
            self._usr_lbl_err.configure(text=f"Error: {e}")
            return
        self._usr_usuario.delete(0, "end")
        self._usr_contrasena.delete(0, "end")
        self._usr_lbl_err.configure(text="")
        self._refresh_usuarios()
        messagebox.showinfo("Listo", f"Usuario '{usuario}' creado con rol '{rol}'.")

    def _refresh_usuarios(self):
        for w in self._usr_scroll.winfo_children():
            w.destroy()
        usuarios = self._dao_usr.listar_usuarios()

        hf = ctk.CTkFrame(self._usr_scroll, fg_color=C["input"], corner_radius=8)
        hf.pack(fill="x", padx=4, pady=(0, 4))
        hf.grid_columnconfigure((0, 1, 2), weight=1)
        for col, txt in enumerate(["Usuario", "Rol", "Empresa"]):
            ctk.CTkLabel(hf, text=txt, font=(FONT, 10, "bold"), text_color=C["muted"]).grid(
                row=0, column=col, padx=12, pady=8, sticky="w")

        for i, usr in enumerate(usuarios):
            bg = C["card"] if i % 2 == 0 else C["input"]
            rf = ctk.CTkFrame(self._usr_scroll, fg_color=bg, corner_radius=8)
            rf.pack(fill="x", padx=4, pady=1)
            rf.grid_columnconfigure((0, 1, 2), weight=1)
            ctk.CTkLabel(rf, text=f"  {usr['usuario']}", font=(FONT, 12), text_color=C["text"], anchor="w").grid(
                row=0, column=0, padx=12, pady=8, sticky="w")
            rol_c = ROL_COLOR.get(usr["rol"], C["muted"])
            ctk.CTkLabel(rf, text=usr["rol"], font=(FONT, 11, "bold"), text_color=rol_c, anchor="w").grid(
                row=0, column=1, padx=12, pady=8, sticky="w")
            ctk.CTkLabel(rf, text=usr.get("empresa_nombre") or "---",
                         font=(FONT, 11), text_color=C["muted"], anchor="w").grid(
                row=0, column=2, padx=12, pady=8, sticky="w")

    # ================================================================
    # TAB: Mi Cuenta
    # ================================================================

    def _build_tab_cuenta(self, parent):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=16, width=420)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="Cambiar Contrasena del SuperAdmin",
                     font=(FONT, 14, "bold"), text_color=C["gold"]).pack(padx=24, pady=(20, 12), anchor="w")

        ctk.CTkLabel(card, text="Nueva contrasena *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=24)
        self._cuenta_nueva = ctk.CTkEntry(card, height=34, font=(FONT, 12), placeholder_text="nueva contrasena",
            fg_color=C["input"], border_color=C["border"], text_color=C["text"], corner_radius=8, show="*", width=320)
        self._cuenta_nueva.pack(padx=24, pady=(2, 8))

        ctk.CTkLabel(card, text="Confirmar contrasena *", font=(FONT, 11), text_color=C["muted"]).pack(anchor="w", padx=24)
        self._cuenta_conf = ctk.CTkEntry(card, height=34, font=(FONT, 12), placeholder_text="repetir",
            fg_color=C["input"], border_color=C["border"], text_color=C["text"], corner_radius=8, show="*", width=320)
        self._cuenta_conf.pack(padx=24, pady=(2, 8))

        self._cuenta_err = ctk.CTkLabel(card, text="", font=(FONT, 10), text_color=C["danger"])
        self._cuenta_err.pack(padx=24)

        ctk.CTkButton(card, text="Guardar Contrasena", height=40, width=320,
            font=(FONT, 13, "bold"), fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#fff", corner_radius=10, command=self._cambiar_contrasena).pack(padx=24, pady=(6, 20))

    def _cambiar_contrasena(self):
        nueva = self._cuenta_nueva.get()
        conf  = self._cuenta_conf.get()
        if not nueva or not conf:
            self._cuenta_err.configure(text="Completa ambos campos.")
            return
        if nueva != conf:
            self._cuenta_err.configure(text="Las contrasenas no coinciden.")
            return
        if len(nueva) < 4:
            self._cuenta_err.configure(text="Minimo 4 caracteres.")
            return
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT id FROM usuarios WHERE rol = 'SuperAdmin' LIMIT 1").fetchone()
            if not row:
                self._cuenta_err.configure(text="No se encontro el SuperAdmin.")
                return
            self._dao_usr.cambiar_contrasena(row["id"], nueva)
            self._cuenta_nueva.delete(0, "end")
            self._cuenta_conf.delete(0, "end")
            self._cuenta_err.configure(text="")
            messagebox.showinfo("Listo", "Contrasena actualizada correctamente.")
        except Exception as e:
            self._cuenta_err.configure(text=f"Error: {e}")
