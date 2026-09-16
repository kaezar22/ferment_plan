"""
alertas.py
----------
Envío de alertas por correo (SMTP de Gmail). Sin dependencia de
Streamlit para poder usarse también desde scripts/check_alerts.py
(GitHub Actions).
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def antelacion_a_timedelta(valor: float, unidad: str) -> timedelta:
    valor = float(valor)
    if unidad.lower().startswith("hora"):
        return timedelta(hours=valor)
    return timedelta(days=valor)


def debe_enviar_alerta(
    fecha_fin_fase: datetime,
    antelacion_valor: float,
    antelacion_unidad: str,
    ya_enviada: bool,
    ahora: Optional[datetime] = None,
) -> bool:
    if ya_enviada:
        return False
    ahora = ahora or datetime.now(timezone.utc)
    umbral = fecha_fin_fase - antelacion_a_timedelta(antelacion_valor, antelacion_unidad)
    return ahora >= umbral


@dataclass
class SmtpCredentials:
    address: str
    app_password: str


def send_email(creds: SmtpCredentials, destinatarios: list[str], asunto: str, cuerpo: str) -> None:
    destinatarios = [d.strip() for d in destinatarios if d.strip()]
    if not destinatarios:
        raise ValueError("No hay destinatarios configurados (email_alertas está vacío).")

    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = creds.address
    msg["To"] = ", ".join(destinatarios)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(creds.address, creds.app_password)
        server.sendmail(creds.address, destinatarios, msg.as_string())


def construir_mensaje_alerta(lote: dict, fase: str, fecha_fin_fase: datetime) -> tuple[str, str]:
    """fase: 'fermentacion' o 'maduracion'. Devuelve (asunto, cuerpo)."""
    nombre_fase = "fermentación" if fase == "fermentacion" else "maduración"
    asunto = f"[Ferment Plan] {lote['fermentador_nombre']} - {nombre_fase} por terminar"
    cuerpo = (
        f"El fermentador '{lote['fermentador_nombre']}' (lote {lote['id']}, "
        f"{lote['tipo_cerveza']}) está por terminar su fase de {nombre_fase}.\n\n"
        f"Fecha/hora estimada de fin: {fecha_fin_fase.isoformat()}\n\n"
        f"Revisa la app Ferment Plan para confirmar la transición o el cierre del lote."
    )
    return asunto, cuerpo
