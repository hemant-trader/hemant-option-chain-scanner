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

# ----------------- CSS FOR PULSING SIGNALS & BADGES -----------------
st.markdown("""
<style>
@keyframes pulseGreen {
    0% { background-color: rgba(46, 204, 113, 0.15); border-color: #2ecc71; }
    50% { background-color: rgba(46, 204, 113, 0.45); border-color: #00ff7f; }
    100% { background-color: rgba(46, 204, 113, 0.15); border-color: #2ecc71; }
}
@keyframes pulseGold {
    0% { background-color: rgba(255, 215, 0, 0.15); border-color: #ffd700; }
    50% { background-color: rgba(255, 215, 0, 0.45); border-color: #ffaa00; }
    100% { background-color: rgba(255, 215, 0, 0.15); border-color: #ffd700; }
}
@keyframes pulseRed {
    0% { background-color: rgba(231, 76, 60, 0.15); border-color: #e74c3c; }
    50% { background-color: rgba(231, 76, 60, 0.50); border-color: #ff3838; }
    100% { background-color: rgba(231, 76, 60, 0.15); border-color: #e74c3c; }
}
.pre-alert-flash { animation: pulseGreen 1.4s infinite; font-weight: bold; }
.budget-flash { animation: pulseGold 1.5s infinite; font-weight: bold; }
.exit-flash { animation: pulseRed 1.1s infinite; font-weight: bold; }
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

# Silent OAuth Code Capture on URL Callback
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
max_budget = st.sidebar.number_input("Max Premium (₹)", min_value=50, max_value=1200, value=350, step=25)
scalp_mode = st.sidebar.toggle("🚀 Aggressive OTM Scalp Mode", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Trade Tracker (Manual Exit)")
user_entry_price = st.sidebar.number_input("Aapka Entry Price (₹)", min_value=0.0, value=0.0, step=1.0)
target_strike = st.sidebar.number_input("Active Strike (Track karne ke liye)", min_value=0, value=0, step=50)

st.sidebar.markdown("---")
st.sidebar.subheader("💡 Signal Guide")
st.sidebar.markdown("""
- 💎 **BUDGET PICK**: ₹20–₹350 me high momentum strike.
- 🚀 **OTM SCALP**: Dynamic Delta (0.15–0.38) with 5M volume breakout.
- 🟢 **CONFIRMED 5M BUY**: 5-Min Candle close + EMA/RSI confirmed.
- ⚡ **PRE-ALERT**: Live candle momentum build up.
- 🔴 **BOOK PROFIT / EXIT**: Momentum peak decline / Trend reversal.
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
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
    <h2 style="margin:0;">🎯 Hemant <span style="color:#2ecc71;">Option Chain</span> Intelligence V3</h2>
</div>
""", unsafe_allow_html=True)

if not token:
    st.info("👋 कृपया जारी रखने के लिए बाईं साइडबार से Upstox में लॉगिन करें। (लॉगिन के बाद कोई कोड डालने की जरूरत नहीं)")
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

# --- 5-Minute Technical Indicators ---
market_bias = "NEUTRAL ⚪"
ema_9 = ema_21 = rsi_14 = 0.0
candle_closed_bullish = candle_closed_bearish = False

if not candle_df.empty and len(candle_df) >= 22:
    candle_df["ema_9"] = candle_df["close"].ewm(span=9, adjust=False).mean()
    candle_df["ema_21"] = candle_df["close"].ewm(span=21, adjust=False).mean()
    
    # RSI 14
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

    if c_close > ema_9 > ema_21 and rsi_14 >= 52:
        market_bias = "5M BULLISH 🟢"
        candle_closed_bullish = True
    elif c_close < ema_9 < ema_21 and rsi_14 <= 48:
        market_bias = "5M BEARISH 🔴"
        candle_closed_bearish = True

if not expiries:
    st.warning("⚠️ एक्सपायरी कॉन्ट्रैक्ट्स लोड हो रहे हैं...")
    time.sleep(2)
    st.rerun()

selected_expiry = st.sidebar.selectbox("एक्सपायरी चुनें", expiries, index=0)
chain_data = get_chain(inst_key, selected_expiry, token)

if spot_price > 0 and chain_data:
    atm_strike = round(spot_price / step_size) * step_size

    # Top Status Banner
    st.markdown(f"""
    <div style="background-color:#111622; border:1px solid #1f293d; border-radius:8px; padding:10px 18px; display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div><span style="color:#8892b0; font-size:11px;">SPOT PRICE</span><br><b style="font-size:20px; color:#ffffff;">₹{spot_price:,.2f}</b></div>
        <div><span style="color:#8892b0; font-size:11px;">ATM STRIKE</span><br><b style="font-size:19px; color:#64ffda;">{atm_strike}</b></div>
        <div><span style="color:#8892b0; font-size:11px;">5M RSI (14)</span><br><b style="font-size:18px; color:#ffd700;">{rsi_14:.1f}</b></div>
        <div><span style="color:#8892b0; font-size:11px;">5M TREND</span><br><b style="font-size:17px; color:{'#2ecc71' if 'BULLISH' in market_bias else ('#e74c3c' if 'BEARISH' in market_bias else '#94a3b8')};">{market_bias}</b></div>
        <div><span style="color:#8892b0; font-size:11px;">EXPIRY</span><br><b style="font-size:17px; color:#ccd6f6;">{selected_expiry}</b></div>
    </div>
    """, unsafe_allow_html=True)

    rows = []

    # Store peak prices in session state for momentum profit-booking
    if "peaks" not in st.session_state:
        st.session_state["peaks"] = {}

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

        # Delta validation: NO ESTIMATED DELTA ALLOWED FOR BUY SIGNALS
        c_delta_raw = c_grk.get("delta")
        c_delta_valid = (c_delta_raw is not None and float(c_delta_raw) != 0.0)
        c_delta = abs(float(c_delta_raw)) if c_delta_valid else 0.0

        p_ltp = float(p_mkt.get("ltp", 0.0) or 0.0)
        p_bid = float(p_mkt.get("bid_price", 0.0) or 0.0)
        p_ask = float(p_mkt.get("ask_price", 0.0) or 0.0)
        p_vol = int(p_mkt.get("volume", 0) or 0)
        p_oi = int(p_mkt.get("oi", 0) or 0)

        p_delta_raw = p_grk.get("delta")
        p_delta_valid = (p_delta_raw is not None and float(p_delta_raw) != 0.0)
        p_delta = abs(float(p_delta_raw)) if p_delta_valid else 0.0

        # Spread Filter: Disqualify high spreads
        c_spread = ((c_ask - c_bid) / c_ltp) if (c_ltp > 0 and c_ask > 0 and c_ask >= c_bid) else 1.0
        p_spread = ((p_ask - p_bid) / p_ltp) if (p_ltp > 0 and p_ask > 0 and p_ask >= p_bid) else 1.0

        c_type = "ATM" if stk == atm_strike else ("ITM" if stk < atm_strike else "OTM")
        p_type = "ATM" if stk == atm_strike else ("OTM" if stk < atm_strike else "ITM")

        # Track Peaks for Active Strike
        if stk not in st.session_state["peaks"]:
            st.session_state["peaks"][stk] = {"call": c_ltp, "put": p_ltp}
        else:
            st.session_state["peaks"][stk]["call"] = max(st.session_state["peaks"][stk]["call"], c_ltp)
            st.session_state["peaks"][stk]["put"] = max(st.session_state["peaks"][stk]["put"], p_ltp)

        c_peak = st.session_state["peaks"][stk]["call"]
        p_peak = st.session_state["peaks"][stk]["put"]

        # Call Scoring Logic (100 Pts)
        c_score = 0.0
        c_signal = "NEUTRAL"
        if c_ltp >= 8.0 and c_vol >= 15000 and c_oi >= 5000 and c_spread <= 0.03 and c_delta_valid:
            vol_score = min(25.0, (math.log10(max(10, c_vol)) / 6.0) * 25.0)
            oi_score = min(15.0, (math.log10(max(10, c_oi)) / 5.5) * 15.0)
            delta_target = 0.55 if c_type == "ITM" else (0.50 if c_type == "ATM" else 0.30)
            delta_score = max(0.0, 1.0 - (abs(c_delta - delta_target) / 0.20)) * 25.0
            spread_score = max(0.0, 1.0 - (c_spread / 0.03)) * 15.0
            mom_score = 20.0 if candle_closed_bullish else (8.0 if "BULLISH" in market_bias else 0.0)
            c_score = vol_score + oi_score + delta_score + spread_score + mom_score

            c_is_budget = (min_budget <= c_ltp <= max_budget)
            c_is_otm_scalp = scalp_mode and (c_type == "OTM") and (0.15 <= c_delta <= 0.38) and (c_vol >= 35000)

            # Signal Hierarchy
            if candle_closed_bullish and c_score >= 75.0:
                if c_is_otm_scalp:
                    c_signal = "🚀 OTM 5M BUY"
                elif c_is_budget:
                    c_signal = "💎 BUDGET BUY"
                else:
                    c_signal = "🟢 CONFIRMED BUY"
            elif "BULLISH" in market_bias and c_score >= 60.0:
                c_signal = "⚡ 5M PRE-ALERT"
            elif candle_closed_bearish or (c_peak > 0 and (c_peak - c_ltp) / c_peak >= 0.06):
                c_signal = "🔴 EXIT/BOOK"
        elif not c_delta_valid:
            c_signal = "NO GREEK DATA"

        # Put Scoring Logic (100 Pts)
        p_score = 0.0
        p_signal = "NEUTRAL"
        if p_ltp >= 8.0 and p_vol >= 15000 and p_oi >= 5000 and p_spread <= 0.03 and p_delta_valid:
            vol_score = min(25.0, (math.log10(max(10, p_vol)) / 6.0) * 25.0)
            oi_score = min(15.0, (math.log10(max(10, p_oi)) / 5.5) * 15.0)
            delta_target = 0.55 if p_type == "ITM" else (0.50 if p_type == "ATM" else 0.30)
            delta_score = max(0.0, 1.0 - (abs(p_delta - delta_target) / 0.20)) * 25.0
            spread_score = max(0.0, 1.0 - (p_spread / 0.03)) * 15.0
            mom_score = 20.0 if candle_closed_bearish else (8.0 if "BEARISH" in market_bias else 0.0)
            p_score = vol_score + oi_score + delta_score + spread_score + mom_score

            p_is_budget = (min_budget <= p_ltp <= max_budget)
            p_is_otm_scalp = scalp_mode and (p_type == "OTM") and (0.15 <= p_delta <= 0.38) and (p_vol >= 35000)

            if candle_closed_bearish and p_score >= 75.0:
                if p_is_otm_scalp:
                    p_signal = "🚀 OTM 5M BUY"
                elif p_is_budget:
                    p_signal = "💎 BUDGET BUY"
                else:
                    p_signal = "🟢 CONFIRMED BUY"
            elif "BEARISH" in market_bias and p_score >= 60.0:
                p_signal = "⚡ 5M PRE-ALERT"
            elif candle_closed_bullish or (p_peak > 0 and (p_peak - p_ltp) / p_peak >= 0.06):
                p_signal = "🔴 EXIT/BOOK"
        elif not p_delta_valid:
            p_signal = "NO GREEK DATA"

        # Trade Tracker Alert for Active Strike
        if target_strike > 0 and stk == target_strike and user_entry_price > 0:
            active_ltp = c_ltp if "BULLISH" in market_bias else p_ltp
            pnl_pct = ((active_ltp - user_entry_price) / user_entry_price) * 100.0
            st.sidebar.markdown(f"**Tracked Strike {int(stk)}:** LTP ₹{active_ltp:.1f} | PnL: `{pnl_pct:+.1f}%`")
            if pnl_pct >= 12.0:
                st.sidebar.markdown('<span class="budget-flash" style="padding:4px 8px; border-radius:4px;">💰 BOOK PROFIT ZONE</span>', unsafe_allow_html=True)
            elif pnl_pct <= -7.0 or ("EXIT" in c_signal or "EXIT" in p_signal):
                st.sidebar.markdown('<span class="exit-flash" style="padding:4px 8px; border-radius:4px;">🚨 EXIT ALERT / STOPLOSS</span>', unsafe_allow_html=True)

        rows.append({
            "strike": stk,
            "c_type": c_type,
            "p_type": p_type,
            "c_ltp": c_ltp,
            "c_vol": c_vol,
            "c_oi": c_oi,
            "c_delta": c_delta,
            "c_delta_valid": c_delta_valid,
            "c_signal": c_signal,
            "p_ltp": p_ltp,
            "p_vol": p_vol,
            "p_oi": p_oi,
            "p_delta": p_delta,
            "p_delta_valid": p_delta_valid,
            "p_signal": p_signal,
        })

    # Show ALL strikes sorted ascending (No Truncation)
    focused = sorted(rows, key=lambda x: x["strike"])

    # ----------------- RENDER FULL OPTION MATRIX -----------------
    html_parts = []
    html_parts.append('<table style="width:100%; border-collapse:collapse; text-align:center; font-family:monospace; font-size:12.5px; background-color:#0b0f19;">')
    html_parts.append('<thead><tr style="background-color:#1e293b; color:#94a3b8; border-bottom:2px solid #334155;">')
    html_parts.append('<th style="padding:10px;">Call Signal</th>')
    html_parts.append('<th>Delta (Δ)</th>')
    html_parts.append('<th>Call LTP</th>')
    html_parts.append('<th>Call Vol</th>')
    html_parts.append('<th>Call OI</th>')
    html_parts.append('<th style="background-color:#0f172a; color:#f8fafc; font-size:15px; width:120px;">STRIKE</th>')
    html_parts.append('<th>Put OI</th>')
    html_parts.append('<th>Put Vol</th>')
    html_parts.append('<th>Put LTP</th>')
    html_parts.append('<th>Delta (Δ)</th>')
    html_parts.append('<th style="padding:10px;">Put Signal</th>')
    html_parts.append('</tr></thead><tbody>')

    for r in focused:
        stk = r["strike"]

        # Call Badge Styling
        c_sig = r["c_signal"]
        if "🚀 OTM" in c_sig:
            c_style = "background-color:rgba(0, 255, 204, 0.18); color:#00ffcc; font-weight:bold; border-left:4px solid #00ffcc;"
            c_badge = f'<span class="pre-alert-flash" style="background-color:#032924; border:1px solid #00ffcc; border-radius:4px; padding:2px 6px;">{c_sig}</span>'
        elif "💎 BUDGET" in c_sig:
            c_style = "background-color:rgba(255, 215, 0, 0.16); color:#ffd700; font-weight:bold; border-left:4px solid #ffd700;"
            c_badge = f'<span class="budget-flash" style="background-color:#2a2505; border:1px solid #ffd700; border-radius:4px; padding:2px 6px;">{c_sig}</span>'
        elif "🟢 CONFIRMED" in c_sig:
            c_style = "background-color:rgba(46, 204, 113, 0.25); color:#2ecc71; font-weight:bold; border-left:4px solid #2ecc71;"
            c_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 6px;">{c_sig}</span>'
        elif "⚡ 5M PRE-ALERT" in c_sig:
            c_style = "color:#2ecc71;"
            c_badge = f'<span class="pre-alert-flash" style="border:1px dashed #2ecc71; border-radius:4px; padding:2px 6px;">{c_sig}</span>'
        elif "🔴 EXIT" in c_sig:
            c_style = "color:#e74c3c;"
            c_badge = f'<span class="exit-flash" style="border:1px solid #e74c3c; border-radius:4px; padding:2px 6px;">{c_sig}</span>'
        else:
            c_style = "color:#64748b;"
            c_badge = f'<span style="color:#475569;">{r["c_type"]}</span>'

        # Put Badge Styling
        p_sig = r["p_signal"]
        if "🚀 OTM" in p_sig:
            p_style = "background-color:rgba(0, 255, 204, 0.18); color:#00ffcc; font-weight:bold; border-right:4px solid #00ffcc;"
            p_badge = f'<span class="pre-alert-flash" style="background-color:#032924; border:1px solid #00ffcc; border-radius:4px; padding:2px 6px;">{p_sig}</span>'
        elif "💎 BUDGET" in p_sig:
            p_style = "background-color:rgba(255, 215, 0, 0.16); color:#ffd700; font-weight:bold; border-right:4px solid #ffd700;"
            p_badge = f'<span class="budget-flash" style="background-color:#2a2505; border:1px solid #ffd700; border-radius:4px; padding:2px 6px;">{p_sig}</span>'
        elif "🟢 CONFIRMED" in p_sig:
            p_style = "background-color:rgba(46, 204, 113, 0.25); color:#2ecc71; font-weight:bold; border-right:4px solid #2ecc71;"
            p_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 6px;">{p_sig}</span>'
        elif "⚡ 5M PRE-ALERT" in p_sig:
            p_style = "color:#2ecc71;"
            p_badge = f'<span class="pre-alert-flash" style="border:1px dashed #2ecc71; border-radius:4px; padding:2px 6px;">{p_sig}</span>'
        elif "🔴 EXIT" in p_sig:
            p_style = "color:#e74c3c;"
            p_badge = f'<span class="exit-flash" style="border:1px solid #e74c3c; border-radius:4px; padding:2px 6px;">{p_sig}</span>'
        else:
            p_style = "color:#64748b;"
            p_badge = f'<span style="color:#475569;">{r["p_type"]}</span>'

        mid_bg = "#1e293b; font-weight:bold; color:#64ffda;" if stk == atm_strike else "#0f172a; color:#f8fafc;"
        c_delta_disp = f"{r['c_delta']:.2f}" if r["c_delta_valid"] else "-"
        p_delta_disp = f"{r['p_delta']:.2f}" if r["p_delta_valid"] else "-"

        row_str = (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:7px; {c_style}">{c_badge}</td>'
            f'<td style="{c_style}">{c_delta_disp}</td>'
            f'<td style="{c_style}">₹{r["c_ltp"]:.1f}</td>'
            f'<td style="{c_style}">{r["c_vol"]:,}</td>'
            f'<td style="{c_style}">{r["c_oi"]:,}</td>'
            f'<td style="background-color:{mid_bg}; font-size:14px;">{int(stk)}</td>'
            f'<td style="{p_style}">{r["p_oi"]:,}</td>'
            f'<td style="{p_style}">{r["p_vol"]:,}</td>'
            f'<td style="{p_style}">₹{r["p_ltp"]:.1f}</td>'
            f'<td style="{p_style}">{p_delta_disp}</td>'
            f'<td style="padding:7px; {p_style}">{p_badge}</td>'
            f'</tr>'
        )
        html_parts.append(row_str)

    html_parts.append('</tbody></table>')
    table_rendered = "".join(html_parts)
    st.markdown(table_rendered, unsafe_allow_html=True)

if auto_refresh:
    time.sleep(3.0)
    st.rerun()
