# TickerMeter Web (Railway)

Web de control para los displays E-Ink del TickerMeter.
La Pi consulta `/api/config` cada pocos minutos; nada de la red local queda expuesto.

## Archivos
- `app.py` — app Flask (web de control + API)
- `requirements.txt` — dependencias
- `Procfile` — comando de arranque (gunicorn)

## Deploy en Railway

1. Crear un nuevo proyecto en Railway y subir esta carpeta
   (o conectar un repo de GitHub con estos archivos).

2. En la pestaña **Variables**, agregar:
   - `TICKERMETER_TOKEN` = tu token secreto (largo y aleatorio)
   - `DATA_DIR` = `/data`

3. En **Settings → Volumes**, crear un volumen montado en `/data`.
   Ahi se guarda `config.json` de forma persistente.

4. Railway expone una URL publica (ej: `https://algo.up.railway.app`).

## Uso

- Web de control (en el navegador):
  `https://TU-URL.up.railway.app/?token=TU_TOKEN`

- API que consume la Pi:
  `https://TU-URL.up.railway.app/api/config?token=TU_TOKEN`

## Notas de seguridad
- El token viaja en la URL. No compartir el link en lugares publicos.
- Solo la Pi hace pedidos salientes; el cuadro nunca recibe conexiones.
