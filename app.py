import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="AI Crypto Pro Scanner & Risk Calculator",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ AI Pro Crypto Scanner & Risk Management Terminal")
st.caption("$300M+ Liquid Coins | Real-Time Funding Rates | Long/Short Setups & Position Risk Calculator")

# Sidebar Settings
st.sidebar.header("⚙️ Scanner & Strategy Settings")
exchange_name = st.sidebar.selectbox("Select Exchange", ["MEXC", "BYBIT"])
timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h"], index=0)

risk_reward = st.sidebar.slider("Risk-to-Reward Ratio (TP Multiplier)", 1.0, 5.0, 2.0, 0.5)
sl_mult = st.sidebar.slider("Stop Loss ATR Multiplier", 1.0, 3.0, 1.5, 0.1)

# Initialize Exchange
@st.cache_resource
def get_exchange(name):
    config = {'options': {'defaultType': 'swap'}, 'enableRateLimit': True}
    return ccxt.bybit(config) if name == "BYBIT" else ccxt.mexc(config)

exchange = get_exchange(exchange_name)

# Fetch Top Coins with Market Cap > $300M from CoinGecko
@st.cache_data(ttl=600)
def get_top_300m_coins():
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
        symbols = []
        for coin in data:
            if coin['market_cap'] and coin['market_cap'] > 300000000: # $300M+ Filter
                symbol = f"{coin['symbol'].upper()}/USDT:USDT"
                symbols.append(symbol)
        return symbols
    except Exception as e:
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT", "DOGE/USDT:USDT"]

# Pure Pandas ATR Calculation
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# Analysis Function for a Single Coin
def analyze_coin(symbol, tf):
    try:
        # Funding Rate
        funding_info = exchange.fetch_funding_rate(symbol)
        funding_rate = funding_info.get('fundingRate', 0.0001) * 100

        # OHLCV Data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # ATR & Pivots
        df['ATR'] = calculate_atr(df, length=14)
        df['Resistance'] = df['high'].rolling(window=10).max()
        df['Support'] = df['low'].rolling(window=10).min()
        
        # CVD Proxy
        df['vol_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['cvd'] = (df['volume'] * df['vol_dir']).cumsum()
        
        last_close = df['close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        if pd.isna(last_atr):
            last_atr = last_close * 0.01
            
        res_zone = df['Resistance'].iloc[-2]
        sup_zone = df['Support'].iloc[-2]
        cvd_bullish = df['cvd'].iloc[-1] > df['cvd'].iloc[-5]
        
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
            
        return {
            "Coin": symbol.split('/')[0],
            "Price": round(last_close, 4),
            "Funding Rate (%)": round(funding_rate, 4),
            "CVD Flow": "BULLISH 🟢" if cvd_bullish else "BEARISH 🔴",
            "Signal": signal,
            "Entry": round(last_close, 4) if "NEUTRAL" not in signal else 0.0,
            "TP": round(tp, 4) if "NEUTRAL" not in signal else 0.0,
            "SL": round(sl, 4) if "NEUTRAL" not in signal else 0.0
        }
    except Exception as e:
        return None

# Main Execution Button
if st.button("🚀 Run Master Scan ($300M+ Coins & Funding Rates)"):
    with st.spinner("Scanning all $300M+ market cap coins, fetching live funding rates and calculating Long/Short setups..."):
        coins = get_top_300m_coins()
        scanned_results = []
        
        for coin in coins:
            res = analyze_coin(coin, timeframe)
            if res:
                scanned_results.append(res)
                
        if scanned_results:
            st.session_state['scan_data'] = pd.DataFrame(scanned_results)
            st.success("✅ Master Scan Completed Successfully!")
        else:
            st.warning("Could not fetch market data. Please try again.")

# Display Master Table if scanned data exists
if 'scan_data' in st.session_state:
    df_results = st.session_state['scan_data']
    
    st.subheader("📊 Master Market Scanner Results ($300M+ Liquid Coins)")
    st.dataframe(df_results, use_container_width=True, height=400)
    
    st.markdown("---")
    st.subheader("🔍 Detailed Chart, Long/Short Setup & Risk Calculator")
    
    coin_list = df_results['Coin'].tolist()
    selected_coin = st.selectbox("Select a coin to view setup & Risk Calculator:", coin_list)
    
    if selected_coin:
        coin_row = df_results[df_results['Coin'] == selected_coin].iloc[0]
        
        col_chart, col_calc = st.columns([1.3, 0.7])
        
        with col_chart:
            st.markdown(f"### Live Chart: `{selected_coin}USDT`")
            tv_exchange = "BYBIT" if exchange_name == "BYBIT" else "MEXC"
            tv_symbol_str = f"{tv_exchange}:{selected_coin}USDT"
            
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
            st.markdown(f"### 🧮 Position & Risk Calculator")
            st.info(f"Selected Setup: **{coin_row['Signal']}**")
            
            # Risk Calculator User Inputs
            balance = st.number_input("Account Balance (USDT)", min_value=10.0, value=1000.0, step=50.0)
            risk_pct = st.slider("Risk Tolerance (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.5)
            leverage = st.selectbox("Leverage (x)", [1, 2, 5, 10, 20, 50], index=3)
            
            entry_p = coin_row['Entry']
            tp_p = coin_row['TP']
            sl_p = coin_row['SL']
            
            if "NEUTRAL" not in coin_row['Signal'] and entry_p > 0 and sl_p > 0:
                # Calculations
                risk_amount_usdt = balance * (risk_pct / 100.0)
                price_diff = abs(entry_p - sl_p)
                
                if price_diff > 0:
                    position_size_tokens = risk_amount_usdt / price_diff
                    position_size_usdt = position_size_tokens * entry_p
                    margin_required = position_size_usdt / leverage
                    
                    tp_diff = abs(tp_p - entry_p)
                    potential_profit = position_size_tokens * tp_diff
                    
                    st.markdown("---")
                    st.markdown(f"**🎯 Entry Price:** `${entry_p:,.4f}`")
                    st.markdown(f"**🟢 Take Profit:** `${tp_p:,.4f}`")
                    st.markdown(f"**🔴 Stop Loss:** `${sl_p:,.4f}`")
                    st.markdown("---")
                    
                    st.success(f"💰 **Position Size:** `{position_size_tokens:,.2f} {selected_coin}` (`${position_size_usdt:,.2f} USDT`)")
                    st.warning(f"⚠️ **Margin Required ({leverage}x):** `${margin_required:,.2f} USDT`")
                    st.error(f"🛑 **Max Risk Loss:** `${risk_amount_usdt:,.2f} USDT` ({risk_pct}%)")
                    st.info(f"🏆 **Target Profit:** `${potential_profit:,.2f} USDT`")
                else:
                    st.warning("Invalid SL range for calculation.")
            else:
                st.warning("Market is currently in Neutral range. No active Long/Short setup to calculate.")
else:
    st.info("👆 Click the **'Run Master Scan'** button above to scan all $300M+ market cap coins and use the Risk Calculator.")
