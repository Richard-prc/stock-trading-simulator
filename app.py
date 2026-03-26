import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from simulator import StockSimulator

st.set_page_config(page_title="专业A股模拟操盘系统", layout="wide", page_icon="📈")
st.title("📈 专业A股模拟操盘系统")

if "current_user" not in st.session_state:
    st.session_state.current_user = "user1"

users = StockSimulator.get_all_users()
if not users:
    users = ["user1"]

col1, col2, col3 = st.columns([2, 2, 6])
with col1:
    selected_user = st.selectbox("当前账户", users, index=users.index(st.session_state.current_user))
    if selected_user != st.session_state.current_user:
        st.session_state.current_user = selected_user
        st.rerun()
with col2:
    new_user = st.text_input("新建账户", placeholder="输入新账户名")
    if st.button("创建账户"):
        if new_user and new_user not in users:
            sim = StockSimulator(user_id=new_user)
            sim.save_account()
            st.success(f"账户 {new_user} 创建成功！")
            st.rerun()

sim = StockSimulator(user_id=st.session_state.current_user)
triggered_orders = sim.check_condition_orders()
for msg in triggered_orders:
    st.success(msg)

assets = sim.get_assets()
col1, col2, col3, col4 = st.columns(4)
col1.metric("可用资金", f"¥{assets['cash']:,}")
col2.metric("总资产", f"¥{assets['total_assets']:,}")
col3.metric("持仓盈亏", f"¥{assets['profit']:,}", delta=f"{assets['profit']/100000*100:.2f}%")
col4.metric("初始资金", "¥100,000.00")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 交易", "📈 K线图", "🔍 条件单", "📊 策略回测", "📋 持仓/历史"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("买入股票")
        code = st.text_input("股票代码（如600000）", key="buy_code")
        amount = st.number_input("买入股数（100整数倍）", min_value=100, step=100)
        if st.button("买入", type="primary"):
            msg = sim.buy(code, amount)
            st.info(msg)
            st.rerun()

    with col2:
        st.subheader("卖出股票")
        if sim.holdings:
            sell_code = st.selectbox("选择持仓", list(sim.holdings.keys()), format_func=lambda x: f"{x} {sim.holdings[x]['name']}")
            sell_amount = st.number_input("卖出股数", min_value=100, step=100)
            if st.button("卖出", type="primary"):
                msg = sim.sell(sell_code, sell_amount)
                st.info(msg)
                st.rerun()
        else:
            st.write("暂无持仓")

with tab2:
    st.subheader("个股K线图")
    code = st.text_input("输入股票代码", key="kline_code")
    period = st.selectbox("周期", ["日线", "周线", "月线"])
    period_map = {"日线": "daily", "周线": "weekly", "月线": "monthly"}

    if code and st.button("查询K线"):
        df = sim.get_kline_data(code, period_map[period])
        if df is not None and not df.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=df["日期"], open=df["开盘"], high=df["最高"], low=df["最低"], close=df["收盘"]
            )])
            fig.add_trace(go.Scatter(x=df["日期"], y=df["收盘"].rolling(5).mean(), name="MA5"))
            fig.add_trace(go.Scatter(x=df["日期"], y=df["收盘"].rolling(10).mean(), name="MA10"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("云端暂时无法获取K线数据")

with tab3:
    st.subheader("止盈止损条件单")
    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("股票代码")
        order_type = st.selectbox("类型", ["止盈", "止损"])
        trigger_price = st.number_input("触发价格", min_value=0.01)
        amount = st.number_input("委托股数", min_value=100, step=100)
        if st.button("添加条件单", type="primary"):
            msg = sim.add_condition_order(code, order_type, trigger_price, amount)
            st.info(msg)
            st.rerun()
    with col2:
        st.dataframe(pd.DataFrame(sim.condition_orders), use_container_width=True, hide_index=True)

with tab4:
    st.subheader("策略回测（云端简化版）")
    st.info("云端网络限制，回测功能暂时简化使用")

with tab5:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("当前持仓")
        holdings_data = []
        for code, item in sim.holdings.items():
            price, _, _, _ = sim.get_price(code)
            profit = (price - item["cost"]) * item["amount"] if price else 0
            holdings_data.append({
                "代码": code, "名称": item["name"], "持仓": item["amount"],
                "成本": item["cost"], "当前价": price if price else "获取失败", "盈亏": profit
            })
        st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("交易历史")
        history_data = []
        for log in reversed(sim.trade_history[-50:]):
            history_data.append(log)
        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)

st.caption("✅ 云端专业版 | 手机/电脑随时随地交易")
