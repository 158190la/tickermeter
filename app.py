import os
import json
from flask import Flask, request, jsonify, redirect, abort

app = Flask(__name__)

# Token secreto desde variable de entorno (configurar en Railway)
TOKEN = os.environ.get("TICKERMETER_TOKEN", "cambiame")

# Ruta del archivo de config en el volumen persistente de Railway.
# El volumen se monta en /data (lo configuras en Railway).
DATA_DIR = os.environ.get("DATA_DIR", "/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "displays": [
        {"slot": "d1", "ticker": "SPY"},
        {"slot": "d2", "ticker": "MSFT"},
        {"slot": "d3", "ticker": "NVDA"},
        {"slot": "d4", "ticker": "QQQ"},
    ],
    "sparkline_dias": 60,
    "force_update": False,
}


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        # Si no existe todavia, devolver el default y crearlo
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def check_token():
    t = request.args.get("token", "")
    if t != TOKEN:
        abort(403)


# ---- API que consume la Pi ----
@app.route("/api/config")
def api_config():
    check_token()
    return jsonify(load_config())


@app.route("/api/ack", methods=["POST"])
def api_ack():
    # La Pi avisa que ya aplico el force_update -> lo bajamos a false
    check_token()
    cfg = load_config()
    cfg["force_update"] = False
    save_config(cfg)
    return jsonify({"ok": True})


# ---- Web de control ----
PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TickerMeter</title>
<style>
  body {{ font-family:-apple-system,Segoe UI,sans-serif; background:#0B2545;
         color:#fff; margin:0; padding:24px; }}
  h1 {{ color:#C9A84C; font-size:22px; text-align:center; margin-bottom:4px; }}
  .sub {{ text-align:center; color:#8aa; font-size:12px; margin-bottom:20px; }}
  .card {{ background:#13355f; border-radius:12px; padding:16px; margin:12px 0; }}
  label {{ display:block; font-size:13px; color:#C9A84C; margin-bottom:6px; }}
  input {{ width:100%; box-sizing:border-box; padding:12px; font-size:18px;
           border:none; border-radius:8px; text-transform:uppercase; }}
  .slot {{ font-size:12px; color:#8aa; margin-bottom:8px; }}
  .row {{ display:flex; gap:12px; }}
  .row .card {{ flex:1; }}
  button {{ width:100%; padding:16px; font-size:18px; font-weight:bold;
            background:#C9A84C; color:#0B2545; border:none; border-radius:10px;
            margin-top:16px; }}
  .global {{ background:#13355f; border-radius:12px; padding:16px; margin:12px 0; }}
</style>
</head>
<body>
<h1>TickerMeter</h1>
<div class="sub">Control de activos</div>
<form method="POST" action="/save?token={token}">
{cards}
<div class="global">
  <label>Dias del sparkline</label>
  <input name="sparkline_dias" value="{dias}" type="number" min="5" max="365">
</div>
<button type="submit">Actualizar ahora</button>
</form>
</body>
</html>"""

CARD = """<div class="card">
  <div class="slot">Display {n} ({slot})</div>
  <label>Ticker</label>
  <input name="ticker_{i}" value="{ticker}" maxlength="12" autocapitalize="characters" autocomplete="off">
</div>"""


@app.route("/")
def index():
    check_token()
    cfg = load_config()
    cards = ""
    for i, d in enumerate(cfg["displays"]):
        cards += CARD.format(n=i + 1, i=i, slot=d["slot"], ticker=d["ticker"])
    return PAGE.format(cards=cards, dias=cfg.get("sparkline_dias", 60), token=TOKEN)


@app.route("/save", methods=["POST"])
def save():
    check_token()
    cfg = load_config()
    for i, d in enumerate(cfg["displays"]):
        nuevo = request.form.get(f"ticker_{i}", "").strip().upper()
        if nuevo:
            d["ticker"] = nuevo
    try:
        dias = int(request.form.get("sparkline_dias", 60))
        cfg["sparkline_dias"] = max(5, min(365, dias))
    except ValueError:
        pass
    cfg["force_update"] = True
    save_config(cfg)
    return redirect(f"/?token={TOKEN}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
