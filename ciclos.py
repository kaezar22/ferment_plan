"""
ciclos.py
---------
Cálculo de fases (fermentación / maduración): fecha de fin de fase y
% de avance. Sin envío de alertas por ahora.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def calcular_fin_fase(fecha_inicio_fase: datetime, dias_duracion: float) -> datetime:
    return fecha_inicio_fase + timedelta(days=float(dias_duracion))


def progreso_fase(fecha_inicio_fase: datetime, fecha_fin_fase: datetime, ahora: Optional[datetime] = None) -> float:
    """Devuelve el % de avance de la fase actual, entre 0 y 100."""
    ahora = ahora or datetime.now(timezone.utc)
    total = (fecha_fin_fase - fecha_inicio_fase).total_seconds()
    if total <= 0:
        return 100.0
    transcurrido = (ahora - fecha_inicio_fase).total_seconds()
    pct = (transcurrido / total) * 100
    return max(0.0, min(100.0, pct))
