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
    page_title="AI Pro Crypto & Gold Terminal (Funding & DOM)",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ AI Pro Crypto & Gold Terminal (Funding Rates, DOM & Heatmap)")
st.caption("Real-Time Funding Rates | DOM Depth Chart | Liquidity Heatmap | AI Signals & TP/SL")

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

# Fetch Top Coins with Market Cap > $300M + Gold (XAU)
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

# Advanced Analysis & Real-Time Funding Rate Fetch
def analyze_asset(symbol, tf):
    try:
        fetch_sym = "PAXG/USDT:USDT" if "XAU" in symbol else symbol
        
        # Real-Time Funding Rate Fetch
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

run_scan = st.button("🚀 Run Master Scan ($300M+ Coins & Gold)")

assets = get_top_assets()

if run_scan:
    with st.spinner("Scanning all $300M+ coins and Gold (XAU), fetching live funding rates & liquidity pools..."):
        scanned = []
        for asset in assets:
            res = analyze_asset(asset, timeframe)
            if res:
                scanned.append(res)
        if scanned:
            st.session_state['scan_data'] = pd.DataFrame(scanned)
            st.success("✅ Scan & Live Funding Rate Fetch Completed!")

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
        st.subheader("📊 Master Market Scanner & Real-Time Funding Rates")
        
        target_columns = ['Asset', 'Price', 'Funding Rate (%)', 'CVD Flow', 'Signal', 'Buy-Side Liquidity Pool', 'Sell-Side Liquidity Pool']
        safe_columns = [col for col in target_columns if col in df_results.columns]
        
        st.dataframe(df_results[safe_columns], use_container_width=True, height=330)
        
        # --- Funding Rate Squeeze Radar ---
        st.markdown("---")
        st.subheader("🔥 Real-Time Funding Rate Squeeze Radar")
        col_fr1, col_fr2 = st.columns(2)
        
        with col_fr1:
            st.markdown("#### 🚀 Highest Positive Funding Rates (Long Squeeze Risk)")
            high_fr = df_results.sort_values(by="Funding Rate (%)", ascending=False).head(3)
            for idx, row in high_fr.iterrows():
                st.markdown(f"• **{row['Asset']}**: `{row['Funding Rate (%)']}%` (Price: ${row['Price']})")
                
        with col_fr2:
            st.markdown("#### 📉 Most Negative Funding Rates (Short Squeeze Risk)")
            low_fr = df_results.sort_values(by="Funding Rate (%)", ascending=True).head(3)
            for idx, row in low_fr.iterrows():
                st.markdown(f"• **{row['Asset']}**: `{row['Funding Rate (%)']}%` (Price: ${row['Price']})")

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
                <!DOCTYPE html>
                <html>
                <head></head>
                <body style="margin:0;background-color:#131722;">
                    <div class="tradingview-widget-container" style="height:500px;width:100%">
                      <div id="tradingview_widget" style="height:100%;width:100%"></div>
                      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                      <script type="text/javascript">
                      new TradingView.widget(
                      {
                        "autosize": true,
                        "symbol": "TV_SYMBOL_PLACEHOLDER",
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
                      });
                      </script>
                    </div>
                </body>
                </html>
                """.replace("TV_SYMBOL_PLACEHOLDER", tv_symbol_str)
                components.html(tradingview_html, height=520)
                
            with tab_dom:
                st.markdown(f"### 📊 Depth of Market (DOM) / Order Book: `{selected_asset}`")
                try:
                    order_book = exchange.fetch_order_book(raw_sym, limit=25)
                    bids = pd.DataFrame(order_book['bids'], columns=['Price', 'Amount'])
                    asks = pd.DataFrame(order_book['asks'], columns=['Price', 'Amount'])
                    
                    bids['Cumulative'] = bids['Amount'].cumsum()
                    asks['Cumulative'] = asks['Amount'].cumsum()
                    
                    fig_dom = go.Figure()
                    fig_dom.add_trace(go.Scatter(x=bids['Price'], y=bids['Cumulative'], name='Bids (Buy Wall)', fill='tozeroy', line_color='green'))
                    fig_dom.add_trace(go.Scatter(x=asks['Price'], y=asks['Cumulative'], name='Asks (Sell Wall)', fill='tozeroy', line_color='red'))
                    fig_dom.update_layout(title=f"Order Book Depth ({selected_asset})", template="plotly_dark", height=450, xaxis_title="Price", yaxis_title="Cumulative Volume")
                    st.plotly_chart(fig_dom, use_container_width=True)
                except Exception as e:
                    st.warning("Could not fetch real-time DOM order book for this asset right now.")
                    
            with tab_heatmap:
                st.markdown(f"### 🔥 Whale Leverage Liquidity Heatmap: `{selected_asset}`")
                st.caption("Estimated Liquidation Clusters across 10x, 25x, 50x, and 100x leverage tiers.")
                try:
                    curr_p = asset_row['Price']
                    leverages = [10, 25, 50, 100]
                    heatmap_prices = []
                    heatmap_liquidity = []
                    
                    for lev in leverages:
                        long_liq = curr_p * (1 - (0.9 / lev))
                        short_liq = curr_p * (1 + (0.9 / lev))
                        
                        heatmap_prices.extend([long_liq, short_liq])
                        heatmap_liquidity.extend([lev * 15000, lev * 20000])
                        
                    df_heat = pd.DataFrame({'Price': heatmap_prices, 'Liquidity': heatmap_liquidity})
                    
                    fig_heat = px.density_heatmap(df_heat, x="Price", y="Liquidity", nbinsx=20, title=f"Estimated Liquidation Heatmap Zones ({selected_asset})", color_continuous_scale="Viridis")
                    fig_heat.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig_heat, use_container_width=True)
                except Exception as e:
                    st.warning("Could not render heatmap for this asset.")

            # --- RISK CALCULATOR & TP/SL PANEL ---
            st.markdown("---")
            st.subheader("🧮 AI Setup, TP/SL & Risk Calculator")
            
            col_setup, col_calc = st.columns(2)
            
            with col_setup:
                st.info(f"Signal: **{asset_row['Signal']}**")
                entry_p = asset_row['Entry']
                tp_p = asset_row['TP']
                sl_p = asset_row['SL']
                
                st.metric(label="Real-Time Funding Rate", value=f"{asset_row['Funding Rate (%)']}%")
                
                if "NEUTRAL" not in asset_row['Signal'] and entry_p >
