"""
main.py
=======
Punto de entrada del Sistema de Gestión de Inventario.

Flujo de arranque:
  1. Inicializa la base de datos (crea tablas y admin por defecto si es necesario).
  2. Abre DashboardApp — que internamente muestra LoginWindow modal.
  3. Si el login es exitoso, construye el Dashboard con sidebar.
  4. Si el usuario cierra el login sin autenticarse, la app se cierra limpiamente.

Ejecutar con:
    python main.py
"""

from database.inventario_db import inicializar_db
from ui.dashboard import DashboardApp

if __name__ == "__main__":
    # ── Paso 1: Inicializar BD (idempotente — seguro en cada arranque) ──
    inicializar_db()

    # ── Paso 2: Ejecutar Dashboard ───────────────────────────────────────
    app = DashboardApp()
    app.mainloop()
