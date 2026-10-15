import streamlit as st
import streamlit.components.v1 as components

# Page Configuration
st.set_page_config(
    page_title="Crypto TradingView & Real-Time Funding Rate Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("🔥 Real-Time Crypto TradingView & Funding Rate Terminal")
st.caption("TradingView Live Charts | Real-Time Funding Rate | Order Flow & SMC Setup ($300M+ Liquid Coins)")

# Sidebar Controls for Coin & Exchange Selection
st.sidebar.header("⚙️ Market & Coin Settings")
exchange_choice = st.sidebar.selectbox("Exchange Feed", ["BINANCE", "BYBIT"])
coin_choice = st.sidebar.selectbox(
    "Select Crypto Coin ($300M+ Liquid Market)",
    [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
        "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "SUIUSDT",
        "NEARUSDT", "APTUSDT", "PEPEUSDT", "FETUSDT", "RENDERUSDT", "TAOUSDT"
    ]
)

st.markdown(f"### 📊 Live Interactive Chart: `{exchange_choice}:{coin_choice}`")
st.info("💡 **Tip:** Real-time Funding Rate බලාගැනීමට පහත Chart එකේ ඉහළ ඇති **'Indicators'** (fx) Button එක click කර **'Funding Rate'** ලෙස search කර Chart එකට එකතු කරගන්න.")

# Embedded TradingView Advanced Chart Widget (Bypasses all Cloud / AWS Server Blocks)
tv_symbol = f"{exchange_choice}:{coin_choice}"

tradingview_html = f"""
<!DOCTYPE html>
<html>
<head>
</head>
<body style="margin:0;background-color:#131722;">
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:620px;width:100%">
      <div id="tradingview_widget" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{tv_symbol}",
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
        "hotlist": false,
        "calendar": false,
        "studies": [
          "Funding_Rate@tv-basicstudies",
          "VolumeProfile@tv-basicstudies"
        ],
        "container_id": "tradingview_widget"
      }}
      );
      </script>
    </div>
    <!-- TradingView Widget END -->
</body>
</html>
"""

components.html(tradingview_html, height=640)

# Instructions for Indicators
st.markdown("---")
st.markdown("### 🛠️ Required Strategy Indicators Setup on TradingView:")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    * **Real-Time Funding Rate:** Chart එකේ ඉහළ ඇති `Indicators` ගොස් **Funding Rate** තෝරන්න.
    * **Order Flow & CVD:** Search කරන්න **Cumulative Volume Delta (CVD)**.
    * **Volume Profile:** Chart එකට Fixed Range Volume Profile (FRVP) හෝ Session Volume Profile දාගන්න.
    """)

with col2:
    st.markdown("""
    * **SMC & ICT:** Search කරන්න **Smart Money Concepts [LuxAlgo]**.
    * **Malaysian SnR / CRT:** Search කරන්න **Support Resistance / Malaysian SnR** indicators.
    * **Auto TP/SL:** Risk-Reward tool එක භාවිතයෙන් TP සහ SL levels mark කරගන්න.
    """)
