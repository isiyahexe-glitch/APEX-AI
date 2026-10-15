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
        symbols = ["XAU/USDT:USDT"]
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
        fetch_sym = "PAXG/USDT:USDT" if "XAU" in symbol else symbol
        
        try:
            funding_info = exchange.fetch_funding_rate(fetch_sym)
            funding_rate = funding_info.get('fundingRate', 0.0001) * 100
        except:
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
            
        display_name = "GOLD (XAU)"
