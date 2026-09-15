"""
utils/updater.py
================
Sistema profesional de actualizaciones basado en GitHub Releases (Tags).

Características:
  - Consulta la API de GitHub para obtener el último Release (tag oficial).
  - Compara con la versión local del archivo VERSION.
  - Actualiza haciendo git fetch --tags y git checkout al tag oficial.
  - Guarda el tag anterior para permitir Rollback.
  - Nunca toca: *.db, logos/, inventario_img/, imagenes_repuestos/, reportes/, config/*.json
"""

import os
import sys
import json
import shutil
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

APP_DIR    = Path(__file__).resolve().parent.parent
VERSION_FILE   = APP_DIR / "VERSION"
ROLLBACK_FILE  = APP_DIR / "config" / ".last_version"   # guarda tag anterior
GITHUB_REPO    = "XekRed/inventario-repuestos"           # CAMBIA si cambia tu repo
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Archivos y carpetas que NUNCA se tocan durante actualización / rollback
PROTECTED = [
    "database/",
    "logos/",
    "inventario_img/",
    "imagenes_repuestos/",
    "pedidos_img/",
    "reportes/",
    "facturas/",
    "config/tasa.json",
    "config/theme.json",
    "VERSION",  # lo actualizamos manualmente nosotros
]

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
    """'1.2.3' → (1, 2, 3). Ignora prefijo 'v'."""
    try:
        clean = str(v).strip().lstrip("v").lstrip("V")
        return tuple(int(x) for x in clean.split("."))
    except Exception:
        return (0, 0, 0)


def get_local_version() -> str:
    """Lee VERSION del disco. Fallback '1.0.0'."""
    try:
        lines = VERSION_FILE.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                return line.lstrip("vV")
    except Exception:
        pass
    return "1.0.0"


def _set_local_version(tag: str):
    """Escribe el tag limpio en VERSION."""
    clean = tag.lstrip("vV")
    VERSION_FILE.write_text(f"{clean}\n", encoding="utf-8")


def _save_rollback_tag(tag: str):
    """Guarda el tag actual antes de actualizar (para rollback)."""
    ROLLBACK_FILE.parent.mkdir(exist_ok=True)
    ROLLBACK_FILE.write_text(tag, encoding="utf-8")


def _load_rollback_tag() -> str | None:
    """Lee el tag guardado para rollback. None si no existe."""
    try:
        t = ROLLBACK_FILE.read_text(encoding="utf-8").strip()
        return t if t else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(*args, timeout=30) -> tuple[bool, str, str]:
    """Ejecuta git y retorna (success, stdout, stderr)."""
    try:
        r = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True,
            cwd=str(APP_DIR), timeout=timeout,
        )
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return False, "", "Git no está instalado o no está en el PATH."
    except subprocess.TimeoutExpired:
        return False, "", "Tiempo de espera agotado."
    except Exception as e:
        return False, "", str(e)


def _backup_protected():
    """Hace backup de archivos protegidos antes del checkout."""
    backups = {}
    for rel in PROTECTED:
        src = APP_DIR / rel
        if src.is_file():
            bak = APP_DIR / "config" / f"_bak_{src.name}"
            shutil.copy2(src, bak)
            backups[str(rel)] = str(bak)
        elif src.is_dir():
            pass  # las carpetas git checkout no las borra por defecto
    return backups


def _restore_protected(backups: dict):
    """Restaura archivos protegidos después del checkout."""
    for rel, bak_path in backups.items():
        dst = APP_DIR / rel
        bak = Path(bak_path)
        if bak.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bak, dst)
            bak.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Verificación de Release en GitHub
# ---------------------------------------------------------------------------

def check_for_release() -> dict:
    """
    Consulta la API de GitHub para obtener el último Release.

    Retorna:
        {
          'has_update': bool,
          'latest_tag': str,      # p.ej. 'v1.2.0'
          'release_name': str,    # nombre del release
          'release_notes': str,   # body del release
          'local_version': str,
          'error': str | None,
        }
    """
    local_v = get_local_version()
    result = {
        "has_update": False,
        "latest_tag": "",
        "release_name": "",
        "release_notes": "",
        "local_version": local_v,
        "error": None,
    }
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "RepuestosDB-Updater/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        latest_tag   = data.get("tag_name", "")
        release_name = data.get("name", latest_tag)
        release_body = data.get("body", "Sin notas de versión.")

        result["latest_tag"]   = latest_tag
        result["release_name"] = release_name
        result["release_notes"] = release_body[:400] if release_body else "—"

        if _parse_version(latest_tag) > _parse_version(local_v):
            result["has_update"] = True

    except urllib.error.URLError as e:
        result["error"] = f"Sin conexión a internet: {e.reason}"
    except Exception as e:
        result["error"] = f"Error al verificar: {e}"

    return result


# ---------------------------------------------------------------------------
# Actualización segura a un tag específico
# ---------------------------------------------------------------------------

def do_update_to_tag(tag: str) -> tuple[bool, str]:
    """
    Actualiza al tag indicado usando:
      git fetch --tags
      git checkout tags/<tag>   (detached HEAD, limpio y predecible)

    Protege DB, logos, imágenes y configs.

    Retorna (ok, mensaje).
    """
    # 1. Backup de protegidos
    backups = _backup_protected()

    # 2. Guardar versión actual como rollback
    current_tag = f"v{get_local_version()}"
    _save_rollback_tag(current_tag)

    # 3. Fetch todos los tags
    ok, _, err = _run_git("fetch", "--tags", "--force", timeout=60)
    if not ok:
        _restore_protected(backups)
        return False, f"Error en git fetch: {err}"

    # 4. Checkout al tag
    ok, out, err = _run_git("checkout", f"tags/{tag}", "--force", timeout=60)
    _restore_protected(backups)

    if ok:
        # Actualizar archivo VERSION con el nuevo tag
        _set_local_version(tag)
        return True, f"Actualizado correctamente a {tag}."
    else:
        # Intentar recuperar estado anterior
        _run_git("checkout", "-", "--force", timeout=30)
        return False, f"Error en git checkout: {err}"


def do_rollback() -> tuple[bool, str]:
    """
    Hace rollback al tag guardado en .last_version.
    Retorna (ok, mensaje).
    """
    prev_tag = _load_rollback_tag()
    if not prev_tag:
        return False, "No hay versión anterior guardada para hacer rollback."

    backups = _backup_protected()

    ok, _, err = _run_git("fetch", "--tags", "--force", timeout=60)
    if not ok:
        _restore_protected(backups)
        return False, f"Error en git fetch: {err}"

    # Intentar primero como tag
    ok, out, err = _run_git("checkout", f"tags/{prev_tag}", "--force", timeout=60)
    if not ok:
        # Intentar como commit/branch directamente
        ok, out, err = _run_git("checkout", prev_tag, "--force", timeout=60)

    _restore_protected(backups)

    if ok:
        _set_local_version(prev_tag)
        ROLLBACK_FILE.unlink(missing_ok=True)  # consumir el rollback point
        return True, f"Rollback completado a {prev_tag}."
    else:
        return False, f"Error en rollback: {err}"


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------

def restart_app():
    """Reinicia el proceso de la aplicación."""
    try:
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception:
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)


# ---------------------------------------------------------------------------
# Función de verificación rápida (para notificaciones, sin bloquear UI)
# ---------------------------------------------------------------------------

_cached_release_check: dict | None = None
_cache_ts: float = 0


def check_for_release_cached() -> dict:
    """Misma que check_for_release() pero cachea el resultado 5 minutos."""
    import time
    global _cached_release_check, _cache_ts
    now = time.time()
    if _cached_release_check is not None and (now - _cache_ts) < 300:
        return _cached_release_check
    result = check_for_release()
    _cached_release_check = result
    _cache_ts = now
    return result


# ---------------------------------------------------------------------------
# Ventana de Actualizaciones
# ---------------------------------------------------------------------------

class UpdaterWindow(ctk.CTkToplevel):
    """Modal para gestionar actualizaciones basadas en Releases de GitHub."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Actualizaciones del Sistema")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self._updating = False
        self._check_result = None

        self._build()
        self._center(parent)
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _build(self):
        self.configure(fg_color=COLORS["bg"])
        wrapper = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=18)
        wrapper.pack(padx=20, pady=20, fill="both", expand=True)

        # Título
        hdr = ctk.CTkFrame(wrapper, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 0))
        ctk.CTkLabel(hdr, text="🚀", font=(F, 28)).pack(side="left", padx=(0, 10))
        ttl = ctk.CTkFrame(hdr, fg_color="transparent")
        ttl.pack(side="left")
        ctk.CTkLabel(ttl, text="Actualizaciones del Sistema",
                     font=(F, 18, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        ctk.CTkLabel(ttl, text="Buscando el último Release oficial en GitHub…",
                     font=(F, 11), text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        ctk.CTkFrame(wrapper, fg_color=COLORS["border"], height=1).pack(fill="x", padx=16, pady=14)

        # Versión local
        r1 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r1.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(r1, text="💻  Versión instalada", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(r1, text=f"v{get_local_version()}", font=(F, 13, "bold"),
                     text_color=COLORS["text"]).pack(side="right", padx=14)

        # Versión remota
        r2 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r2.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(r2, text="☁️  Último Release en GitHub", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        self._lbl_remote = ctk.CTkLabel(r2, text="Verificando…", font=(F, 13, "bold"),
                                         text_color=COLORS["muted"])
        self._lbl_remote.pack(side="right", padx=14)

        # Progress
        self._progress = ctk.CTkProgressBar(wrapper, width=380, height=5,
                                             fg_color=COLORS["border"],
                                             progress_color=COLORS["accent"])
        self._progress.pack(padx=16, pady=(0, 8))
        self._progress.configure(mode="indeterminate")
        self._progress.start()

        # Estado
        self._lbl_status = ctk.CTkLabel(wrapper, text="Conectando con GitHub…",
                                         font=(F, 11), text_color=COLORS["muted"])
        self._lbl_status.pack(pady=(0, 8))

        # Notas del release (oculto hasta que haya resultado)
        self._frame_notes = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        self._lbl_notes = ctk.CTkLabel(self._frame_notes, text="",
                                        font=(F, 11), text_color=COLORS["muted"],
                                        wraplength=360, justify="left")
        self._lbl_notes.pack(padx=14, pady=10, anchor="w")

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

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 460, 460
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")

    def _check_thread(self):
        result = check_for_release()
        self.after(0, self._on_check_done, result)

    def _on_check_done(self, result: dict):
        self._check_result = result
        self._progress.stop()
        self._progress.configure(mode="determinate")

        if result["error"]:
            self._progress.set(0)
            self._lbl_remote.configure(text="Sin conexión", text_color=COLORS["danger"])
            self._lbl_status.configure(text=f"⚠️  {result['error']}", text_color=COLORS["warn"])
            return

        latest = result["latest_tag"]
        if result["has_update"]:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["warn"])
            self._lbl_remote.configure(text=f"{latest}  🎉  ¡Nueva versión!", text_color=COLORS["warn"])
            self._lbl_status.configure(
                text=f"🚀  Release {result['release_name']} disponible.",
                text_color=COLORS["warn"])
            notes = result["release_notes"]
            self._lbl_notes.configure(text=f"📝 Notas:\n{notes}")
            self._frame_notes.pack(fill="x", padx=16, pady=(0, 10))
            self._btn_update.configure(state="normal")
        else:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_remote.configure(
                text=f"{latest} (igual a la local)", text_color=COLORS["success"])
            self._lbl_status.configure(
                text="✅  ¡Tienes la versión más reciente instalada!",
                text_color=COLORS["success"])

    def _do_update(self):
        if self._updating or not self._check_result:
            return
        self._updating = True
        tag = self._check_result.get("latest_tag", "")
        if not tag:
            return
        self._btn_update.configure(state="disabled", text="Descargando…")
        self._btn_close.configure(state="disabled")
        self._lbl_status.configure(text=f"⬇️  Descargando {tag}…", text_color=COLORS["accent"])
        self._progress.configure(mode="indeterminate")
        self._progress.start()
        threading.Thread(target=self._update_thread, args=(tag,), daemon=True).start()

    def _update_thread(self, tag: str):
        ok, msg = do_update_to_tag(tag)
        self.after(0, self._on_update_done, ok, msg)

    def _on_update_done(self, ok: bool, msg: str):
        self._progress.stop()
        self._progress.configure(mode="determinate")
        if ok:
            self._progress.set(1)
            self._progress.configure(progress_color=COLORS["success"])
            self._lbl_status.configure(text="✅  ¡Actualización completada! Reiniciando…",
                                        text_color=COLORS["success"])
            self.after(1800, self._restart_now)
        else:
            self._progress.set(0)
            self._lbl_status.configure(text=f"❌  {msg[:120]}", text_color=COLORS["danger"])
            self._btn_update.configure(state="normal", text="⬇️  Reintentar")
            self._btn_close.configure(state="normal")
            self._updating = False

    def _restart_now(self):
        self.destroy()
        restart_app()


# ---------------------------------------------------------------------------
# Ventana de Rollback
# ---------------------------------------------------------------------------

class RollbackWindow(ctk.CTkToplevel):
    """Modal de confirmación para hacer rollback a la versión anterior."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Deshacer Actualización (Rollback)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        self._rolling = False
        self._build()
        self._center(parent)

    def _build(self):
        self.configure(fg_color=COLORS["bg"])
        wrapper = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=18)
        wrapper.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(wrapper, text="⏪", font=(F, 48)).pack(pady=(24, 4))
        ctk.CTkLabel(wrapper, text="Deshacer Última Actualización",
                     font=(F, 18, "bold"), text_color=COLORS["danger"]).pack(pady=(0, 8))

        local_v   = get_local_version()
        prev_tag  = _load_rollback_tag()
        prev_text = prev_tag if prev_tag else "No disponible"

        r1 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r1.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkLabel(r1, text="Versión actual:", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(r1, text=f"v{local_v}", font=(F, 13, "bold"),
                     text_color=COLORS["text"]).pack(side="right", padx=14)

        r2 = ctk.CTkFrame(wrapper, fg_color=COLORS["input"], corner_radius=10)
        r2.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkLabel(r2, text="Se revertirá a:", font=(F, 12),
                     text_color=COLORS["muted"]).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(r2, text=prev_text, font=(F, 13, "bold"),
                     text_color=COLORS["warn"]).pack(side="right", padx=14)

        warn_frame = ctk.CTkFrame(wrapper, fg_color="#2d0e0e", corner_radius=10)
        warn_frame.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkLabel(warn_frame,
                     text="⚠️  La base de datos, imágenes y configuración\nNO se verán afectadas.",
                     font=(F, 11), text_color="#e05c5c", justify="center").pack(padx=14, pady=10)

        self._lbl_status = ctk.CTkLabel(wrapper, text="", font=(F, 11), text_color=COLORS["muted"])
        self._lbl_status.pack(pady=(0, 8))

        btn_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self._btn_rb = ctk.CTkButton(
            btn_row, text="⏪  Hacer Rollback", height=44,
            font=(F, 13, "bold"), fg_color=COLORS["danger"],
            hover_color="#c94a4a", text_color="#fff",
            corner_radius=12,
            state="normal" if prev_tag else "disabled",
            command=self._do_rollback)
        self._btn_rb.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_row, text="Cancelar", height=44, font=(F, 13),
            fg_color=COLORS["input"], hover_color=COLORS["border"],
            text_color=COLORS["muted"], corner_radius=12,
            command=self.destroy).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = 420, 420
        self.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py + (ph - h)//2}")

    def _do_rollback(self):
        if self._rolling:
            return
        self._rolling = True
        self._btn_rb.configure(state="disabled", text="Revirtiendo…")
        self._lbl_status.configure(text="⏳ Ejecutando rollback…", text_color=COLORS["warn"])
        threading.Thread(target=self._rollback_thread, daemon=True).start()

    def _rollback_thread(self):
        ok, msg = do_rollback()
        self.after(0, self._on_rollback_done, ok, msg)

    def _on_rollback_done(self, ok: bool, msg: str):
        if ok:
            self._lbl_status.configure(text=f"✅ {msg} Reiniciando…", text_color=COLORS["success"])
            self.after(1800, self._restart_now)
        else:
            self._lbl_status.configure(text=f"❌ {msg}", text_color=COLORS["danger"])
            self._btn_rb.configure(state="normal", text="⏪  Reintentar")
            self._rolling = False

    def _restart_now(self):
        self.destroy()
        restart_app()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def abrir_actualizador(parent):
    UpdaterWindow(parent)


def abrir_rollback(parent):
    RollbackWindow(parent)
