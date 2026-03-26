import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from simulator import StockSimulator

st.set_page_config(page_title="专业A股模拟交易", layout="wide", page_icon="📊")

# 🔴 核心：只初始化一次sim
if "sim" not in st.session_state:
    st.session_state.sim = StockSimulator(initial_cash=100000)
sim = st.session_state.sim

# 开盘自动处理预委托
executed = sim.process_pending_orders()
for msg in executed:
    st.success(msg)

# 条件单触发
triggered = sim.check_condition_orders()
for msg in triggered:
    st.success(msg)

# CSS（白色清爽界面）
st.markdown("""
<style>
    .stMetric {background:#fff; border-radius:12px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.08);}
    .stButton>button {border-radius:8px; height:46px; font-weight:600;}
</style>
""", unsafe_allow_html=True)

st.title("📊 专业A股模拟交易系统")
st.divider()

# 资金面板
assets = sim.get_assets()
c1,c2,c3,c4=st.columns(4)
c1.metric("可用资金", f"¥{assets['cash']:,}")
c2.metric("总资产", f"¥{assets['total']:,}")
c3.metric("持仓盈亏", f"¥{assets['profit']:,}", delta=f"{assets['profit']/100000*100:.2f}%")
c4.metric("初始资金", "¥100,000")

st.divider()

tab1,tab2,tab3,tab4=st.tabs(["📗 快速交易","📈 K线图表","⏯ 止盈止损","📋 持仓历史"])

# 1. 快速交易
with tab1:
    buy_col, sell_col = st.columns(2)
    with buy_col:
        st.subheader("📗 买入股票")
        code=st.text_input("股票代码（6位）", key="buy_code")
        amt=st.number_input("买入股数", min_value=100, step=100, value=100)
        if st.button("✅ 确认买入", type="primary", use_container_width=True):
            res=sim.buy(code, amt)
            st.info(res)
            st.rerun()
    with sell_col:
        st.subheader("📕 卖出股票")
        if sim.holdings:
            sell_code=st.selectbox("选择持仓", list(sim.holdings.keys()),
                                  format_func=lambda x: f"{x} {sim.holdings[x]['name']}")
            max_amt=sim.holdings[sell_code]["amount"]
            sell_amt=st.number_input("卖出股数", min_value=100, step=100, max_value=max_amt)
            if st.button("❌ 确认卖出", type="primary", use_container_width=True):
                res=sim.sell(sell_code, sell_amt)
                st.info(res)
                st.rerun()
        else:
            st.info("📭 当前空仓")

    # 显示预委托单
    if sim.pending_orders:
        st.divider()
        st.subheader("⏸️ 休市预委托单（开盘自动成交）")
        st.dataframe(pd.DataFrame(sim.pending_orders), hide_index=True)

# 2. K线
with tab2:
    st.subheader("📈 K线图表")
    code=st.text_input("股票代码", key="kcode")
    period=st.selectbox("周期", ["日线","周线","月线"])
    p_map={"日线":"daily","周线":"weekly","月线":"monthly"}
    if st.button("📊 加载K线"):
        df=sim.get_kline_data(code, p_map[period])
        if not df.empty:
            fig=go.Figure(data=[go.Candlestick(x=df["日期"],open=df["开盘"],high=df["最高"],low=df["最低"],close=df["收盘"])])
            fig.update_layout(template="plotly_white", height=500)
            st.plotly_chart(fig, use_container_width=True)

# 3. 止盈止损
with tab3:
    st.subheader("⏯ 止盈止损")
    c1,c2=st.columns(2)
    with c1:
        code=st.text_input("股票代码", key="condcode")
        t=st.selectbox("类型", ["止盈","止损"])
        p=st.number_input("触发价", min_value=0.01, step=0.01)
        amt=st.number_input("股数", min_value=100, step=100)
        if st.button("✅ 添加条件单", type="primary", use_container_width=True):
            res=sim.add_condition_order(code,t,p,amt)
            st.info(res)
    with c2:
        if sim.condition_orders:
            st.dataframe(pd.DataFrame(sim.condition_orders), hide_index=True)
        else:
            st.info("📭 暂无条件单")

# 4. 持仓历史
with tab4:
    c1,c2=st.columns(2)
    with c1:
        st.subheader("📦 当前持仓")
        if sim.holdings:
            holds=[]
            for c,item in sim.holdings.items():
                p,_,_,_=sim.get_price(c)
                p=p if p else 0
                prof=(p-item["cost"])*item["amount"]
                holds.append({"代码":c,"名称":item["name"],"股数":item["amount"],
                              "成本":f"¥{item['cost']:.2f}","现价":f"¥{p:.2f}",
                              "盈亏":f"¥{prof:.2f}"})
            st.dataframe(pd.DataFrame(holds), hide_index=True)
        else:
            st.info("📭 空仓")
    with c2:
        st.subheader("📜 交易历史")
        if sim.trade_history:
            st.dataframe(pd.DataFrame(sim.trade_history[-50:][::-1]), hide_index=True)
        else:
            st.info("📭 无记录")

st.divider()
st.caption("📈 专业模拟交易 | T+1 | 手续费 | 止盈止损 | 休市预委托")
