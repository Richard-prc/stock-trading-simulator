import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
from simulator import StockSimulator

# 时区
TZ = pytz.timezone("Asia/Shanghai")

st.set_page_config(
    page_title="多账户模拟交易",
    layout="wide",
    page_icon="📊"
)

# ====================== 多账户系统 ======================
if "accounts" not in st.session_state:
    st.session_state.accounts = {
        "账户1": StockSimulator(100000),
    }
if "current_account" not in st.session_state:
    st.session_state.current_account = "账户1"

# 侧边栏：账户管理
with st.sidebar:
    st.title("🏦 账户管理")
    accounts = list(st.session_state.accounts.keys())
    current = st.selectbox(
        "当前账户",
        accounts,
        index=accounts.index(st.session_state.current_account)
    )
    st.session_state.current_account = current

    new_acc = st.text_input("新账户名称")
    if st.button("➕ 新增账户"):
        if new_acc and new_acc not in st.session_state.accounts:
            st.session_state.accounts[new_acc] = StockSimulator(100000)
            st.session_state.current_account = new_acc
            st.rerun()

    if len(accounts) > 1:
        if st.button("🗑️ 删除当前账户"):
            del st.session_state.accounts[current]
            st.session_state.current_account = list(st.session_state.accounts.keys())[0]
            st.rerun()

    st.divider()
    st.caption(f"北京时间：{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")

# 当前账户
sim = st.session_state.accounts[st.session_state.current_account]

# 自动执行预委托
for msg in sim.process_pending_orders():
    st.success(msg)

for msg in sim.check_condition_orders():
    st.success(msg)

# 极简样式
st.markdown("""
<style>
.stMetric {
    background: #fff;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
}
.stButton>button {
    border-radius: 8px;
    height: 46px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title(f"📊 交易系统 — {st.session_state.current_account}")
st.divider()

# 资产面板
assets = sim.get_assets()
c1, c2, c3, c4 = st.columns(4)
c1.metric("可用资金", f"¥{assets['cash']:,}")
c2.metric("总资产", f"¥{assets['total']:,}")
c3.metric("持仓盈亏", f"¥{assets['profit']:,}", delta=f"{assets['profit']/100000*100:.2f}%")
c4.metric("初始资金", "¥100,000")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📗 交易", "📈 K线", "⏯ 止盈止损", "📋 持仓"])

# 交易
with tab1:
    bc, sc = st.columns(2)
    with bc:
        st.subheader("买入")
        code = st.text_input("股票代码", key="bcode")
        amt = st.number_input("股数", 100, step=100)
        if st.button("✅ 买入", type="primary", use_container_width=True):
            r = sim.buy(code, amt)
            st.info(r)
            st.rerun()
    with sc:
        st.subheader("卖出")
        if sim.holdings:
            scode = st.selectbox("持仓", list(sim.holdings.keys()),
                                 format_func=lambda x: f"{x} {sim.holdings[x]['name']}")
            maxa = sim.holdings[scode]["amount"]
            samt = st.number_input("卖出股数", 100, step=100, max_value=maxa)
            if st.button("❌ 卖出", type="primary", use_container_width=True):
                r = sim.sell(scode, samt)
                st.info(r)
                st.rerun()
        else:
            st.info("空仓")

    if sim.pending_orders:
        st.divider()
        st.subheader("⏸ 预委托（开盘自动成交）")
        st.dataframe(pd.DataFrame(sim.pending_orders), hide_index=True)

# K线
with tab2:
    st.subheader("K线图表")
    code = st.text_input("代码", key="kcode")
    period = st.selectbox("周期", ["日线", "周线", "月线"])
    pm = {"日线": "daily", "周线": "weekly", "月线": "monthly"}
    if st.button("📊 加载K线"):
        df = sim.get_kline_data(code, pm[period])
        if not df.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=df["日期"], open=df["开盘"], high=df["最高"], low=df["最低"], close=df["收盘"]
            )])
            fig.update_layout(template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)

# 止盈止损
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("新增条件单")
        code = st.text_input("代码", key="condcode")
        t = st.selectbox("类型", ["止盈", "止损"])
        p = st.number_input("触发价", 0.01, step=0.01)
        amt = st.number_input("股数", 100, step=100)
        if st.button("✅ 添加", type="primary", use_container_width=True):
            r = sim.add_condition_order(code, t, p, amt)
            st.info(r)
    with c2:
        st.subheader("条件单列表")
        if sim.condition_orders:
            st.dataframe(pd.DataFrame(sim.condition_orders), hide_index=True)
        else:
            st.info("无")

# 持仓 & 历史
with tab4:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("当前持仓")
        if sim.holdings:
            data = []
            for code, item in sim.holdings.items():
                p, _, _, _ = sim.get_price(code)
                p = p if p else item["cost"]
                prof = (p - item["cost"]) * item["amount"]
                data.append({
                    "代码": code,
                    "名称": item["name"],
                    "股数": item["amount"],
                    "成本": f"{item['cost']:.2f}",
                    "现价": f"{p:.2f}",
                    "盈亏": f"{prof:.0f}"
                })
            st.dataframe(pd.DataFrame(data), hide_index=True)
        else:
            st.info("空仓")
    with c2:
        st.subheader("交易记录")
        if sim.trade_history:
            st.dataframe(pd.DataFrame(sim.trade_history[-50:][::-1]), hide_index=True)
        else:
            st.info("无记录")

st.divider()
st.caption("📈 多账户 | 北京时间 | 休市预委托 | T+1 模拟交易")
