import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="AI Crypto Pro Terminal & Order Flow",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 AI Pro Crypto Terminal: Analysis, Chart & Orders")
st.caption("Advanced AI Analysis (SMC, Malaysian SnR, CVD, Funding Rate) + Live Chart + API Order Tracker")

# Sidebar - Exchange & API Configuration
st.sidebar.header("⚙️ Exchange & API Connection")
exchange_name = st.sidebar.selectbox("Select Exchange", ["MEXC", "BYBIT"])

# Optional API Keys for Order/Position tracking
with st.sidebar.expander("🔑 Connect Exchange API (Optional for Orders)"):
    api_key_input = st.text_input("API Key", type="password")
    api_secret_input = st.text_input("API Secret", type="password")

# Initialize Exchange
@st.cache_resource
def get_exchange(name, api_key, api_secret):
    config = {'options': {'defaultType': 'swap'}, 'enableRateLimit': True}
    if api_key and api_secret:
        config['apiKey'] = api_key
        config['secret'] = api_secret
        
    if name == "BYBIT":
        return ccxt.bybit(config)
    else:
        return ccxt.mexc(config)

exchange = get_exchange(exchange_name, api_key_input, api_secret_input)

# Sidebar - Coin Search & Strategy Settings
st.sidebar.header("📊 Market & Strategy Settings")
coin_search = st.sidebar.text_input("Search Coin (e.g. BTC, ETH, SOL, PEPE)", value="BTC")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h", "4h"], index=1)

risk_reward = st.sidebar.slider("Risk-to-Reward Ratio (TP Multiplier)", 1.0, 5.0, 2.0, 0.5)
sl_mult = st.sidebar.slider("Stop Loss ATR Multiplier", 1.0, 3.0, 1.5, 0.1)

# Format Symbol
formatted_symbol = f"{coin_search.upper().strip()}/USDT:USDT"

# Pure Pandas ATR Calculation
def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()

# AI Analysis Engine
def run_analysis(symbol, tf):
    try:
        # Fetch Funding Rate
        funding_info = exchange.fetch_funding_rate(symbol)
        funding_rate = funding_info.get('fundingRate', 0.0001) * 100

        # Fetch OHLCV Candlestick Data
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
            signal = "BUY / LONG 🚀"
            sl = last_close - (last_atr * sl_mult)
            tp = last_close + ((last_close - sl) * risk_reward)
        elif last_close < sup_zone and not cvd_bullish:
            signal = "SELL / SHORT 📉"
            sl = last_close + (last_atr * sl_mult)
            tp = last_close - ((sl - last_close) * risk_reward)
            
        return {
            "Price": last_close,
            "Funding Rate": funding_rate,
            "CVD": "BULLISH 🟢" if cvd_bullish else "BEARISH 🔴",
            "Signal": signal,
            "Entry": last_close if "NEUTRAL" not in signal else 0,
            "TP": tp if "NEUTRAL" not in signal else 0,
            "SL": sl if "NEUTRAL" not in signal else 0
        }
    except Exception as e:
        return None

# Main Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"📊 Live TradingView Chart: `{formatted_symbol}`")
    
    # Embedded TradingView Chart Widget
    tv_exchange = "BYBIT" if exchange_name == "BYBIT" else "MEXC"
    tv_symbol_str = f"{tv_exchange}:{coin_search.upper().strip()}USDT"
    
    tradingview_html = f"""
    <!DOCTYPE html>
    <html>
    <head></head>
    <body style="margin:0;background-color:#131722;">
        <div class="tradingview-widget-container" style="height:550px;width:100%">
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
    components.html(tradingview_html, height=570)

with col2:
    st.subheader("🤖 AI Analysis & Trade Setup")
    
    with st.spinner("Analyzing market structure..."):
        analysis = run_analysis(formatted_symbol, timeframe)
        
    if analysis:
        st.metric(label="Current Price", value=f"${analysis['Price']:,.4f}")
        st.metric(label="Real-Time Funding Rate", value=f"{analysis['Funding Rate']:.4f}%")
        st.metric(label="CVD / Order Flow", value=analysis['CVD'])
        
        st.markdown("---")
        st.markdown(f"### Signal: **{analysis['Signal']}**")
        if "NEUTRAL" not in analysis['Signal']:
            st.success(f"**Entry:** `${analysis['Entry']:,.4f}`\n\n**Take Profit (TP):** `${analysis['TP']:,.4f}`\n\n**Stop Loss (SL):** `${analysis['SL']:,.4f}`")
        else:
            st.info("Market is consolidating. Wait for breakout of key Malaysian SnR zones.")
    else:
        st.error("Could not fetch data for this coin. Please check the symbol name (e.g. BTC, ETH, SOL).")

# API Orders & Positions Section
st.markdown("---")
st.subheader("📋 Connected Exchange Orders & Positions")
if api_key_input and api_secret_input:
    try:
        open_orders = exchange.fetch_open_orders(formatted_symbol)
        positions = exchange.fetch_positions([formatted_symbol]) if hasattr(exchange, 'fetch_positions') else []
        
        col_ord, col_pos = st.columns(2)
        with col_ord:
            st.markdown("#### Open Orders")
            if open_orders:
                st.write(pd.DataFrame(open_orders)[['id', 'type', 'side', 'price', 'amount']])
            else:
                st.info("No open orders found for this coin.")
                
        with col_pos:
            st.markdown("#### Open Positions")
            if positions:
                st.write(pd.DataFrame(positions)[['symbol', 'side', 'contracts', 'entryPrice', 'unrealizedPnl']])
            else:
                st.info("No active positions found.")
    except Exception as e:
        st.warning(f"API Connection notice: Ensure correct API keys or permissions (Futures enabled). Details: {e}")
else:
    st.info("💡 **Tip:** To view your live Exchange Orders and Positions here, enter your Exchange API Key and Secret in the sidebar options.")
