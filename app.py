import os
import json
from flask import Flask, request, jsonify, redirect, abort
import yfinance as yf
import urllib.request
import time as _time

app = Flask(__name__)

# Token secreto desde variable de entorno (configurar en Railway)
TOKEN = os.environ.get("TICKERMETER_TOKEN", "cambiame")

# Ruta del archivo de config en el volumen persistente de Railway.
# El volumen se monta en /data (lo configuras en Railway).
DATA_DIR = os.environ.get("DATA_DIR", "/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "displays": [
        {"slot": "d1", "tipo": "indices", "titulo": "INDICES",
         "items": [
             {"label": "SP500", "symbol": "^GSPC"},
             {"label": "FTSE", "symbol": "^FTSE"},
             {"label": "DAX", "symbol": "^GDAXI"},
             {"label": "NIKKEI", "symbol": "^N225"},
             {"label": "HANGSE", "symbol": "^HSI"},
             {"label": "MERVAL", "symbol": "^MERV"},
         ]},
        {"slot": "d2", "ticker": "MSFT"},
        {"slot": "d3", "ticker": "", "tipo": "treasury",
         "plazos": ["1Y", "3Y", "5Y", "7Y", "10Y"]},
        {"slot": "d4", "tipo": "monedas", "titulo": "MONEDAS",
         "items": [
             {"label": "EUR/USD", "symbol": "EURUSD=X"},
             {"label": "USD/JPY", "symbol": "JPY=X"},
             {"label": "GBP/USD", "symbol": "GBPUSD=X"},
             {"label": "USD/ARS", "symbol": "ARS=X"},
             {"label": "BTC", "symbol": "BTC-USD"},
         ]},
    ],
    "sparkline_dias": 60,
    "force_update": False,
}

# Plazos validos de Treasury Constant Maturity en FRED, en orden
PLAZOS_VALIDOS = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]

# Catalogo de indices mundiales (etiqueta -> simbolo Yahoo)
CAT_INDICES = [
    ("SP500", "^GSPC"), ("NASDAQ", "^IXIC"), ("DOWJONES", "^DJI"),
    ("FTSE", "^FTSE"), ("DAX", "^GDAXI"), ("CAC40", "^FCHI"),
    ("IBEX35", "^IBEX"), ("NIKKEI", "^N225"), ("HANGSENG", "^HSI"),
    ("SHANGHAI", "000001.SS"), ("SENSEX", "^BSESN"), ("BOVESPA", "^BVSP"),
    ("MERVAL", "^MERV"), ("SP/TSX", "^GSPTSE"), ("ASX200", "^AXJO"),
]

# Catalogo de monedas y cripto (etiqueta -> simbolo Yahoo)
CAT_MONEDAS = [
    ("EUR/USD", "EURUSD=X"), ("USD/JPY", "JPY=X"), ("GBP/USD", "GBPUSD=X"),
    ("USD/CHF", "CHF=X"), ("USD/ARS", "ARS=X"), ("USD/BRL", "BRL=X"),
    ("USD/MXN", "MXN=X"), ("USD/CLP", "CLP=X"), ("DXY", "DX-Y.NYB"),
    ("BTC", "BTC-USD"), ("ETH", "ETH-USD"), ("ORO", "GC=F"),
    ("PLATA", "SI=F"), ("PETROLEO", "CL=F"),
]

CATALOGOS = {"indices": CAT_INDICES, "monedas": CAT_MONEDAS}

FRED_KEY = os.environ.get("FRED_KEY", "")
FRED_MAP = {
    "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO", "1Y": "DGS1", "2Y": "DGS2",
    "3Y": "DGS3", "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10",
    "20Y": "DGS20", "30Y": "DGS30",
}

def fetch_ticker(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d")
        closes = [c for c in hist["Close"].tolist() if c == c]
        if len(closes) >= 2:
            return closes[-1], ((closes[-1]-closes[-2])/closes[-2])*100
        if len(closes) == 1:
            return closes[-1], 0.0
    except Exception:
        pass
    return None, None

def fetch_name(symbol):
    try:
        return yf.Ticker(symbol).info.get("shortName", "") or ""
    except Exception:
        return ""

def fetch_treasury(plazos):
    rows = []
    for etiqueta in plazos:
        serie = FRED_MAP.get(etiqueta)
        if not serie:
            continue
        try:
            url = ("https://api.stlouisfed.org/fred/series/observations"
                   f"?series_id={serie}&api_key={FRED_KEY}&file_type=json"
                   "&sort_order=desc&limit=2")
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
            vals = [o["value"] for o in data.get("observations", []) if o["value"] != "."]
            if len(vals) >= 2:
                rows.append({"label": etiqueta, "val": float(vals[0]),
                             "chg": float(vals[0])-float(vals[1])})
            elif len(vals) == 1:
                rows.append({"label": etiqueta, "val": float(vals[0]), "chg": 0.0})
            else:
                rows.append({"label": etiqueta, "val": None, "chg": None})
        except Exception:
            rows.append({"label": etiqueta, "val": None, "chg": None})
        _time.sleep(0.4)
    return rows



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


@app.route("/api/reset")
def api_reset():
    check_token()
    save_config(dict(DEFAULT_CONFIG))
    return jsonify({"ok": True, "config": DEFAULT_CONFIG})


@app.route("/api/preview")
def api_preview():
    check_token()
    cfg = load_config()
    out = []
    for d in cfg["displays"]:
        tipo = d.get("tipo", "ticker")
        item = {"slot": d["slot"], "tipo": tipo}
        if tipo == "treasury":
            item["titulo"] = "US TREASURY YIELDS"
            item["rows"] = fetch_treasury(d.get("plazos", []))
        elif tipo in ("indices", "monedas"):
            item["titulo"] = d.get("titulo", tipo.upper())
            rows = []
            for it in d.get("items", []):
                val, chg = fetch_ticker(it["symbol"])
                rows.append({"label": it.get("label", it["symbol"]),
                             "val": val, "chg": chg})
            item["rows"] = rows
        else:
            ticker = d.get("ticker", "")
            val, chg = fetch_ticker(ticker)
            item["ticker"] = ticker
            item["name"] = fetch_name(ticker)
            item["val"] = val
            item["chg"] = chg
        out.append(item)
    return jsonify({"displays": out, "sparkline_dias": cfg.get("sparkline_dias", 60)})


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
  .preview-wrap {{ margin:16px 0 24px; }}
  .preview-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  .eink {{ background:#e8e8e0; color:#111; border:2px solid #444; border-radius:6px;
           aspect-ratio:250/122; padding:0; overflow:hidden; position:relative;
           font-family:"DejaVu Sans Mono",monospace; }}
  .eink .hdr {{ background:#111; color:#e8e8e0; font-weight:bold; font-size:11px;
                padding:3px 6px; display:flex; justify-content:space-between; }}
  .eink .big {{ font-size:26px; font-weight:bold; padding:2px 6px; }}
  .eink .band {{ background:#111; color:#e8e8e0; font-size:13px; font-weight:bold;
                 padding:2px 6px; display:flex; justify-content:space-between; }}
  .eink .row {{ display:flex; justify-content:space-between; font-size:12px;
                padding:1px 6px; }}
  .eink .lbl {{ font-weight:bold; }}
  .tri-up::before {{ content:"\\25B2"; font-size:9px; }}
  .tri-dn::before {{ content:"\\25BC"; font-size:9px; }}
  .reload {{ width:100%; padding:12px; font-size:15px; background:#13355f;
             color:#C9A84C; border:1px solid #C9A84C; border-radius:8px; margin-top:8px; }}

</style>
</head>
<body>
<h1>TickerMeter</h1>
<div class="sub">Control de activos</div>
<div class="preview-wrap">
  <div id="preview" class="preview-grid"></div>
  <button type="button" class="reload" onclick="cargarPreview()">Recargar vista en vivo</button>
</div>
<script>
const TK = "{token}";
let SPARK_DIAS = 60;
function tri(chg) {{
  if (chg === null || chg === undefined) return "";
  return chg >= 0 ? "<span class='tri-up'></span>" : "<span class='tri-dn'></span>";
}}
function fmtVal(v) {{
  if (v === null || v === undefined) return "N/A";
  if (v >= 1000) return v.toLocaleString("en-US", {{maximumFractionDigits:0}});
  if (v >= 10) return v.toFixed(2);
  return v.toFixed(4);
}}
function cargarPreview() {{
  const cont = document.getElementById("preview");
  cont.innerHTML = "<div style='grid-column:1/3;text-align:center;color:#8aa'>Cargando datos en vivo...</div>";
  fetch("/api/preview?token=" + TK).then(r => r.json()).then(data => {{
    window.SPARK_DIAS = data.sparkline_dias || 60;
    cont.innerHTML = "";
    data.displays.forEach(d => {{
      let html = "<div class='eink'>";
      if (d.tipo === "ticker") {{
        const chgTxt = (d.chg===null) ? "N/A" : (Math.abs(d.chg).toFixed(2)+"%");
        html += "<div class='hdr'><span>"+(d.ticker||"")+"</span><span>"+(d.name||"")+"</span></div>";
        html += "<div class='big'>$"+fmtVal(d.val)+"</div>";
        html += "<div class='band'><span>"+tri(d.chg)+" "+chgTxt+"</span><span>"+SPARK_DIAS+"d</span></div>";
      }} else {{
        html += "<div class='hdr'><span>"+d.titulo+"</span></div>";
        (d.rows||[]).forEach(rw => {{
          const v = (d.tipo==="treasury") ? (rw.val===null?"N/A":rw.val.toFixed(2)+"%") : ("$"+fmtVal(rw.val));
          const c = (rw.chg===null) ? "" : (tri(rw.chg)+" "+Math.abs(rw.chg).toFixed(2));
          html += "<div class='row'><span class='lbl'>"+rw.label+"</span><span>"+v+"</span><span>"+c+"</span></div>";
        }});
      }}
      html += "</div>";
      cont.innerHTML += html;
    }});
  }}).catch(e => {{
    cont.innerHTML = "<div style='grid-column:1/3;color:#e88'>Error cargando: "+e+"</div>";
  }});
}}
window.addEventListener("load", cargarPreview);
</script>
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

INFO_CARD = """<div class="card">
  <div class="slot">Display {n} ({slot})</div>
  <label>{titulo} &mdash; eleg&iacute; hasta ~9</label>
  <div class="plazos">{checks}</div>
</div>"""

ITEM_CHK = """<label class="chk"><input type="checkbox" name="item_{slot}" value="{sym}" {checked}> {label}</label>"""


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
        elif d.get("tipo") in ("indices", "monedas"):
            tipo = d["tipo"]
            simbolos_activos = [it.get("symbol") for it in d.get("items", [])]
            checks = ""
            for label, sym in CATALOGOS[tipo]:
                marcado = "checked" if sym in simbolos_activos else ""
                checks += ITEM_CHK.format(slot=d["slot"], sym=sym, label=label, checked=marcado)
            cards += INFO_CARD.format(n=i + 1, slot=d["slot"],
                                      titulo=d.get("titulo", tipo.upper()),
                                      checks=checks)
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
        if d.get("tipo") in ("indices", "monedas"):
            tipo = d["tipo"]
            elegidos = request.form.getlist(f"item_{d['slot']}")
            # Reconstruir items con label+symbol, en el orden del catalogo
            d["items"] = [
                {"label": label, "symbol": sym}
                for label, sym in CATALOGOS[tipo]
                if sym in elegidos
            ]
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
