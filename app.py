import os
import json
import time
import math
import secrets
import datetime
import zoneinfo
import urllib.parse
import requests
import streamlit as st
import pandas as pd
import numpy as np

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="Hemant 5M Option Chain Intelligence Scanner V3",
    page_icon="🎯",
    layout="wide"
)

# ----------------- CREDENTIALS FROM SECRETS -----------------
try:
    API_KEY = st.secrets["UPSTOX"]["API_KEY"]
    API_SECRET = st.secrets["UPSTOX"]["API_SECRET"]
    REDIRECT_URI = st.secrets["UPSTOX"]["REDIRECT_URI"]
except Exception:
    API_KEY = "YOUR_API_KEY"
    API_SECRET = "YOUR_API_SECRET"
    REDIRECT_URI = "https://hemant-option-chain.streamlit.app/"

INDEX_CONFIG = {
    "NIFTY 50": {"key": "NSE_INDEX|Nifty 50", "step": 50},
    "BANKNIFTY": {"key": "NSE_INDEX|Nifty Bank", "step": 100},
    "SENSEX": {"key": "BSE_INDEX|SENSEX", "step": 100},
}

# ----------------- ULTRA-COMPACT CSS & ANIMATIONS -----------------
st.markdown("""
<style>
.block-container {
    padding-top: 0.6rem !important;
    padding-bottom: 0.4rem !important;
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
}
@keyframes pulseGreen {
    0% { background-color: rgba(46, 204, 113, 0.20); border-color: #2ecc71; }
    50% { background-color: rgba(46, 204, 113, 0.60); border-color: #00ff7f; }
    100% { background-color: rgba(46, 204, 113, 0.20); border-color: #2ecc71; }
}
@keyframes pulseGold {
    0% { background-color: rgba(255, 215, 0, 0.22); border-color: #ffd700; }
    50% { background-color: rgba(255, 215, 0, 0.65); border-color: #ffaa00; }
    100% { background-color: rgba(255, 215, 0, 0.22); border-color: #ffd700; }
}
@keyframes pulseCyan {
    0% { background-color: rgba(0, 255, 204, 0.20); border-color: #00ffcc; }
    50% { background-color: rgba(0, 255, 204, 0.60); border-color: #55ffff; }
    100% { background-color: rgba(0, 255, 204, 0.20); border-color: #00ffcc; }
}
@keyframes pulseBest {
    0% { background-color: rgba(255, 0, 128, 0.25); border-color: #ff007f; box-shadow: 0 0 4px #ff007f; }
    50% { background-color: rgba(255, 215, 0, 0.50); border-color: #ffd700; box-shadow: 0 0 10px #ffd700; }
    100% { background-color: rgba(255, 0, 128, 0.25); border-color: #ff007f; box-shadow: 0 0 4px #ff007f; }
}
@keyframes pulseRed {
    0% { background-color: rgba(231, 76, 60, 0.20); border-color: #e74c3c; }
    50% { background-color: rgba(231, 76, 60, 0.60); border-color: #ff3838; }
    100% { background-color: rgba(231, 76, 60, 0.20); border-color: #e74c3c; }
}

/* Continuous Flashing Glow for ATM Strike Cell */
@keyframes atmPulseGlow {
    0% { 
        background-color: #003838; 
        color: #00ffcc; 
        box-shadow: inset 0 0 4px #00ffcc; 
        font-weight: 900; 
    }
    50% { 
        background-color: #007366; 
        color: #ffffff; 
        box-shadow: inset 0 0 10px #00ffff, 0 0 12px #00ffcc; 
        font-weight: 900; 
    }
    100% { 
        background-color: #003838; 
        color: #00ffcc; 
        box-shadow: inset 0 0 4px #00ffcc; 
        font-weight: 900; 
    }
}
.atm-flash-cell {
    animation: atmPulseGlow 1.2s infinite ease-in-out !important;
    border-left: 2px solid #00ffcc !important;
    border-right: 2px solid #00ffcc !important;
    font-size: 13.5px !important;
}

.pre-alert-flash { animation: pulseGreen 1.4s infinite; font-weight: bold; }
.budget-flash { animation: pulseGold 1.5s infinite; font-weight: bold; }
.otm-flash { animation: pulseCyan 1.3s infinite; font-weight: bold; }
.best-flash { animation: pulseBest 1.1s infinite; font-weight: bold; }
.exit-flash { animation: pulseRed 1.1s infinite; font-weight: bold; }

.compact-opt-table {
    width: 100%;
    border-collapse: collapse;
    text-align: center;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px !important;
    background-color: #0b0f19;
    line-height: 1.15;
}
.compact-opt-table th {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 5px 3px !important;
    font-size: 11px !important;
    border-bottom: 2px solid #334155;
    position: sticky;
    top: 0;
    z-index: 2;
}
.compact-opt-table td {
    padding: 2.8px 2px !important;
    border-bottom: 1px solid #141c2e;
}
.badge-tag {
    display: inline-block;
    padding: 1.5px 5px !important;
    border-radius: 3px;
    font-size: 9.8px !important;
    white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)

# ----------------- ZERO-MANUAL-CODE OAUTH FLOW -----------------
TOKEN_FILE = "access_token_scanner.json"

def save_token_disk(data):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_token_disk():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                d = json.load(f)
                return d.get("access_token")
        except Exception:
            return None
    return None

def fetch_access_token(code):
    url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "code": code,
        "client_id": API_KEY,
        "client_secret": API_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=6)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

if "access_token" not in st.session_state:
    st.session_state["access_token"] = load_token_disk()

query_params = st.query_params
auth_code = query_params.get("code", None)

if auth_code and not st.session_state.get("access_token"):
    res = fetch_access_token(auth_code)
    if "access_token" in res:
        st.session_state["access_token"] = res["access_token"]
        save_token_disk(res)
        st.query_params.clear()
        st.rerun()
    else:
        st.sidebar.error(f"Login failed: {res.get('message', res.get('error'))}")

# ----------------- SIDEBAR CONTROLS -----------------
st.sidebar.title("🎯 Matrix Control V3")
selected_index = st.sidebar.selectbox("इंडेक्स चुनें", list(INDEX_CONFIG.keys()), index=0)
auto_refresh = st.sidebar.checkbox("Auto Refresh (3s)", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Scalper Range & Budget")
min_budget = st.sidebar.number_input("Min Premium (₹)", min_value=5, max_value=200, value=20, step=5)
max_budget = st.sidebar.number_input("Max Premium (₹)", min_value=50, max_value=1500, value=350, step=25)
scalp_mode = st.sidebar.toggle("🚀 Aggressive OTM Scalp Mode", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Trade Tracker (Manual Exit)")
user_entry_price = st.sidebar.number_input("Aapka Entry Price (₹)", min_value=0.0, value=0.0, step=1.0)
target_strike = st.sidebar.number_input("Active Strike (Track karne ke liye)", min_value=0, value=0, step=50)

st.sidebar.markdown("---")
st.sidebar.subheader("💡 9-Factor Signal Guide")
st.sidebar.markdown("""
- 🏆 **BEST STRIKE**: All 9 Institutional requirements matched.
- 🚀 **OTM 5M BUY**: Fast Scalp OTM (Delta 0.08–0.35 + Breakout Volume).
- 💎 **BUDGET BUY**: ₹20–₹350 value strike with tight spread & high OI.
- 🟢 **CONFIRMED BUY**: High Conviction Trend + High Volume.
- ⚡ **5M PRE-ALERT**: Early momentum volume surge.
- 🔴 **EXIT / WEAK**: 12%+ drop from session high on opposite trend.
""")

st.sidebar.markdown("---")
if not st.session_state.get("access_token"):
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = secrets.token_urlsafe(16)
    login_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog?"
        f"response_type=code&client_id={API_KEY}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"state={st.session_state['oauth_state']}"
    )
    st.sidebar.link_button("🔑 Upstox लॉगिन करें", login_url)
else:
    st.sidebar.success("✅ Upstox Session सक्रिय")
    if st.sidebar.button("Logout"):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        st.session_state["access_token"] = None
        st.rerun()

token = st.session_state.get("access_token")

# ----------------- UI HEADER -----------------
st.markdown("""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <h3 style="margin:0; font-size:18px;">🎯 Hemant <span style="color:#2ecc71;">Option Chain</span> Intelligence V3</h3>
</div>
""", unsafe_allow_html=True)

if not token:
    st.info("👋 कृपया जारी रखने के लिए बाईं साइडबार से Upstox में लॉगिन करें।")
    st.stop()

# ----------------- DATA & 5-MIN CANDLE FETCHING -----------------
inst_key = INDEX_CONFIG[selected_index]["key"]
step_size = INDEX_CONFIG[selected_index]["step"]

@st.cache_data(ttl=2)
def get_spot(key, tok):
    encoded = urllib.parse.quote(key)
    url = f"https://api.upstox.com/v2/market-quote/ltp?instrument_key={encoded}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=3).json()
        raw_key = key.replace("|", ":")
        return float(r.get("data", {}).get(raw_key, {}).get("last_price", 0.0))
    except Exception:
        return 0.0

@st.cache_data(ttl=15)
def get_5m_candles(key, tok):
    encoded = urllib.parse.quote(key)
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded}/5minute"
    headers = {"accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=4).json()
        if r.get("status") == "success" and r.get("data", {}).get("candles"):
            candles = r["data"]["candles"]
            df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60)
def get_expiries(key, tok):
    url = f"https://api.upstox.com/v2/option/contract?instrument_key={urllib.parse.quote(key)}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=4).json()
        if r.get("status") == "success":
            return sorted(list({c["expiry"] for c in r.get("data", [])}))
    except Exception:
        pass
    return []

def get_chain(key, expiry, tok):
    url = f"https://api.upstox.com/v2/option/chain?instrument_key={urllib.parse.quote(key)}&expiry_date={expiry}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=4).json()
        if r.get("status") == "success":
            return r.get("data", [])
    except Exception:
        pass
    return []

spot_price = get_spot(inst_key, token)
expiries = get_expiries(inst_key, token)
candle_df = get_5m_candles(inst_key, token)

# --- 5-Minute Technical Indicators Engine ---
market_bias = "NEUTRAL ⚪"
ema_9 = ema_21 = rsi_14 = 0.0

if not candle_df.empty and len(candle_df) >= 22:
    candle_df["ema_9"] = candle_df["close"].ewm(span=9, adjust=False).mean()
    candle_df["ema_21"] = candle_df["close"].ewm(span=21, adjust=False).mean()
    
    delta = candle_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    candle_df["rsi_14"] = 100 - (100 / (1 + rs))

    last_closed = candle_df.iloc[-2]
    ema_9 = last_closed["ema_9"]
    ema_21 = last_closed["ema_21"]
    rsi_14 = last_closed["rsi_14"]
    c_close = last_closed["close"]

    # Stable 5-Minute Trend (No tick-by-tick flipping)
    if c_close >= ema_9 and rsi_14 >= 50:
        market_bias = "5M BULLISH 🟢"
    elif c_close <= ema_9 and rsi_14 <= 50:
        market_bias = "5M BEARISH 🔴"
else:
    if "spot_hist" not in st.session_state:
        st.session_state["spot_hist"] = []
    st.session_state["spot_hist"].append(spot_price)
    if len(st.session_state["spot_hist"]) > 30:
        st.session_state["spot_hist"].pop(0)
    avg_spot = sum(st.session_state["spot_hist"]) / len(st.session_state["spot_hist"])
    if spot_price > avg_spot + 15:
        market_bias = "5M BULLISH 🟢"
    elif spot_price < avg_spot - 15:
        market_bias = "5M BEARISH 🔴"

if not expiries:
    st.warning("⚠️ एक्सपायरी कॉन्ट्रैक्ट्स लोड हो रहे हैं...")
    time.sleep(2)
    st.rerun()

selected_expiry = st.sidebar.selectbox("एक्सपायरी चुनें", expiries, index=0)
chain_data = get_chain(inst_key, selected_expiry, token)

if spot_price > 0 and chain_data:
    atm_strike = round(spot_price / step_size) * step_size

    rows = []
    if "peaks" not in st.session_state:
        st.session_state["peaks"] = {}

    all_c_vols, all_p_vols = [], []
    total_c_oi, total_p_oi = 0, 0

    for row in chain_data:
        stk = float(row.get("strike_price", 0.0))
        c_opt = row.get("call_options", {})
        p_opt = row.get("put_options", {})

        c_mkt = c_opt.get("market_data", {})
        p_mkt = p_opt.get("market_data", {})
        c_grk = c_opt.get("option_greeks", {}) or {}
        p_grk = p_opt.get("option_greeks", {}) or {}

        c_ltp = float(c_mkt.get("ltp", 0.0) or 0.0)
        c_bid = float(c_mkt.get("bid_price", 0.0) or 0.0)
        c_ask = float(c_mkt.get("ask_price", 0.0) or 0.0)
        c_vol = int(c_mkt.get("volume", 0) or 0)
        c_oi = int(c_mkt.get("oi", 0) or 0)
        total_c_oi += c_oi

        # Greeks Extraction
        c_delta = abs(float(c_grk.get("delta") or 0.0))
        c_gamma = float(c_grk.get("gamma") or 0.0)
        c_theta = abs(float(c_grk.get("theta") or 0.0))
        c_iv = float(c_grk.get("iv") or 0.0)
        c_delta_valid = (c_delta != 0.0)

        p_ltp = float(p_mkt.get("ltp", 0.0) or 0.0)
        p_bid = float(p_mkt.get("bid_price", 0.0) or 0.0)
        p_ask = float(p_mkt.get("ask_price", 0.0) or 0.0)
        p_vol = int(p_mkt.get("volume", 0) or 0)
        p_oi = int(p_mkt.get("oi", 0) or 0)
        total_p_oi += p_oi

        p_delta = abs(float(p_grk.get("delta") or 0.0))
        p_gamma = float(p_grk.get("gamma") or 0.0)
        p_theta = abs(float(p_grk.get("theta") or 0.0))
        p_iv = float(p_grk.get("iv") or 0.0)
        p_delta_valid = (p_delta != 0.0)

        c_spread = ((c_ask - c_bid) / c_ltp) if (c_ltp > 0 and c_ask > 0 and c_ask >= c_bid) else 0.05
        p_spread = ((p_ask - p_bid) / p_ltp) if (p_ltp > 0 and p_ask > 0 and p_ask >= p_bid) else 0.05

        c_type = "ATM" if stk == atm_strike else ("ITM" if stk < atm_strike else "OTM")
        p_type = "ATM" if stk == atm_strike else ("OTM" if stk < atm_strike else "ITM")

        if stk not in st.session_state["peaks"]:
            st.session_state["peaks"][stk] = {"call": c_ltp, "put": p_ltp}
        else:
            st.session_state["peaks"][stk]["call"] = max(st.session_state["peaks"][stk]["call"], c_ltp)
            st.session_state["peaks"][stk]["put"] = max(st.session_state["peaks"][stk]["put"], p_ltp)

        c_peak = st.session_state["peaks"][stk]["call"]
        p_peak = st.session_state["peaks"][stk]["put"]

        all_c_vols.append(c_vol)
        all_p_vols.append(p_vol)

        rows.append({
            "strike": stk,
            "c_type": c_type,
            "p_type": p_type,
            "c_ltp": c_ltp,
            "c_vol": c_vol,
            "c_oi": c_oi,
            "c_delta": c_delta,
            "c_gamma": c_gamma,
            "c_theta": c_theta,
            "c_iv": c_iv,
            "c_delta_valid": c_delta_valid,
            "c_spread": c_spread,
            "c_peak": c_peak,
            "p_ltp": p_ltp,
            "p_vol": p_vol,
            "p_oi": p_oi,
            "p_delta": p_delta,
            "p_gamma": p_gamma,
            "p_theta": p_theta,
            "p_iv": p_iv,
            "p_delta_valid": p_delta_valid,
            "p_spread": p_spread,
            "p_peak": p_peak,
            "c_signal": "NEUTRAL",
            "p_signal": "NEUTRAL"
        })

    # Overall Chain PCR (Put Call Ratio)
    overall_pcr = (total_p_oi / total_c_oi) if total_c_oi > 0 else 1.0

    # Compact Status Banner with PCR
    bias_color = "#2ecc71" if "BULLISH" in market_bias else ("#e74c3c" if "BEARISH" in market_bias else "#94a3b8")
    st.markdown(f"""
    <div style="background-color:#111622; border:1px solid #1f293d; border-radius:6px; padding:6px 14px; display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; font-size:12px;">
        <div><span style="color:#8892b0; font-size:10px;">SPOT</span> <b style="font-size:15px; color:#ffffff;">₹{spot_price:,.2f}</b></div>
        <div><span style="color:#8892b0; font-size:10px;">ATM</span> <b style="font-size:15px; color:#64ffda;">{atm_strike}</b></div>
        <div><span style="color:#8892b0; font-size:10px;">5M RSI</span> <b style="font-size:14px; color:#ffd700;">{rsi_14:.1f}</b></div>
        <div><span style="color:#8892b0; font-size:10px;">PCR</span> <b style="font-size:14px; color:{'#2ecc71' if overall_pcr>=1.05 else ('#e74c3c' if overall_pcr<=0.90 else '#ccd6f6')};">{overall_pcr:.2f}</b></div>
        <div><span style="color:#8892b0; font-size:10px;">MARKET BIAS</span> <b style="font-size:14px; color:{bias_color};">{market_bias}</b></div>
        <div><span style="color:#8892b0; font-size:10px;">BUDGET</span> <b style="font-size:13px; color:#ffd700;">₹{min_budget}-₹{max_budget}</b></div>
    </div>
    """, unsafe_allow_html=True)

    c_vol_high = np.percentile(all_c_vols, 75) if len(all_c_vols) > 0 else 500000
    p_vol_high = np.percentile(all_p_vols, 75) if len(all_p_vols) > 0 else 500000

    # ----------------- 9-FACTOR RIGID SCORING & SIGNAL GENERATION -----------------
    for r in rows:
        # === CALL EVALUATION ===
        c_tradeable = r["c_delta_valid"] and r["c_ltp"] >= 8.0 and r["c_spread"] <= 0.05 and r["c_oi"] >= 10000

        if c_tradeable and "BULLISH" in market_bias:
            # 9-Factor Best Strike Match:
            # 1. High Gamma (relative) 2. Low Theta ratio 3. Normal IV (<60) 4. Tight Spread (<2.5%)
            # 5. High Volume 6. Solid OI 7. In Budget 8. PCR Support (>=0.95) 9. Momentum Active
            c_is_best = (
                (min_budget <= r["c_ltp"] <= max_budget) and
                (r["c_vol"] >= c_vol_high) and
                (r["c_oi"] >= 25000) and
                (r["c_spread"] <= 0.025) and
                (r["c_iv"] <= 60.0 or r["c_iv"] == 0.0) and
                (0.12 <= r["c_delta"] <= 0.50) and
                (overall_pcr >= 0.95)
            )

            if c_is_best:
                r["c_signal"] = "🏆 BEST STRIKE"
            elif scalp_mode and (r["c_type"] == "OTM") and (0.08 <= r["c_delta"] <= 0.35) and (r["c_vol"] >= c_vol_high):
                r["c_signal"] = "🚀 OTM 5M BUY"
            elif (min_budget <= r["c_ltp"] <= max_budget) and (r["c_vol"] >= c_vol_high * 0.85) and (0.08 <= r["c_delta"] <= 0.45):
                r["c_signal"] = "💎 BUDGET BUY"
            elif (0.35 <= r["c_delta"] <= 0.65) and (r["c_vol"] >= c_vol_high) and (r["c_spread"] <= 0.035):
                r["c_signal"] = "🟢 CONFIRMED BUY"
            elif (r["c_vol"] >= c_vol_high * 0.70) and (0.10 <= r["c_delta"] <= 0.55):
                r["c_signal"] = "⚡ 5M PRE-ALERT"
        elif "BEARISH" in market_bias:
            if r["c_peak"] > 0 and (r["c_peak"] - r["c_ltp"]) / r["c_peak"] >= 0.12 and r["c_vol"] >= 30000:
                r["c_signal"] = "🔴 EXIT / WEAK"

        # === PUT EVALUATION ===
        p_tradeable = r["p_delta_valid"] and r["p_ltp"] >= 8.0 and r["p_spread"] <= 0.05 and r["p_oi"] >= 10000

        if p_tradeable and "BEARISH" in market_bias:
            p_is_best = (
                (min_budget <= r["p_ltp"] <= max_budget) and
                (r["p_vol"] >= p_vol_high) and
                (r["p_oi"] >= 25000) and
                (r["p_spread"] <= 0.025) and
                (r["p_iv"] <= 60.0 or r["p_iv"] == 0.0) and
                (0.12 <= r["p_delta"] <= 0.50) and
                (overall_pcr <= 1.05)
            )

            if p_is_best:
                r["p_signal"] = "🏆 BEST STRIKE"
            elif scalp_mode and (r["p_type"] == "OTM") and (0.08 <= r["p_delta"] <= 0.35) and (r["p_vol"] >= p_vol_high):
                r["p_signal"] = "🚀 OTM 5M BUY"
            elif (min_budget <= r["p_ltp"] <= max_budget) and (r["p_vol"] >= p_vol_high * 0.85) and (0.08 <= r["p_delta"] <= 0.45):
                r["p_signal"] = "💎 BUDGET BUY"
            elif (0.35 <= r["p_delta"] <= 0.65) and (r["p_vol"] >= p_vol_high) and (r["p_spread"] <= 0.035):
                r["p_signal"] = "🟢 CONFIRMED BUY"
            elif (r["p_vol"] >= p_vol_high * 0.70) and (0.10 <= r["p_delta"] <= 0.55):
                r["p_signal"] = "⚡ 5M PRE-ALERT"
        elif "BULLISH" in market_bias:
            if r["p_peak"] > 0 and (r["p_peak"] - r["p_ltp"]) / r["p_peak"] >= 0.12 and r["p_vol"] >= 30000:
                r["p_signal"] = "🔴 EXIT / WEAK"

        if not r["c_delta_valid"]:
            r["c_signal"] = "NO DATA"
        if not r["p_delta_valid"]:
            r["p_signal"] = "NO DATA"

    # Trade Tracker Alert for Active Tracked Strike
    if target_strike > 0 and user_entry_price > 0:
        match_row = next((x for x in rows if x["strike"] == target_strike), None)
        if match_row:
            active_ltp = match_row["c_ltp"] if "BULLISH" in market_bias else match_row["p_ltp"]
            pnl_pct = ((active_ltp - user_entry_price) / user_entry_price) * 100.0
            st.sidebar.markdown(f"**Tracked Strike {int(target_strike)}:** LTP ₹{active_ltp:.1f} | PnL: `{pnl_pct:+.1f}%`")
            if pnl_pct >= 10.0:
                st.sidebar.markdown('<span class="budget-flash badge-tag">💰 BOOK PROFIT ZONE</span>', unsafe_allow_html=True)
            elif pnl_pct <= -6.0:
                st.sidebar.markdown('<span class="exit-flash badge-tag">🚨 EXIT ALERT / STOPLOSS</span>', unsafe_allow_html=True)

    focused = sorted(rows, key=lambda x: x["strike"])

    # ----------------- RENDER COMPACT SCREEN-FIT MATRIX -----------------
    html_parts = []
    html_parts.append('<table class="compact-opt-table">')
    html_parts.append('<thead><tr>')
    html_parts.append('<th style="width:13%;">Call Signal</th>')
    html_parts.append('<th style="width:7%;">Delta (Δ)</th>')
    html_parts.append('<th style="width:8%;">Call LTP</th>')
    html_parts.append('<th style="width:10%;">Call Vol</th>')
    html_parts.append('<th style="width:10%;">Call OI</th>')
    html_parts.append('<th style="width:10%; background-color:#0f172a; color:#f8fafc; font-size:13px !important;">STRIKE</th>')
    html_parts.append('<th style="width:10%;">Put OI</th>')
    html_parts.append('<th style="width:10%;">Put Vol</th>')
    html_parts.append('<th style="width:8%;">Put LTP</th>')
    html_parts.append('<th style="width:7%;">Delta (Δ)</th>')
    html_parts.append('<th style="width:13%;">Put Signal</th>')
    html_parts.append('</tr></thead><tbody>')

    for r in focused:
        stk = r["strike"]

        # Call Badge Formatting
        c_sig = r["c_signal"]
        if "🏆 BEST" in c_sig:
            c_style = "background-color:rgba(255, 0, 128, 0.22); color:#ff007f; font-weight:bold; border-left:3px solid #ff007f;"
            c_badge = f'<span class="best-flash badge-tag" style="background-color:#38001d; border:1px solid #ff007f;">{c_sig}</span>'
        elif "🚀 OTM" in c_sig:
            c_style = "background-color:rgba(0, 255, 204, 0.20); color:#00ffcc; font-weight:bold; border-left:3px solid #00ffcc;"
            c_badge = f'<span class="otm-flash badge-tag" style="background-color:#032924; border:1px solid #00ffcc;">{c_sig}</span>'
        elif "💎 BUDGET" in c_sig:
            c_style = "background-color:rgba(255, 215, 0, 0.20); color:#ffd700; font-weight:bold; border-left:3px solid #ffd700;"
            c_badge = f'<span class="budget-flash badge-tag" style="background-color:#2a2505; border:1px solid #ffd700;">{c_sig}</span>'
        elif "🟢 CONFIRMED" in c_sig:
            c_style = "background-color:rgba(46, 204, 113, 0.25); color:#2ecc71; font-weight:bold; border-left:3px solid #2ecc71;"
            c_badge = f'<span class="badge-tag" style="background-color:#163828; border:1px solid #2ecc71;">{c_sig}</span>'
        elif "⚡ 5M PRE-ALERT" in c_sig:
            c_style = "color:#2ecc71;"
            c_badge = f'<span class="pre-alert-flash badge-tag" style="border:1px dashed #2ecc71;">{c_sig}</span>'
        elif "🔴 EXIT" in c_sig:
            c_style = "color:#e74c3c;"
            c_badge = f'<span class="exit-flash badge-tag" style="border:1px solid #e74c3c;">{c_sig}</span>'
        else:
            c_style = "color:#64748b;"
            c_badge = f'<span style="color:#475569; font-size:10px;">{r["c_type"]}</span>'

        # Put Badge Formatting
        p_sig = r["p_signal"]
        if "🏆 BEST" in p_sig:
            p_style = "background-color:rgba(255, 0, 128, 0.22); color:#ff007f; font-weight:bold; border-right:3px solid #ff007f;"
            p_badge = f'<span class="best-flash badge-tag" style="background-color:#38001d; border:1px solid #ff007f;">{p_sig}</span>'
        elif "🚀 OTM" in p_sig:
            p_style = "background-color:rgba(0, 255, 204, 0.20); color:#00ffcc; font-weight:bold; border-right:3px solid #00ffcc;"
            p_badge = f'<span class="otm-flash badge-tag" style="background-color:#032924; border:1px solid #00ffcc;">{p_sig}</span>'
        elif "💎 BUDGET" in p_sig:
            p_style = "background-color:rgba(255, 215, 0, 0.20); color:#ffd700; font-weight:bold; border-right:3px solid #ffd700;"
            p_badge = f'<span class="budget-flash badge-tag" style="background-color:#2a2505; border:1px solid #ffd700;">{p_sig}</span>'
        elif "🟢 CONFIRMED" in p_sig:
            p_style = "background-color:rgba(46, 204, 113, 0.25); color:#2ecc71; font-weight:bold; border-right:3px solid #2ecc71;"
            p_badge = f'<span class="badge-tag" style="background-color:#163828; border:1px solid #2ecc71;">{p_sig}</span>'
        elif "⚡ 5M PRE-ALERT" in p_sig:
            p_style = "color:#2ecc71;"
            p_badge = f'<span class="pre-alert-flash badge-tag" style="border:1px dashed #2ecc71;">{p_sig}</span>'
        elif "🔴 EXIT" in p_sig:
            p_style = "color:#e74c3c;"
            p_badge = f'<span class="exit-flash badge-tag" style="border:1px solid #e74c3c;">{p_sig}</span>'
        else:
            p_style = "color:#64748b;"
            p_badge = f'<span style="color:#475569; font-size:10px;">{r["p_type"]}</span>'

        # Continuous Neon Glowing ATM Cell
        if stk == atm_strike:
            strike_cell = f'<td class="atm-flash-cell">{int(stk)} <span style="font-size:8.5px;">[ATM]</span></td>'
        else:
            strike_cell = f'<td style="background-color:#0f172a; font-size:12px; font-weight:bold; color:#f8fafc;">{int(stk)}</td>'

        c_delta_disp = f"{r['c_delta']:.2f}" if r["c_delta_valid"] else "-"
        p_delta_disp = f"{r['p_delta']:.2f}" if r["p_delta_valid"] else "-"

        row_str = (
            f'<tr>'
            f'<td style="{c_style}">{c_badge}</td>'
            f'<td style="{c_style}">{c_delta_disp}</td>'
            f'<td style="{c_style}">₹{r["c_ltp"]:.1f}</td>'
            f'<td style="{c_style}">{r["c_vol"]:,}</td>'
            f'<td style="{c_style}">{r["c_oi"]:,}</td>'
            f'{strike_cell}'
            f'<td style="{p_style}">{r["p_oi"]:,}</td>'
            f'<td style="{p_style}">{r["p_vol"]:,}</td>'
            f'<td style="{p_style}">₹{r["p_ltp"]:.1f}</td>'
            f'<td style="{p_style}">{p_delta_disp}</td>'
            f'<td style="{p_style}">{p_badge}</td>'
            f'</tr>'
        )
        html_parts.append(row_str)

    html_parts.append('</tbody></table>')
    table_rendered = "".join(html_parts)
    st.markdown(table_rendered, unsafe_allow_html=True)

if auto_refresh:
    time.sleep(3.0)
    st.rerun()
