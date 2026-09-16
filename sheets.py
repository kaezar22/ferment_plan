"""
sheets.py
---------
Capa de acceso a Google Sheets para Ferment Plan.

No depende de Streamlit: recibe las credenciales de la cuenta de servicio
y el ID del spreadsheet como parámetros, para poder usarse tanto desde
app.py (Streamlit) como desde scripts/check_alerts.py (GitHub Actions).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import gspread

# ID del Google Sheet por defecto (el que ya está compartido con la cuenta
# de servicio). Se puede sobreescribir vía secrets/env var SPREADSHEET_ID.
DEFAULT_SPREADSHEET_ID = "160F053a-MKrFQAet7MA28FDU6i5cJCiucM6-9XYiZ_M"

TZ = timezone.utc  # las fechas se guardan en UTC; la conversión a la zona
# horaria local (America/Bogota) se hace solo al mostrarlas en la UI.

FERMENTADORES_HEADERS = ["id", "nombre", "capacidad_litros", "activo", "creado_en"]

LOTES_HEADERS = [
    "id",
    "fermentador_id",
    "fermentador_nombre",
    "tipo_cerveza",
    "fecha_inicio",
    "dias_fermentacion",
    "dias_maduracion",
    "fecha_fin_fermentacion",
    "fecha_inicio_maduracion",
    "fecha_fin_maduracion",
    "estado",  # en_fermentacion | en_maduracion | completado
    "alerta_fermentacion_enviada",
    "alerta_maduracion_enviada",
    "fecha_completado",
    "notas",
]

CONFIG_HEADERS = ["clave", "valor"]

CONFIG_DEFAULTS = {
    "email_alertas": "",
    "antelacion_valor": "12",
    "antelacion_unidad": "horas",  # "horas" | "dias"
}


def now_iso() -> str:
    return datetime.now(TZ).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class SheetsClient:
    """Envoltorio delgado sobre gspread con las operaciones que necesita la app."""

    def __init__(self, creds_dict: dict, spreadsheet_id: Optional[str] = None):
        self._gc = gspread.service_account_from_dict(creds_dict)
        self.spreadsheet_id = spreadsheet_id or DEFAULT_SPREADSHEET_ID
        self._sh = self._gc.open_by_key(self.spreadsheet_id)

    # ------------------------------------------------------------------ #
    # Setup / migraciones
    # ------------------------------------------------------------------ #
    def _get_or_create_ws(self, title: str, headers: list[str]):
        try:
            ws = self._sh.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(title=title, rows=200, cols=max(len(headers), 10))
            ws.append_row(headers)
            return ws
        # si la hoja existe pero está vacía, escribe encabezados
        if not ws.row_values(1):
            ws.append_row(headers)
        return ws

    def ensure_sheets(self):
        self._ws_fermentadores = self._get_or_create_ws("Fermentadores", FERMENTADORES_HEADERS)
        self._ws_lotes = self._get_or_create_ws("Lotes", LOTES_HEADERS)
        self._ws_config = self._get_or_create_ws("Config", CONFIG_HEADERS)

        existing_keys = {row["clave"] for row in self._ws_config.get_all_records()}
        for k, v in CONFIG_DEFAULTS.items():
            if k not in existing_keys:
                self._ws_config.append_row([k, v])

    # ------------------------------------------------------------------ #
    # Fermentadores
    # ------------------------------------------------------------------ #
    def get_fermentadores(self, solo_activos: bool = False) -> list[dict]:
        rows = self._ws_fermentadores.get_all_records()
        if solo_activos:
            rows = [r for r in rows if str(r.get("activo")).upper() == "TRUE"]
        return rows

    def add_fermentador(self, nombre: str, capacidad_litros: str = "") -> str:
        fid = new_id()
        self._ws_fermentadores.append_row([fid, nombre, capacidad_litros, "TRUE", now_iso()])
        return fid

    def set_fermentador_activo(self, fermentador_id: str, activo: bool):
        self._update_cell_by_id(self._ws_fermentadores, fermentador_id, "activo", "TRUE" if activo else "FALSE")

    # ------------------------------------------------------------------ #
    # Lotes
    # ------------------------------------------------------------------ #
    def get_lotes(self, estado: Optional[str] = None) -> list[dict]:
        rows = self._ws_lotes.get_all_records()
        if estado is not None:
            if isinstance(estado, (list, tuple, set)):
                rows = [r for r in rows if r.get("estado") in estado]
            else:
                rows = [r for r in rows if r.get("estado") == estado]
        return rows

    def fermentador_tiene_lote_activo(self, fermentador_id: str) -> bool:
        activos = self.get_lotes(estado=["en_fermentacion", "en_maduracion"])
        return any(r.get("fermentador_id") == fermentador_id for r in activos)

    def add_lote(
        self,
        fermentador_id: str,
        fermentador_nombre: str,
        tipo_cerveza: str,
        fecha_inicio_iso: str,
        dias_fermentacion: float,
        dias_maduracion: float,
        fecha_fin_fermentacion_iso: str,
        notas: str = "",
    ) -> str:
        lid = new_id()
        self._ws_lotes.append_row(
            [
                lid,
                fermentador_id,
                fermentador_nombre,
                tipo_cerveza,
                fecha_inicio_iso,
                dias_fermentacion,
                dias_maduracion,
                fecha_fin_fermentacion_iso,
                "",  # fecha_inicio_maduracion (se llena al confirmar transición)
                "",  # fecha_fin_maduracion (se calcula al confirmar transición)
                "en_fermentacion",
                "FALSE",
                "FALSE",
                "",  # fecha_completado
                notas,
            ]
        )
        return lid

    def confirmar_fin_fermentacion(self, lote_id: str, fecha_inicio_maduracion_iso: str, fecha_fin_maduracion_iso: str):
        self._update_row_by_id(
            self._ws_lotes,
            lote_id,
            {
                "estado": "en_maduracion",
                "fecha_inicio_maduracion": fecha_inicio_maduracion_iso,
                "fecha_fin_maduracion": fecha_fin_maduracion_iso,
            },
        )

    def confirmar_fin_maduracion(self, lote_id: str, fecha_completado_iso: str):
        self._update_row_by_id(
            self._ws_lotes,
            lote_id,
            {
                "estado": "completado",
                "fecha_completado": fecha_completado_iso,
            },
        )

    def marcar_alerta_enviada(self, lote_id: str, campo: str):
        """campo: 'alerta_fermentacion_enviada' o 'alerta_maduracion_enviada'"""
        self._update_cell_by_id(self._ws_lotes, lote_id, campo, "TRUE")

    # ------------------------------------------------------------------ #
    # Config
    # ------------------------------------------------------------------ #
    def get_config(self) -> dict:
        rows = self._ws_config.get_all_records()
        cfg = dict(CONFIG_DEFAULTS)
        for r in rows:
            cfg[r["clave"]] = r["valor"]
        return cfg

    def set_config(self, **kwargs):
        rows = self._ws_config.get_all_records()
        claves_existentes = {r["clave"]: i + 2 for i, r in enumerate(rows)}  # fila real (1-indexed + header)
        for k, v in kwargs.items():
            if k in claves_existentes:
                self._ws_config.update_cell(claves_existentes[k], 2, str(v))
            else:
                self._ws_config.append_row([k, str(v)])

    # ------------------------------------------------------------------ #
    # Helpers internos
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_row_index(ws, row_id: str) -> Optional[int]:
        ids = ws.col_values(1)  # columna "id" siempre es la primera
        for i, val in enumerate(ids):
            if val == row_id:
                return i + 1  # 1-indexed para gspread
        return None

    def _update_cell_by_id(self, ws, row_id: str, campo: str, valor):
        row_idx = self._find_row_index(ws, row_id)
        if row_idx is None:
            raise ValueError(f"No se encontró la fila con id={row_id}")
        headers = ws.row_values(1)
        col_idx = headers.index(campo) + 1
        ws.update_cell(row_idx, col_idx, valor)

    def _update_row_by_id(self, ws, row_id: str, campos: dict):
        for campo, valor in campos.items():
            self._update_cell_by_id(ws, row_id, campo, valor)
