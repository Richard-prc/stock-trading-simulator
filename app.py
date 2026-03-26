import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from simulator import StockSimulator

st.set_page_config(page_title="专业A股模拟操盘系统", layout="wide", page_icon="📈")
st.title("📈 专业A股模拟操盘系统")

# 多账户管理
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
        st.experimental_rerun()
with col2:
    new_user = st.text_input("新建账户", placeholder="输入新账户名")
    if st.button("创建账户"):
        if new_user and new_user not in users:
            sim = StockSimulator(user_id=new_user)
            sim.save_account()
            st.success(f"账户 {new_user} 创建成功！")
            st.experimental_rerun()

sim = StockSimulator(user_id=st.session_state.current_user)
triggered_orders = sim.check_condition_orders()
for msg in triggered_orders:
    st.success(msg)

# 资产概览
assets = sim.get_assets()
col1, col2, col3, col4 = st.columns(4)
col1.metric("可用资金", f"¥{assets['cash']:,}")
col2.metric("总资产", f"¥{assets['total_assets']:,}")
col3.metric("持仓盈亏", f"¥{assets['profit']:,}", delta=f"{assets['profit']/100000*100:.2f}%")
col4.metric("初始资金", "¥100,000.00")

# 主界面分栏
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 交易", "📈 K线图", "🔍 条件单", "📊 策略回测", "📋 持仓/历史"])

# 交易页
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("买入股票")
        code = st.text_input("股票代码（如600000）", key="buy_code")
        amount = st.number_input("买入股数（100整数倍）", min_value=100, step=100, key="buy_amount")
        if st.button("买入", type="primary"):
            msg = sim.buy(code, amount)
            st.info(msg)
            st.experimental_rerun()

    with col2:
        st.subheader("卖出股票")
        if sim.holdings:
            sell_code = st.selectbox("选择持仓", list(sim.holdings.keys()), format_func=lambda x: f"{x} {sim.holdings[x]['name']}", key="sell_code")
            sell_amount = st.number_input("卖出股数", min_value=100, step=100, key="sell_amount")
            if st.button("卖出", type="primary"):
                msg = sim.sell(sell_code, sell_amount)
                st.info(msg)
                st.experimental_rerun()
        else:
            st.write("暂无持仓")

# K线图页
with tab2:
    st.subheader("个股K线图")
    code = st.text_input("输入股票代码", key="kline_code")
    period = st.selectbox("周期", ["日线", "周线", "月线"], index=0)
    period_map = {"日线": "daily", "周线": "weekly", "月线": "monthly"}

    if code and st.button("查询K线"):
        df = sim.get_kline_data(code, period_map[period])
        if df is not None:
            fig = go.Figure(data=[go.Candlestick(
                x=df["日期"],
                open=df["开盘"],
                high=df["最高"],
                low=df["最低"],
                close=df["收盘"],
                name="K线"
            )])
            fig.add_trace(go.Scatter(x=df["日期"], y=df["收盘"].rolling(5).mean(), name="MA5", line=dict(color="orange")))
            fig.add_trace(go.Scatter(x=df["日期"], y=df["收盘"].rolling(10).mean(), name="MA10", line=dict(color="blue")))
            fig.update_layout(
                title=f"{code} {period}K线图",
                xaxis_title="日期",
                yaxis_title="价格",
                template="plotly_dark",
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

            price, name, _, _ = sim.get_price(code)
            st.metric(f"{name} 当前价", f"¥{price:.2f}")
        else:
            st.error("获取K线数据失败")

# 条件单页
with tab3:
    st.subheader("止盈止损条件单")
    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("股票代码", key="condition_code")
        order_type = st.selectbox("条件单类型", ["止盈", "止损"])
        trigger_price = st.number_input("触发价格", min_value=0.01, step=0.01)
        amount = st.number_input("委托股数", min_value=100, step=100)
        if st.button("添加条件单", type="primary"):
            msg = sim.add_condition_order(code, order_type, trigger_price, amount)
            st.info(msg)
            st.experimental_rerun()

    with col2:
        st.subheader("当前条件单")
        if sim.condition_orders:
            df = pd.DataFrame(sim.condition_orders)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.write("暂无条件单")

# 策略回测页
with tab4:
    st.subheader("交易策略回测")
    code = st.text_input("股票代码", key="backtest_code")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("结束日期", value=datetime.now())

    strategy = st.selectbox("选择策略", ["均线金叉死叉(MA5/MA10)"])
    initial_cash = st.number_input("初始资金", value=100000, min_value=10000)

    if st.button("开始回测", type="primary"):
        with st.spinner("回测中..."):
            result, msg = sim.backtest_strategy(code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), initial_cash)
            if result:
                st.success(msg)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("初始资金", f"¥{result['initial_cash']:,}")
                col2.metric("最终资产", f"¥{result['final_value']:,}")
                col3.metric("总收益率", f"{result['total_return']}%")
                col4.metric("最大回撤", f"{result['max_drawdown']}%")

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=result["portfolio"]["date"], y=result["portfolio"]["total_value"], name="资产净值", line=dict(color="green")))
                fig.update_layout(
                    title="回测资产净值曲线",
                    xaxis_title="日期",
                    yaxis_title="资产价值",
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("交易记录")
                st.dataframe(pd.DataFrame(result["trades"]), use_container_width=True, hide_index=True)
            else:
                st.error(msg)

# 持仓/历史页
with tab5:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("当前持仓")
        if sim.holdings:
            holdings_data = []
            for code, item in sim.holdings.items():
                price, _, _, _ = sim.get_price(code)
                profit = (price - item["cost"]) * item["amount"]
                profit_pct = (price - item["cost"]) / item["cost"] * 100
                holdings_data.append({
                    "代码": code,
                    "名称": item["name"],
                    "持仓股数": item["amount"],
                    "成本价": f"¥{item['cost']:.2f}",
                    "当前价": f"¥{price:.2f}",
                    "持仓盈亏": f"¥{profit:.2f}",
                    "盈亏比例": f"{profit_pct:.2f}%"
                })
            st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)
        else:
            st.write("空仓")

    with col2:
        st.subheader("交易历史")
        if sim.trade_history:
            history_data = []
            for log in reversed(sim.trade_history[-50:]):
                history_data.append({
                    "时间": log["time"],
                    "类型": log["type"],
                    "代码": log["code"],
                    "名称": log["name"],
                    "价格": f"¥{log['price']:.2f}",
                    "股数": log["amount"],
                    "手续费": f"¥{log['fee']['total']:.2f}"
                })
            st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)
        else:
            st.write("暂无交易记录")

# 页脚
st.markdown("---")
st.caption("专业A股模拟操盘系统 | 支持T+1、涨跌停、真实手续费、条件单、策略回测")