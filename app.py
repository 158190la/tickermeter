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
        {"slot": "d3", "ticker": "", "tipo": "treasury",
         "plazos": ["1Y", "3Y", "5Y", "7Y", "10Y"]},
        {"slot": "d4", "ticker": "QQQ"},
    ],
    "sparkline_dias": 60,
    "force_update": False,
}

# Plazos validos de Treasury Constant Maturity en FRED, en orden
PLAZOS_VALIDOS = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]


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
  .plazos {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:8px; }}
  .chk {{ display:flex; align-items:center; gap:6px; font-size:16px; color:#fff;
          background:#0B2545; padding:8px 12px; border-radius:8px; cursor:pointer; }}
  .chk input {{ width:auto; }}
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

TREASURY_CARD = """<div class="card">
  <div class="slot">Display {n} ({slot})</div>
  <label>US Treasury Yields &mdash; eleg&iacute; los plazos</label>
  <div class="plazos">{checks}</div>
</div>"""

PLAZO_CHK = """<label class="chk"><input type="checkbox" name="plazo_{slot}" value="{plazo}" {checked}> {plazo}</label>"""


@app.route("/")
def index():
    check_token()
    cfg = load_config()
    cards = ""
    for i, d in enumerate(cfg["displays"]):
        if d.get("tipo") == "treasury":
            activos = d.get("plazos", [])
            checks = ""
            for plazo in PLAZOS_VALIDOS:
                marcado = "checked" if plazo in activos else ""
                checks += PLAZO_CHK.format(slot=d["slot"], plazo=plazo, checked=marcado)
            cards += TREASURY_CARD.format(n=i + 1, slot=d["slot"], checks=checks)
        else:
            cards += CARD.format(n=i + 1, i=i, slot=d["slot"], ticker=d["ticker"])
    return PAGE.format(cards=cards, dias=cfg.get("sparkline_dias", 60), token=TOKEN)


@app.route("/save", methods=["POST"])
def save():
    check_token()
    cfg = load_config()
    for i, d in enumerate(cfg["displays"]):
        if d.get("tipo") == "treasury":
            elegidos = request.form.getlist(f"plazo_{d['slot']}")
            # Guardar en el orden de PLAZOS_VALIDOS, no en el orden del form
            d["plazos"] = [p for p in PLAZOS_VALIDOS if p in elegidos]
            continue
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
