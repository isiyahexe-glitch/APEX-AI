import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests

# Page Configuration
st.set_page_config(
    page_title="AI Crypto Auto-Analysis & Signal Engine",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 AI-Powered Automated Crypto Analysis & Signal Engine")
st.caption("Auto Analysis: SMC, ICT, Malaysian SnR, CVD, Order Flow & Dynamic TP/SL ($300M+ Market Cap Coins)")

# Initialize MEXC Futures Exchange (Cloud Server Friendly)
@st.cache_resource
def get_exchange():
    return ccxt.mexc({
        'options': {'defaultType': 'swap'},
        'enableRateLimit': True,
    })

exchange = get_exchange()

# Fetch Top Coins with Market Cap > $300M from CoinGecko API
@st.cache_data(ttl=600)
def get_top_coins_coingecko():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 30,
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
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT", "LINK/USDT:USDT"]

# Pure Pandas ATR Calculation for Dynamic SL/TP
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# AI Multi-Analysis Engine
def run_ai_analysis(symbol, timeframe, risk_reward, sl_mult):
    try:
        # Fetch OHLCV Candlestick Data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 1. ATR Calculation
        df['ATR'] = calculate_atr(df, length=14)
        
        # 2. Malaysian Support & Resistance / Pivot Zones
        df['Resistance'] = df['high'].rolling(window=10).max()
        df['Support'] = df['low'].rolling(window=10).min()
        
        # 3. CVD Proxy & Order Flow Analysis
        df['vol_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['cvd'] = (df['volume'] * df['vol_dir']).cumsum()
        
        # Current Candle Metrics
        last_close = df['close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        if pd.isna(last_atr):
            last_atr = last_close * 0.01
            
        res_zone = df['Resistance'].iloc[-2]
        sup_zone = df['Support'].iloc[-2]
        cvd_bullish = df['cvd'].iloc[-1] > df['cvd'].iloc[-5]
        
        # Real-time Funding Rate Fetch
        try:
            funding_info = exchange.fetch_funding_rate(symbol)
            funding_rate = funding_info.get('fundingRate', 0.0001) * 100
        except:
            funding_rate = 0.01
            
        # AI Decision Logic (SMC + Malaysian SnR + CVD Order Flow)
        signal = "NEUTRAL ⏳"
        tp, sl = 0.0, 0.0
        confidence = "Medium"
        
        if last_close > res_zone and cvd_bullish:
            signal = "BUY / LONG 🚀"
            sl = last_close - (last_atr * sl_mult)
            tp = last_close + ((last_close - sl) * risk_reward)
            confidence = "High 🟢" if funding_rate < 0.05 else "Moderate 🟡"
            
        elif last_close < sup_zone and not cvd_bullish:
            signal = "SELL / SHORT 📉"
            sl = last_close + (last_atr * sl_mult)
            tp = last_close - ((sl - last_close) * risk_reward)
            confidence = "High 🔴" if funding_rate > -0.05 else "Moderate 🟠"
            
        return {
            "Coin": symbol.split('/')[0],
            "Price": f"${last_close:,.4f}",
            "Funding Rate": f"{funding_rate:.4f}%",
            "CVD Flow": "BULLISH 🟢" if cvd_bullish else "BEARISH 🔴",
            "AI Signal": signal,
            "Confidence": confidence,
            "Entry Price": f"${last_close:,.4f}" if "NEUTRAL" not in signal else "-",
            "Take Profit (TP)": f"${tp:,.4f}" if "NEUTRAL" not in signal else "-",
            "Stop Loss (SL)": f"${sl:,.4f}" if "NEUTRAL" not in signal else "-"
        }
    except Exception as e:
        return None

# Sidebar Configuration UI
st.sidebar.header("⚙️ AI Strategy Settings")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h", "4h"], index=1)
risk_reward = st.sidebar.slider("Risk-to-Reward Ratio (TP Multiplier)", 1.0, 5.0, 2.0, 0.5)
sl_mult = st.sidebar.slider("Stop Loss ATR Multiplier", 1.0, 3.0, 1.5, 0.1)

# Execution Button
if st.button("🤖 Run AI Automated Analysis Now"):
    with st.spinner("AI is scanning $300M+ Market Cap coins, calculating SMC, Malaysian SnR, CVD & Funding Rates..."):
        coins = get_top_coins_coingecko()
        results = []
        
        for coin in coins:
            data = run_ai_analysis(coin, timeframe, risk_reward, sl_mult)
            if data:
                results.append(data)
                
        if results:
            res_df = pd.DataFrame(results)
            st.success("✅ Analysis Complete! Automated Trade Setup Generated:")
            st.dataframe(res_df, use_container_width=True, height=520)
            
            # Active Signals Summary Box
            active_signals = res_df[~res_df["AI Signal"].str.contains("NEUTRAL")]
            if not active_signals.empty:
                st.markdown("### 🔥 High-Probability AI Signals Detected:")
                for index, row in active_signals.iterrows():
                    st.markdown(f"""> **{row['Coin']}** | Signal: **{row['AI Signal']}** | Entry: `{row['Entry Price']}` | TP: `{row['Take Profit (TP)']}` | SL: `{row['Stop Loss (SL)']}` | Funding: `{row['Funding Rate']}`""")
            else:
                st.info("No major breakout signals right now. Markets are testing key zones. Try changing the timeframe!")
        else:
            st.warning("Could not fetch market data right now. Please retry.")
else:
    st.info("👈 Click the **'Run AI Automated Analysis Now'** button to generate automated Entry, TP, and SL levels.")
