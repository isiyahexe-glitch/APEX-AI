import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="AI Pro Crypto & Gold Liquidity Terminal",
    page_icon="👑",
    layout="wide"
)

st.title("👑 AI Pro Crypto & Gold Liquidity Terminal")
st.caption("Gold (XAU) & Crypto | $300M+ Liquid Coins | Liquidity Pools & Whale Zones | Risk Calculator")

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

# Fetch Top Coins with Market Cap > $300M from CoinGecko + Gold (XAU)
@st.cache_data(ttl=600)
def get_top_assets():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 40,
            'page': 1,
            'sparkline': 'false'
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        symbols = ["XAU/USDT:USDT"] # Explicitly add Gold (PAXG / Crypto Gold representation)
        for coin in data:
            if coin['market_cap'] and coin['market_cap'] > 300000000:
                symbol = f"{coin['symbol'].upper()}/USDT:USDT"
                if symbol not in symbols:
                    symbols.append(symbol)
        return symbols
    except Exception as e:
        return ["XAU/USDT:USDT", "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT"]

# Pure Pandas ATR Calculation
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# Advanced Analysis & Liquidity Pool Detection
def analyze_asset(symbol, tf):
    try:
        # Handle Gold symbol mapping if needed
        fetch_sym = "PAXG/USDT:USDT" if "XAU" in symbol else symbol
        
        # Funding Rate
        try:
            funding_info = exchange.fetch_funding_rate(fetch_sym)
            funding_rate = funding_info.get('fundingRate', 0.0001) * 100
        except:
            funding_rate = 0.01

        # OHLCV Data
        ohlcv = exchange.fetch_ohlcv(fetch_sym, timeframe=tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # ATR & Pivots (SMC / Malaysian SnR)
        df['ATR'] = calculate_atr(df, length=14)
        df['Resistance'] = df['high'].rolling(window=10).max()
        df['Support'] = df['low'].rolling(window=10).min()
        
        # CVD Proxy & Whale Liquidity Pool Estimation
        df['vol_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['cvd'] = (df['volume'] * df['vol_dir']).cumsum()
        
        last_close = df['close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        if pd.isna(last_atr):
            last_atr = last_close * 0.01
            
        res_zone = df['Resistance'].iloc[-2]
        sup_zone = df['Support'].iloc[-2]
        cvd_bullish = df['cvd'].iloc[-1] > df['cvd'].iloc[-5]
        
        # Liquidity Pool Zones (Whale Stop Loss Clusters)
        buy_side_liquidity = res_zone + (last_atr * 0.5)  # Above resistance where shorts put SL
        sell_side_liquidity = sup_zone - (last_atr * 0.5) # Below support where longs put SL

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
            "RawSymbol": symbol,
            "Price": round(last_close, 4),
            "Funding Rate (%)": round(funding_rate, 4),
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

col_btn1, col_btn2 = st.columns(2)
run_scan = col_btn1.button("🚀 Run Master Scan ($300M+ Coins & Gold)")

# Asset selection logic
assets = get_top_assets()

if run_scan:
    with st.spinner("Scanning all $300M+ coins and Gold (XAU), calculating liquidity pools & funding rates..."):
        scanned = []
        for asset in assets:
            res = analyze_asset(asset, timeframe)
            if res:
                scanned.append(res)
        if scanned:
            st.session_state['scan_data'] = pd.DataFrame(scanned)
            st.success("✅ Scan Completed Successfully!")

# Handle direct custom search if typed
if custom_search:
    search_sym = f"{custom_search.upper().strip()}/USDT:USDT"
    if "XAU" in custom_search.upper() or "GOLD" in custom_search.upper():
        search_sym = "XAU/USDT:USDT"
    
    single_res = analyze_asset(search_sym, timeframe)
    if single_res:
        # Put into session state dataframe as single or primary row
        df_single = pd.DataFrame([single_res])
        if 'scan_data' not in st.session_state:
            st.session_state['scan_data'] = df_single
        else:
            # prepend or update
            pass

# Display Results if available
if 'scan_data' in st.session_state:
    df_results = st.session_state['scan_data']
    
    st.subheader("📊 Market Scanner & Liquidity Overview")
    st.dataframe(df_results[['Asset', 'Price', 'Funding Rate (%)', 'CVD Flow', 'Signal', 'Buy-Side Liquidity Pool', 'Sell-Side Liquidity Pool']], use_container_width=True, height=350)
    
    st.markdown("---")
    st.subheader("🎯 Detailed Chart, Whale Liquidity Pools & Risk Calculator")
    
    asset_list = df_results['Asset'].tolist()
    selected_asset = st.selectbox("Select Asset to view TradingView Chart & Liquidity Analysis:", asset_list)
    
    if selected_asset:
        asset_row = df_results[df_results['Asset'] == selected_asset].iloc[0]
        
        col_chart, col_calc = st.columns([1.3, 0.7])
        
        with col_chart:
            st.markdown(f"### Live Chart: `{selected_asset}`")
            
            # Map symbol for TradingView widget
            if selected_asset == "GOLD (XAU)":
                tv_symbol_str = "OANDA:XAUUSD"
            else:
                tv_exchange = "BYBIT" if exchange_name == "BYBIT" else "MEXC"
                tv_symbol_str = f"{tv_exchange}:{selected_asset}USDT"
            
            tradingview_html = f"""
            <!DOCTYPE html>
            <html>
            <head></head>
            <body style="margin:0;background-color:#131722;">
                <div class="tradingview-widget-container" style="height:520px;width:100%">
                  <div id="tradingview_widget" style="height:100%;width:100%"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                  <script type="text/javascript">
                  new TradingView.widget(
                  {{
                    "autosize": true,
                    "symbol": "{tv_symbol_str}",
                    "interval": "15",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#f1f3f6",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": true,
                    "details": true,
                    "studies": [
                      "Funding_Rate@tv-basicstudies",
                      "VolumeProfile@tv-basicstudies"
                    ],
                    "container_id": "tradingview_widget"
                  }});
                  </script>
                </div>
            </body>
            </html>
            """
            components.html(tradingview_html, height=540)
            
        with col_calc:
            st.markdown(f"### 🌊 Whale Liquidity Pools & Setup")
            st.info(f"Signal: **{asset_row['Signal']}**")
            
            # Liquidity Pool display (Coinglass style estimation)
            st.markdown(f"🔴 **Buy-Side Liquidity (Short SL Pool):** `${asset_row['Buy-Side Liquidity Pool']:,.4f}`")
            st.markdown(f"🟢 **Sell-Side Liquidity (Long SL Pool):** `${asset_row['Sell-Side Liquidity Pool']:,.4f}`")
            st.caption("💡 *Whalesලා සාමාන්‍යයෙන් මේ Liquidity Pools Sweep (Hunt) කරලා තමයි Reversal එකක් දෙන්නේ.*")
            
            st.markdown("---")
            st.markdown("### 🧮 Risk & Position Calculator")
            balance = st.number_input("Account Balance (USDT)", min_value=10.0, value=1000.0, step=50.0)
            risk_pct = st.slider("Risk Tolerance (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)
            leverage = st.selectbox("Leverage (x)", [1, 2, 5, 10, 20, 50], index=3)
            
            entry_p = asset_row['Entry']
            tp_p = asset_row['TP']
            sl_p = asset_row['SL']
            
            if "NEUTRAL" not in asset_row['Signal'] and entry_p > 0 and sl_p > 0:
                risk_amount_usdt = balance * (risk_pct / 100.0)
                price_diff = abs(entry_p - sl_p)
                
                if price_diff > 0:
                    position_size_tokens = risk_amount_usdt / price_diff
                    position_size_usdt = position_size_tokens * entry_p
                    margin_required = position_size_usdt / leverage
                    
                    tp_diff = abs(tp_p - entry_p)
                    potential_profit = position_size_tokens * tp_diff
                    
                    st.markdown(f"**🎯 Entry:** `${entry_p:,.4f}` | **TP:** `${tp_p:,.4f}` | **SL:** `${sl_p:,.4f}`")
                    st.success(f"💰 **Position Size:** `{position_size_tokens:,.2f} {selected_asset}` (`${position_size_usdt:,.2f}`)बाड़ी")
                    st.warning(f"⚠️ **Margin Required ({leverage}x):** `${margin_required:,.2f} USDT`")
                    st.error(f"🛑 **Max Risk Loss:** `${risk_amount_usdt:,.2f} USDT` ({risk_pct}%)")
                    st.info(f"🏆 **Target Profit:** `${potential_profit:,.2f} USDT`")
                else:
                    st.warning("Invalid SL range.")
            else:
                st.warning("Market is in Neutral range. Wait for breakout of Liquidity Pools.")
else:
    st.info("👆 Type any asset in the search box above (e.g. `XAU`, `BTC`, `SOL`) or click **'Run Master Scan'** to start.")
