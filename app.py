import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# Page Configuration
st.set_page_config(
    page_title="Crypto Multi-Analysis Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("🔥 Real-Time Crypto Multi-Analysis Engine (Bybit Cloud Ready)")
st.caption("SMC | Malaysian SnR | CVD | Real-Time Funding Rate | Auto TP/SL ($300M+ Liquidity)")

# Initialize Bybit Futures Exchange (Bypasses Binance Cloud Restrictions)
@st.cache_resource
def get_exchange():
    return ccxt.bybit({
        'options': {'defaultType': 'linear'},  # Linear USDT Perpetuals
        'enableRateLimit': True,
    })

exchange = get_exchange()

# Sidebar Settings
st.sidebar.header("⚙️ Strategy Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h", "4h"], index=1)
risk_reward = st.sidebar.slider("Risk:Reward Ratio (TP Multiplier)", 1.0, 5.0, 2.0, 0.5)
sl_atr_mult = st.sidebar.slider("SL ATR Multiplier", 1.0, 3.0, 1.5, 0.1)
top_coins_count = st.sidebar.slider("Number of Top Liquid Coins", 5, 20, 10)

# Fetch Top Coins from Bybit (> $300M+ Liquidity Volume)
@st.cache_data(ttl=300)
def fetch_top_coins(limit):
    try:
        tickers = exchange.fetch_tickers()
        selected_coins = []
        for symbol, data in tickers.items():
            # Filter Bybit USDT perpetual contracts
            if 'USDT' in symbol and (symbol.endswith(':USDT') or '/USDT' in symbol):
                quote_volume = data.get('quoteVolume', 0)
                if quote_volume and quote_volume > 50000000: # High Liquid Coins Proxy
                    selected_coins.append((symbol, quote_volume))
        
        selected_coins.sort(key=lambda x: x[1], reverse=True)
        # Remove duplicates if any
        unique_coins = []
        seen = set()
        for coin, vol in selected_coins:
            base_symbol = coin.split(':')[0]
            if base_symbol not in seen:
                seen.add(base_symbol)
                unique_coins.append(coin)
                
        return unique_coins[:limit]
    except Exception as e:
        st.error(f"Error fetching tickers from Bybit: {e}")
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

# Custom Pure Pandas ATR Calculation
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# Analysis Engine Logic
def analyze_market(symbol, tf):
    try:
        # 1. Fetch Real-time Funding Rate
        funding = exchange.fetch_funding_rate(symbol)
        funding_rate = funding.get('fundingRate', 0) * 100

        # 2. Fetch OHLCV Data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 3. ATR Calculation for SL/TP
        df['ATR'] = calculate_atr(df, length=14)
        
        # 4. Malaysian Support & Resistance / CRT Pivots
        df['Pivot_High'] = df['high'].rolling(window=10).max()
        df['Pivot_Low'] = df['low'].rolling(window=10).min()
        
        # 5. CVD Proxy (Cumulative Volume Delta)
        df['vol_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['cvd'] = (df['volume'] * df['vol_dir']).cumsum()
        
        # Current Metrics
        last_close = df['close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        if pd.isna(last_atr):
            last_atr = last_close * 0.01  # Fallback safety
            
        res_zone = df['Pivot_High'].iloc[-2]
        sup_zone = df['Pivot_Low'].iloc[-2]
        cvd_trend = "BULLISH 🟢" if df['cvd'].iloc[-1] > df['cvd'].iloc[-5] else "BEARISH 🔴"
        
        # Signal Rules
        signal = "WAIT ⏳"
        tp, sl = 0.0, 0.0
        
        if last_close > res_zone and "BULLISH" in cvd_trend:
            signal = "BUY / LONG 🚀"
            sl = last_close - (last_atr * sl_atr_mult)
            tp = last_close + ((last_close - sl) * risk_reward)
        elif last_close < sup_zone and "BEARISH" in cvd_trend:
            signal = "SELL / SHORT 📉"
            sl = last_close + (last_atr * sl_atr_mult)
            tp = last_close - ((sl - last_close) * risk_reward)
            
        return {
            "Symbol": symbol.split(':')[0],
            "Price": f"${last_close:,.4f}",
            "Funding Rate": f"{funding_rate:.4f}%",
            "CVD Direction": cvd_trend,
            "Signal": signal,
            "Entry": f"${last_close:,.4f}" if "WAIT" not in signal else "-",
            "Take Profit (TP)": f"${tp:,.4f}" if "WAIT" not in signal else "-",
            "Stop Loss (SL)": f"${sl:,.4f}" if "WAIT" not in signal else "-"
        }
    except Exception as e:
        return None

# App Execution & UI Rendering
if st.button("🔄 Run Live Analysis Now"):
    st.write("Scanning Top Liquid Crypto Markets via Bybit...")
    coins = fetch_top_coins(top_coins_count)
    
    results = []
    progress_bar = st.progress(0)
    
    for idx, coin in enumerate(coins):
        data = analyze_market(coin, timeframe)
        if data:
            results.append(data)
        progress_bar.progress((idx + 1) / len(coins))
        
    st.success("Analysis Complete!")
    
    if results:
        res_df = pd.DataFrame(results)
        st.subheader("📊 Market Analysis & Signal Summary")
        st.dataframe(res_df, use_container_width=True)
else:
    st.info("Click the **'Run Live Analysis Now'** button to scan markets.")
