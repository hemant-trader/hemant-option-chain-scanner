import os
import json
import time
import math
import secrets
import datetime
import zoneinfo
import requests
import urllib.parse
import pandas as pd
import streamlit as st

from config import UPSTOX_CONFIG

st.set_page_config(
    page_title="Hemant Option Chain Matrix",
    page_icon="🎯",
    layout="wide"
)

TOKEN_FILE = "access_token.json"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

INDEX_CONFIG = {
    "NIFTY 50": {"key": "NSE_INDEX|Nifty 50", "step": 50},
    "BANKNIFTY": {"key": "NSE_INDEX|Nifty Bank", "step": 100},
    "SENSEX": {"key": "BSE_INDEX|SENSEX", "step": 100},
}

# --- Token Management ---
def save_token(data):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                d = json.load(f)
                return d.get("access_token")
        except Exception:
            return None
    return None

def get_access_token(code):
    url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "code": code,
        "client_id": UPSTOX_CONFIG["API_KEY"],
        "client_secret": UPSTOX_CONFIG["API_SECRET"],
        "redirect_uri": UPSTOX_CONFIG["REDIRECT_URI"],
        "grant_type": "authorization_code"
    }
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=5)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

# Session & OAuth Handling
if "access_token" not in st.session_state:
    saved = load_token()
    if saved:
        st.session_state["access_token"] = saved

query_params = st.query_params
auth_code = query_params.get("code", None)
if auth_code and "access_token" not in st.session_state:
    res = get_access_token(auth_code)
    if "access_token" in res:
        st.session_state["access_token"] = res["access_token"]
        save_token(res)
        st.query_params.clear()
        st.rerun()

# --- Sidebar Controls ---
st.sidebar.title("⚡ Control Panel")
selected_index = st.sidebar.selectbox("Select Index", list(INDEX_CONFIG.keys()), index=0)
auto_refresh = st.sidebar.checkbox("Live Auto Refresh (3s)", value=True)
strikes_count = st.sidebar.slider("Strikes Display Window", min_value=10, max_value=30, value=16, step=2)

st.sidebar.markdown("---")
if "access_token" not in st.session_state:
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = secrets.token_urlsafe(16)
    login_url = (
        f"https://api.upstox.com/v2/login/authorization/dialog?"
        f"response_type=code&client_id={UPSTOX_CONFIG['API_KEY']}&"
        f"redirect_uri={urllib.parse.quote(UPSTOX_CONFIG['REDIRECT_URI'])}&"
        f"state={st.session_state['oauth_state']}"
    )
    st.sidebar.link_button("🔑 Login with Upstox", login_url)
    manual_code = st.sidebar.text_input("Paste Auth Code Manually:")
    if st.sidebar.button("Connect"):
        if manual_code:
            res = get_access_token(manual_code)
            if "access_token" in res:
                st.session_state["access_token"] = res["access_token"]
                save_token(res)
                st.rerun()
else:
    st.sidebar.success("✅ Upstox Session Active")
    if st.sidebar.button("Logout Session"):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        del st.session_state["access_token"]
        st.rerun()

token = st.session_state.get("access_token")

# --- UI Header ---
st.markdown("""
<div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
    <h1 style="margin:0; font-size:32px;">🎯 Hemant <span style="color:#2ecc71;">Option Chain</span> Matrix</h1>
</div>
""", unsafe_allow_html=True)

if not token:
    st.info("👋 Kripya sidebar mein 'Login with Upstox' par click karke login karein.")
    st.stop()

# --- Data Fetchers ---
inst_key = INDEX_CONFIG[selected_index]["key"]
step_size = INDEX_CONFIG[selected_index]["step"]

def fetch_spot(key, tok):
    url = f"https://api.upstox.com/v2/market-quote/ltp?instrument_key={urllib.parse.quote(key)}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=3).json()
        raw_key = key.replace("|", ":")
        return float(r.get("data", {}).get(raw_key, {}).get("last_price", 0.0))
    except Exception:
        return 0.0

def fetch_expiries(key, tok):
    url = f"https://api.upstox.com/v2/option/contract?instrument_key={urllib.parse.quote(key)}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=4).json()
        if r.get("status") == "success":
            return sorted(list({c["expiry"] for c in r.get("data", [])}))
    except Exception:
        pass
    return []

def fetch_chain(key, expiry, tok):
    url = f"https://api.upstox.com/v2/option/chain?instrument_key={urllib.parse.quote(key)}&expiry_date={expiry}"
    headers = {"accept": "application/json", "Authorization": f"Bearer {tok}"}
    try:
        r = requests.get(url, headers=headers, timeout=4).json()
        if r.get("status") == "success":
            return r.get("data", [])
    except Exception:
        pass
    return []

spot_price = fetch_spot(inst_key, token)
expiries = fetch_expiries(inst_key, token)

if not expiries:
    st.warning("Contracts load ho rahe hain...")
    time.sleep(2)
    st.rerun()

selected_expiry = st.sidebar.selectbox("Select Expiry", expiries, index=0)
chain_data = fetch_chain(inst_key, selected_expiry, token)

if spot_price > 0 and chain_data:
    atm_strike = round(spot_price / step_size) * step_size

    st.markdown(f"""
    <div style="background-color:#111622; border:1px solid #1f293d; border-radius:8px; padding:12px 18px; display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
        <div><span style="color:#8892b0; font-size:12px;">INDEX SPOT</span><br><b style="font-size:22px; color:#ffffff;">₹{spot_price:,.2f}</b></div>
        <div><span style="color:#8892b0; font-size:12px;">ATM STRIKE</span><br><b style="font-size:20px; color:#64ffda;">{atm_strike}</b></div>
        <div><span style="color:#8892b0; font-size:12px;">ACTIVE EXPIRY</span><br><b style="font-size:18px; color:#ccd6f6;">{selected_expiry}</b></div>
    </div>
    """, unsafe_allow_html=True)

    rows = []
    for row in chain_data:
        stk = float(row.get("strike_price", 0.0))
        c_market = row.get("call_options", {}).get("market_data", {})
        p_market = row.get("put_options", {}).get("market_data", {})

        c_ltp = float(c_market.get("ltp", 0.0) or 0.0)
        c_vol = int(c_market.get("volume", 0) or 0)
        c_oi = int(c_market.get("oi", 0) or 0)

        p_ltp = float(p_market.get("ltp", 0.0) or 0.0)
        p_vol = int(p_market.get("volume", 0) or 0)
        p_oi = int(p_market.get("oi", 0) or 0)

        c_type = "ATM" if stk == atm_strike else ("ITM" if stk < atm_strike else "OTM")
        p_type = "ATM" if stk == atm_strike else ("OTM" if stk < atm_strike else "ITM")

        # Liquidity score (filter dead penny options < 10)
        c_score = (math.log10(max(10, c_vol)) * 6.0) + (math.log10(max(10, c_oi)) * 4.0) if c_ltp >= 10.0 else 0
        p_score = (math.log10(max(10, p_vol)) * 6.0) + (math.log10(max(10, p_oi)) * 4.0) if p_ltp >= 10.0 else 0

        rows.append({
            "strike": stk,
            "c_type": c_type,
            "p_type": p_type,
            "c_ltp": c_ltp,
            "c_vol": c_vol,
            "c_oi": c_oi,
            "c_score": c_score,
            "p_ltp": p_ltp,
            "p_vol": p_vol,
            "p_oi": p_oi,
            "p_score": p_score,
            "dist": abs(stk - atm_strike)
        })

    rows.sort(key=lambda x: x["dist"])
    focused = rows[:strikes_count]
    focused.sort(key=lambda x: x["strike"])

    # Best Call Selection
    best_c_atm = max([r for r in focused if r["c_type"] == "ATM"], key=lambda x: x["c_score"], default=None)
    best_c_itm = max([r for r in focused if r["c_type"] == "ITM" and r["dist"] <= step_size * 2], key=lambda x: x["c_score"], default=None)
    best_c_otm = max([r for r in focused if r["c_type"] == "OTM" and r["dist"] <= step_size * 2], key=lambda x: x["c_score"], default=None)

    # Best Put Selection
    best_p_atm = max([r for r in focused if r["p_type"] == "ATM"], key=lambda x: x["p_score"], default=None)
    best_p_itm = max([r for r in focused if r["p_type"] == "ITM" and r["dist"] <= step_size * 2], key=lambda x: x["p_score"], default=None)
    best_p_otm = max([r for r in focused if r["p_type"] == "OTM" and r["dist"] <= step_size * 2], key=lambda x: x["p_score"], default=None)

    call_winners = {
        best_c_itm["strike"]: "BEST ITM" if best_c_itm else None,
        best_c_atm["strike"]: "BEST ATM" if best_c_atm else None,
        best_c_otm["strike"]: "BEST OTM" if best_c_otm else None
    }
    put_winners = {
        best_p_itm["strike"]: "BEST ITM" if best_p_itm else None,
        best_p_atm["strike"]: "BEST ATM" if best_p_atm else None,
        best_p_otm["strike"]: "BEST OTM" if best_p_otm else None
    }

    # Render Table
    html = """
    <table style="width:100%; border-collapse:collapse; text-align:center; font-family:monospace; font-size:13px;">
        <tr style="background-color:#1e293b; color:#8892b0; border-bottom:2px solid #334155;">
            <th style="padding:10px;">Call Signal</th>
            <th>Call LTP</th>
            <th>Call Volume</th>
            <th>Call OI</th>
            <th style="background-color:#0f172a; color:#f8fafc; font-size:15px;">STRIKE</th>
            <th>Put OI</th>
            <th>Put Volume</th>
            <th>Put LTP</th>
            <th>Put Signal</th>
        </tr>
    """

    for r in focused:
        stk = r["strike"]
        c_tag = call_winners.get(stk)
        p_tag = put_winners.get(stk)

        # Call styling
        if c_tag:
            c_style = "background-color:rgba(46, 204, 113, 0.22); color:#2ecc71; font-weight:bold; border-left:4px solid #2ecc71;"
            c_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 8px;">🟢 {c_tag}</span>'
        else:
            c_style = "color:#ff6b6b;"
            c_badge = f'<span style="color:#64748b;">{r["c_type"]}</span>'

        # Put styling
        if p_tag:
            p_style = "background-color:rgba(46, 204, 113, 0.22); color:#2ecc71; font-weight:bold; border-right:4px solid #2ecc71;"
            p_badge = f'<span style="background-color:#163828; border:1px solid #2ecc71; border-radius:4px; padding:2px 8px;">🟢 {p_tag}</span>'
        else:
            p_style = "color:#ff6b6b;"
            p_badge = f'<span style="color:#64748b;">{r["p_type"]}</span>'

        mid_bg = "#1e293b; font-weight:bold; color:#64ffda;" if stk == atm_strike else "#0f172a; color:#f8fafc;"

        html += f"""
        <tr style="border-bottom:1px solid #1e293b;">
            <td style="padding:8px; {c_style}">{c_badge}</td>
            <td style="{c_style}">₹{r['c_ltp']:.1f}</td>
            <td style="{c_style}">{r['c_vol']:,}</td>
            <td style="{c_style}">{r['c_oi']:,}</td>
            <td style="background-color:{mid_bg}; font-size:14px;">{int(stk)}</td>
            <td style="{p_style}">{r['p_oi']:,}</td>
            <td style="{p_style}">{r['p_vol']:,}</td>
            <td style="{p_style}">₹{r['p_ltp']:.1f}</td>
            <td style="padding:8px; {p_style}">{p_badge}</td>
        </tr>
        """

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)

if auto_refresh:
    time.sleep(3.0)
    st.rerun()
