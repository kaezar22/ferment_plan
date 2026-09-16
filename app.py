"""
Ferment Plan
------------
Webapp en Streamlit para planificar y monitorear ciclos de fermentadores
de una cervecería, con alertas por correo cuando un ciclo está por
terminar (el envío automático real lo hace scripts/check_alerts.py vía
GitHub Actions; esta app además permite mandar una alerta de prueba).
"""

from __future__ import annotations

from datetime import datetime, date, time as dtime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from sheets import SheetsClient, DEFAULT_SPREADSHEET_ID, now_iso
from ciclos import calcular_fin_fase, parse_iso, progreso_fase
from alertas import send_email, SmtpCredentials

TZ_LOCAL = ZoneInfo("America/Bogota")

st.set_page_config(page_title="Ferment Plan", page_icon="🍺", layout="wide")


# ---------------------------------------------------------------------- #
# Conexión a Google Sheets
# ---------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Conectando a Google Sheets...")
def get_client() -> SheetsClient:
    creds_dict = dict(st.secrets["gcp_service_account"])
    spreadsheet_id = st.secrets.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)
    client = SheetsClient(creds_dict, spreadsheet_id)
    client.ensure_sheets()
    return client


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(TZ_LOCAL)


def fmt(dt: datetime) -> str:
    return to_local(dt).strftime("%Y-%m-%d %H:%M")


try:
    client = get_client()
except Exception as e:
    st.error(
        "No se pudo conectar a Google Sheets. Revisa que exista "
        "`.streamlit/secrets.toml` (o los secrets en Streamlit Cloud) con la "
        "sección `[gcp_service_account]` y que la hoja esté compartida con "
        "el email de esa cuenta de servicio.\n\nError original: "
        f"`{e}`"
    )
    st.stop()


st.title("🍺 Ferment Plan")
st.caption("Planificación, monitoreo y alertas de ciclos de fermentación")

tab_config, tab_monitoreo, tab_historial = st.tabs(
    ["⚙️ Configuración", "📊 Monitoreo", "📜 Historial"]
)

# ======================================================================
# TAB 1 — CONFIGURACIÓN
# ======================================================================
with tab_config:
    st.subheader("Alertas")
    cfg = client.get_config()

    with st.form("form_config_alertas"):
        col1, col2, col3 = st.columns([2, 1, 1])
        email_alertas = col1.text_input(
            "Email(s) para alertas (separados por coma)",
            value=cfg.get("email_alertas", ""),
        )
        antelacion_valor = col2.number_input(
            "Antelación",
            min_value=0.0,
            value=float(cfg.get("antelacion_valor", 12) or 0),
            step=1.0,
        )
        antelacion_unidad = col3.selectbox(
            "Unidad",
            options=["horas", "dias"],
            index=0 if cfg.get("antelacion_unidad", "horas") == "horas" else 1,
        )
        if st.form_submit_button("Guardar configuración de alertas"):
            client.set_config(
                email_alertas=email_alertas,
                antelacion_valor=antelacion_valor,
                antelacion_unidad=antelacion_unidad,
            )
            st.success("Configuración guardada.")
            st.rerun()

    with st.expander("Enviar correo de prueba"):
        st.caption(
            "Requiere que `[gmail]` esté configurado en secrets (address y "
            "app_password) para poder probar el envío desde la propia app."
        )
        if st.button("Enviar alerta de prueba"):
            try:
                gmail_cfg = st.secrets["gmail"]
                creds = SmtpCredentials(gmail_cfg["address"], gmail_cfg["app_password"])
                destinatarios = cfg.get("email_alertas", "").split(",")
                send_email(
                    creds,
                    destinatarios,
                    "[Ferment Plan] Correo de prueba",
                    "Este es un correo de prueba de Ferment Plan. Si lo recibiste, "
                    "la configuración de envío funciona correctamente.",
                )
                st.success(f"Correo de prueba enviado a: {cfg.get('email_alertas', '')}")
            except KeyError:
                st.error(
                    "No encontré `[gmail]` en secrets.toml. Agrega `address` y "
                    "`app_password` (ver README) para poder mandar correos de prueba "
                    "desde la app."
                )
            except Exception as e:
                st.error(f"No se pudo enviar el correo: {e}")

    st.divider()
    st.subheader("Fermentadores")

    fermentadores = client.get_fermentadores()
    if fermentadores:
        df_ferm = pd.DataFrame(fermentadores)[["id", "nombre", "capacidad_litros", "activo"]]
        st.dataframe(df_ferm, hide_index=True, use_container_width=True)
    else:
        st.info("Todavía no has agregado ningún fermentador.")

    with st.form("form_nuevo_fermentador", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        nombre_ferm = col1.text_input("Nombre del fermentador (ej: FV-01)")
        capacidad = col2.text_input("Capacidad (L, opcional)")
        if st.form_submit_button("Agregar fermentador"):
            if nombre_ferm.strip():
                client.add_fermentador(nombre_ferm.strip(), capacidad.strip())
                st.success(f"Fermentador '{nombre_ferm}' agregado.")
                st.rerun()
            else:
                st.warning("Ponle un nombre al fermentador.")

    st.divider()
    st.subheader("Iniciar nuevo lote")

    fermentadores_activos = [f for f in fermentadores if str(f.get("activo")).upper() == "TRUE"]
    fermentadores_libres = [
        f for f in fermentadores_activos if not client.fermentador_tiene_lote_activo(f["id"])
    ]

    if not fermentadores_libres:
        st.info(
            "No hay fermentadores libres. Agrega uno nuevo arriba, o cierra un lote "
            "activo en la pestaña Monitoreo."
        )
    else:
        with st.form("form_nuevo_lote", clear_on_submit=True):
            opciones = {f["nombre"]: f["id"] for f in fermentadores_libres}
            nombre_sel = st.selectbox("Fermentador", options=list(opciones.keys()))
            tipo_cerveza = st.text_input("Tipo de cerveza / receta")

            colf1, colf2 = st.columns(2)
            fecha_inicio_d = colf1.date_input("Fecha de inicio", value=date.today())
            fecha_inicio_t = colf2.time_input("Hora de inicio", value=datetime.now().time().replace(microsecond=0))

            cold1, cold2 = st.columns(2)
            dias_fermentacion = cold1.number_input("Días de fermentación", min_value=0.0, value=7.0, step=0.5)
            dias_maduracion = cold2.number_input("Días de maduración", min_value=0.0, value=14.0, step=0.5)

            notas = st.text_area("Notas (opcional)")

            if st.form_submit_button("Iniciar lote"):
                if not tipo_cerveza.strip():
                    st.warning("Especifica el tipo de cerveza.")
                else:
                    fecha_inicio_local = datetime.combine(fecha_inicio_d, fecha_inicio_t, tzinfo=TZ_LOCAL)
                    fecha_inicio_utc = fecha_inicio_local.astimezone(timezone.utc)
                    fecha_fin_ferm = calcular_fin_fase(fecha_inicio_utc, dias_fermentacion)
                    client.add_lote(
                        fermentador_id=opciones[nombre_sel],
                        fermentador_nombre=nombre_sel,
                        tipo_cerveza=tipo_cerveza.strip(),
                        fecha_inicio_iso=fecha_inicio_utc.isoformat(),
                        dias_fermentacion=dias_fermentacion,
                        dias_maduracion=dias_maduracion,
                        fecha_fin_fermentacion_iso=fecha_fin_ferm.isoformat(),
                        notas=notas.strip(),
                    )
                    st.success(f"Lote iniciado en {nombre_sel}.")
                    st.rerun()

# ======================================================================
# TAB 2 — MONITOREO
# ======================================================================
with tab_monitoreo:
    lotes_activos = client.get_lotes(estado=["en_fermentacion", "en_maduracion"])

    if not lotes_activos:
        st.info("No hay lotes activos en este momento.")
    else:
        ahora = datetime.now(timezone.utc)
        for lote in lotes_activos:
            fase = "fermentacion" if lote["estado"] == "en_fermentacion" else "maduracion"

            if fase == "fermentacion":
                inicio_fase = parse_iso(lote["fecha_inicio"])
                fin_fase = parse_iso(lote["fecha_fin_fermentacion"])
                dias_fase = lote["dias_fermentacion"]
            else:
                inicio_fase = parse_iso(lote["fecha_inicio_maduracion"]) or parse_iso(lote["fecha_fin_fermentacion"])
                fin_fase = parse_iso(lote["fecha_fin_maduracion"])
                dias_fase = lote["dias_maduracion"]

            pct = progreso_fase(inicio_fase, fin_fase, ahora)
            transcurrido = ahora - inicio_fase
            restante = fin_fase - ahora

            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"### {lote['fermentador_nombre']} — {lote['tipo_cerveza']}")
                    st.caption(
                        f"Fase actual: **{'Fermentación' if fase == 'fermentacion' else 'Maduración'}** "
                        f"({dias_fase} días) · Lote `{lote['id']}`"
                    )
                    st.progress(pct / 100, text=f"{pct:.0f}% de avance")
                    dias_transcurridos = max(transcurrido.total_seconds(), 0) / 86400
                    if restante.total_seconds() >= 0:
                        st.write(
                            f"⏱️ Lleva **{dias_transcurridos:.1f} días** — "
                            f"faltan **{restante.total_seconds() / 3600:.1f} horas** "
                            f"(fin estimado: {fmt(fin_fase)})"
                        )
                    else:
                        st.write(
                            f"⚠️ Fase **vencida** desde el {fmt(fin_fase)} "
                            f"(hace {abs(restante.total_seconds()) / 3600:.1f} horas). "
                            f"Lleva {dias_transcurridos:.1f} días en esta fase."
                        )

                with c2:
                    if fase == "fermentacion":
                        if st.button("✅ Confirmar fin de fermentación → iniciar maduración", key=f"fin_ferm_{lote['id']}"):
                            inicio_madur = ahora
                            fin_madur = calcular_fin_fase(inicio_madur, lote["dias_maduracion"])
                            client.confirmar_fin_fermentacion(
                                lote["id"], inicio_madur.isoformat(), fin_madur.isoformat()
                            )
                            st.success("Lote pasó a maduración.")
                            st.rerun()
                    else:
                        if st.button("🏁 Confirmar fin de maduración → archivar lote", key=f"fin_madur_{lote['id']}"):
                            client.confirmar_fin_maduracion(lote["id"], ahora.isoformat())
                            st.success("Lote completado y movido al historial.")
                            st.rerun()

# ======================================================================
# TAB 3 — HISTORIAL
# ======================================================================
with tab_historial:
    lotes_hist = client.get_lotes(estado="completado")
    if not lotes_hist:
        st.info("Todavía no hay lotes completados.")
    else:
        df = pd.DataFrame(lotes_hist)
        df["fecha_inicio"] = df["fecha_inicio"].apply(lambda x: fmt(parse_iso(x)) if x else "")
        df["fecha_completado"] = df["fecha_completado"].apply(lambda x: fmt(parse_iso(x)) if x else "")

        colf1, colf2 = st.columns(2)
        fermentador_filtro = colf1.multiselect(
            "Filtrar por fermentador", options=sorted(df["fermentador_nombre"].unique())
        )
        cerveza_filtro = colf2.multiselect(
            "Filtrar por tipo de cerveza", options=sorted(df["tipo_cerveza"].unique())
        )

        df_show = df.copy()
        if fermentador_filtro:
            df_show = df_show[df_show["fermentador_nombre"].isin(fermentador_filtro)]
        if cerveza_filtro:
            df_show = df_show[df_show["tipo_cerveza"].isin(cerveza_filtro)]

        columnas = [
            "fermentador_nombre",
            "tipo_cerveza",
            "fecha_inicio",
            "dias_fermentacion",
            "dias_maduracion",
            "fecha_completado",
            "notas",
        ]
        st.dataframe(
            df_show[columnas].sort_values("fecha_completado", ascending=False),
            hide_index=True,
            use_container_width=True,
        )
