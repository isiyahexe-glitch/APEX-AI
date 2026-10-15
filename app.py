import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
import plotly.express as px
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="AI Pro Crypto & Gold Terminal (All Coins Scan)",
    page_icon="💎",
    layout="wide"
)

st.title("💎 AI Pro Crypto & Gold Terminal (All $300M+ Liquid Coins)")
st.caption("Complete Market Scanner | Real-Time Funding Rates | DOM Depth Chart | Liquidity Heatmap & Risk Calculator")

# Sidebar Settings
st.sidebar.header("⚙️ Market & Strategy Settings")
exchange_name = st.sidebar.selectbox("Select Exchange", ["MEXC", "BYBIT"])
timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h"], index=1)

risk_reward = st.sidebar.slider("Risk-to-Reward Ratio (TP Multiplier)", 1.0, 5.0, 2.0, 0.5)
sl_mult = st.sidebar.slider("Stop Loss ATR Multiplier", 1.0, 3.0, 1.5, 0.1)

# Initialize Exchange
@st.cache_resource
def get_exchange(name):
    config = {'options': {'defaultType': 'swap'}, 'enableRateLimit': True}
    return ccxt.bybit(config) if name == "BYBIT" else ccxt.mexc(config)

exchange = get_exchange(exchange_name)

# Fetch ALL Coins with Market Cap > $300M from CoinGecko + Gold (XAU)
@st.cache_data(ttl=600)
def get_top_assets():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 250,
            'page': 1,
            'sparkline': 'false'
        }
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        symbols = ["XAU/USDT:USDT"]
        for coin in data:
            if coin['market_cap'] and coin['market_cap'] > 300000000:
                symbol = f"{coin['symbol'].upper()}/USDT:USDT"
                if symbol not in symbols:
                    symbols.append(symbol)
        return symbols
    except Exception as e:
        return ["XAU/USDT:USDT", "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT"]

# Pure Pandas ATR Calculation
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# Advanced Analysis & Real-Time Funding Rate Fetch
def analyze_asset(symbol, tf):
    try:
        fetch_sym = "PAXG/USDT:USDT" if "XAU" in symbol else symbol
        
        funding_rate = 0.0
        try:
            funding_info = exchange.fetch_funding_rate(fetch_sym)
            if funding_info and 'fundingRate' in funding_info and funding_info['fundingRate'] is not None:
                funding_rate = float(funding_info['fundingRate']) * 100
        except Exception as fr_err:
            funding_rate = 0.01

        ohlcv = exchange.fetch_ohlcv(fetch_sym, timeframe=tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['ATR'] = calculate_atr(df, length=14)
        df['Resistance'] = df['high'].rolling(window=10).max()
        df['Support'] = df['low'].rolling(window=10).min()
        
        df['vol_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['cvd'] = (df['volume'] * df['vol_dir']).cumsum()
        
        last_close = df['close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        if pd.isna(last_atr):
            last_atr = last_close * 0.01
            
        res_zone = df['Resistance'].iloc[-2]
        sup_zone = df['Support'].iloc[-2]
        cvd_bullish = df['cvd'].iloc[-1] > df['cvd'].iloc[-5]
        
        buy_side_liquidity = res_zone + (last_atr * 0.5)
        sell_side_liquidity = sup_zone - (last_atr * 0.5)

        signal = "NEUTRAL ⏳"
        tp, sl = 0.0, 0.0
        
        if last_close > res_zone and cvd_bullish:
            signal = "LONG POSITION 🚀"
            sl = last_close - (last_atr * sl_mult)
            tp = last_close + ((last_close - sl) * risk_reward)
        elif last_close < sup_zone and not cvd_bullish:
            signal = "SHORT POSITION 📉"
            sl = last_close + (last_atr * sl_mult)
            tp = last_close - ((sl - last_close) * risk_reward)
            
        display_name = "GOLD (XAU)" if "XAU" in symbol else symbol.split('/')[0]
        
        return {
            "Asset": display_name,
            "RawSymbol": fetch_sym,
            "Price": round(last_close, 4),
            "Funding Rate (%)": round(funding_rate, 5),
            "CVD Flow": "BULLISH 🟢" if cvd_bullish else "BEARISH 🔴",
            "Signal": signal,
            "Entry": round(last_close, 4) if "NEUTRAL" not in signal else 0.0,
            "TP": round(tp, 4) if "NEUTRAL" not in signal else 0.0,
            "SL": round(sl, 4) if "NEUTRAL" not in signal else 0.0,
            "Buy-Side Liquidity Pool": round(buy_side_liquidity, 4),
            "Sell-Side Liquidity Pool": round(sell_side_liquidity, 4)
        }
    except Exception as e:
        return None

# --- UI LAYOUT ---
st.markdown("### 🔍 Search Asset / Coin (e.g. BTC, ETH, XAU, SOL, PEPE)")
custom_search = st.text_input("Type asset symbol manually or run Master Scan below:", value="")

run_scan = st.button("🚀 Run Master Scan (Scan ALL $300M+ Coins & Gold)")

assets = get_top_assets()

if run_scan:
    scanned = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_assets = len(assets)
    
    for i, asset in enumerate(assets):
        status_text.text(f"Analyzing ({i+1}/{total_assets}): {asset.split('/')[0]}...")
        res = analyze_asset(asset, timeframe)
        if res:
            scanned.append(res)
        progress_bar.progress((i + 1) / total_assets)
        
    status_text.empty()
    progress_bar.empty()
    
    if scanned:
        st.session_state['scan_data'] = pd.DataFrame(scanned)
        st.success(f"✅ Successfully scanned all {len(scanned)} liquid assets ($300M+ & Gold)!")

if custom_search and custom_search.strip() != "":
    search_sym = f"{custom_search.upper().strip()}/USDT:USDT"
    if "XAU" in custom_search.upper() or "GOLD" in custom_search.upper():
        search_sym = "XAU/USDT:USDT"
    
    single_res = analyze_asset(search_sym, timeframe)
    if single_res:
        st.session_state['scan_data'] = pd.DataFrame([single_res])

# Display Results if available
if 'scan_data' in st.session_state and not st.session_state['scan_data'].empty:
    df_results = st.session_state['scan_data']
    
    if 'Asset' in df_results.columns:
        st.subheader("📊 Master Market Scanner & Real-Time Funding Rates (All Coins)")
        
        target_columns = ['Asset', 'Price', 'Funding Rate (%)', 'CVD Flow', 'Signal', 'Buy-Side Liquidity Pool', 'Sell-Side Liquidity Pool']
        safe_columns = [col for col in target_columns if col in df_results.columns]
        
        st.dataframe(df_results[safe_columns], use_container_width=True, height=350)
        
        # --- Funding Rate Squeeze Radar ---
        st.markdown("---")
        st.subheader("🔥 Real-Time Funding Rate Squeeze Radar")
        col_fr1, col_fr2 = st.columns(2)
        
        with col_fr1:
            st.markdown("#### 🚀 Highest Positive Funding Rates (Long Squeeze Risk)")
            high_fr = df_results.sort_values(by="Funding Rate (%)", ascending=False).head(3)
            for idx, row in high_fr.iterrows():
                st.markdown(f"• **{row['Asset']}**: `{row['Funding Rate (%)']}%` (Price: `${row['Price']}`)".replace("$$", "$"))
                
        with col_fr2:
            st.markdown("#### 📉 Most Negative Funding Rates (Short Squeeze Risk)")
            low_fr = df_results.sort_values(by="Funding Rate (%)", ascending=True).head(3)
            for idx, row in low_fr.iterrows():
                st.markdown(f"• **{row['Asset']}**: `{row['Funding Rate (%)']}%` (Price: `${row['Price']}`)".replace("$$", "$"))

        st.markdown("---")
        st.subheader("🎯 Detailed Chart, DOM, Liquidity Heatmap & Risk Calculator")
        
        asset_list = df_results['Asset'].tolist()
        selected_asset = st.selectbox("Select Asset to view Analysis & Charts:", asset_list)
        
        if selected_asset:
            asset_row = df_results[df_results['Asset'] == selected_asset].iloc[0]
            raw_sym = asset_row['RawSymbol']
            
            # Layout Tabs for TradingView, DOM, and Heatmap
            tab_chart, tab_dom, tab_heatmap = st.tabs(["📈 TradingView Live Chart", "📊 DOM / Depth Chart", "🔥 Liquidity Heatmap"])
            
            with tab_chart:
                st.markdown(f"### Live Chart: `{selected_asset}`")
                if selected_asset == "GOLD (XAU)":
                    tv_symbol_str = "OANDA:XAUUSD"
                else:
                    tv_exchange = "BYBIT" if exchange_name == "BYBIT" else "MEXC"
                    tv_symbol_str = f"{tv_exchange}:{selected_asset}USDT"
                
                tradingview_html = """
