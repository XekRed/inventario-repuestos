"""
utils/updater.py
================
Sistema de actualizaciones automáticas desde GitHub (repositorio privado).

Usa git fetch + git log para comparar commits sin necesitar acceso HTTP
al raw del repositorio, lo que funciona con repos privados si las
credenciales de git ya están guardadas.
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

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "tasa.json"
APP_DIR     = Path(__file__).resolve().parent.parent

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
    "warn":    "#e0954a",
}
F = "Segoe UI"


# ---------------------------------------------------------------------------
# Funciones de versión
# ---------------------------------------------------------------------------

def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except Exception:
        return (0, 0, 0)


def get_local_version() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "1.0.0")
    except Exception:
        return "1.0.0"


def _run_git(*args, timeout=15) -> tuple:
    """Ejecuta un comando git. Devuelve (success, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True,
            cwd=str(APP_DIR), timeout=timeout,
        )
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return False, "", "Git no está instalado."
    except subprocess.TimeoutExpired:
        return False, "", "Tiempo de espera agotado."
    except Exception as e:
        return False, "", str(e)


def check_for_updates() -> dict:
    """
    Verifica si hay actualizaciones usando git fetch + git log.
    Retorna un dict con:
      - 'has_update': bool
      - 'commits_behind': int
      - 'latest_msg': str  (mensaje del commit más reciente remoto)
      - 'error': str | None
    """
    # 1. Fetch silencioso
    ok, _, err = _run_git("fetch", "origin", "--quiet", timeout=20)
    if not ok:
        if "not a git repository" in err.lower():
            return {"has_update": False, "commits_behind": 0, "latest_msg": "", "error": "Este directorio no es un repositorio git."}
        return {"has_update": False, "commits_behind": 0, "latest_msg": "", "error": f"Sin conexión o error de red: {err}"}

    # 2. Contar commits que hay en remoto pero no en local
    ok2, behind_str, _ = _run_git("rev-list", "--count", "HEAD..origin/master")
    try:
        behind = int(behind_str) if ok2 else 0
    except ValueError:
        behind = 0

    # 3. Obtener mensaje del commit más reciente en remoto
    ok3, latest_msg, _ = _run_git("log", "origin/master", "-1", "--pretty=%s")
    latest_msg = latest_msg or "Sin información"

    return {
        "has_update": behind > 0,
        "commits_behind": behind,
        "latest_msg": latest_msg,
        "error": None,
    }


def do_git_pull() -> tuple:
    """Ejecuta git pull. Retorna (éxito, mensaje)."""
    ok, out, err = _run_git("pull", "--ff-only", timeout=60)
    if ok:
        return True, out or "Actualización completada correctamente."
    return False, err or "Error desconocido al actualizar."


def restart_app():
    """Reinicia el proceso de la aplicación."""
    try:
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception:
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)


# ---------------------------------------------------------------------------
# Ventana de actualización
# ---------------------------------------------------------------------------

class UpdaterWindow(ctk.CTkToplevel):
    """Modal para gestionar actualizaciones."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Buscar Actualizaciones")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self._updating = False
        self._check_result = None

        self._build()
        self._center(parent)
        threading.Thread(target=self._check_update_thread, daemon=True).start()

    # ------------------------------------------------------------------
    def _build(self):
        self.configure(fg_color=COLORS["bg"])

        wrapper = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=18)
        wrapper.pack(padx=20, pady=20, fill="both", expand=True)

        # Título
        hdr = ctk.CTkFrame(wrapper, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 0))
        ctk.CTkLabel(hdr, text="🔄", font=(F, 28)).pack(side="left", padx=(0, 10))
        ttl = ctk.CTkFrame(hdr, fg_color="transparent")
        ttl.pack(side="left")
        ctk.CTkLabel(ttl, text="Buscar Actualizaciones",
                     font=(F, 18, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        ctk.CTkLabel(ttl, text="Conectando con el servidor de actualizaciones…",
                     font=(F, 11), text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        ctk.CTkFrame(wrapper, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=14)

        # Versión local
        r1 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r1.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(r1, text="💻  Versión instalada", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(r1, text=get_local_version(), font=(F, 13, "bold"),
                     text_color=COLORS["text"]).pack(side="right", padx=14)

        # Versión remota
        r2 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r2.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(r2, text="☁️  Última versión disponible", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        self._lbl_remote = ctk.CTkLabel(r2, text="Verificando…", font=(F, 13, "bold"),
                                         text_color=COLORS["muted"])
        self._lbl_remote.pack(side="right", padx=14)

        # Barra progreso
        self._progress = ctk.CTkProgressBar(wrapper, width=380, height=5,
                                             fg_color=COLORS["border"],
                                             progress_color=COLORS["accent"])
        self._progress.pack(padx=16, pady=(0, 8))
        self._progress.configure(mode="indeterminate")
        self._progress.start()

        # Estado
        self._lbl_status = ctk.CTkLabel(wrapper, text="Conectando con GitHub…",
                                         font=(F, 11), text_color=COLORS["muted"])
        self._lbl_status.pack(pady=(0, 14))

        # Detalles (oculto hasta que haya resultado)
        self._frame_detail = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        self._lbl_detail = ctk.CTkLabel(self._frame_detail, text="",
                                         font=(F, 11), text_color=COLORS["muted"],
                                         wraplength=340, justify="left")
        self._lbl_detail.pack(padx=14, pady=10, anchor="w")

        # Botones
        btn_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._btn_update = ctk.CTkButton(
            btn_row, text="⬇️  Instalar Actualización", height=44,
            font=(F, 13, "bold"), fg_color=COLORS["accent"],
            hover_color="#3a6fd8", text_color="#fff",
            corner_radius=12, state="disabled",
            command=self._do_update)
        self._btn_update.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self._btn_close = ctk.CTkButton(
            btn_row, text="Cerrar", height=44, font=(F, 13),
            fg_color=COLORS["input"], hover_color=COLORS["border"],
            text_color=COLORS["muted"], corner_radius=12,
            command=self.destroy)
        self._btn_close.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ------------------------------------------------------------------
    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 440, 440
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")

    def _check_update_thread(self):
        result = check_for_updates()
        self.after(0, self._on_check_done, result)

    def _on_check_done(self, result: dict):
        self._check_result = result
        self._progress.stop()
        self._progress.configure(mode="determinate")

        if result["error"]:
            self._progress.set(0)
            self._lbl_remote.configure(text="Sin conexión", text_color=COLORS["danger"])
            self._lbl_status.configure(
                text=f"⚠️  {result['error']}", text_color=COLORS["warn"])
            return

        if result["has_update"]:
            behind = result["commits_behind"]
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["warn"])
            self._lbl_remote.configure(text=f"¡Nueva versión!", text_color=COLORS["warn"])
            self._lbl_status.configure(
                text=f"🎉  Hay {behind} actualización{'es' if behind > 1 else ''} disponible{'s' if behind > 1 else ''}.",
                text_color=COLORS["warn"])
            self._frame_detail.pack(fill="x", padx=16, pady=(0, 10))
            self._lbl_detail.configure(
                text=f"Cambios incluidos: {result['latest_msg']}")
            self._btn_update.configure(state="normal")
        else:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_remote.configure(
                text=f"v{get_local_version()} (actual)", text_color=COLORS["success"])
            self._lbl_status.configure(
                text="✅  ¡Tienes la versión más reciente instalada!",
                text_color=COLORS["success"])

    # ------------------------------------------------------------------
    def _do_update(self):
        if self._updating:
            return
        self._updating = True
        self._btn_update.configure(state="disabled", text="Descargando…")
        self._btn_close.configure(state="disabled")
        self._lbl_status.configure(text="⬇️  Descargando actualización…",
                                    text_color=COLORS["accent"])
        self._progress.configure(mode="indeterminate")
        self._progress.start()
        threading.Thread(target=self._pull_thread, daemon=True).start()

    def _pull_thread(self):
        ok, msg = do_git_pull()
        self.after(0, self._on_pull_done, ok, msg)

    def _on_pull_done(self, ok: bool, msg: str):
        self._progress.stop()
        self._progress.configure(mode="determinate")
        if ok:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_status.configure(
                text="✅  ¡Actualización completada! Reiniciando…",
                text_color=COLORS["success"])
            self.after(1800, self._restart_now)
        else:
            self._progress.set(0)
            self._lbl_status.configure(
                text=f"❌  Error: {msg[:100]}", text_color=COLORS["danger"])
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
    """Abre la ventana del actualizador."""
    UpdaterWindow(parent)
