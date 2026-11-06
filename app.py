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

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="Hemant Option Chain Intelligence Scanner V2",
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
    REDIRECT_URI = "https://your-new-scanner.streamlit.app/"

INDEX_CONFIG = {
    "NIFTY 50": {"key": "NSE_INDEX|Nifty 50", "step": 50},
    "BANKNIFTY": {"key": "NSE_INDEX|Nifty Bank", "step": 100},
    "SENSEX": {"key": "BSE_INDEX|SENSEX", "step": 100},
}

# ----------------- CSS FOR PULSING PRE-ALERT -----------------
st.markdown("""
<style>
@keyframes pulseGreen {
    0% { background-color: rgba(46, 204, 113, 0.15); border-color: #2ecc71; }
    50% { background-color: rgba(46, 204, 113, 0.45); border-color: #00ff7f; }
    100% { background-color: rgba(46, 204, 113, 0.15); border-color: #2ecc71; }
}
.pre-alert-flash {
    animation: pulseGreen 1.5s infinite;
    font-weight: bold;
}
.best-confirmed {
    background-color: rgba(46, 204, 113, 0.30) !important;
    color: #2ecc71 !important;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ----------------- TOKEN / OAUTH FLOW -----------------
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

# Auto-capture OAuth code from URL
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
        st.error(f"Login विफल: {res.get('message', res.get('error'))}")

# ----------------- SIDEBAR -----------------
st.sidebar.title("🎯 Matrix Control")
selected_index = st.sidebar.selectbox("इंडेक्स चुनें", list(INDEX_CONFIG.keys()), index=0)
auto_refresh = st.sidebar.checkbox("Auto Refresh (3s)", value=True)
strikes_count = st.sidebar.slider("ATM के आसपास स्ट्राइक संख्या", 8, 26, 14, 2)

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
    manual_code = st.sidebar.text_input("या Authorization Code यहाँ डालें:")
    if st.sidebar.button("Connect"):
        if manual_code:
            res = fetch_access_token(manual_code.strip())
            if "access_token" in res:
                st.session_state["access_token"] = res["access_token"]
                save_token_disk(res)
                st.query_params.clear()
                st.rerun()
            else:
                st.sidebar.error("अमान्य कोड")
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
    <h2 style="margin:0;">🎯 Hemant <span style="color:#2ecc71;">Option Chain</span> Intelligence V2</h2>
</div>
""", unsafe_allow_html=True)

if not token:
    st.info("👋 कृपया जारी रखने के लिए बाईं साइडबार से Upstox में लॉगिन करें।")
    st.stop()

# ----------------- DATA FETCHING -----------------
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
        <div><span style="color:#8892b0; font-size:11px;">EXPIRY</span><br><b style="font-size:17px; color:#ccd6f6;">{selected_expiry}</b></div>
        <div><span style="color:#8892b0; font-size:11px;">STATUS</span><br><span style="background-color:#163828; color:#2ecc71; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px;">ACTIVE GREEKS</span></div>
    </div>
    """, unsafe_allow_html=True)

    rows = []

    # ----------------- PARSE & SCORE STRIKES -----------------
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
        c_delta = abs(float(c_grk.get("delta", 0.0) or 0.0))
        c_iv = float(c_grk.get("iv", 0.0) or 0.0)

        p_ltp = float(p_mkt.get("ltp", 0.0) or 0.0)
        p_bid = float(p_mkt.get("bid_price", 0.0) or 0.0)
        p_ask = float(p_mkt.get("ask_price", 0.0) or 0.0)
        p_vol = int(p_mkt.get("volume", 0) or 0)
        p_oi = int(p_mkt.get("oi", 0) or 0)
        p_delta = abs(float(p_grk.get("delta", 0.0) or 0.0))
        p_iv = float(p_grk.get("iv", 0.0) or 0.0)

        # Spreads
        c_spread = ((c_ask - c_bid) / c_ltp) if c_ltp > 0 and c_ask > 0 else 0.08
        p_spread = ((p_ask - p_bid) / p_ltp) if p_ltp > 0 and p_ask > 0 else 0.08

        # Fallback delta approximation
        if c_delta == 0.0:
            c_delta = max(0.1, min(0.9, 0.50 + ((spot_price - stk) / spot_price) * 3.0))
        if p_delta == 0.0:
            p_delta = max(0.1, min(0.9, 0.50 + ((stk - spot_price) / spot_price) * 3.0))

        c_type = "ATM" if stk == atm_strike else ("ITM" if stk < atm_strike else "OTM")
        p_type = "ATM" if stk == atm_strike else ("OTM" if stk < atm_strike else "ITM")

        c_score = 0.0
        if c_ltp >= 10.0 and c_spread <= 0.06:
            vol_score = min(1.0, math.log10(max(10, c_vol)) / 5.5) * 40.0
            delta_target = 0.58 if c_type == "ITM" else (0.50 if c_type == "ATM" else 0.38)
            delta_score = max(0.0, 1.0 - (abs(c_delta - delta_target) / 0.20)) * 40.0
            spread_score = max(0.0, 1.0 - (c_spread / 0.06)) * 20.0
            c_score = vol_score + delta_score + spread_score

        p_score = 0.0
        if p_ltp >= 10.0 and p_spread <= 0.06:
            vol_score = min(1.0, math.log10(max(10, p_vol)) / 5.5) * 40.0
            delta_target = 0.58 if p_type == "ITM" else (0.50 if p_type == "ATM" else 0.38)
            delta_score = max(0.0, 1.0 - (abs(p_delta - delta_target) / 0.20)) * 40.0
            spread_score = max(0.0, 1.0 - (p_spread / 0.06)) * 20.0
            p_score = vol_score + delta_score + spread_score

        rows.append({
            "strike": stk,
            "c_type": c_type,
            "p_type": p_type,
            "c_ltp": c_ltp,
            "c_vol": c_vol,
            "c_oi": c_oi,
            "c_delta": c_delta,
            "c_score": c_score,
            "p_ltp": p_ltp,
            "p_vol": p_vol,
            "p_oi": p_oi,
            "p_delta": p_delta,
            "p_score": p_score,
            "dist": abs(stk - atm_strike)
        })

    rows.sort(key=lambda x: x["dist"])
    focused = rows[:strikes_count]
    focused.sort(key=lambda x: x["strike"])

    # ----------------- CRASH-FREE WINNER EVALUATION -----------------
    def find_best_and_prealert(candidates):
        if not candidates:
            return None, None
        sorted_cand = sorted(candidates, key=lambda x: x[1], reverse=True)
        winner = sorted_cand[0] if sorted_cand[0][1] >= 65.0 else None
        pre_alert = None
        if not winner and len(sorted_cand) > 0 and sorted_cand[0][1] >= 52.0:
            pre_alert = sorted_cand[0]
        elif winner and len(sorted_cand) > 1 and sorted_cand[1][1] >= 55.0:
            pre_alert = sorted_cand[1]
        return winner, pre_alert

    # Calls
    c_itm_cands = [(r["strike"], r["c_score"]) for r in focused if r["c_type"] == "ITM" and r["dist"] <= step_size * 2]
    c_atm_cands = [(r["strike"], r["c_score"]) for r in focused if r["c_type"] == "ATM"]
    c_otm_cands = [(r["strike"], r["c_score"]) for r in focused if r["c_type"] == "OTM" and r["dist"] <= step_size * 2]

    best_c_itm, pre_c_itm = find_best_and_prealert(c_itm_cands)
    best_c_atm, pre_c_atm = find_best_and_prealert(c_atm_cands)
    best_c_otm, pre_c_otm = find_best_and_prealert(c_otm_cands)

    # Puts
    p_itm_cands = [(r["strike"], r["p_score"]) for r in focused if r["p_type"] == "ITM" and r["dist"] <= step_size * 2]
    p_atm_cands = [(r["strike"], r["p_score"]) for r in focused if r["p_type"] == "ATM"]
    p_otm_cands = [(r["strike"], r["p_score"]) for r in focused if r["p_type"] == "OTM" and r["dist"] <= step_size * 2]

    best_p_itm, pre_p_itm = find_best_and_prealert(p_itm_cands)
    best_p_atm, pre_p_atm = find_best_and_prealert(p_atm_cands)
    best_p_otm, pre_p_otm = find_best_and_prealert(p_otm_cands)

    call_winners = {}
    if best_c_itm: call_winners[best_c_itm[0]] = ("BEST ITM", "CONFIRMED")
    elif pre_c_itm: call_winners[pre_c_itm[0]] = ("PRE-ALERT ITM", "PRE_ALERT")

    if best_c_atm: call_winners[best_c_atm[0]] = ("BEST ATM", "CONFIRMED")
    elif pre_c_atm: call_winners[pre_c_atm[0]] = ("PRE-ALERT ATM", "PRE_ALERT")

    if best_c_otm: call_winners[best_c_otm[0]] = ("BEST OTM", "CONFIRMED")
    elif pre_c_otm: call_winners[pre_c_otm[0]] = ("PRE-ALERT OTM", "PRE_ALERT")

    put_winners = {}
    if best_p_itm: put_winners[best_p_itm[0]] = ("BEST ITM", "CONFIRMED")
    elif pre_p_itm: put_winners[pre_p_itm[0]] = ("PRE-ALERT ITM", "PRE_ALERT")

    if best_p_atm: put_winners[best_p_atm[0]] = ("BEST ATM", "CONFIRMED")
    elif pre_p_atm: put_winners[pre_p_atm[0]] = ("PRE-ALERT ATM", "PRE_ALERT")

    if best_p_otm: put_winners[best_p_otm[0]] = ("BEST OTM", "CONFIRMED")
    elif pre_p_otm: put_winners[pre_p_otm[0]] = ("PRE-ALERT OTM", "PRE_ALERT")

    # ----------------- TABLE DISPLAY (FIXED RENDERING) -----------------
    html_parts = []
    html_parts.append('<table style="width:100%; border-collapse:collapse; text-align:center; font-family:monospace; font-size:12.5px; background-color:#0b0f19;">')
    html_parts.append('<thead><tr style="background-color:#1e293b; color:#94a3b8; border-bottom:2px solid #334155;">')
    html_parts.append('<th style="padding:10px;">Call Signal</th>')
    html_parts.append('<th>Delta (Δ)</th>')
    html_parts.append('<th>Call LTP</th>')
    html_parts.append('<th>Call Volume</th>')
    html_parts.append('<th>Call OI</th>')
    html_parts.append('<th style="background-color:#0f172a; color:#f8fafc; font-size:15px; width:120px;">STRIKE</th>')
    html_parts.append('<th>Put OI</th>')
    html_parts.append('<th>Put Volume</th>')
    html_parts.append('<th>Put LTP</th>')
    html_parts.append('<th>Delta (Δ)</th>')
    html_parts.append('<th style="padding:10px;">Put Signal</th>')
    html_parts.append('</tr></thead><tbody>')

    for r in focused:
        stk = r["strike"]
        c_state = call_winners.get(stk)
        p_state = put_winners.get(stk)

        # Call styling
        if c_state and c_state[1] == "CONFIRMED":
            c_style = "background-color:rgba(46, 204, 113, 0.28); color:#2ecc71; font-weight:bold; border-left:4px solid #2ecc71;"
            c_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 6px;">🟢 {c_state[0]}</span>'
        elif c_state and c_state[1] == "PRE_ALERT":
            c_style = "color:#2ecc71;"
            c_badge = f'<span class="pre-alert-flash" style="border:1px dashed #2ecc71; border-radius:4px; padding:2px 6px;">⚡ {c_state[0]}</span>'
        else:
            c_style = "color:#ff6b6b;"
            c_badge = f'<span style="color:#64748b;">{r["c_type"]}</span>'

        # Put styling
        if p_state and p_state[1] == "CONFIRMED":
            p_style = "background-color:rgba(46, 204, 113, 0.28); color:#2ecc71; font-weight:bold; border-right:4px solid #2ecc71;"
            p_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 6px;">🟢 {p_state[0]}</span>'
        elif p_state and p_state[1] == "PRE_ALERT":
            p_style = "color:#2ecc71;"
            p_badge = f'<span class="pre-alert-flash" style="border:1px dashed #2ecc71; border-radius:4px; padding:2px 6px;">⚡ {p_state[0]}</span>'
        else:
            p_style = "color:#ff6b6b;"
            p_badge = f'<span style="color:#64748b;">{r["p_type"]}</span>'

        mid_bg = "#1e293b; font-weight:bold; color:#64ffda;" if stk == atm_strike else "#0f172a; color:#f8fafc;"

        row_str = (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:7px; {c_style}">{c_badge}</td>'
            f'<td style="{c_style}">{r["c_delta"]:.2f}</td>'
            f'<td style="{c_style}">₹{r["c_ltp"]:.1f}</td>'
            f'<td style="{c_style}">{r["c_vol"]:,}</td>'
            f'<td style="{c_style}">{r["c_oi"]:,}</td>'
            f'<td style="background-color:{mid_bg}; font-size:14px;">{int(stk)}</td>'
            f'<td style="{p_style}">{r["p_oi"]:,}</td>'
            f'<td style="{p_style}">{r["p_vol"]:,}</td>'
            f'<td style="{p_style}">₹{r["p_ltp"]:.1f}</td>'
            f'<td style="{p_style}">{r["p_delta"]:.2f}</td>'
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
