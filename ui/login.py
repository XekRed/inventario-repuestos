"""
ui/login.py
===========
Pantalla de inicio de sesión del Sistema de Inventario.

Diseño moderno: panel izquierdo decorativo + tarjeta derecha con el formulario.

Flujo:
  1. El usuario ingresa nombre y contraseña.
  2. Se verifica contra la tabla `usuarios` (hash SHA-256).
  3. Si es correcto, llama a master._on_login_success(resultado).
  4. Si es incorrecto, muestra mensaje de error animado.
"""

import sys
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database.inventario_db import UsuariosDAO  # noqa: E402

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT = "Segoe UI"

C = {
    "bg":           "#0b0d14",
    "panel_left":   "#0f1117",
    "card":         "#1c1f2b",
    "input":        "#252836",
    "border":       "#2e3246",
    "accent":       "#4f8ef7",
    "accent_h":     "#3a6fd8",
    "danger":       "#e05c5c",
    "success":      "#3ecf8e",
    "text":         "#e8eaf0",
    "muted":        "#8b91a7",
    "gold":         "#f5c518",
}

ROL_COLOR = {"Admin": C["accent"], "Empleado": C["success"]}


# ===========================================================================
# LoginWindow
# ===========================================================================

class LoginWindow(ctk.CTkToplevel):
    """
    Ventana de login (CTkToplevel).

    Diseño: ventana dividida en dos partes.
      - Izquierda: panel decorativo oscuro con branding.
      - Derecha:   tarjeta con formulario de acceso.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.result: dict | None = None
        self._dao      = UsuariosDAO()
        self._intentos = 0

        self._setup_window()
        self._build()

    # ------------------------------------------------------------------
    # Ventana
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.title("RepuestosDB — Iniciar Sesión")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.grab_set()
        self.focus_force()

        W, H = 820, 540
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - W) // 2
        y = (self.winfo_screenheight() - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)   # panel izquierdo
        self.grid_columnconfigure(1, weight=1)   # panel derecho

        self._build_left_panel()
        self._build_right_panel()

    # ------------------------------------------------------------------
    # Panel izquierdo — branding
    # ------------------------------------------------------------------

    def _build_left_panel(self):
        left = ctk.CTkFrame(self, fg_color=C["panel_left"], corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(left, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Logo
        ctk.CTkLabel(inner, text="⚡", font=(FONT, 64),
                     text_color=C["accent"]).pack(pady=(0, 8))

        ctk.CTkLabel(inner, text="RepuestosDB",
                     font=(FONT, 26, "bold"), text_color=C["text"]).pack()

        ctk.CTkLabel(inner, text="Sistema de Gestión\nde Inventario Profesional",
                     font=(FONT, 12), text_color=C["muted"],
                     justify="center").pack(pady=(8, 40))

        # Características del sistema
        features = [
            ("📦", "Control de inventario en tiempo real"),
            ("🛒", "Punto de venta integrado"),
            ("📊", "Reportes y estadísticas del día"),
            ("🔒", "Acceso con roles y permisos"),
        ]
        for icon, text in features:
            row = ctk.CTkFrame(inner, fg_color=C["card"], corner_radius=10)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=f" {icon}  {text}",
                         font=(FONT, 11), text_color=C["muted"],
                         anchor="w").pack(padx=14, pady=8, fill="x")

        # Versión
        ctk.CTkLabel(inner, text="v1.0  •  Offline First  •  SQLite",
                     font=(FONT, 9), text_color="#3a3f55").pack(pady=(20, 0))

    # ------------------------------------------------------------------
    # Panel derecho — formulario
    # ------------------------------------------------------------------

    def _build_right_panel(self):
        right = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(right, fg_color="transparent")
        form.place(relx=0.5, rely=0.5, anchor="center")
        form.configure(width=340)

        # ── Encabezado ─────────────────────────────────────────────────
        ctk.CTkLabel(form, text="Bienvenido de vuelta",
                     font=(FONT, 22, "bold"), text_color=C["text"]).pack(anchor="w")

        ctk.CTkLabel(form, text="Ingresa tus credenciales para continuar",
                     font=(FONT, 12), text_color=C["muted"]).pack(anchor="w", pady=(4, 28))

        # ── Usuario ────────────────────────────────────────────────────
        ctk.CTkLabel(form, text="USUARIO", font=(FONT, 10, "bold"),
                     text_color=C["muted"]).pack(anchor="w")

        usuario_frame = ctk.CTkFrame(form, fg_color=C["input"],
                                     corner_radius=10, border_width=1,
                                     border_color=C["border"])
        usuario_frame.pack(fill="x", pady=(4, 16))
        usuario_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(usuario_frame, text=" 👤 ", font=(FONT, 14),
                     text_color=C["muted"]).grid(row=0, column=0, padx=(10, 0), pady=10)

        self._entry_usuario = ctk.CTkEntry(
            usuario_frame,
            placeholder_text="nombre de usuario",
            font=(FONT, 13), height=38, corner_radius=0,
            fg_color="transparent", border_width=0,
            text_color=C["text"],
        )
        self._entry_usuario.grid(row=0, column=1, padx=(4, 10), pady=6, sticky="ew")
        self._entry_usuario.bind("<Return>", lambda _: self._entry_contrasena.focus())

        # ── Contraseña ─────────────────────────────────────────────────
        ctk.CTkLabel(form, text="CONTRASEÑA", font=(FONT, 10, "bold"),
                     text_color=C["muted"]).pack(anchor="w")

        pass_frame = ctk.CTkFrame(form, fg_color=C["input"],
                                  corner_radius=10, border_width=1,
                                  border_color=C["border"])
        pass_frame.pack(fill="x", pady=(4, 8))
        pass_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(pass_frame, text=" 🔑 ", font=(FONT, 14),
                     text_color=C["muted"]).grid(row=0, column=0, padx=(10, 0), pady=10)

        self._entry_contrasena = ctk.CTkEntry(
            pass_frame,
            placeholder_text="contraseña",
            font=(FONT, 13), height=38, corner_radius=0,
            fg_color="transparent", border_width=0,
            text_color=C["text"], show="●",
        )
        self._entry_contrasena.grid(row=0, column=1, padx=(4, 10), pady=6, sticky="ew")
        self._entry_contrasena.bind("<Return>", lambda _: self._on_login())

        # ── Mensaje de error ───────────────────────────────────────────
        self._lbl_error = ctk.CTkLabel(form, text="", font=(FONT, 11),
                                        text_color=C["danger"])
        self._lbl_error.pack(pady=(4, 8))

        # ── Botón ──────────────────────────────────────────────────────
        self._btn_login = ctk.CTkButton(
            form,
            text="Iniciar sesión  →",
            font=(FONT, 14, "bold"),
            height=50, corner_radius=12,
            fg_color=C["accent"], hover_color=C["accent_h"],
            text_color="#fff",
            command=self._on_login,
        )
        self._btn_login.pack(fill="x", pady=(0, 8))

        self._entry_usuario.focus_force()

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------

    def _on_login(self):
        usuario    = self._entry_usuario.get().strip()
        contrasena = self._entry_contrasena.get()

        if not usuario or not contrasena:
            self._mostrar_error("Por favor, completa todos los campos.")
            return

        self._btn_login.configure(text="Verificando…", state="disabled")
        self.update()

        try:
            resultado = self._dao.verificar_credenciales(usuario, contrasena)
        except Exception as e:
            self._mostrar_error(f"Error de base de datos: {e}")
            self._btn_login.configure(text="Iniciar sesión  →", state="normal")
            return

        if resultado:
            self.result = resultado
            self._mostrar_bienvenida(resultado)
            self.after(750, lambda: self.master._on_login_success(resultado))
        else:
            self._intentos += 1
            msg = (
                f"Credenciales incorrectas ({self._intentos} intentos)."
                if self._intentos >= 3
                else "Usuario o contraseña incorrectos."
            )
            self._mostrar_error(msg)
            self._entry_contrasena.delete(0, "end")
            self._btn_login.configure(text="Iniciar sesión  →", state="normal")
            self._entry_contrasena.focus()

    def _mostrar_error(self, mensaje: str):
        self._lbl_error.configure(text=f"⚠  {mensaje}", text_color=C["danger"])

    def _mostrar_bienvenida(self, resultado: dict):
        rol   = resultado["rol"]
        color = ROL_COLOR.get(rol, C["accent"])
        self._lbl_error.configure(
            text=f"✓ Bienvenido, {resultado['usuario']}  [{rol}]",
            text_color=color,
        )
        self._btn_login.configure(text="Cargando…", fg_color=color, state="disabled")

    def _on_close(self):
        self.destroy()
