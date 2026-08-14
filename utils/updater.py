"""
utils/updater.py
================
Sistema de actualizaciones automáticas desde GitHub.

Flujo:
  1. Lee la versión local desde config/tasa.json
  2. Consulta la versión remota desde el raw de GitHub
  3. Compara usando semver
  4. Si hay actualización: muestra diálogo y hace git pull
  5. Reinicia la aplicación
"""

import os
import sys
import json
import threading
import subprocess
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REPO_URL_RAW   = "https://raw.githubusercontent.com/XekRed/inventario-repuestos/master/config/tasa.json"
REPO_GIT       = "https://github.com/XekRed/inventario-repuestos.git"
CONFIG_PATH    = Path(__file__).resolve().parent.parent / "config" / "tasa.json"
APP_DIR        = Path(__file__).resolve().parent.parent

COLORS = {
    "bg":      "#0f1117",
    "card":    "#1c1f2b",
    "input":   "#252836",
    "accent":  "#4f8ef7",
    "success": "#3ecf8e",
    "muted":   "#8b91a7",
    "border":  "#2e3246",
    "text":    "#e8eaf0",
    "danger":  "#e05c5c",
}
F = "Segoe UI"


# ---------------------------------------------------------------------------
# Funciones de versión
# ---------------------------------------------------------------------------

def _parse_version(v: str) -> tuple[int, ...]:
    """Convierte '1.2.3' → (1, 2, 3)"""
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0, 0, 0)


def get_local_version() -> str:
    """Lee la versión almacenada en config/tasa.json"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "1.0.0")
    except Exception:
        return "1.0.0"


def get_remote_version() -> str | None:
    """
    Descarga config/tasa.json desde GitHub y extrae la versión.
    Devuelve None si no hay conexión o falla.
    """
    try:
        import urllib.request
        with urllib.request.urlopen(REPO_URL_RAW, timeout=8) as r:
            data = json.loads(r.read().decode())
        return data.get("version", None)
    except Exception:
        return None


def _has_git() -> bool:
    """Comprueba si git está instalado y disponible."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def do_git_pull() -> tuple[bool, str]:
    """
    Ejecuta `git pull` en el directorio del proyecto.
    Retorna (éxito: bool, mensaje: str).
    """
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True,
            cwd=str(APP_DIR), timeout=60,
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "Actualización completada."
        else:
            return False, result.stderr.strip() or "Error desconocido en git pull."
    except subprocess.TimeoutExpired:
        return False, "La descarga tardó demasiado. Verifica tu conexión a internet."
    except FileNotFoundError:
        return False, "Git no está instalado o no se encontró en el PATH del sistema."
    except Exception as e:
        return False, str(e)


def restart_app():
    """Reinicia el proceso principal de la aplicación."""
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception:
        # Fallback: abrir como nuevo proceso y cerrar éste
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)


# ---------------------------------------------------------------------------
# Ventana de actualización premium
# ---------------------------------------------------------------------------

class UpdaterWindow(ctk.CTkToplevel):
    """Modal premium que gestiona todo el flujo de actualización."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Actualizaciones")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self._local_ver  = get_local_version()
        self._remote_ver = None
        self._updating   = False

        self._build()
        self._center(parent)
        # Buscar en hilo separado para no bloquear la UI
        threading.Thread(target=self._check_update, daemon=True).start()

    # ------------------------------------------------------------------
    def _build(self):
        self.configure(fg_color=COLORS["bg"])

        wrapper = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=18)
        wrapper.pack(padx=24, pady=24, fill="both", expand=True)

        # Encabezado
        ctk.CTkLabel(wrapper, text="⚡ Actualizaciones",
                     font=(F, 20, "bold"), text_color=COLORS["accent"]
                     ).pack(padx=24, pady=(22, 4), anchor="w")

        ctk.CTkLabel(wrapper,
                     text="Se verificará si existe una versión más reciente en GitHub.",
                     font=(F, 11), text_color=COLORS["muted"]
                     ).pack(padx=24, pady=(0, 16), anchor="w")

        # Separador
        ctk.CTkFrame(wrapper, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 16))

        # Versión local
        row_local = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        row_local.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(row_local, text="Versión instalada", font=(F, 11),
                     text_color=COLORS["muted"]).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(row_local, text=self._local_ver, font=(F, 13, "bold"),
                     text_color=COLORS["text"]).pack(side="right", padx=16, pady=12)

        # Versión remota (se actualiza tras búsqueda)
        row_remote = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        row_remote.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(row_remote, text="Última versión disponible", font=(F, 11),
                     text_color=COLORS["muted"]).pack(side="left", padx=16, pady=12)
        self._lbl_remote = ctk.CTkLabel(row_remote, text="Buscando…", font=(F, 13, "bold"),
                                         text_color=COLORS["muted"])
        self._lbl_remote.pack(side="right", padx=16, pady=12)

        # Barra de progreso
        self._progress = ctk.CTkProgressBar(wrapper, width=340, height=6,
                                              fg_color=COLORS["border"],
                                              progress_color=COLORS["accent"])
        self._progress.pack(padx=16, pady=(0, 4))
        self._progress.set(0)
        self._progress.configure(mode="indeterminate")
        self._progress.start()

        # Etiqueta de estado
        self._lbl_status = ctk.CTkLabel(wrapper, text="Conectando con GitHub…",
                                         font=(F, 11), text_color=COLORS["muted"])
        self._lbl_status.pack(pady=(4, 16))

        # Botones
        btn_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._btn_update = ctk.CTkButton(
            btn_row, text="⬇️  Actualizar Ahora", height=42,
            font=(F, 13, "bold"),
            fg_color=COLORS["accent"], hover_color="#3a6fd8",
            text_color="#fff", corner_radius=10, state="disabled",
            command=self._do_update)
        self._btn_update.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_close = ctk.CTkButton(
            btn_row, text="Cerrar", height=42,
            font=(F, 13),
            fg_color=COLORS["input"], hover_color=COLORS["border"],
            text_color=COLORS["muted"], corner_radius=10,
            command=self.destroy)
        self._btn_close.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ------------------------------------------------------------------
    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h   = 440, self.winfo_reqheight() + 20
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")

    # ------------------------------------------------------------------
    def _check_update(self):
        """Hilo: busca la versión remota y actualiza la UI."""
        remote = get_remote_version()
        # Actualizar UI en el hilo principal
        self.after(0, self._on_check_done, remote)

    def _on_check_done(self, remote_ver: str | None):
        self._progress.stop()
        self._progress.configure(mode="determinate")

        if remote_ver is None:
            self._progress.set(0)
            self._lbl_remote.configure(text="Sin conexión", text_color=COLORS["danger"])
            self._lbl_status.configure(
                text="⚠️  No se pudo conectar con GitHub. Verifica tu internet.",
                text_color=COLORS["danger"])
            return

        self._remote_ver = remote_ver
        self._lbl_remote.configure(text=remote_ver, text_color=COLORS["text"])

        local_t  = _parse_version(self._local_ver)
        remote_t = _parse_version(remote_ver)

        if remote_t > local_t:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_status.configure(
                text=f"🎉  Hay una nueva versión disponible: {remote_ver}",
                text_color=COLORS["success"])
            self._btn_update.configure(state="normal")
        else:
            self._progress.set(1)
            self._lbl_status.configure(
                text="✅  Ya tienes la versión más reciente instalada.",
                text_color=COLORS["success"])

    # ------------------------------------------------------------------
    def _do_update(self):
        """Ejecuta git pull en un hilo y muestra progreso."""
        if self._updating:
            return
        self._updating = True
        self._btn_update.configure(state="disabled", text="Actualizando…")
        self._btn_close.configure(state="disabled")
        self._lbl_status.configure(
            text="⬇️  Descargando actualización… por favor espera.",
            text_color=COLORS["accent"])
        self._progress.configure(mode="indeterminate")
        self._progress.start()
        threading.Thread(target=self._run_pull, daemon=True).start()

    def _run_pull(self):
        ok, msg = do_git_pull()
        self.after(0, self._on_pull_done, ok, msg)

    def _on_pull_done(self, ok: bool, msg: str):
        self._progress.stop()
        self._progress.configure(mode="determinate")
        if ok:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_status.configure(
                text="✅  Actualización completada. Reiniciando…",
                text_color=COLORS["success"])
            self.after(1500, self._restart_now)
        else:
            self._progress.set(0)
            self._lbl_status.configure(
                text=f"❌  Error: {msg[:80]}", text_color=COLORS["danger"])
            self._btn_update.configure(state="normal", text="⬇️  Reintentar")
            self._btn_close.configure(state="normal")
            self._updating = False

    def _restart_now(self):
        self.destroy()
        restart_app()


# ---------------------------------------------------------------------------
# Función de lanzamiento rápido
# ---------------------------------------------------------------------------

def abrir_actualizador(parent):
    """Abre la ventana del actualizador desde cualquier botón del sidebar."""
    UpdaterWindow(parent)
