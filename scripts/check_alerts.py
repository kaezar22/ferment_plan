"""
scripts/check_alerts.py
------------------------
Script independiente de Streamlit, pensado para correr por GitHub Actions
con un horario (cron). Revisa los lotes activos en Google Sheets y, si
alguna fase está por terminar (dentro de la antelación configurada) y
todavía no se mandó la alerta, envía un correo y marca el lote.

Variables de entorno requeridas (se configuran como Secrets del repo en
GitHub, ver README.md):
  GCP_SERVICE_ACCOUNT_JSON  -> contenido completo del JSON de la cuenta de servicio
  SPREADSHEET_ID            -> (opcional) ID del Google Sheet, si no se usa el default
  GMAIL_ADDRESS              -> cuenta de Gmail remitente
  GMAIL_APP_PASSWORD         -> contraseña de aplicación de esa cuenta
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sheets import SheetsClient, DEFAULT_SPREADSHEET_ID  # noqa: E402
from alerts import (  # noqa: E402
    parse_iso,
    debe_enviar_alerta,
    construir_mensaje_alerta,
    send_email,
    SmtpCredentials,
)


def main() -> int:
    creds_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("ERROR: falta la variable de entorno GCP_SERVICE_ACCOUNT_JSON", file=sys.stderr)
        return 1
    creds_dict = json.loads(creds_json)

    spreadsheet_id = os.environ.get("SPREADSHEET_ID") or DEFAULT_SPREADSHEET_ID

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("ERROR: faltan GMAIL_ADDRESS / GMAIL_APP_PASSWORD", file=sys.stderr)
        return 1
    smtp_creds = SmtpCredentials(gmail_address, gmail_app_password)

    client = SheetsClient(creds_dict, spreadsheet_id)
    client.ensure_sheets()

    cfg = client.get_config()
    destinatarios = cfg.get("email_alertas", "").split(",")
    antelacion_valor = float(cfg.get("antelacion_valor", 12) or 0)
    antelacion_unidad = cfg.get("antelacion_unidad", "horas")

    ahora = datetime.now(timezone.utc)
    enviados = 0

    lotes = client.get_lotes(estado=["en_fermentacion", "en_maduracion"])
    for lote in lotes:
        if lote["estado"] == "en_fermentacion":
            fase = "fermentacion"
            fin_fase = parse_iso(lote["fecha_fin_fermentacion"])
            ya_enviada = str(lote.get("alerta_fermentacion_enviada")).upper() == "TRUE"
            campo_flag = "alerta_fermentacion_enviada"
        else:
            fase = "maduracion"
            fin_fase = parse_iso(lote["fecha_fin_maduracion"])
            ya_enviada = str(lote.get("alerta_maduracion_enviada")).upper() == "TRUE"
            campo_flag = "alerta_maduracion_enviada"

        if fin_fase is None:
            continue

        if debe_enviar_alerta(fin_fase, antelacion_valor, antelacion_unidad, ya_enviada, ahora):
            asunto, cuerpo = construir_mensaje_alerta(lote, fase, fin_fase)
            try:
                send_email(smtp_creds, destinatarios, asunto, cuerpo)
                client.marcar_alerta_enviada(lote["id"], campo_flag)
                enviados += 1
                print(f"Alerta enviada: lote {lote['id']} ({lote['fermentador_nombre']}, {fase})")
            except Exception as e:
                print(f"ERROR enviando alerta para lote {lote['id']}: {e}", file=sys.stderr)

    print(f"Listo. Alertas enviadas: {enviados}. Lotes revisados: {len(lotes)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
