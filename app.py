import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Crypto Multi-Analysis & TradingView Terminal",
    page_icon="📈",
    layout="wide"
)

st.title("🔥 Real-Time Crypto TradingView & Funding Rate Terminal")
st.caption("SMC | ICT | Malaysian SnR | CVD | Volume Profile | Elliot Wave | Real-Time Funding Rate ($300M+ Liquid Coins)")

st.sidebar.header("⚙️ Market Settings")
exchange_choice = st.sidebar.selectbox("Exchange", ["BINANCE", "BYBIT"])
coin_choice = st.sidebar.selectbox(
    "Select Coin ($300M+ Market Cap)",
    [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
        "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "LINKUSDT", "SUIUSDT",
        "NEARUSDT", "APTUSDT", "PEPEUSDT", "FETUSDT", "RENDERUSDT", "TAOUSDT"
    ]
)

st.markdown(f"### 📊 Live Chart: `{exchange_choice}:{coin_choice}`")
st.info("💡 **Tip:** Add **Funding Rate**, **CVD**, and **Volume Profile** from the TradingView indicator menu above.")

tv_symbol = f"{exchange_choice}:{coin_choice}"

tradingview_html = f"""
<!DOCTYPE html>
<html>
<head>
</head>
<body style="margin:0;background-color:#131722;">
    <div class="tradingview-widget-container" style="height:650px;width:100%">
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
</body>
</html>
"""

components.html(tradingview_html, height=670)

st.markdown("---")
st.markdown("### 🛠️ Required Indicator Stack:")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    * **Funding Rate:** Search `Funding Rate` in TV indicators.
    * **Order Flow & CVD:** Search `Cumulative Volume Delta`.
    * **Volume Profile:** Add `Fixed Range Volume Profile` or `Session Volume Profile`.
    """)

with col2:
    st.markdown("""
    * **SMC & ICT:** Search `Smart Money Concepts [LuxAlgo]`.
    * **Malaysian SnR / CRT:** Search `Support Resistance / Malaysian SnR`.
    * **Elliot Wave:** Search `Auto Elliott Wave` or use manual ZigZag.
    """)
