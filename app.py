import json
import os
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

st.set_page_config(page_title="APEX AI BOT", page_icon="💎", layout="wide")


def get_secret(name, default=""):
    try:
        return st.secrets[name]
    except Exception:
        return default


# =====================================================================
# ACCESS CONTROL (owner = permanent, sub passwords = N days from first use)
# NOTE: on Streamlit Cloud the JSON file resets on reboot/redeploy.
# =====================================================================
OWNER_PASS = get_secret("OWNER_PASS", "apex123")
ACCESS_FILE = "apex_access.json"


def load_access():
    if os.path.exists(ACCESS_FILE):
        try:
            with open(ACCESS_FILE, "r") as f:
                d = json.load(f)
                d.setdefault("users", {})
                return d
        except Exception:
            pass
    return {"users": {}}


def save_access(data):
    with open(ACCESS_FILE, "w") as f:
        json.dump(data, f)


def sub_status(u):
    start, days = u.get("start_time"), u.get("duration_days", 7)
    if start is None:
        return True, f"Not started ({days}d)"
    left = days * 86400 - (time.time() - start)
    return (left > 0), (f"{left / 86400:.1f} days left" if left > 0 else "Expired")


def check_user_access(pass_key):
    if pass_key == OWNER_PASS:
        return True, "owner", "Owner access"
    data = load_access()
    u = data["users"].get(pass_key)
    if u:
        if u.get("start_time") is None:
            u["start_time"] = time.time()
            save_access(data)
        ok, txt = sub_status(u)
        return (True, "sub", txt) if ok else (False, None, "⛔ Password expired!")
    return False, None, "❌ Invalid password!"


# =====================================================================
# GLOBAL CSS (3D / glass)
# =====================================================================
st.markdown(
    """
<style>
.stApp { background: radial-gradient(circle at 15% 0%, #16264a 0%, #0b0f1a 45%, #05070d 100%); }
h1,h2,h3 { letter-spacing:.5px; }
.stButton>button { background:linear-gradient(135deg,#00b4ff,#7c4dff); color:#fff; border:0; border-radius:12px;
  font-weight:700; box-shadow:0 6px 18px #7c4dff44; transition:all .2s; }
.stButton>button:hover { transform:translateY(-2px) scale(1.02); box-shadow:0 10px 26px #00e5ff55; color:#fff; }
button[data-baseweb="tab"] { font-weight:700; }
iframe { border-radius:16px; }
div[data-testid="stMetric"] { background:linear-gradient(145deg,#141b2e,#0c1120); border:1px solid #26324f;
  border-radius:16px; padding:12px 16px; box-shadow:0 8px 20px #00000066; }

.loader-wrap { display:flex; flex-direction:column; align-items:center; padding:26px 0; }
.ring { position:relative; width:104px; height:104px; }
.ring div { position:absolute; inset:0; border-radius:50%; border:4px solid transparent; }
.ring div:nth-child(1){ border-top-color:#00e5ff; animation:spin 1.1s linear infinite; }
.ring div:nth-child(2){ inset:12px; border-right-color:#ffd700; animation:spin 1.6s linear infinite reverse; }
.ring div:nth-child(3){ inset:24px; border-bottom-color:#ff3d71; animation:spin .9s linear infinite; }
.ring span { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:28px;
  animation:pulse 1.4s ease-in-out infinite; }
.loader-text { margin-top:14px; color:#cfe8ff; font-weight:600; letter-spacing:1px; }
.loader-bar { width:320px; height:8px; background:#1b2338; border-radius:20px; margin-top:12px; overflow:hidden; }
.loader-bar i { display:block; height:100%; background:linear-gradient(90deg,#00e5ff,#7c4dff,#ffd700);
  background-size:200% 100%; animation:slide 1.2s linear infinite; border-radius:20px; transition:width .2s; }
@keyframes spin { to { transform:rotate(360deg);} }
@keyframes pulse { 0%,100%{transform:scale(1);} 50%{transform:scale(1.25);} }
@keyframes slide { to { background-position:-200% 0; } }
@keyframes floaty { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-8px);} }
@keyframes glow { 0%,100%{box-shadow:0 0 18px #00e5ff55;} 50%{box-shadow:0 0 38px #7c4dffaa;} }

.login-card { max-width:460px; margin:40px auto 10px auto; padding:34px; border-radius:22px; text-align:center;
  background:linear-gradient(145deg,#141b2e,#0c1120); border:1px solid #26324f;
  animation:floaty 4s ease-in-out infinite, glow 3s ease-in-out infinite; }
.login-card h1 { margin:0; font-size:34px; background:linear-gradient(90deg,#00e5ff,#ffd700);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.login-card p { color:#8fa3c7; margin-top:6px; }

.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(285px,1fr)); gap:18px; perspective:900px; }
.tcard { background:linear-gradient(145deg,#161e33,#0d1324); border:1px solid #26324f; border-radius:18px;
  padding:16px 18px; transition:transform .25s, box-shadow .25s; box-shadow:0 10px 24px #00000066, inset 0 1px 0 #ffffff12; }
.tcard:hover { transform:rotateX(4deg) rotateY(-4deg) translateY(-6px) scale(1.02); box-shadow:0 22px 40px #000000aa, 0 0 22px #00e5ff33; }
.tcard.long { border-left:5px solid #00e676; } .tcard.short { border-left:5px solid #ff3d71; }
.tcard.big { padding:22px 24px; }
.thead { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.tname { font-size:20px; font-weight:800; color:#fff; }
.badge { font-size:11px; font-weight:800; padding:4px 10px; border-radius:20px; letter-spacing:.4px; white-space:nowrap; }
.b-long { background:#00e67622; color:#00e676; border:1px solid #00e67666; }
.b-short { background:#ff3d7122; color:#ff3d71; border:1px solid #ff3d7166; }
.b-watch { background:#ffd70018; color:#ffd700; border:1px solid #ffd70055; }
.b-none { background:#8fa3c718; color:#8fa3c7; border:1px solid #8fa3c755; }
.scorewrap { display:flex; align-items:center; gap:10px; margin-top:10px; }
.scorebar { flex:1; height:8px; background:#1b2338; border-radius:10px; overflow:hidden; }
.scorebar i { display:block; height:100%; background:linear-gradient(90deg,#ff3d71,#ffd700,#00e676); }
.grade { font-weight:800; color:#ffd700; font-size:13px; }
.row { display:flex; justify-content:space-between; margin-top:8px; font-size:14px; }
.lbl { color:#8fa3c7; } .v-entry { color:#00e5ff; font-weight:700; } .v-tp { color:#00e676; font-weight:700; }
.v-sl { color:#ff3d71; font-weight:700; }
.meta { margin-top:10px; padding-top:8px; border-top:1px dashed #26324f; font-size:12px; color:#7d8fb3; }
.alertbox { background:linear-gradient(145deg,#1a2238,#0f1526); border:1px solid #2c3a5e; border-left:4px solid #ffd700;
  border-radius:12px; padding:10px 14px; margin-bottom:8px; font-size:14px; color:#e6eeff; }
.alertbox small { color:#8fa3c7; }
</style>
""",
    unsafe_allow_html=True,
)


def loader_html(text, pct=None, icon="💎"):
    w = 100 if pct is None else int(pct * 100)
    return (
        f'<div class="loader-wrap"><div class="ring"><div></div><div></div><div></div><span>{icon}</span></div>'
        f'<div class="loader-text">{text}</div><div class="loader-bar"><i style="width:{w}%"></i></div></div>'
    )


# =====================================================================
# LOGIN
# =====================================================================
if "role" not in st.session_state:
    st.session_state["role"] = None
    st.session_state["user_pass"] = None

if st.session_state["role"] is None:
    st.markdown(
        '<div class="login-card"><h1>💎 APEX AI BOT</h1>'
        "<p>SMC · ICT · Elliott Wave · Smart Money Terminal</p></div>",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        pw = st.text_input("🔑 Enter Access Password", type="password", key="login_pw")
        if st.button("🚀 Unlock Terminal", use_container_width=True):
            ok, role, msg = check_user_access(pw)
            if ok:
                ph = st.empty()
                for p in range(0, 101, 20):
                    ph.markdown(loader_html("Verifying access...", p / 100, "🔓"), unsafe_allow_html=True)
                    time.sleep(0.1)
                ph.empty()
                st.session_state["role"], st.session_state["user_pass"] = role, pw
                st.rerun()
            else:
                st.error(msg)
    st.stop()

if st.session_state["role"] == "sub":
    ok, _, msg = check_user_access(st.session_state["user_pass"])
    if not ok:
        st.session_state["role"] = None
        st.session_state["user_pass"] = None
        st.warning(msg)
        st.stop()

# =====================================================================
# HEADER + SIDEBAR
# =====================================================================
st.title("💎 APEX AI BOT")
st.caption("SMC · ICT · Elliott Wave | Top 100 Scanner | Real-Time Funding | Smart Alerts")

st.sidebar.markdown(f"**Logged in as:** `{st.session_state['role'].upper()}`")

if st.session_state["role"] == "sub":
    _u = load_access()["users"].get(st.session_state["user_pass"], {})
    st.sidebar.info(f"⏳ {sub_status(_u)[1]}")

if st.session_state["role"] == "owner":
    with st.sidebar.expander("👑 Owner Panel — Sub Passwords"):
        note = st.text_input("Client name / note", "User 1", key="own_note")
        days = st.number_input("Valid days", 1, 90, 7, key="own_days")
        if st.button("🔑 Generate New Password", key="own_gen"):
            key = "sub_" + secrets.token_hex(4)
            data = load_access()
            data["users"][key] = {"note": note, "start_time": None, "duration_days": int(days)}
            save_access(data)
            st.success(f"New password: `{key}`")
        users = load_access()["users"]
        if users:
            st.dataframe(
                pd.DataFrame(
                    [{"Password": k, "Client": u.get("note", ""), "Status": sub_status(u)[1]} for k, u in users.items()]
                ),
                use_container_width=True,
                height=160,
            )
            rev = st.selectbox("Revoke password", ["—"] + list(users.keys()), key="own_rev")
            if st.button("🗑 Revoke", key="own_revbtn") and rev != "—":
                d = load_access()
                d["users"].pop(rev, None)
                save_access(d)
                st.rerun()

if st.sidebar.button("🚪 Logout"):
    st.session_state["role"] = None
    st.session_state["user_pass"] = None
    st.rerun()

st.sidebar.header("⚙️ Strategy Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1)
risk_reward = st.sidebar.slider("Risk-to-Reward (TP2)", 1.0, 5.0, 2.5, 0.5)
sl_mult = st.sidebar.slider("Fallback SL (ATR multiplier)", 1.0, 3.0, 1.5, 0.1)
tv_exchange = st.sidebar.selectbox("TradingView Live exchange", ["BINANCE", "BYBIT", "MEXC", "OKX"])

st.sidebar.header("🔔 Alerts")
alert_min = st.sidebar.slider("Alert when score ≥", 40, 95, 65, 5)
auto_scan = st.sidebar.checkbox("Auto-scan Top 100", value=False)
auto_min = st.sidebar.slider("Auto-scan every (min)", 1, 30, 5) if auto_scan else 5
tg_token = st.sidebar.text_input("Telegram Bot Token", type="password", value=get_secret("TG_TOKEN", ""))
tg_chat = st.sidebar.text_input("Telegram Chat ID", value=get_secret("TG_CHAT", ""))


def send_telegram(token, chat_id, text):
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=6,
        )
        return r.ok
    except Exception:
        return False


if st.sidebar.button("📨 Send Telegram test"):
    ok = send_telegram(tg_token, tg_chat, "✅ APEX AI BOT: Telegram notifications are working.")
    st.sidebar.success("Sent!") if ok else st.sidebar.error("Failed — check token / chat id")

# =====================================================================
# DATA LAYER  (multi-source fallback: works from US-hosted Streamlit Cloud)
# =====================================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def _get(url, params=None, timeout=8):
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


TFM = {
    "15m": dict(binance="15m", okx="15m", kucoin="15min", bybit="15", gate="15m", mexc="15m"),
    "1h": dict(binance="1h", okx="1H", kucoin="1hour", bybit="60", gate="1h", mexc="60m"),
    "4h": dict(binance="4h", okx="4H", kucoin="4hour", bybit="240", gate="4h", mexc="4h"),
    "1d": dict(binance="1d", okx="1D", kucoin="1day", bybit="D", gate="1d", mexc="1d"),
}


def _mk(rows):
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna().sort_values("time").drop_duplicates("time").reset_index(drop=True)


def _src_binance_like(host, key):
    def f(b, tf, lim):
        d = _get(f"{host}/api/v3/klines", {"symbol": b + "USDT", "interval": TFM[tf][key], "limit": lim})
        return _mk([[x[0] / 1000, x[1], x[2], x[3], x[4], x[5]] for x in d])
    return f


def _src_okx(b, tf, lim):
    d = _get("https://www.okx.com/api/v5/market/candles",
             {"instId": f"{b}-USDT", "bar": TFM[tf]["okx"], "limit": min(lim, 300)})
    return _mk([[int(x[0]) / 1000, x[1], x[2], x[3], x[4], x[5]] for x in d["data"]])


def _src_kucoin(b, tf, lim):
    d = _get("https://api.kucoin.com/api/v1/market/candles", {"symbol": f"{b}-USDT", "type": TFM[tf]["kucoin"]})
    return _mk([[x[0], x[1], x[3], x[4], x[2], x[5]] for x in d["data"]][:lim])


def _src_gate(b, tf, lim):
    d = _get("https://api.gateio.ws/api/v4/spot/candlesticks",
             {"currency_pair": f"{b}_USDT", "interval": TFM[tf]["gate"], "limit": lim})
    return _mk([[x[0], x[5], x[3], x[4], x[2], x[6]] for x in d])


def _src_bybit(b, tf, lim):
    d = _get("https://api.bybit.com/v5/market/kline",
             {"category": "spot", "symbol": b + "USDT", "interval": TFM[tf]["bybit"], "limit": lim})
    return _mk([[int(x[0]) / 1000, x[1], x[2], x[3], x[4], x[5]] for x in d["result"]["list"]])


SOURCES = [
    ("Binance", _src_binance_like("https://data-api.binance.vision", "binance")),
    ("Binance.com", _src_binance_like("https://api.binance.com", "binance")),
    ("OKX", _src_okx),
    ("KuCoin", _src_kucoin),
    ("Gate.io", _src_gate),
    ("Bybit", _src_bybit),
    ("MEXC", _src_binance_like("https://api.mexc.com", "mexc")),
]
_KC, _KC_LOCK, _PREF = {}, threading.Lock(), {"i": 0}


def fetch_klines(base, tf, lim=300, ttl=45):
    key, now = (base, tf, lim), time.time()
    with _KC_LOCK:
        hit = _KC.get(key)
        if len(_KC) > 600:
            _KC.clear()
    if hit and now - hit[0] < ttl:
        return hit[1], hit[2], None
    order = [_PREF["i"]] + [i for i in range(len(SOURCES)) if i != _PREF["i"]]
    errs = []
    for i in order:
        name, fn = SOURCES[i]
        try:
            df = fn(base, tf, lim)
            if df is not None and len(df) >= 60:
                _PREF["i"] = i
                with _KC_LOCK:
                    _KC[key] = (now, df, name)
                return df, name, None
            errs.append(f"{name}: no data")
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}")
    return None, None, " | ".join(errs)


def _alias(out, base, val):
    out.setdefault(base, val)
    short = re.sub(r"^(1000000|10000|1000|1M)", "", base)
    if short and short != base:
        out.setdefault(short, val)


@st.cache_data(ttl=60, show_spinner=False)
def get_all_funding():
    out, ok_src = {}, []

    def run(name, fn):
        try:
            fn()
            ok_src.append(name)
        except Exception:
            pass

    def binance():
        for x in _get("https://fapi.binance.com/fapi/v1/premiumIndex"):
            s = x["symbol"]
            if s.endswith("USDT") and x.get("lastFundingRate") not in (None, ""):
                _alias(out, s[:-4], float(x["lastFundingRate"]) * 100)

    def bybit():
        for x in _get("https://api.bybit.com/v5/market/tickers", {"category": "linear"})["result"]["list"]:
            s = x["symbol"]
            if s.endswith("USDT") and x.get("fundingRate") not in (None, ""):
                _alias(out, s[:-4], float(x["fundingRate"]) * 100)

    def gate():
        for x in _get("https://api.gateio.ws/api/v4/futures/usdt/tickers"):
            c = x.get("contract", "")
            if c.endswith("_USDT") and x.get("funding_rate") not in (None, ""):
                _alias(out, c[:-5], float(x["funding_rate"]) * 100)

    def bitget():
        for x in _get("https://api.bitget.com/api/v2/mix/market/tickers", {"productType": "USDT-FUTURES"})["data"]:
            s = x["symbol"]
            if s.endswith("USDT") and x.get("fundingRate") not in (None, ""):
                _alias(out, s[:-4], float(x["fundingRate"]) * 100)

    for n, f in [("Binance", binance), ("Bybit", bybit), ("Gate.io", gate), ("Bitget", bitget)]:
        run(n, f)
    return out, ok_src


EXCLUDE = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "USDS", "BUSD", "PYUSD", "USDD", "USD1", "USDG", "RLUSD",
           "WBTC", "STETH", "WSTETH", "WEETH", "WETH", "WBETH", "CBBTC", "SUSDE", "USDTB", "BUIDL", "XAUT", "PAXG",
           "BSC-USD", "SUSDS", "USDC.E", "WBNB", "WTRX", "LBTC", "SOLVBTC"}


@st.cache_data(ttl=300, show_spinner=False)
def get_top100():
    try:
        d = _get("https://api.coingecko.com/api/v3/coins/markets",
                 {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 130, "page": 1,
                  "sparkline": "false"}, timeout=12)
        rows = []
        for i, c in enumerate(d):
            b = c["symbol"].upper()
            if b in EXCLUDE:
                continue
            rows.append(dict(Rank=c.get("market_cap_rank") or i + 1, Name=c["name"], Coin=b,
                             Price=c.get("current_price"), Chg24=c.get("price_change_percentage_24h") or 0.0,
                             MCap=c.get("market_cap") or 0, Vol=c.get("total_volume") or 0))
        if len(rows) >= 50:
            return pd.DataFrame(rows[:100]), "CoinGecko (market cap)"
    except Exception:
        pass
    try:  # fallback: top pairs by volume
        d = _get("https://data-api.binance.vision/api/v3/ticker/24hr")
        d = [x for x in d if x["symbol"].endswith("USDT") and not re.search(r"(UP|DOWN|BULL|BEAR)USDT$", x["symbol"])]
        d.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
        rows = []
        for x in d:
            b = x["symbol"][:-4]
            if b in EXCLUDE:
                continue
            rows.append(dict(Rank=len(rows) + 1, Name=b, Coin=b, Price=float(x["lastPrice"]),
                             Chg24=float(x["priceChangePercent"]), MCap=0, Vol=float(x["quoteVolume"])))
            if len(rows) >= 100:
                break
        return pd.DataFrame(rows), "Binance (by volume)"
    except Exception:
        return pd.DataFrame(), "unavailable"


def fp(x):
    x = float(x)
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:,.4f}"
    if abs(x) >= 0.01:
        return f"{x:.6f}"
    return f"{x:.8f}"


# ==== ANALYSIS ENGINE START ====
def calc_atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def find_swings(df, left=3, right=3):
    h, l = df["high"].values, df["low"].values
    sh, sl = [], []
    for i in range(left, len(df) - right):
        if h[i] > h[i - left:i].max() and h[i] >= h[i + 1:i + right + 1].max():
            sh.append((i, float(h[i])))
        if l[i] < l[i - left:i].min() and l[i] <= l[i + 1:i + right + 1].min():
            sl.append((i, float(l[i])))
    return sh, sl


def market_structure(df, sh, sl, right):
    shc = {i + right: (i, p) for i, p in sh}
    slc = {i + right: (i, p) for i, p in sl}
    last_h = last_l = None
    trend, events = 0, []
    c = df["close"].values
    for i in range(len(df)):
        if i in shc:
            last_h = shc[i]
        if i in slc:
            last_l = slc[i]
        if last_h and c[i] > last_h[1]:
            events.append(dict(type="CHoCH" if trend == -1 else "BOS", dir="BULL", level=last_h[1],
                               frm=last_h[0], at=i))
            trend, last_h = 1, None
        elif last_l and c[i] < last_l[1]:
            events.append(dict(type="CHoCH" if trend == 1 else "BOS", dir="BEAR", level=last_l[1],
                               frm=last_l[0], at=i))
            trend, last_l = -1, None
    return trend, events


def find_order_blocks(df, events, a):
    o, c, h, l = (df[k].values for k in ("open", "close", "high", "low"))
    n, obs = len(df), []
    for ev in events[-8:]:
        f, at = ev["frm"], ev["at"]
        if at <= f:
            continue
        if ev["dir"] == "BULL":
            j = f + int(np.argmin(l[f:at + 1]))
            if c[at] - l[j] < 0.8 * a:
                continue
            k = next((q for q in range(j, max(j - 4, -1), -1) if c[q] < o[q]), None)
            if k is None:
                continue
            mit = bool((c[at + 1:] < l[k]).any()) if at + 1 < n else False
            if not mit:
                obs.append(dict(dir="BULL", idx=k, top=float(h[k]), bottom=float(l[k]), kind=ev["type"]))
        else:
            j = f + int(np.argmax(h[f:at + 1]))
            if h[j] - c[at] < 0.8 * a:
                continue
            k = next((q for q in range(j, max(j - 4, -1), -1) if c[q] > o[q]), None)
            if k is None:
                continue
            mit = bool((c[at + 1:] > h[k]).any()) if at + 1 < n else False
            if not mit:
                obs.append(dict(dir="BEAR", idx=k, top=float(h[k]), bottom=float(l[k]), kind=ev["type"]))
    out = []
    for d in ("BULL", "BEAR"):
        out += [x for x in obs if x["dir"] == d][-3:]
    return out


def find_fvgs(df, a, lookback=150):
    h, l, n, out = df["high"].values, df["low"].values, len(df), []
    for i in range(max(2, n - lookback), n):
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) > 0.15 * a:
            bot = float(h[i - 2])
            if not (i + 1 < n and (l[i + 1:] <= bot).any()):
                out.append(dict(dir="BULL", idx=i - 1, top=float(l[i]), bottom=bot))
        elif h[i] < l[i - 2] and (l[i - 2] - h[i]) > 0.15 * a:
            top = float(l[i - 2])
            if not (i + 1 < n and (h[i + 1:] >= top).any()):
                out.append(dict(dir="BEAR", idx=i - 1, top=top, bottom=float(h[i])))
    res = []
    for d in ("BULL", "BEAR"):
        res += [x for x in out if x["dir"] == d][-3:]
    return res


def liquidity_levels(df, sh, sl, a, price):
    h, l = df["high"].values, df["low"].values
    uh = [(i, p) for i, p in sh if not (h[i + 1:] > p).any()]
    ul = [(i, p) for i, p in sl if not (l[i + 1:] < p).any()]
    tol = 0.12 * a

    def eq(lst):
        res = []
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                if abs(lst[x][1] - lst[y][1]) <= tol:
                    res.append(max(lst[x][1], lst[y][1]))
        return sorted(set(res))[-3:]

    above = [p for _, p in uh if p > price]
    below = [p for _, p in ul if p < price]
    return dict(bsl=min(above) if above else None, ssl=max(below) if below else None,
                eqh=eq(uh[-8:]), eql=eq(ul[-8:]))


def find_sweeps(df, sh, sl, right=3, lookback=15):
    n, h, l, c, out = len(df), df["high"].values, df["low"].values, df["close"].values, []
    for i in range(max(5, n - lookback), n):
        ph = [p for j, p in sh if j + right < i][-5:]
        pl = [p for j, p in sl if j + right < i][-5:]
        if any(h[i] > p and c[i] < p for p in ph):
            out.append(dict(dir="BEAR", idx=i))
        if any(l[i] < p and c[i] > p for p in pl):
            out.append(dict(dir="BULL", idx=i))
    return out


def killzone_now():
    t = datetime.now(timezone.utc)
    hr = t.hour + t.minute / 60
    if 7 <= hr < 10:
        return "London Killzone"
    if 12 <= hr < 15:
        return "New York Killzone"
    if 0 <= hr < 4:
        return "Asian Range"
    return None


def zigzag(df, atr_s, mult=2.0):
    h, l = df["high"].values, df["low"].values
    a = atr_s.bfill().fillna(0).values
    piv, dirn = [], 0
    hi_i = lo_i = 0
    hi_p, lo_p = h[0], l[0]
    for i in range(1, len(df)):
        thr = max(a[i], 1e-12) * mult
        if dirn == 0:
            if h[i] > hi_p:
                hi_i, hi_p = i, h[i]
            if l[i] < lo_p:
                lo_i, lo_p = i, l[i]
            if hi_p - l[i] >= thr and hi_i < i:
                piv.append((hi_i, float(hi_p), "H", True))
                dirn, lo_i, lo_p = -1, i, l[i]
            elif h[i] - lo_p >= thr and lo_i < i:
                piv.append((lo_i, float(lo_p), "L", True))
                dirn, hi_i, hi_p = 1, i, h[i]
        elif dirn == 1:
            if h[i] > hi_p:
                hi_i, hi_p = i, h[i]
            elif hi_p - l[i] >= thr:
                piv.append((hi_i, float(hi_p), "H", True))
                dirn, lo_i, lo_p = -1, i, l[i]
        else:
            if l[i] < lo_p:
                lo_i, lo_p = i, l[i]
            elif h[i] - lo_p >= thr:
                piv.append((lo_i, float(lo_p), "L", True))
                dirn, hi_i, hi_p = 1, i, h[i]
    if dirn == 1:
        piv.append((hi_i, float(hi_p), "H", False))
    elif dirn == -1:
        piv.append((lo_i, float(lo_p), "L", False))
    return piv


def detect_elliott(piv):
    for k in (5, 4, 3, 2):
        if len(piv) < k + 1:
            continue
        pts = piv[-(k + 1):]
        P = [p[1] for p in pts]
        s = 1 if P[1] > P[0] else -1
        if pts[0][2] != ("L" if s == 1 else "H"):
            continue
        q = [s * x for x in P]
        ok = q[2] > q[0] and q[2] < q[1]
        if ok and k >= 3:
            ok = q[3] > q[1]
        if ok and k >= 4:
            ok = q[4] > q[1] and q[4] < q[3]
        if ok and k >= 5:
            w1, w3, w5 = q[1] - q[0], q[3] - q[2], q[5] - q[4]
            ok = q[5] > q[3] and not (w3 < w1 and w3 < w5)
        if ok and k == 2:
            r = (q[1] - q[2]) / max(q[1] - q[0], 1e-12)
            ok = 0.236 <= r <= 0.886
        if not ok:
            continue
        conf, w1 = pts[-1][3], q[1] - q[0]
        dir_s, opp = ("LONG", "SHORT") if s == 1 else ("SHORT", "LONG")
        bias, strength, target, invalid = None, 0.0, None, None
        if k == 2:
            wave = "Wave 3 launching (wave 2 correction done)" if conf else "Wave 2 correction still forming"
            bias, strength = (dir_s, 1.0) if conf else (None, 0.0)
            target, invalid = s * (q[2] + 1.618 * w1), P[0]
        elif k == 3:
            if not conf:
                wave, bias, strength = "Wave 3 in progress", dir_s, 0.9
                mult = 2.618 if pts[-1][1] * s >= q[2] + 1.618 * w1 else 1.618
                target, invalid = s * (q[2] + mult * w1), P[0]
            else:
                wave = "Wave 3 completed — wave 4 pullback expected"
                target, invalid = s * (q[3] - 0.382 * (q[3] - q[2])), P[1]
        elif k == 4:
            if conf:
                wave, bias, strength = "Wave 4 complete — wave 5 expected", dir_s, 0.6
                target = s * (q[4] + w1)
            else:
                wave = "Wave 4 correction forming"
            invalid = P[1]
        else:
            if conf:
                wave, bias, strength = "Wave 5 complete — ABC correction expected", opp, 0.6
                target, invalid = s * (q[5] - 0.382 * (q[5] - q[0])), P[5]
            else:
                wave, bias, strength = "Wave 5 in progress", dir_s, 0.4
                target, invalid = s * (q[4] + w1), P[4]
        return dict(k=k, wave=wave, bias=bias, strength=strength,
                    target=float(target) if target is not None else None,
                    invalid=float(invalid) if invalid is not None else None, pts=pts, dir=dir_s,
                    labels=["0", "1", "2", "3", "4", "5"][:k + 1])
    return None


def build_levels(d, price, a, obs, liq, sl_mult, rr):
    bull = d == "LONG"
    wd = "BULL" if bull else "BEAR"
    entry, etype, sl = price, "MARKET", None
    cand = [o for o in obs if o["dir"] == wd]
    inside = [o for o in cand if o["bottom"] - 0.5 * a <= price <= o["top"] + 0.5 * a]
    if inside:
        o = inside[-1]
        sl = o["bottom"] - 0.25 * a if bull else o["top"] + 0.25 * a
    else:
        near = [o for o in cand if (bull and o["top"] < price and price - o["top"] <= 3 * a)
                or (not bull and o["bottom"] > price and o["bottom"] - price <= 3 * a)]
        if near:
            o = max(near, key=lambda x: x["top"]) if bull else min(near, key=lambda x: x["bottom"])
            entry, etype = (o["top"] + o["bottom"]) / 2, "LIMIT"
            sl = o["bottom"] - 0.25 * a if bull else o["top"] + 0.25 * a
    if sl is None:
        sl = price - sl_mult * a if bull else price + sl_mult * a
    risk = abs(entry - sl)
    if risk < 0.8 * a:
        risk = 0.8 * a
        sl = entry - risk if bull else entry + risk
    if risk > 4 * a:
        risk = sl_mult * a
        sl = entry - risk if bull else entry + risk
    s = 1 if bull else -1
    tp1, tp2, tp3 = (entry + s * risk * max(1.0, rr * 0.5), entry + s * risk * rr, entry + s * risk * rr * 1.8)
    lt = liq["bsl"] if bull else liq["ssl"]
    if lt and (lt - tp2) * s > 0 and abs(lt - entry) <= 8 * risk:
        tp3 = lt
    return dict(entry=float(entry), sl=float(sl), tp1=float(tp1), tp2=float(tp2), tp3=float(tp3), etype=etype,
                risk=float(risk))


def analyze_df(df, base, tf, sl_mult, rr):
    df = df.copy()
    df["atr"] = calc_atr(df)
    n = len(df)
    price = float(df["close"].iloc[-1])
    a = df["atr"].iloc[-1]
    a = float(a) if not np.isnan(a) else price * 0.01
    a = max(a, price * 0.0005)
    R = 3
    sh, sl = find_swings(df, 3, R)
    trend, events = market_structure(df, sh, sl, R)
    obs = find_order_blocks(df, events, a)
    fvgs = find_fvgs(df, a)
    liq = liquidity_levels(df, sh, sl, a, price)
    sweeps = find_sweeps(df, sh, sl, R)
    piv = zigzag(df, df["atr"])
    ew = detect_elliott(piv)
    rng_h, rng_l = float(df["high"].iloc[-60:].max()), float(df["low"].iloc[-60:].min())
    pos = (price - rng_l) / (rng_h - rng_l + 1e-12)
    delta = float((np.where(df["close"] >= df["open"], 1, -1) * df["volume"]).iloc[-10:].sum())
    kz = killzone_now()

    def score_dir(d):
        bull = d == "LONG"
        wd = "BULL" if bull else "BEAR"
        s, why = 0, []
        if (trend == 1 and bull) or (trend == -1 and not bull):
            s += 12
            why.append("Bullish market structure (higher highs / higher lows)" if bull
                       else "Bearish market structure (lower highs / lower lows)")
        rec = [e for e in events if e["dir"] == wd and n - 1 - e["at"] <= 30]
        if rec:
            s += 8
            why.append(f"{rec[-1]['type']} {'up' if bull else 'down'} confirmed {n - 1 - rec[-1]['at']} bars ago")
        if bull:
            if pos < 0.5:
                s += 4
                why.append(f"Price in discount zone ({pos * 100:.0f}% of range)")
            if 0.21 <= pos <= 0.38:
                s += 6
                why.append("Inside OTE (62-79% retracement) buy zone")
        else:
            if pos > 0.5:
                s += 4
                why.append(f"Price in premium zone ({pos * 100:.0f}% of range)")
            if 0.62 <= pos <= 0.79:
                s += 6
                why.append("Inside OTE (62-79% retracement) sell zone")
        near = [o for o in obs if o["dir"] == wd]
        inside = [o for o in near if o["bottom"] - 0.5 * a <= price <= o["top"] + 0.5 * a]
        if inside:
            s += 20
            why.append(f"Price at unmitigated {'bullish' if bull else 'bearish'} order block "
                       f"({fp(inside[-1]['bottom'])} - {fp(inside[-1]['top'])})")
        elif any((bull and o["top"] < price and price - o["top"] <= 2.5 * a)
                 or (not bull and o["bottom"] > price and o["bottom"] - price <= 2.5 * a) for o in near):
            s += 10
            why.append("Unmitigated order block nearby — waiting for retest")
        if any(g["dir"] == wd and g["bottom"] - a <= price <= g["top"] + a for g in fvgs):
            s += 10
            why.append("Unfilled fair value gap (imbalance) in play")
        sw = [x for x in sweeps if x["dir"] == wd]
        if sw:
            s += 15
            why.append(f"{'Sell' if bull else 'Buy'}-side liquidity swept {n - 1 - sw[-1]['idx']} bars ago")
        if ew and ew["bias"] is not None:
            if ew["bias"] == d:
                s += round(15 * ew["strength"])
                why.append("Elliott Wave: " + ew["wave"])
            else:
                s -= 10
        if kz in ("London Killzone", "New York Killzone"):
            s += 5
            why.append(f"{kz} active")
        if delta != 0 and (delta > 0) == bull:
            s += 5
            why.append("Order-flow delta supports the direction")
        return max(0, min(100, int(s))), why

    sc = {d: score_dir(d) for d in ("LONG", "SHORT")}
    if sc["LONG"][0] > sc["SHORT"][0]:
        d = "LONG"
    elif sc["LONG"][0] < sc["SHORT"][0]:
        d = "SHORT"
    else:
        d = "LONG" if trend == 1 else "SHORT"
    score, why = sc[d]
    wd = "BULL" if d == "LONG" else "BEAR"
    supports = any(e["dir"] == wd and n - 1 - e["at"] <= 30 for e in events) or any(x["dir"] == wd for x in sweeps)
    status = "CONFIRMED" if (score >= 65 and supports) else ("WATCH" if score >= 45 else "NO CLEAR SETUP")
    grade = "A+" if score >= 85 else "A" if score >= 72 else "B" if score >= 60 else "C"
    return dict(base=base, tf=tf, price=price, atr=a, direction=d, status=status, grade=grade, score=score,
                reasons=why, levels=build_levels(d, price, a, obs, liq, sl_mult, rr), ew=ew, trend=trend,
                events=events, obs=obs, fvgs=fvgs, liq=liq, sweeps=sweeps, killzone=kz, pos=pos,
                last_time=int(df["time"].iloc[-1]), df=df, scores={k: v[0] for k, v in sc.items()})
# ==== ANALYSIS ENGINE END ====


def pair_name(base):
    return "GOLD (XAU) · PAXG/USDT" if base == "PAXG" else f"{base}/USDT"


def analyze(base, tf, sl_m, rr):
    df, src, err = fetch_klines(base, tf, 300)
    if df is None:
        return None, err
    A = analyze_df(df, base, tf, sl_m, rr)
    A["source"] = src
    return A, None


def normalize_coin(txt):
    t = re.sub(r"[\s/\-_]", "", txt.upper())
    t = re.sub(r"(USDT|USD)$", "", t)
    return "PAXG" if t in ("XAU", "GOLD", "XAUUSD", "PAXG") else t


# =====================================================================
# CHART (TradingView Lightweight Charts with SMC / ICT / Elliott overlays)
# =====================================================================
def build_payload(A):
    df, lv = A["df"], A["levels"]
    t = df["time"].astype(int).values
    price = A["price"]
    prec = 2 if price >= 1000 else 4 if price >= 1 else 5 if price >= 0.1 else 6 if price >= 0.01 else 8
    candles = [dict(time=int(t[i]), open=float(r.open), high=float(r.high), low=float(r.low), close=float(r.close))
               for i, r in enumerate(df.itertuples())]
    volume = [dict(time=int(t[i]), value=float(r.volume),
                   color="rgba(0,230,118,.35)" if r.close >= r.open else "rgba(255,61,113,.35)")
              for i, r in enumerate(df.itertuples())]
    markers, paths, lines, zones = [], [], [], []
    for e in A["events"][-5:]:
        bull = e["dir"] == "BULL"
        markers.append(dict(time=int(t[e["at"]]), position="belowBar" if bull else "aboveBar",
                            color="#00e676" if bull else "#ff3d71", shape="arrowUp" if bull else "arrowDown",
                            text=e["type"], cat="smc"))
        if t[e["at"]] > t[e["frm"]]:
            paths.append(dict(cat="smc", color="#00e676aa" if bull else "#ff3d71aa", width=1, style=2,
                              data=[dict(time=int(t[e["frm"]]), value=e["level"]),
                                    dict(time=int(t[e["at"]]), value=e["level"])]))
    for s in A["sweeps"][-3:]:
        bull = s["dir"] == "BULL"
        markers.append(dict(time=int(t[s["idx"]]), position="belowBar" if bull else "aboveBar", color="#ffd700",
                            shape="circle", text="SSL sweep" if bull else "BSL sweep", cat="smc"))
    ew = A["ew"]
    if ew:
        for pt, lab in zip(ew["pts"], ew["labels"]):
            markers.append(dict(time=int(t[pt[0]]), position="aboveBar" if pt[2] == "H" else "belowBar",
                                color="#b388ff", shape="circle", text=lab, cat="ew"))
        paths.append(dict(cat="ew", color="#b388ff", width=2, style=0,
                          data=[dict(time=int(t[p[0]]), value=p[1]) for p in ew["pts"]]))
        if ew["target"]:
            lines.append(dict(price=ew["target"], color="#b388ff", style=3, width=1, title="EW target"))
    markers.sort(key=lambda m: m["time"])
    lines += [dict(price=lv["entry"], color="#00e5ff", style=0, width=2, title=f"ENTRY ({lv['etype']})"),
              dict(price=lv["sl"], color="#ff3d71", style=0, width=2, title="SL"),
              dict(price=lv["tp1"], color="#00e676", style=2, width=1, title="TP1"),
              dict(price=lv["tp2"], color="#00e676", style=2, width=2, title="TP2"),
              dict(price=lv["tp3"], color="#00e676", style=2, width=1, title="TP3")]
    liq = A["liq"]
    if liq["bsl"]:
        lines.append(dict(price=liq["bsl"], color="#ffd700", style=3, width=1, title="BSL"))
    if liq["ssl"]:
        lines.append(dict(price=liq["ssl"], color="#ffd700", style=3, width=1, title="SSL"))
    for p in liq["eqh"]:
        lines.append(dict(price=p, color="#ffb74d", style=1, width=1, title="EQH"))
    for p in liq["eql"]:
        lines.append(dict(price=p, color="#ffb74d", style=1, width=1, title="EQL"))
    for o in A["obs"]:
        bull = o["dir"] == "BULL"
        zones.append(dict(t1=int(t[o["idx"]]), t2=None, top=o["top"], bottom=o["bottom"],
                          fill="rgba(0,230,118,.14)" if bull else "rgba(255,61,113,.14)",
                          border="#00e676" if bull else "#ff3d71", label=("Bull OB" if bull else "Bear OB")))
    for g in A["fvgs"]:
        bull = g["dir"] == "BULL"
        zones.append(dict(t1=int(t[g["idx"]]), t2=None, top=g["top"], bottom=g["bottom"],
                          fill="rgba(0,229,255,.10)" if bull else "rgba(255,138,168,.10)",
                          border="#00e5ff" if bull else "#ff8aa8", label="Bull FVG" if bull else "Bear FVG"))
    title = (f"{pair_name(A['base'])} · {A['tf']} · {A['direction']} · {A['status']} · "
             f"Grade {A['grade']} ({A['score']}/100)")
    return dict(candles=candles, volume=volume, markers=markers, paths=paths, lines=lines, zones=zones,
                prec=prec, minMove=10 ** (-prec), title=title, n=len(candles),
                color="#00e676" if A["direction"] == "LONG" else "#ff3d71")


CHART_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#0b0f1a;font-family:Segoe UI,Arial,sans-serif;">
<div id="wrap" style="position:relative;width:100%;height:640px;background:#0b0f1a;border:1px solid #26324f;border-radius:16px;overflow:hidden;box-shadow:0 14px 40px #000a;">
 <div id="chart" style="position:absolute;inset:0"></div>
 <div id="zones" style="position:absolute;inset:0;pointer-events:none;overflow:hidden"></div>
 <div id="bar" style="position:absolute;left:10px;top:8px;z-index:5;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
   <span id="ttl" style="background:#0b0f1acc;border:1px solid #26324f;padding:5px 10px;border-radius:10px;font-weight:700;font-size:13px"></span>
   <label class="tg"><input type="checkbox" id="c_zones" checked> OB / FVG</label>
   <label class="tg"><input type="checkbox" id="c_smc" checked> BOS / CHoCH</label>
   <label class="tg"><input type="checkbox" id="c_ew" checked> Elliott</label>
 </div>
</div>
<style>.tg{background:#0b0f1acc;border:1px solid #26324f;padding:5px 9px;border-radius:10px;font-size:12px;color:#cfd8ea;cursor:pointer}</style>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
const D = __DATA__;
const el = document.getElementById('chart');
const chart = LightweightCharts.createChart(el, {
  width: el.clientWidth, height: el.clientHeight,
  layout: {background: {type: 'solid', color: '#0b0f1a'}, textColor: '#cfd8ea'},
  grid: {vertLines: {color: '#121a2b'}, horzLines: {color: '#121a2b'}},
  crosshair: {mode: 0},
  rightPriceScale: {borderColor: '#26324f', scaleMargins: {top: 0.08, bottom: 0.2}},
  timeScale: {borderColor: '#26324f', timeVisible: true, secondsVisible: false, rightOffset: 10}
});
const candles = chart.addCandlestickSeries({upColor:'#00e676', downColor:'#ff3d71', borderVisible:false,
  wickUpColor:'#00e676', wickDownColor:'#ff3d71',
  priceFormat:{type:'price', precision:D.prec, minMove:D.minMove}});
candles.setData(D.candles);
const vol = chart.addHistogramSeries({priceFormat:{type:'volume'}, priceScaleId:'vol'});
chart.priceScale('vol').applyOptions({scaleMargins:{top:0.86, bottom:0}});
vol.setData(D.volume);
D.lines.forEach(l => candles.createPriceLine({price:l.price, color:l.color, lineWidth:l.width||1,
  lineStyle:l.style===undefined?2:l.style, axisLabelVisible:true, title:l.title}));
const ps = D.paths.map(p => {
  const s = chart.addLineSeries({color:p.color, lineWidth:p.width||1, lineStyle:p.style||0,
    priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false});
  s.setData(p.data); return {s:s, cat:p.cat};
});
const state = {zones:true, smc:true, ew:true};
const zonesEl = document.getElementById('zones');
function apply() {
  candles.setMarkers(D.markers.filter(m => state[m.cat] !== false)
    .map(m => ({time:m.time, position:m.position, color:m.color, shape:m.shape, text:m.text})));
  ps.forEach(p => p.s.applyOptions({visible: state[p.cat] !== false}));
  zonesEl.style.display = state.zones ? 'block' : 'none';
}
const zdivs = D.zones.map(z => {
  const d = document.createElement('div');
  d.style.cssText = 'position:absolute;box-sizing:border-box;font:11px sans-serif;padding:1px 5px;white-space:nowrap;overflow:hidden;border:1px solid '+z.border+';background:'+z.fill+';color:'+z.border;
  d.textContent = z.label; zonesEl.appendChild(d); return d;
});
function pw() { try { return chart.priceScale('right').width(); } catch(e) { return 62; } }
function layout() {
  const ts = chart.timeScale(), w = el.clientWidth - pw();
  D.zones.forEach((z, i) => {
    const d = zdivs[i], y1 = candles.priceToCoordinate(z.top), y2 = candles.priceToCoordinate(z.bottom);
    if (y1 === null || y2 === null) { d.style.display = 'none'; return; }
    let x1 = ts.timeToCoordinate(z.t1); if (x1 === null) x1 = 0;
    let x2 = z.t2 ? ts.timeToCoordinate(z.t2) : w; if (x2 === null) x2 = w;
    const left = Math.max(0, Math.min(x1, w)), right = Math.max(0, Math.min(x2, w));
    if (right - left < 2) { d.style.display = 'none'; return; }
    d.style.display = 'block'; d.style.left = left+'px'; d.style.top = Math.min(y1,y2)+'px';
    d.style.width = (right-left)+'px'; d.style.height = Math.max(Math.abs(y2-y1), 2)+'px';
  });
  requestAnimationFrame(layout);
}
['zones','smc','ew'].forEach(k => document.getElementById('c_'+k).addEventListener('change', e => { state[k] = e.target.checked; apply(); }));
document.getElementById('ttl').textContent = D.title;
document.getElementById('ttl').style.color = D.color;
apply();
chart.timeScale().setVisibleLogicalRange({from: Math.max(0, D.n - 130), to: D.n + 12});
requestAnimationFrame(layout);
window.addEventListener('resize', () => chart.resize(el.clientWidth, el.clientHeight));
</script></body></html>"""


def render_chart(A):
    html = CHART_HTML.replace("__DATA__", json.dumps(build_payload(A)))
    components.html(html, height=660)


def tv_live(base):
    sym = "OANDA:XAUUSD" if base == "PAXG" else f"{tv_exchange}:{base}USDT"
    html = """<!DOCTYPE html><html><body style="margin:0;background:#131722;">
<div style="height:600px;width:100%"><div id="tvw" style="height:100%;width:100%"></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>new TradingView.widget({"autosize":true,"symbol":"__SYM__","interval":"60","timezone":"Etc/UTC",
"theme":"dark","style":"1","locale":"en","enable_publishing":false,"allow_symbol_change":true,
"details":true,"container_id":"tvw"});</script></div></body></html>""".replace("__SYM__", sym)
    components.html(html, height=620)


# =====================================================================
# ALERTS (English)
# =====================================================================
def alert_text(r):
    why = "; ".join(r["Reasons"][:3])
    return (f"{r['Pair']} ({r['TF']}): {r['Direction']} setup detected — Grade {r['Grade']} (score {r['Score']}/100). "
            f"Entry {fp(r['Entry'])} | SL {fp(r['SL'])} | TP1 {fp(r['TP1'])} | TP2 {fp(r['TP2'])} | TP3 {fp(r['TP3'])}."
            + (f" Why: {why}." if why else ""))


def maybe_alert(rows, max_toasts=5, max_tg=8):
    st.session_state.setdefault("alerted", set())
    st.session_state.setdefault("alerts", [])
    fresh = []
    for r in sorted(rows, key=lambda x: -x["Score"]):
        if r["Status"] != "CONFIRMED" or r["Score"] < alert_min:
            continue
        key = f"{r['Pair']}|{r['TF']}|{r['Direction']}|{r['LastTime']}"
        if key in st.session_state["alerted"]:
            continue
        st.session_state["alerted"].add(key)
        fresh.append(r)
    for i, r in enumerate(fresh):
        txt = alert_text(r)
        st.session_state["alerts"].insert(0, dict(ts=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"), text=txt,
                                                  dir=r["Direction"]))
        if i < max_toasts:
            st.toast(txt.split(" Entry")[0], icon="🚨")
        if i < max_tg:
            send_telegram(tg_token, tg_chat, "🚨 APEX AI BOT\n" + txt)
    st.session_state["alerts"] = st.session_state["alerts"][:40]
    return len(fresh)


def summarize(A, meta):
    lv = A["levels"]
    ew = A["ew"]
    return dict(Rank=meta.get("Rank", 0), Coin=A["base"] if A["base"] != "PAXG" else "GOLD", Base=A["base"],
                Pair=pair_name(A["base"]), TF=A["tf"], Price=A["price"], Chg24=meta.get("Chg24", 0.0),
                Funding=meta.get("Funding"), Direction=A["direction"], Status=A["status"], Grade=A["grade"],
                Score=A["score"], Entry=lv["entry"], SL=lv["sl"], TP1=lv["tp1"], TP2=lv["tp2"], TP3=lv["tp3"],
                EntryType=lv["etype"], EW=ew["wave"] if ew else "No clear count", Reasons=A["reasons"],
                LastTime=A["last_time"])


def card_html(r):
    cls = "long" if r["Direction"] == "LONG" else "short"
    bcls = {"CONFIRMED": f"b-{cls}", "WATCH": "b-watch"}.get(r["Status"], "b-none")
    fr = "—" if r["Funding"] is None else f"{r['Funding']:.4f}%"
    return f"""<div class="tcard {cls}">
<div class="thead"><span class="tname">{r['Coin']}</span><span class="badge {bcls}">{r['Direction']} · {r['Status']}</span></div>
<div class="scorewrap"><div class="scorebar"><i style="width:{r['Score']}%"></i></div><span class="grade">{r['Grade']} · {r['Score']}</span></div>
<div class="row"><span class="lbl">🎯 Entry ({r['EntryType']})</span><span class="v-entry">${fp(r['Entry'])}</span></div>
<div class="row"><span class="lbl">🔴 Stop Loss</span><span class="v-sl">${fp(r['SL'])}</span></div>
<div class="row"><span class="lbl">🟢 TP1</span><span class="v-tp">${fp(r['TP1'])}</span></div>
<div class="row"><span class="lbl">🟢 TP2</span><span class="v-tp">${fp(r['TP2'])}</span></div>
<div class="row"><span class="lbl">🟢 TP3</span><span class="v-tp">${fp(r['TP3'])}</span></div>
<div class="meta">🌊 {r['EW']}<br>💸 Funding {fr} · 24h {r['Chg24']:+.2f}%</div></div>"""


# =====================================================================
# ANALYSIS VIEW (card + reasons + chart + risk calculator)
# =====================================================================
def render_analysis(A, ctx):
    lv, d = A["levels"], A["direction"]
    cls = "long" if d == "LONG" else "short"
    bcls = {"CONFIRMED": f"b-{cls}", "WATCH": "b-watch"}.get(A["status"], "b-none")
    fund = get_all_funding()[0].get(A["base"])
    risk = lv["risk"]
    rmul = lambda x: abs(x - lv["entry"]) / risk if risk else 0
    c_card, c_info = st.columns([1, 1.7])
    with c_card:
        st.markdown(f"""<div class="tcard big {cls}">
<div class="thead"><span class="tname">{pair_name(A['base'])}</span><span class="badge {bcls}">{d} · {A['status']}</span></div>
<div class="scorewrap"><div class="scorebar"><i style="width:{A['score']}%"></i></div><span class="grade">Grade {A['grade']} · {A['score']}/100</span></div>
<div class="row"><span class="lbl">💵 Price</span><span style="color:#fff;font-weight:700">${fp(A['price'])}</span></div>
<div class="row"><span class="lbl">🎯 Entry ({lv['etype']})</span><span class="v-entry">${fp(lv['entry'])}</span></div>
<div class="row"><span class="lbl">🔴 Stop Loss</span><span class="v-sl">${fp(lv['sl'])}</span></div>
<div class="row"><span class="lbl">🟢 TP1 ({rmul(lv['tp1']):.1f}R)</span><span class="v-tp">${fp(lv['tp1'])}</span></div>
<div class="row"><span class="lbl">🟢 TP2 ({rmul(lv['tp2']):.1f}R)</span><span class="v-tp">${fp(lv['tp2'])}</span></div>
<div class="row"><span class="lbl">🟢 TP3 ({rmul(lv['tp3']):.1f}R)</span><span class="v-tp">${fp(lv['tp3'])}</span></div>
<div class="meta">Data: {A.get('source', '—')} · TF {A['tf']} · Long score {A['scores']['LONG']} / Short score {A['scores']['SHORT']}</div></div>""",
                    unsafe_allow_html=True)
    with c_info:
        m1, m2, m3 = st.columns(3)
        m1.metric("Real-time funding", "—" if fund is None else f"{fund:.4f}%")
        m2.metric("Structure", {1: "Bullish", -1: "Bearish", 0: "Ranging"}[A["trend"]])
        m3.metric("Session", A["killzone"] or "Off-session")
        st.markdown("**🧠 Why this setup**")
        for r in A["reasons"] or ["No strong confluence found right now."]:
            st.markdown(f"- ✅ {r}")
        ew = A["ew"]
        if ew:
            tgt = f" · target `${fp(ew['target'])}`" if ew["target"] else ""
            inv = f" · invalidation `${fp(ew['invalid'])}`" if ew["invalid"] else ""
            st.markdown(f"🌊 **Elliott Wave:** {ew['wave']}{tgt}{inv}")
        else:
            st.markdown("🌊 **Elliott Wave:** no valid impulse count right now")
        if fund is not None and abs(fund) >= 0.03:
            st.warning("Funding is extreme — " + ("longs are crowded (long-squeeze risk)." if fund > 0
                                                  else "shorts are crowded (short-squeeze risk)."))
        if A["status"] != "CONFIRMED":
            st.info("This is not a confirmed setup yet — treat levels as a watch-list plan and wait for confirmation.")
    t1, t2 = st.tabs(["🧠 AI Analysis Chart (SMC · ICT · Elliott)", "📡 TradingView Live"])
    with t1:
        render_chart(A)
        st.caption("🟩/🟥 boxes = unmitigated order blocks · 🟦/🟪 boxes = unfilled FVGs · yellow dotted = BSL/SSL liquidity · "
                   "purple = Elliott count · cyan/red/green = Entry/SL/TP")
    with t2:
        tv_live(A["base"])
    st.subheader("🧮 Position Size & Risk Calculator")
    r1, r2 = st.columns(2)
    with r1:
        bal = st.number_input("Account balance (USDT)", 10.0, 10_000_000.0, 1000.0, 50.0, key=f"{ctx}_bal")
        rp = st.slider("Risk per trade (%)", 0.25, 5.0, 1.0, 0.25, key=f"{ctx}_rp")
        lev = st.selectbox("Leverage (x)", [1, 2, 3, 5, 10, 20, 50], index=3, key=f"{ctx}_lev")
    with r2:
        diff = abs(lv["entry"] - lv["sl"])
        if diff > 0:
            risk_usdt = bal * rp / 100
            qty = risk_usdt / diff
            notional = qty * lv["entry"]
            st.markdown(f"💰 **Position size:** `{qty:,.4f} {A['base']}` (`${notional:,.2f}`)")
            st.markdown(f"⚠️ **Margin ({lev}x):** `${notional / lev:,.2f}`")
            st.markdown(f"🛑 **Max loss at SL:** `${risk_usdt:,.2f}` ({rp}%)")
            st.markdown(f"🏆 **Profit @TP1 / TP2 / TP3:** `${qty * abs(lv['tp1'] - lv['entry']):,.2f}` / "
                        f"`${qty * abs(lv['tp2'] - lv['entry']):,.2f}` / `${qty * abs(lv['tp3'] - lv['entry']):,.2f}`")


# =====================================================================
# TABS
# =====================================================================
top_df, top_src = get_top100()
funding, fund_src = get_all_funding()
bases = top_df["Coin"].tolist() if not top_df.empty else []
meta_map = {}
for r in top_df.itertuples():
    meta_map[r.Coin] = dict(Rank=int(r.Rank), Chg24=float(r.Chg24), Funding=funding.get(r.Coin))
meta_map["PAXG"] = dict(Rank=0, Chg24=0.0, Funding=funding.get("PAXG"))

tab_scan, tab_an, tab_fund, tab_mkt = st.tabs(
    ["🎯 AI Scanner (Top 100)", "🔍 Coin Analyzer", "🔥 Funding Rates (Top 100)", "🌐 Market Top 100"]
)


# ---------------------------------------------------------------- SCANNER
def scan_universe(universe, tf, progress):
    out, total, done = [], len(universe), 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(analyze, b, tf, sl_mult, risk_reward): b for b in universe}
        for f in as_completed(futs):
            done += 1
            b = futs[f]
            progress(done, total, b)
            try:
                A, _ = f.result()
            except Exception:
                A = None
            if A:
                A.pop("df", None)
                out.append(summarize(A, meta_map.get(b, {})))
    return out


def scanner_fragment():
    c1, c2 = st.columns([1, 3])
    run = c1.button("🚀 Scan Top 100 Now", use_container_width=True, key="scan_btn")
    last = st.session_state.get("last_scan_ts", 0)
    due = auto_scan and (time.time() - last >= auto_min * 60 - 5)
    if auto_scan:
        c2.caption(f"🟢 Auto-scan ON — every {auto_min} min · timeframe {timeframe}")
    if run or due:
        if not bases:
            st.error("Could not load the Top 100 list (CoinGecko / Binance unreachable). Try again in a minute.")
        else:
            ph = st.empty()
            universe = ["PAXG"] + bases

            def prog(k, tot, b):
                ph.markdown(loader_html(f"Analyzing {b}  ({k}/{tot})", k / tot, "📡"), unsafe_allow_html=True)

            prog(0, len(universe), "...")
            rows = scan_universe(universe, timeframe, prog)
            ph.empty()
            rows.sort(key=lambda r: (-(r["Status"] == "CONFIRMED"), -r["Score"]))
            st.session_state["scan_rows"] = rows
            st.session_state["last_scan_ts"] = time.time()
            n = maybe_alert(rows)
            st.toast(f"✅ Scan complete: {len(rows)} pairs analyzed, {n} new alert(s).", icon="📡")

    rows = st.session_state.get("scan_rows")
    if not rows:
        st.info("Click **Scan Top 100 Now** to analyze every top-100 coin + Gold with SMC, ICT & Elliott Wave.")
        return
    conf = [r for r in rows if r["Status"] == "CONFIRMED"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pairs analyzed", len(rows))
    k2.metric("Confirmed LONG 🟢", sum(r["Direction"] == "LONG" for r in conf))
    k3.metric("Confirmed SHORT 🔴", sum(r["Direction"] == "SHORT" for r in conf))
    k4.metric("Last scan", datetime.fromtimestamp(st.session_state["last_scan_ts"], timezone.utc).strftime("%H:%M:%S UTC"))

    st.subheader("🔔 Live Alerts")
    if st.session_state.get("alerts"):
        for a in st.session_state["alerts"][:6]:
            st.markdown(f'<div class="alertbox">🚨 {a["text"]}<br><small>{a["ts"]}</small></div>', unsafe_allow_html=True)
    else:
        st.caption(f"No alerts yet — alerts fire for CONFIRMED setups with score ≥ {alert_min}.")

    st.subheader("🏆 Top Setups")
    best = [r for r in rows if r["Status"] != "NO CLEAR SETUP"][:12]
    if best:
        st.markdown('<div class="grid">' + "".join(card_html(r) for r in best) + "</div>", unsafe_allow_html=True)
    else:
        st.info("No setups above the watch threshold at the moment.")

    st.subheader("📊 Full Scanner Table — Entry / SL / TP for every coin")
    f1, f2 = st.columns([2, 2])
    view = f1.radio("Filter", ["All", "Confirmed", "Long", "Short"], horizontal=True, key="scan_filter")
    q = f2.text_input("Search coin", "", key="scan_q")
    t = rows
    if view == "Confirmed":
        t = [r for r in t if r["Status"] == "CONFIRMED"]
    elif view in ("Long", "Short"):
        t = [r for r in t if r["Direction"] == view.upper()]
    if q.strip():
        t = [r for r in t if q.strip().upper() in r["Coin"].upper()]
    if t:
        tdf = pd.DataFrame([{
            "#": r["Rank"], "Coin": r["Coin"], "Price": fp(r["Price"]), "24h %": round(r["Chg24"], 2),
            "Funding %": None if r["Funding"] is None else round(r["Funding"], 4),
            "Direction": ("🟢 " if r["Direction"] == "LONG" else "🔴 ") + r["Direction"], "Status": r["Status"],
            "Grade": r["Grade"], "Score": r["Score"], "Entry": fp(r["Entry"]), "SL": fp(r["SL"]),
            "TP1": fp(r["TP1"]), "TP2": fp(r["TP2"]), "TP3": fp(r["TP3"]), "Elliott Wave": r["EW"]} for r in t])
        st.dataframe(tdf, use_container_width=True, height=420, hide_index=True,
                     column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                                             format="%d")})
    else:
        st.info("No pairs match this filter.")

    if HAS_PLOTLY:
        st.subheader("🧊 3D Market Map")
        st.caption("X = confluence score · Y = funding rate % · Z = 24h change % · bigger = higher market-cap rank")
        d3 = pd.DataFrame([r for r in rows if r["Funding"] is not None])
        if not d3.empty:
            fig = go.Figure(data=[go.Scatter3d(
                x=d3["Score"], y=d3["Funding"], z=d3["Chg24"], mode="markers+text", text=d3["Coin"],
                textposition="top center", textfont=dict(size=9, color="#cfd8ea"),
                marker=dict(size=np.clip(14 - d3["Rank"].fillna(0) / 9, 5, 14), color=d3["Score"],
                            colorscale="Turbo", opacity=0.92, line=dict(width=0.5, color="#ffffff")),
                hovertemplate="<b>%{text}</b><br>Score %{x}<br>Funding %{y:.4f}%<br>24h %{z:.2f}%<extra></extra>")])
            fig.update_layout(template="plotly_dark", height=560, margin=dict(l=0, r=0, t=10, b=0),
                              paper_bgcolor="rgba(0,0,0,0)",
                              scene=dict(xaxis_title="Score", yaxis_title="Funding %", zaxis_title="24h %"))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 Chart view")
    opts = [r["Base"] for r in rows]
    sel = st.selectbox("Open analysis chart for", opts, key="scan_view",
                       format_func=lambda b: next(f"{r['Coin']} — {r['Direction']} {r['Status']} ({r['Score']})"
                                                   for r in rows if r["Base"] == b))
    if sel:
        with st.spinner("Loading chart..."):
            A, err = analyze(sel, timeframe, sl_mult, risk_reward)
        if A:
            render_analysis(A, "scan")
        else:
            st.error(f"Could not load {sel}: {err}")


with tab_scan:
    if hasattr(st, "fragment"):
        if auto_scan:
            st.fragment(run_every=max(30, auto_min * 60))(scanner_fragment)()
        else:
            st.fragment(scanner_fragment)()
    else:
        scanner_fragment()

# ---------------------------------------------------------------- ANALYZER
with tab_an:
    a1, a2, a3 = st.columns([2, 2, 1])
    typed = a1.text_input("Type coin (BTC, ETH, SOL, PEPE, XAU...)", value="BTC", key="an_typed")
    pick = a2.selectbox("…or quick-pick from Top 100", ["—"] + bases, key="an_pick")
    a3.write("")
    a3.write("")
    go_btn = a3.button("🚀 Analyze", use_container_width=True, key="an_go")
    if go_btn:
        base = normalize_coin(pick if pick != "—" else typed)
        ph = st.empty()
        ph.markdown(loader_html(f"Analyzing {base}/USDT with SMC + ICT + Elliott Wave...", None, "🔎"),
                    unsafe_allow_html=True)
        A, err = analyze(base, timeframe, sl_mult, risk_reward)
        ph.empty()
        if A:
            st.session_state["an_result"] = A
            st.toast(f"✅ {pair_name(base)} analysis ready: {A['direction']} · {A['status']} ({A['score']}/100)",
                     icon="🧠")
            maybe_alert([summarize(A, meta_map.get(base, {}))])
        else:
            st.error(f"Could not load data for {base}. Tried: {err}")
    if "an_result" in st.session_state:
        render_analysis(st.session_state["an_result"], "an")
    else:
        st.info("Enter a coin and press **Analyze** to get a full SMC · ICT · Elliott Wave breakdown on the chart.")

# ---------------------------------------------------------------- FUNDING
with tab_fund:
    fc1, fc2 = st.columns([1, 3])
    if fc1.button("🔄 Refresh funding", key="fund_refresh"):
        get_all_funding.clear()
        st.rerun()
    fc2.caption(f"Sources: {', '.join(fund_src) if fund_src else 'none reachable'} · updates every 60s "
                f"· coin list: {top_src}")
    if top_df.empty or not funding:
        st.warning("Funding or market data is temporarily unreachable. Press refresh in a few seconds.")
    else:
        fdf = top_df.copy()
        fdf["Funding"] = fdf["Coin"].map(funding)
        fdf = fdf.dropna(subset=["Funding"]).copy()
        fdf["Bias"] = np.where(fdf["Funding"] > 0.03, "🔴 Longs crowded",
                               np.where(fdf["Funding"] < -0.03, "🟢 Shorts crowded", "⚪ Neutral"))
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("#### 🔺 Highest funding (long-squeeze risk)")
            for x in fdf.sort_values("Funding", ascending=False).head(5).itertuples():
                st.markdown(f"• **{x.Coin}** `{x.Funding:.4f}%` · ${fp(x.Price)}")
        with r2:
            st.markdown("#### 🔻 Lowest funding (short-squeeze risk)")
            for x in fdf.sort_values("Funding").head(5).itertuples():
                st.markdown(f"• **{x.Coin}** `{x.Funding:.4f}%` · ${fp(x.Price)}")
        st.dataframe(
            pd.DataFrame({"#": fdf["Rank"], "Coin": fdf["Coin"], "Price": fdf["Price"].map(fp),
                          "24h %": fdf["Chg24"].round(2), "Funding %": fdf["Funding"].round(4), "Bias": fdf["Bias"]}),
            use_container_width=True, height=520, hide_index=True)

# ---------------------------------------------------------------- MARKET
with tab_mkt:
    st.caption(f"Top 100 by market cap · {top_src} · cached 5 min")
    if top_df.empty:
        st.warning("Market data unavailable right now.")
    else:
        st.dataframe(
            pd.DataFrame({"#": top_df["Rank"], "Name": top_df["Name"], "Coin": top_df["Coin"],
                          "Price": top_df["Price"].map(lambda x: fp(x) if x else "—"),
                          "24h %": top_df["Chg24"].round(2),
                          "Market Cap": top_df["MCap"].map(lambda x: f"${x:,.0f}" if x else "—"),
                          "24h Volume": top_df["Vol"].map(lambda x: f"${x:,.0f}")}),
            use_container_width=True, height=600, hide_index=True)

st.markdown("---")
st.caption("⚠️ Analysis is algorithmic (SMC / ICT / Elliott Wave heuristics) and is not financial advice. "
           "Scores measure how many conditions line up — they are not a win-rate. Always manage your risk.")
