# Ferment Plan 🍺

Webapp en Streamlit para planificar y monitorear ciclos de fermentación y
maduración de una cervecería.

> Nota: la idea original incluía alertas automáticas por email cuando un
> ciclo está por terminar. Por ahora esa parte se quitó para simplificar
> el proyecto y enfocarnos en que la app base funcione bien; se puede
> volver a agregar más adelante.

## Cómo funciona

- **Datos**: se guardan en un Google Sheet (hojas `Fermentadores` y
  `Lotes`), a las que la app accede con una cuenta de servicio de Google
  Cloud. Las hojas y sus encabezados se crean solas la primera vez que
  corre la app, así que no hace falta prepararlas a mano.
- **App (`app.py`)**: tiene 3 pestañas — Configuración (fermentadores,
  iniciar lotes), Monitoreo (% de avance de cada fermentador activo) e
  Historial (lotes completados).

## 1. Requisitos previos

- Una cuenta de servicio de Google Cloud con la API de Google Sheets (y
  Drive) habilitada — ya la tienes en `service_account.json` (este
  archivo **no se sube al repo**, está en `.gitignore`).
- El Google Sheet ya compartido con el email de esa cuenta de servicio
  (el campo `client_email` dentro del JSON) con permiso de **Editor**.

## 2. Probar localmente (opcional)

```bash
python -m venv .venv
.venv\Scripts\activate        # en Windows
pip install -r requirements.txt

copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# edita .streamlit\secrets.toml y pega ahí los datos de
# service_account.json dentro de [gcp_service_account]

streamlit run app.py
```

## 3. Subir el repo a GitHub

```bash
git init
git add .
git commit -m "Ferment Plan: app inicial"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/ferment_plan.git
git push -u origin main
```

⚠️ Antes de hacer el primer commit, confirma que `service_account.json` y
`.streamlit/secrets.toml` **no aparecen** en `git status` (deben estar
ignorados). Si por error alguno quedó rastreado, corre
`git rm --cached <archivo>` antes de commitear.

## 4. Desplegar en Streamlit Community Cloud

1. Ve a https://share.streamlit.io y conecta tu repo `ferment_plan`.
2. Archivo principal: `app.py`.
3. En **Settings -> Secrets** de la app en Streamlit Cloud, pega el mismo
   contenido que tienes en tu `.streamlit/secrets.toml` local (con tus
   valores reales).
4. Guarda y despliega. La primera vez que cargue, la app creará las hojas
   `Fermentadores` y `Lotes` dentro del Google Sheet si no existen
   todavía.

## 5. Uso diario

- **Configuración**: agrega tus fermentadores, e inicia un lote nuevo
  eligiendo fermentador, tipo de cerveza, fecha/hora de inicio y duración
  de cada fase.
- **Monitoreo**: ve el % de avance de la fase actual de cada fermentador
  activo. Cuando termines la fermentación de verdad (por lectura de
  densidad, cata, etc.), confirma la transición a maduración con el botón
  correspondiente; cuando termines la maduración, confirma el cierre del
  lote y pasa automáticamente al Historial.
- **Historial**: consulta y filtra todos los lotes ya completados.

## Notas de seguridad

- `service_account.json` y `.streamlit/secrets.toml` están en
  `.gitignore` — nunca deben quedar en el repo público de GitHub.
- Streamlit Community Cloud gratis publica la app en una URL pública. Si
  más adelante quieres protegerla con contraseña, se puede agregar
  fácilmente un campo de acceso simple.

## Alertas por email (pendiente)

Cuando quieras retomar esto, la idea es: agregar de nuevo un campo de
email y antelación en Configuración, y un script aparte corrido por
GitHub Actions con un horario (cron) que revise los lotes activos y
mande el correo cuando una fase esté por terminar — así funciona aunque
nadie tenga la app abierta. Avísame cuando quieras que lo agreguemos de
nuevo.
