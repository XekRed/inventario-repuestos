"""
inventario_db.py
================
Módulo principal de base de datos para el sistema de gestión de
repuestos de electrodomésticos.

Tablas:
  - inventario  : Repuestos y piezas.
  - usuarios    : Cuentas de acceso con roles (SuperAdmin / Admin / Empleado).
  - empresas    : Empresas registradas en el sistema (Marca Blanca).
  - clientes    : Directorio de clientes para autocompletado en POS.

Arquitectura: Offline First — SQLite local.
"""

import sqlite3
import hashlib
import logging
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "inventario.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("inventario_db")


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Crea y devuelve una conexión a la base de datos SQLite.

    Returns:
        sqlite3.Connection: Conexión activa con row_factory configurada
                            para devolver filas como diccionarios.

    Raises:
        sqlite3.Error: Si no se puede establecer la conexión.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row          # acceso por nombre de columna
        conn.execute("PRAGMA journal_mode=WAL") # mejor concurrencia de lectura
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except sqlite3.Error as e:
        logger.error("Error al conectar con la base de datos: %s", e)
        raise


# ---------------------------------------------------------------------------
# Inicialización / Migración de esquema
# ---------------------------------------------------------------------------

def inicializar_db() -> None:
    """
    Crea la base de datos, la tabla `inventario` y la tabla `usuarios`
    si no existen. Es seguro ejecutar esta función en cada arranque
    (utiliza CREATE TABLE IF NOT EXISTS).
    Al terminar, inserta automáticamente el usuario Admin por defecto
    si la tabla de usuarios está vacía.
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS inventario (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre          TEXT    NOT NULL,
        modelo          TEXT    NOT NULL,
        marca           TEXT    NOT NULL,
        precio_entrada  REAL    NOT NULL CHECK(precio_entrada  >= 0),
        precio_venta    REAL    NOT NULL CHECK(precio_venta    >= 0),
        cantidad        INTEGER NOT NULL DEFAULT 0 CHECK(cantidad >= 0),
        sku             TEXT    NOT NULL UNIQUE,
        ubicacion       TEXT,
        descripcion     TEXT,
        imagen_ruta     TEXT,
        creado_en       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
        actualizado_en  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
    );

    CREATE TABLE IF NOT EXISTS empresas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre          TEXT    NOT NULL UNIQUE,
        ruta_logo       TEXT    NOT NULL DEFAULT '',
        licencia_activa INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS usuarios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario     TEXT    NOT NULL UNIQUE,
        contrasena  TEXT    NOT NULL,
        rol         TEXT    NOT NULL DEFAULT 'Empleado',
        empresa_id  INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
        creado_en   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
    );

    CREATE TABLE IF NOT EXISTS clientes (
        cedula   TEXT    PRIMARY KEY,
        nombre   TEXT    NOT NULL DEFAULT '',
        telefono TEXT    NOT NULL DEFAULT ''
    );

    -- Índices para búsquedas rápidas
    CREATE INDEX IF NOT EXISTS idx_inventario_nombre ON inventario(nombre);
    CREATE INDEX IF NOT EXISTS idx_inventario_marca  ON inventario(marca);

    CREATE TABLE IF NOT EXISTS ventas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
        nombre_cliente  TEXT    NOT NULL DEFAULT 'Cliente general',
        cedula_cliente  TEXT    NOT NULL DEFAULT 'S/C',
        total_usd       REAL    NOT NULL DEFAULT 0,
        total_bs        REAL    NOT NULL DEFAULT 0,
        metodo_pago     TEXT    NOT NULL DEFAULT 'Punto'
    );

    CREATE TABLE IF NOT EXISTS detalles_venta (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta        INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
        id_producto     INTEGER NOT NULL REFERENCES inventario(id),
        nombre_producto TEXT    NOT NULL,
        cantidad        INTEGER NOT NULL CHECK(cantidad > 0),
        precio_unitario REAL    NOT NULL CHECK(precio_unitario >= 0)
    );

    CREATE INDEX IF NOT EXISTS idx_detalles_venta ON detalles_venta(id_venta);

    CREATE TABLE IF NOT EXISTS deudores (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre            TEXT    NOT NULL,
        telefono          TEXT    NOT NULL DEFAULT '',
        monto_deuda_usd   REAL    NOT NULL DEFAULT 0,
        monto_deuda_bs    REAL    NOT NULL DEFAULT 0,
        fecha_venta       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
        fecha_limite_pago TEXT    NOT NULL DEFAULT '',
        estado            TEXT    NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'Pagada'))
    );

    CREATE INDEX IF NOT EXISTS idx_deudores_estado ON deudores(estado);

    CREATE TABLE IF NOT EXISTS cuentas_por_pagar (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre      TEXT    NOT NULL,
        descripcion TEXT    NOT NULL DEFAULT '',
        banco       TEXT    NOT NULL DEFAULT '',
        cedula      TEXT    NOT NULL DEFAULT '',
        telefono    TEXT    NOT NULL DEFAULT '',
        monto_usd   REAL    NOT NULL DEFAULT 0,
        monto_bs    REAL    NOT NULL DEFAULT 0,
        fecha       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
        estado      TEXT    NOT NULL DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'Pagada'))
    );

    CREATE TABLE IF NOT EXISTS proveedores (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre        TEXT    NOT NULL UNIQUE,
        telefono      TEXT    NOT NULL DEFAULT '',
        representante TEXT    NOT NULL DEFAULT '',
        ruta_logo     TEXT    NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS pedidos (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER NOT NULL REFERENCES proveedores(id) ON DELETE CASCADE,
        fecha        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
        ruta_imagen  TEXT    NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS pedido_items (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id    INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
        codigo       TEXT    NOT NULL DEFAULT '',
        nombre       TEXT    NOT NULL,
        tipo         TEXT    NOT NULL DEFAULT '',
        cantidad     INTEGER NOT NULL DEFAULT 1,
        unidad       TEXT    NOT NULL DEFAULT 'Unidad'
    );
    """
    try:
        with get_connection() as conn:
            conn.executescript(ddl)
            # Migraciones silenciosas para bases de datos existentes
            _migraciones_seguras(conn)
        logger.info("Base de datos inicializada correctamente en: %s", DB_PATH)
        # Crear superadmin por defecto si no existe ningún usuario
        UsuariosDAO().insertar_admin_defecto()
    except sqlite3.Error as e:
        logger.error("Error al inicializar la base de datos: %s", e)
        raise


def _migraciones_seguras(conn: sqlite3.Connection) -> None:
    """Aplica migraciones ALTER TABLE sin fallar si la columna ya existe."""
    alteraciones = [
        "ALTER TABLE ventas ADD COLUMN metodo_pago TEXT NOT NULL DEFAULT 'Punto'",
        "ALTER TABLE proveedores ADD COLUMN telefono TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE proveedores ADD COLUMN representante TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE usuarios ADD COLUMN empresa_id INTEGER REFERENCES empresas(id)",
        "ALTER TABLE inventario ADD COLUMN stock_minimo INTEGER NOT NULL DEFAULT 5",
    ]
    for sql in alteraciones:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # columna ya existe


# ---------------------------------------------------------------------------
# Capa de acceso a datos (DAO)
# ---------------------------------------------------------------------------

class InventarioDAO:
    """
    Data Access Object para la tabla `inventario`.

    Todas las operaciones abren su propia conexión y la cierran al
    finalizar (context manager), garantizando que no haya conexiones
    huérfanas.

    Ejemplo de uso rápido::

        dao = InventarioDAO()
        dao.crear(
            nombre="Termostato universal",
            modelo="TX-200",
            marca="Genco",
            precio_entrada=8.50,
            precio_venta=18.00,
            cantidad=30,
            sku="TERM-TX200-GNC",
            ubicacion="Estante B-3",
            descripcion="Termostato bimetálico 16 A / 250 V",
            imagen_ruta="imagenes/termostato_tx200.jpg",
        )
    """

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def crear(
        self,
        nombre: str,
        modelo: str,
        marca: str,
        precio_entrada: float,
        precio_venta: float,
        cantidad: int,
        sku: str,
        ubicacion: Optional[str] = None,
        descripcion: Optional[str] = None,
        imagen_ruta: Optional[str] = None,
        stock_minimo: int = 5,
    ) -> int:
        """
        Inserta un nuevo repuesto en el inventario.

        Returns:
            int: ID (rowid) del registro creado.

        Raises:
            ValueError: Si el SKU ya existe o los datos son inválidos.
            sqlite3.Error: Ante cualquier otro error de base de datos.
        """
        sql = """
        INSERT INTO inventario
            (nombre, modelo, marca, precio_entrada, precio_venta,
             cantidad, sku, ubicacion, descripcion, imagen_ruta, stock_minimo)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (nombre, modelo, marca, precio_entrada, precio_venta,
                     cantidad, sku, ubicacion, descripcion, imagen_ruta, stock_minimo),
                )
                new_id = cursor.lastrowid
                logger.info("Repuesto creado — ID: %s, SKU: %s", new_id, sku)
                return new_id
        except sqlite3.IntegrityError as e:
            logger.warning("SKU duplicado o restricción violada: %s", e)
            raise ValueError(f"SKU '{sku}' ya existe o datos inválidos: {e}") from e
        except sqlite3.Error as e:
            logger.error("Error al crear repuesto: %s", e)
            raise

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def obtener_por_id(self, repuesto_id: int) -> Optional[dict]:
        """
        Obtiene un repuesto por su ID primario.

        Returns:
            dict con los campos del repuesto, o None si no existe.
        """
        sql = "SELECT * FROM inventario WHERE id = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (repuesto_id,)).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Error al obtener repuesto ID %s: %s", repuesto_id, e)
            raise

    def listar_todos(self, orden_por: str = "nombre") -> list[dict]:
        """
        Devuelve todos los repuestos ordenados por el campo indicado.

        Args:
            orden_por: Nombre de columna válido (por defecto 'nombre').

        Returns:
            Lista de dicts, uno por repuesto.
        """
        columnas_validas = {
            "id", "nombre", "modelo", "marca", "precio_venta", "cantidad", "sku"
        }
        if orden_por not in columnas_validas:
            raise ValueError(
                f"Columna de orden inválida: '{orden_por}'. "
                f"Use una de: {columnas_validas}"
            )
        sql = f"SELECT * FROM inventario ORDER BY {orden_por}"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Error al listar inventario: %s", e)
            raise

    def listar_stock_bajo(self, limite: int = None) -> list[dict]:
        """
        Devuelve productos cuya cantidad disponible es menor al umbral del producto.
        Si se pasa `limite`, lo usa como umbral global (para compatibilidad);
        de lo contrario usa la columna `stock_minimo` de cada producto.

        Returns:
            Lista de dicts ordenada por cantidad ascendente.
        """
        if limite is not None:
            sql = """
                SELECT id, nombre, sku, cantidad, stock_minimo
                FROM   inventario
                WHERE  cantidad < ?
                ORDER  BY cantidad ASC
            """
            params = (limite,)
        else:
            sql = """
                SELECT id, nombre, sku, cantidad, stock_minimo
                FROM   inventario
                WHERE  cantidad < stock_minimo
                ORDER  BY cantidad ASC
            """
            params = ()
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar stock bajo: %s", e)
            raise

    # ------------------------------------------------------------------
    # SEARCH (por SKU o nombre)
    # ------------------------------------------------------------------

    def buscar(self, termino: str) -> list[dict]:
        """
        Busca repuestos cuyo nombre contenga el término dado, **o** cuyo
        SKU sea una coincidencia exacta.

        Args:
            termino: Cadena de búsqueda (se aplica LIKE en nombre; exact match en sku).

        Returns:
            Lista de dicts con los resultados encontrados.
        """
        sql = """
        SELECT * FROM inventario
        WHERE  sku = ?
           OR  nombre LIKE ?
        ORDER BY nombre
        """
        patron = f"%{termino}%"
        try:
            with get_connection() as conn:
                rows = conn.execute(sql, (termino, patron)).fetchall()
                logger.info(
                    "Búsqueda '%s' — %d resultado(s) encontrado(s)", termino, len(rows)
                )
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Error en búsqueda '%s': %s", termino, e)
            raise

    def buscar_por_sku(self, sku: str) -> Optional[dict]:
        """
        Obtiene un repuesto por su código SKU (coincidencia exacta).

        Returns:
            dict del repuesto, o None si no existe.
        """
        sql = "SELECT * FROM inventario WHERE sku = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (sku,)).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Error al buscar SKU '%s': %s", sku, e)
            raise

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def actualizar(self, repuesto_id: int, **campos) -> bool:
        """
        Actualiza uno o más campos de un repuesto existente.

        Args:
            repuesto_id: ID del repuesto a modificar.
            **campos:    Pares clave=valor de los campos a actualizar.
                         Ejemplo: actualizar(1, precio_venta=25.99, cantidad=50)

        Returns:
            True si se modificó al menos una fila, False si el ID no existe.

        Raises:
            ValueError: Si no se reciben campos o algún campo es inválido.
        """
        columnas_validas = {
            "nombre", "modelo", "marca", "precio_entrada", "precio_venta",
            "cantidad", "sku", "ubicacion", "descripcion", "imagen_ruta",
            "stock_minimo",
        }
        if not campos:
            raise ValueError("Debe proporcionar al menos un campo para actualizar.")

        campos_invalidos = set(campos) - columnas_validas
        if campos_invalidos:
            raise ValueError(f"Campo(s) inválido(s): {campos_invalidos}")

        # Actualiza automáticamente la marca de tiempo
        campos["actualizado_en"] = "strftime('%Y-%m-%dT%H:%M:%S', 'now')"

        set_clauses = []
        valores = []
        for col, val in campos.items():
            if col == "actualizado_en":
                set_clauses.append(f"{col} = {val}")   # expresión SQL, sin placeholder
            else:
                set_clauses.append(f"{col} = ?")
                valores.append(val)

        valores.append(repuesto_id)
        sql = f"UPDATE inventario SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, valores)
                actualizado = cursor.rowcount > 0
                if actualizado:
                    logger.info("Repuesto ID %s actualizado.", repuesto_id)
                else:
                    logger.warning("No se encontró repuesto con ID %s.", repuesto_id)
                return actualizado
        except sqlite3.IntegrityError as e:
            logger.warning("Restricción de integridad al actualizar: %s", e)
            raise ValueError(f"Error de integridad: {e}") from e
        except sqlite3.Error as e:
            logger.error("Error al actualizar repuesto ID %s: %s", repuesto_id, e)
            raise

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def eliminar(self, repuesto_id: int) -> bool:
        """
        Elimina un repuesto del inventario por su ID.

        Returns:
            True si la fila fue eliminada, False si el ID no existía.
        """
        sql = "DELETE FROM inventario WHERE id = ?"
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (repuesto_id,))
                eliminado = cursor.rowcount > 0
                if eliminado:
                    logger.info("Repuesto ID %s eliminado.", repuesto_id)
                else:
                    logger.warning(
                        "Intento de eliminar ID %s que no existe.", repuesto_id
                    )
                return eliminado
        except sqlite3.Error as e:
            logger.error("Error al eliminar repuesto ID %s: %s", repuesto_id, e)
            raise


# ---------------------------------------------------------------------------
# DAO de Usuarios
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Devuelve el hash SHA-256 de la contraseña en hexadecimal."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class UsuariosDAO:
    """
    Data Access Object para la tabla `usuarios`.

    Seguridad:
        Las contraseñas se almacenan como SHA-256 (hashlib built-in).
        No se guardan en texto plano en ningún momento.

    Roles disponibles:
        'Admin'    → acceso completo (CRUD + imágenes).
        'Empleado' → solo lectura y búsqueda.
    """

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def crear_usuario(
        self,
        usuario: str,
        contrasena: str,
        rol: str = "Empleado",
        empresa_id: int = None,
    ) -> int:
        """
        Inserta un nuevo usuario.

        Args:
            usuario:    Nombre de usuario único.
            contrasena: Contraseña en texto plano (se hashea antes de guardar).
            rol:        'SuperAdmin', 'Admin' o 'Empleado'.
            empresa_id: ID de la empresa asignada (None para SuperAdmin).

        Returns:
            int: ID del usuario creado.

        Raises:
            ValueError: Si el usuario ya existe o el rol es inválido.
        """
        if rol not in ("Admin", "Empleado", "SuperAdmin"):
            raise ValueError(f"Rol inválido: '{rol}'. Use 'Admin', 'Empleado' o 'SuperAdmin'.")

        sql = """
        INSERT INTO usuarios (usuario, contrasena, rol, empresa_id)
        VALUES (?, ?, ?, ?)
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql, (usuario, _hash_password(contrasena), rol, empresa_id))
                new_id = cursor.lastrowid
                logger.info("Usuario creado — ID: %s, usuario: %s, rol: %s", new_id, usuario, rol)
                return new_id
        except sqlite3.IntegrityError as e:
            logger.warning("Usuario duplicado: %s", e)
            raise ValueError(f"El usuario '{usuario}' ya existe.") from e
        except sqlite3.Error as e:
            logger.error("Error al crear usuario: %s", e)
            raise

    # ------------------------------------------------------------------
    # VERIFY (Login)
    # ------------------------------------------------------------------

    def verificar_credenciales(
        self,
        usuario: str,
        contrasena: str,
    ) -> Optional[dict]:
        """
        Verifica usuario y contraseña.

        Returns:
            dict con {id, usuario, rol, empresa_id} si las credenciales son correctas.
            None si el usuario no existe o la contraseña es incorrecta.
        """
        sql = "SELECT id, usuario, rol, empresa_id FROM usuarios WHERE usuario = ? AND contrasena = ?"
        try:
            with get_connection() as conn:
                row = conn.execute(sql, (usuario, _hash_password(contrasena))).fetchone()
                if row:
                    logger.info("Login exitoso — usuario: %s, rol: %s", usuario, row["rol"])
                    return dict(row)
                logger.warning("Credenciales incorrectas para usuario: %s", usuario)
                return None
        except sqlite3.Error as e:
            logger.error("Error al verificar credenciales: %s", e)
            raise

    # ------------------------------------------------------------------
    # ADMIN POR DEFECTO
    # ------------------------------------------------------------------

    def insertar_admin_defecto(self) -> bool:
        """
        Garantiza que el SuperAdmin 'XekRed' SIEMPRE existe en la BD.
        Si la tabla está vacía también crea un 'admin' básico.
        Credenciales SuperAdmin: usuario='XekRed' / contraseña='Db123456'
        """
        try:
            with get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]

                # Si la tabla está vacía crear ambos usuarios iniciales
                if total == 0:
                    self.crear_usuario("XekRed", "Db123456", "SuperAdmin")
                    self.crear_usuario("admin",  "admin123",  "Admin")
                    logger.info("SuperAdmin y Admin por defecto creados.")
                    return True

                # Migrar: asegurarse de que XekRed SuperAdmin siempre exista
                existe = conn.execute(
                    "SELECT id FROM usuarios WHERE usuario = 'XekRed' LIMIT 1"
                ).fetchone()
                if not existe:
                    try:
                        self.crear_usuario("XekRed", "Db123456", "SuperAdmin")
                        logger.info("SuperAdmin 'XekRed' creado en migración.")
                    except ValueError:
                        pass  # ya existía con otro hash
                else:
                    # Actualizar la contraseña a la versión sin punto por si acaso
                    conn.execute(
                        "UPDATE usuarios SET contrasena=? WHERE usuario='XekRed'",
                        (_hash_password("Db123456"),)
                    )
                    conn.commit()

                return False
        except sqlite3.Error as e:
            logger.error("Error al verificar/insertar admin defecto: %s", e)
            raise

    # ------------------------------------------------------------------
    # LIST (para panel de administración futuro)
    # ------------------------------------------------------------------

    def listar_usuarios(self) -> list[dict]:
        """Devuelve todos los usuarios (sin incluir la contraseña)."""
        sql = """
        SELECT u.id, u.usuario, u.rol, u.creado_en, u.empresa_id,
               e.nombre AS empresa_nombre
        FROM usuarios u
        LEFT JOIN empresas e ON e.id = u.empresa_id
        ORDER BY u.usuario
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(sql).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            logger.error("Error al listar usuarios: %s", e)
            raise

    def cambiar_contrasena(self, usuario_id: int, nueva_contrasena: str) -> None:
        """Cambia la contraseña de un usuario por su ID."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET contrasena = ? WHERE id = ?",
                (_hash_password(nueva_contrasena), usuario_id)
            )
            conn.commit()


# ---------------------------------------------------------------------------
# DAO de Empresas
# ---------------------------------------------------------------------------

class EmpresasDAO:
    """Gestiona la tabla `empresas` para el sistema multi-marca."""

    def crear(self, nombre: str, ruta_logo: str = "") -> int:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO empresas (nombre, ruta_logo) VALUES (?, ?)",
                (nombre.strip(), ruta_logo)
            )
            conn.commit()
            return cur.lastrowid

    def listar(self) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, nombre, ruta_logo, licencia_activa FROM empresas ORDER BY nombre"
            ).fetchall()
            return [dict(r) for r in rows]

    def obtener_primera(self) -> Optional[dict]:
        """Devuelve la primera empresa registrada, o None si no hay ninguna."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id, nombre, ruta_logo, licencia_activa FROM empresas LIMIT 1"
                ).fetchone()
                return dict(row) if row else None
        except Exception:
            return None

    def obtener_por_id(self, empresa_id: int) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, nombre, ruta_logo, licencia_activa FROM empresas WHERE id = ?",
                (empresa_id,)
            ).fetchone()
            return dict(row) if row else None

    def actualizar(self, empresa_id: int, nombre: str, ruta_logo: str = "") -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE empresas SET nombre = ?, ruta_logo = ? WHERE id = ?",
                (nombre.strip(), ruta_logo, empresa_id)
            )
            conn.commit()

    def eliminar(self, empresa_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM empresas WHERE id = ?", (empresa_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# DAO de Clientes
# ---------------------------------------------------------------------------

class ClientesDAO:
    """Gestiona la tabla `clientes` para autocompletado en el POS."""

    def buscar(self, termino: str, limite: int = 10) -> list[dict]:
        """
        Busca clientes por cédula o nombre (parcial, case-insensitive).
        Devuelve hasta `limite` resultados.
        """
        if not termino or not termino.strip():
            return []
        t = f"%{termino.strip().lower()}%"
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT cedula, nombre, telefono FROM clientes"
                    " WHERE LOWER(cedula) LIKE ? OR LOWER(nombre) LIKE ?"
                    " ORDER BY nombre LIMIT ?",
                    (t, t, limite)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def upsert(self, cedula: str, nombre: str, telefono: str = "") -> None:
        """
        Inserta o actualiza un cliente.
        Si la cédula ya existe, actualiza nombre y teléfono si se proveen.
        Si no existe, lo inserta.
        """
        if not cedula or cedula.strip() in ("", "N/A", "S/C"):
            return
        cedula = cedula.strip()
        nombre = nombre.strip()
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO clientes (cedula, nombre, telefono) VALUES (?, ?, ?)"
                    " ON CONFLICT(cedula) DO UPDATE SET"
                    " nombre = CASE WHEN excluded.nombre != '' THEN excluded.nombre ELSE nombre END,"
                    " telefono = CASE WHEN excluded.telefono != '' THEN excluded.telefono ELSE telefono END",
                    (cedula, nombre, telefono)
                )
                conn.commit()
        except Exception as e:
            logger.warning("ClientesDAO.upsert error: %s", e)

    def listar(self) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT cedula, nombre, telefono FROM clientes ORDER BY nombre"
            ).fetchall()
            return [dict(r) for r in rows]

    def eliminar(self, cedula: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM clientes WHERE cedula = ?", (cedula,))
            conn.commit()

# ---------------------------------------------------------------------------
# VentasDAO
# ---------------------------------------------------------------------------

class VentasDAO:
    """
    Data Access Object para las tablas `ventas` y `detalles_venta`.
    """

    def registrar_venta(
        self,
        nombre_cliente: str,
        cedula_cliente: str,
        total_usd: float,
        total_bs: float,
        items: list,
        metodo_pago: str = "Punto",
    ) -> int:
        """
        Registra una venta en una sola transacción atómica:
          1. Inserta cabecera en `ventas`.
          2. Inserta cada línea en `detalles_venta`.
          3. Descuenta stock en `inventario`.

        Args:
            nombre_cliente: Nombre del comprador.
            cedula_cliente:  Cédula / RIF del comprador.
            total_usd:       Total en dólares.
            total_bs:        Total en bolívares.
            items:           Lista de dicts {'id','nombre','qty','precio_venta'}.

        Returns:
            int: ID de la venta creada.

        Raises:
            ValueError: Carrito vacío o stock insuficiente.
            sqlite3.Error: Error de base de datos.
        """
        if not items:
            raise ValueError("El carrito está vacío.")

        sql_venta = """
            INSERT INTO ventas (nombre_cliente, cedula_cliente, total_usd, total_bs, metodo_pago)
            VALUES (?, ?, ?, ?, ?)
        """
        sql_detalle = """
            INSERT INTO detalles_venta
                   (id_venta, id_producto, nombre_producto, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?)
        """
        sql_stock   = """
            UPDATE inventario
            SET    cantidad       = cantidad - ?,
                   actualizado_en = strftime('%Y-%m-%dT%H:%M:%S', 'now')
            WHERE  id = ? AND cantidad >= ?
        """
        sql_check   = "SELECT cantidad FROM inventario WHERE id = ?"

        try:
            with get_connection() as conn:
                # Verificar stock antes de escribir
                for item in items:
                    row = conn.execute(sql_check, (item["id"],)).fetchone()
                    if row is None:
                        raise ValueError(f"Producto ID {item['id']} no encontrado.")
                    if row["cantidad"] < item["qty"]:
                        raise ValueError(
                            f"Stock insuficiente para '{item['nombre']}'. "
                            f"Disponible: {row['cantidad']}, solicitado: {item['qty']}."
                        )

                # 1. Cabecera
                cur      = conn.execute(sql_venta, (nombre_cliente, cedula_cliente, total_usd, total_bs, metodo_pago))
                id_venta = cur.lastrowid

                # 2. Líneas + descuento de stock
                for item in items:
                    conn.execute(sql_detalle, (
                        id_venta, item["id"], item["nombre"],
                        item["qty"], item["precio_venta"],
                    ))
                    conn.execute(sql_stock, (item["qty"], item["id"], item["qty"]))

                conn.commit()
                logger.info(
                    "Venta #%d registrada — Cliente: %s — Total: $%.2f USD",
                    id_venta, nombre_cliente, total_usd,
                )
                return id_venta

        except sqlite3.Error as e:
            logger.error("Error al registrar venta: %s", e)
            raise

    def listar_ventas(self) -> list:
        """Devuelve todas las ventas de más reciente a más antigua."""
        sql = """
            SELECT id, fecha, nombre_cliente, cedula_cliente, total_usd, total_bs,
                   COALESCE(metodo_pago, 'Punto') AS metodo_pago
            FROM   ventas
            ORDER  BY fecha DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar ventas: %s", e)
            raise

    def obtener_detalles_venta(self, id_venta: int) -> list:
        """Devuelve las líneas de detalle de una venta."""
        sql = """
            SELECT d.id, d.id_venta, d.id_producto, d.nombre_producto,
                   d.cantidad, d.precio_unitario,
                   (d.cantidad * d.precio_unitario) AS subtotal
            FROM   detalles_venta d
            WHERE  d.id_venta = ?
            ORDER  BY d.id
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql, (id_venta,)).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al obtener detalles de venta #%d: %s", id_venta, e)
            raise

    def listar_ventas_del_dia(self, fecha: str | None = None) -> list:
        """
        Devuelve todas las ventas del día indicado (por defecto, hoy).

        Args:
            fecha: Fecha en formato 'YYYY-MM-DD'. Si es None usa la fecha de hoy.
        """
        if fecha is None:
            from datetime import datetime, timezone
            # SQLite guarda las fechas con strftime(...,'now') que es UTC.
            # Usamos UTC aqui para que la consulta coincida.
            fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        sql = """
            SELECT id, fecha, nombre_cliente, cedula_cliente, total_usd, total_bs,
                   COALESCE(metodo_pago, 'Punto') AS metodo_pago
            FROM   ventas
            WHERE  strftime('%Y-%m-%d', fecha) = ?
            ORDER  BY fecha ASC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql, (fecha,)).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar ventas del día %s: %s", fecha, e)
            raise

    def resumen_dia(self, fecha: str | None = None) -> dict:
        """
        Calcula el resumen agregado del día.

        Returns dict con claves:
            fecha, total_ventas, total_usd, total_bs, productos.
        """
        if fecha is None:
            from datetime import datetime, timezone
            # SQLite guarda las fechas con strftime(...,'now') que es UTC.
            # Usamos UTC aqui para que la consulta coincida.
            fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        sql_cab = """
            SELECT COUNT(*) AS total_ventas,
                   COALESCE(SUM(total_usd), 0) AS total_usd,
                   COALESCE(SUM(total_bs),  0) AS total_bs
            FROM   ventas
            WHERE  strftime('%Y-%m-%d', fecha) = ?
        """
        sql_prods = """
            SELECT d.nombre_producto,
                   SUM(d.cantidad)                     AS cantidad_total,
                   SUM(d.cantidad * d.precio_unitario) AS subtotal
            FROM   detalles_venta d
            JOIN   ventas         v ON v.id = d.id_venta
            WHERE  strftime('%Y-%m-%d', v.fecha) = ?
            GROUP  BY d.nombre_producto
            ORDER  BY subtotal DESC
        """
        try:
            with get_connection() as conn:
                cab   = dict(conn.execute(sql_cab,   (fecha,)).fetchone())
                prods = [dict(r) for r in conn.execute(sql_prods, (fecha,)).fetchall()]
                return {
                    "fecha":        fecha,
                    "total_ventas": cab["total_ventas"],
                    "total_usd":    cab["total_usd"],
                    "total_bs":     cab["total_bs"],
                    "productos":    prods,
                }
        except sqlite3.Error as e:
            logger.error("Error al calcular resumen del día %s: %s", fecha, e)
            raise


# ===========================================================================
# DAO: Deudores (Fiado)
# ===========================================================================

class DeudoresDAO:
    """
    Data Access Object para la tabla `deudores`.

    Métodos:
        crear_deuda(...)      → int  (id del nuevo deudor)
        listar_deudores()     → list[dict]  (todos, ordenados por fecha DESC)
        listar_pendientes()   → list[dict]  (solo estado='Pendiente')
        marcar_pagada(id)     → None
    """

    def crear_deuda(
        self,
        nombre: str,
        telefono: str,
        monto_usd: float,
        monto_bs: float,
        fecha_limite_pago: str,
    ) -> int:
        """Inserta un nuevo deudor y devuelve su ID."""
        sql = """
            INSERT INTO deudores (nombre, telefono, monto_deuda_usd, monto_deuda_bs,
                                  fecha_limite_pago, estado)
            VALUES (?, ?, ?, ?, ?, 'Pendiente')
        """
        try:
            with get_connection() as conn:
                cur = conn.execute(sql, (nombre, telefono, monto_usd, monto_bs, fecha_limite_pago))
                conn.commit()
                id_deudor = cur.lastrowid
                logger.info("Deuda registrada — ID: %d | Cliente: %s | $%.2f USD", id_deudor, nombre, monto_usd)
                return id_deudor
        except sqlite3.Error as e:
            logger.error("Error al registrar deuda: %s", e)
            raise

    def listar_deudores(self) -> list:
        """Devuelve todos los deudores ordenados por fecha de venta descendente."""
        sql = """
            SELECT id, nombre, telefono, monto_deuda_usd, monto_deuda_bs,
                   fecha_venta, fecha_limite_pago, estado
            FROM   deudores
            ORDER  BY fecha_venta DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar deudores: %s", e)
            raise

    def listar_pendientes(self) -> list:
        """Devuelve solo los deudores con deuda pendiente."""
        sql = """
            SELECT id, nombre, telefono, monto_deuda_usd, monto_deuda_bs,
                   fecha_venta, fecha_limite_pago, estado
            FROM   deudores
            WHERE  estado = 'Pendiente'
            ORDER  BY fecha_limite_pago ASC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar deudores pendientes: %s", e)
            raise

    def listar_pagadas(self) -> list:
        """Devuelve solo los deudores con deuda pagada."""
        sql = """
            SELECT id, nombre, telefono, monto_deuda_usd, monto_deuda_bs,
                   fecha_venta, fecha_limite_pago, estado
            FROM   deudores
            WHERE  estado = 'Pagada'
            ORDER  BY fecha_venta DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar deudores pagadas: %s", e)
            raise

    def marcar_pagada(self, id_deudor: int) -> None:
        """Cambia el estado de un deudor a 'Pagada'."""
        sql = "UPDATE deudores SET estado = 'Pagada' WHERE id = ?"
        try:
            with get_connection() as conn:
                conn.execute(sql, (id_deudor,))
                conn.commit()
                logger.info("Deuda #%d marcada como Pagada", id_deudor)
        except sqlite3.Error as e:
            logger.error("Error al marcar deuda #%d como pagada: %s", id_deudor, e)
            raise

    def listar_vencidos(self) -> list[dict]:
        """
        Devuelve los deudores pendientes cuya fecha límite de pago ya pasó.
        Parsea fecha_limite_pago en formato DD/MM/AAAA o AAAA-MM-DD.

        Returns:
            Lista de dicts, con campo extra 'dias_atraso'. Más atrasados primero.
        """
        from datetime import datetime
        hoy = datetime.now().date()
        try:
            pendientes = self.listar_pendientes()
        except Exception as e:
            logger.error("Error al obtener vencidos: %s", e)
            raise
        vencidos = []
        for d in pendientes:
            fecha_str = (d.get("fecha_limite_pago") or "").strip()
            if not fecha_str:
                continue
            fecha_limite = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    fecha_limite = datetime.strptime(fecha_str, fmt).date()
                    break
                except ValueError:
                    continue
            if fecha_limite is not None and fecha_limite < hoy:
                d["dias_atraso"] = (hoy - fecha_limite).days
                vencidos.append(d)
        vencidos.sort(key=lambda x: x["dias_atraso"], reverse=True)
        return vencidos


# ===========================================================================
# DAO: Cuentas por Pagar (nuestras deudas)
# ===========================================================================

class CuentasPorPagarDAO:
    """
    Data Access Object para la tabla `cuentas_por_pagar`.
    Registra deudas propias del negocio (lo que nosotros debemos).
    """

    def crear(
        self,
        nombre: str,
        descripcion: str = "",
        banco: str = "",
        cedula: str = "",
        telefono: str = "",
        monto_usd: float = 0.0,
        monto_bs: float = 0.0,
    ) -> int:
        """Inserta una nueva cuenta por pagar y devuelve su ID."""
        sql = """
            INSERT INTO cuentas_por_pagar
                (nombre, descripcion, banco, cedula, telefono, monto_usd, monto_bs, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente')
        """
        try:
            with get_connection() as conn:
                cur = conn.execute(sql, (nombre, descripcion, banco, cedula, telefono, monto_usd, monto_bs))
                conn.commit()
                new_id = cur.lastrowid
                logger.info("Cuenta por pagar registrada — ID: %d | %s | $%.2f", new_id, nombre, monto_usd)
                return new_id
        except sqlite3.Error as e:
            logger.error("Error al registrar cuenta por pagar: %s", e)
            raise

    def listar_todas(self) -> list:
        """Devuelve todas las cuentas por pagar ordenadas por fecha descendente."""
        sql = """
            SELECT id, nombre, descripcion, banco, cedula, telefono,
                   monto_usd, monto_bs, fecha, estado
            FROM   cuentas_por_pagar
            ORDER  BY fecha DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar cuentas por pagar: %s", e)
            raise

    def listar_pendientes(self) -> list:
        """Devuelve solo las cuentas pendientes."""
        sql = """
            SELECT id, nombre, descripcion, banco, cedula, telefono,
                   monto_usd, monto_bs, fecha, estado
            FROM   cuentas_por_pagar
            WHERE  estado = 'Pendiente'
            ORDER  BY fecha DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar cuentas pendientes: %s", e)
            raise

    def listar_pagadas(self) -> list:
        """Devuelve solo las cuentas pagadas."""
        sql = """
            SELECT id, nombre, descripcion, banco, cedula, telefono,
                   monto_usd, monto_bs, fecha, estado
            FROM   cuentas_por_pagar
            WHERE  estado = 'Pagada'
            ORDER  BY fecha DESC
        """
        try:
            with get_connection() as conn:
                return [dict(r) for r in conn.execute(sql).fetchall()]
        except sqlite3.Error as e:
            logger.error("Error al listar cuentas pagadas: %s", e)
            raise

    def marcar_pagada(self, cuenta_id: int) -> None:
        """Cambia el estado de una cuenta a 'Pagada'."""
        sql = "UPDATE cuentas_por_pagar SET estado = 'Pagada' WHERE id = ?"
        try:
            with get_connection() as conn:
                conn.execute(sql, (cuenta_id,))
                conn.commit()
                logger.info("Cuenta por pagar #%d marcada como Pagada", cuenta_id)
        except sqlite3.Error as e:
            logger.error("Error al marcar cuenta #%d como pagada: %s", cuenta_id, e)
            raise


# ---------------------------------------------------------------------------
# Entrypoint de demostración
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Inicializar la base de datos
    inicializar_db()

    dao = InventarioDAO()

    # 2. CREATE — insertar repuestos de ejemplo
    print("\n--- CREATE ---")
    id1 = dao.crear(
        nombre="Resistencia calefactora",
        modelo="RH-400W",
        marca="Thermo-Parts",
        precio_entrada=5.00,
        precio_venta=12.50,
        cantidad=100,
        sku="RH-400W-TP",
        ubicacion="Estante A-1",
        descripcion="Resistencia 400 W para lavadoras de carga frontal.",
        imagen_ruta="imagenes/resistencia_rh400.jpg",
    )
    id2 = dao.crear(
        nombre="Termostato bimetálico",
        modelo="TB-16A",
        marca="Genco",
        precio_entrada=3.75,
        precio_venta=9.99,
        cantidad=50,
        sku="TB-16A-GNC",
        ubicacion="Estante A-2",
        descripcion="Termostato bimetálico 16 A / 250 V.",
        imagen_ruta="imagenes/termostato_tb16.jpg",
    )
    print(f"Creados con ID: {id1}, {id2}")

    # 3. READ — listar todos
    print("\n--- READ (listar todos) ---")
    for item in dao.listar_todos():
        print(f"  [{item['id']}] {item['nombre']} | SKU: {item['sku']} | Qty: {item['cantidad']}")

    # 4. SEARCH — buscar por SKU exacto
    print("\n--- SEARCH por SKU ---")
    resultado = dao.buscar_por_sku("RH-400W-TP")
    print(f"  Encontrado: {resultado['nombre']}" if resultado else "  No encontrado")

    # 5. SEARCH — búsqueda general por nombre
    print("\n--- SEARCH por nombre ---")
    for r in dao.buscar("Termo"):
        print(f"  [{r['id']}] {r['nombre']}")

    # 6. UPDATE — modificar precio y cantidad
    print("\n--- UPDATE ---")
    ok = dao.actualizar(id1, precio_venta=14.00, cantidad=95)
    print(f"  Actualización exitosa: {ok}")
    actualizado = dao.obtener_por_id(id1)
    print(f"  Nuevo precio_venta: {actualizado['precio_venta']} | Cantidad: {actualizado['cantidad']}")

    # 7. DELETE
    print("\n--- DELETE ---")
    ok = dao.eliminar(id2)
    print(f"  Eliminación exitosa: {ok}")
    print(f"  Total registros restantes: {len(dao.listar_todos())}")
