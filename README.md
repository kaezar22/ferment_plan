# Ferment Plan 🍺

Webapp en Streamlit para planificar y monitorear ciclos de fermentación y
maduración de una cervecería, con alertas automáticas por correo antes de
que termine cada fase.

## Cómo funciona

- **Datos**: se guardan en un Google Sheet (hojas `Fermentadores`, `Lotes`
  y `Config`), a las que la app accede con una cuenta de servicio de
  Google Cloud. Las hojas y sus encabezados se crean solas la primera vez
  que corre la app, así que no hace falta prepararlas a mano.
- **App (`app.py`)**: tiene 3 pestañas — Configuración (fermentadores,
  email de alertas, antelación, iniciar lotes), Monitoreo (% de avance de
  cada fermentador activo) e Historial (lotes completados).
- **Alertas (`scripts/check_alerts.py`)**: Streamlit solo ejecuta código
  cuando alguien tiene la app abierta, así que las alertas *de verdad*
  automáticas las manda un script aparte, corrido por **GitHub Actions**
  cada hora (`.github/workflows/check_alerts.yml`), independientemente de
  si la app está abierta o no.

## 1. Requisitos previos

- Una cuenta de servicio de Google Cloud con la API de Google Sheets (y
  Drive) habilitada — ya la tienes en `service_account.json` (este
  archivo **no se sube al repo**, está en `.gitignore`).
- El Google Sheet ya compartido con el email de esa cuenta de servicio
  (el campo `client_email` dentro del JSON) con permiso de **Editor**.
- Una cuenta de Gmail para *enviar* los correos, con una **contraseña de
  aplicación** (ver paso 2).

## 2. Generar la contraseña de aplicación de Gmail

1. Entra a tu cuenta de Google -> **Seguridad**.
2. Activa la **verificación en dos pasos** si no la tienes activada (es
   obligatoria para poder generar contraseñas de aplicación).
3. Busca **Contraseñas de aplicaciones** (o ve directo a
   https://myaccount.google.com/apppasswords).
4. Crea una nueva, ponle un nombre como "Ferment Plan", y copia el código
   de 16 caracteres que te da. Esa es tu `GMAIL_APP_PASSWORD` — **no es
   tu contraseña normal de Gmail**.

## 3. Probar localmente (opcional)

```bash
python -m venv .venv
.venv\Scripts\activate        # en Windows
pip install -r requirements.txt

copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# edita .streamlit\secrets.toml y pega ahí:
#  - los datos de service_account.json dentro de [gcp_service_account]
#  - tu Gmail y la contraseña de aplicación dentro de [gmail]

streamlit run app.py
```

## 4. Subir el repo a GitHub

```bash
git add .
git commit -m "Restaurar alertas por email"
git push
```

⚠️ Antes de commitear, confirma que `service_account.json` y
`.streamlit/secrets.toml` **no aparecen** en `git status` (deben estar
ignorados).

## 5. Desplegar en Streamlit Community Cloud

1. Ve a https://share.streamlit.io y conecta tu repo `ferment_plan`.
2. Archivo principal: `app.py`.
3. En **Settings -> Secrets** de la app en Streamlit Cloud, pega el mismo
   contenido que tienes en tu `.streamlit/secrets.toml` local (con tus
   valores reales, incluyendo `[gmail]`).
4. Guarda y despliega. La primera vez que cargue, la app creará las hojas
   `Fermentadores`, `Lotes` y `Config` dentro del Google Sheet si no
   existen todavía.

## 6. Configurar GitHub Actions (las alertas automáticas)

En tu repo de GitHub: **Settings -> Secrets and variables -> Actions ->
New repository secret**. Crea estos 4 secrets:

| Nombre                     | Valor                                                              |
|-----------------------------|---------------------------------------------------------------------|
| `GCP_SERVICE_ACCOUNT_JSON`  | El contenido **completo** de `service_account.json` (todo el JSON, tal cual) |
| `SPREADSHEET_ID`            | `160F053a-MKrFQAet7MA28FDU6i5cJCiucM6-9XYiZ_M` (o el ID de tu Sheet) |
| `GMAIL_ADDRESS`              | Tu cuenta de Gmail remitente                                        |
| `GMAIL_APP_PASSWORD`         | La contraseña de aplicación de 16 caracteres del paso 2              |

El workflow `.github/workflows/check_alerts.yml` corre cada hora en punto
(`cron: "0 * * * *"`, hora UTC) y revisa si algún lote activo está dentro
de la ventana de antelación configurada en la pestaña Configuración de la
app. Si es así, manda el correo y marca el lote para no repetir la
alerta. También puedes dispararlo manualmente desde la pestaña **Actions**
del repo (botón "Run workflow").

Para cambiar la frecuencia, edita la línea `cron` en ese archivo (por
ejemplo `"*/30 * * * *"` para cada 30 minutos).

## 7. Uso diario

- **Configuración**: agrega tus fermentadores, define el email y la
  antelación de las alertas, e inicia un lote nuevo eligiendo fermentador,
  tipo de cerveza, fecha/hora de inicio y duración de cada fase.
- **Monitoreo**: ve el % de avance de la fase actual de cada fermentador
  activo. Cuando termines la fermentación de verdad (por lectura de
  densidad, cata, etc.), confirma la transición a maduración con el botón
  correspondiente; cuando termines la maduración, confirma el cierre del
  lote y pasa automáticamente al Historial.
- **Historial**: consulta y filtra todos los lotes ya completados.

## Notas de seguridad

- `service_account.json` y `.streamlit/secrets.toml` están en
  `.gitignore` — nunca deben quedar en el repo público de GitHub.
- La contraseña de aplicación de Gmail solo sirve para SMTP, no da acceso
  completo a la cuenta; aun así, trátala como una contraseña real.
- Streamlit Community Cloud gratis publica la app en una URL pública. Si
  más adelante quieres protegerla con contraseña, se puede agregar
  fácilmente un campo de acceso simple.
