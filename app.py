import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from simulator import StockSimulator

# ====================== 页面设置（专业版）======================
st.set_page_config(
    page_title="专业A股模拟交易系统",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="collapsed"
)

# ====================== 专业风格CSS（修复按钮点击）=======================
st.markdown("""
<style>
    /* 全局暗黑主题 */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    /* 卡片样式 */
    .stCard {
        background-color: #1A1D24;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        margin-bottom: 20px;
    }
    /* 大数字样式 */
    .big-number {
        font-size: 32px !important;
        font-weight: 700;
        line-height: 1.2;
    }
    /* 标题样式 */
    .card-title {
        font-size: 16px;
        font-weight: 600;
        color: #B0B0B0;
        margin-bottom: 8px;
    }
    /* 按钮样式（修复点击） */
    .stButton > button {
        border-radius: 8px;
        height: 48px;
        font-weight: 600;
        font-size: 16px;
        border: none;
        cursor: pointer;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
    /* 买入按钮绿色 */
    .buy-btn > button {
        background-color: #21C995 !important;
        color: white !important;
    }
    /* 卖出按钮红色 */
    .sell-btn > button {
        background-color: #F74747 !important;
        color: white !important;
    }
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #1A1D24;
        padding: 8px;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #21C995;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ====================== 多账户管理 =======================
if "current_user" not in st.session_state:
    st.session_state.current_user = "user1"

users = StockSimulator.get_all_users()
if not users:
    users = ["user1"]

# ====================== 顶部标题栏 =======================
st.markdown("# 📊 专业A股模拟交易系统")
st.markdown("---")

# ====================== 账户切换 =======================
col_acc1, col_acc2, _ = st.columns([2, 2, 8])
with col_acc1:
    selected_user = st.selectbox("当前账户", users, index=users.index(st.session_state.current_user))
    if selected_user != st.session_state.current_user:
        st.session_state.current_user = selected_user
        st.rerun()
with col_acc2:
    new_user = st.text_input("新建账户", placeholder="输入账户名称")
    if st.button("➕ 创建账户"):
        if new_user and new_user not in users:
            sim = StockSimulator(user_id=new_user)
            sim.save_account()
            st.success(f"✅ 账户 {new_user} 创建成功！")
            st.rerun()

# 初始化交易引擎
sim = StockSimulator(user_id=st.session_state.current_user)

# 自动触发止盈止损条件单
triggered_orders = sim.check_condition_orders()
for msg in triggered_orders:
    st.success(msg)

# ====================== 资金面板（专业卡片）=======================
assets = sim.get_assets()
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.markdown('<p class="card-title">可用资金</p>')
    st.markdown(f'<p class="big-number" style="color:#21C995">¥{assets["cash"]:,}</p>')
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.markdown('<p class="card-title">总资产</p>')
    st.markdown(f'<p class="big-number" style="color:#FFFFFF">¥{assets["total_assets"]:,}</p>')
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.markdown('<p class="card-title">持仓盈亏</p>')
    color = "#21C995" if assets["profit"] >= 0 else "#F74747"
    st.markdown(f'<p class="big-number" style="color:{color}">¥{assets["profit"]:,}</p>')
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.markdown('<p class="card-title">初始资金</p>')
    st.markdown('<p class="big-number" style="color:#B0B0B0">¥100,000.00</p>')
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ====================== 功能标签页 =======================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📗 快速交易",
    "📈 K线图表",
    "⏯ 止盈止损",
    "🧪 策略回测",
    "📋 持仓历史"
])

# -------------------- 1. 交易面板（修复按钮） --------------------
with tab1:
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        st.markdown('<div class="stCard">', unsafe_allow_html=True)
        st.subheader("📗 买入股票")
        code = st.text_input("股票代码（6位数字）", key="buy_code", placeholder="如600000")
        amount = st.number_input("买入股数（100的整数倍）", min_value=100, step=100, value=100)
        
        # 买入按钮（单独容器，修复样式）
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if st.button("✅ 确认买入", type="primary", key="buy_btn"):
                with st.spinner("执行买入中..."):
                    msg = sim.buy(code, amount)
                    st.info(msg)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_sell:
        st.markdown('<div class="stCard">', unsafe_allow_html=True)
        st.subheader("📕 卖出股票")
        if sim.holdings:
            sell_code = st.selectbox(
                "选择持仓", 
                list(sim.holdings.keys()), 
                format_func=lambda x: f"{x} {sim.holdings[x]['name']}",
                key="sell_code"
            )
            max_amt = sim.holdings[sell_code]["amount"]
            sell_amt = st.number_input("卖出股数", min_value=100, step=100, max_value=max_amt, value=100)
            
            col_btn, _ = st.columns([1, 3])
            with col_btn:
                if st.button("❌ 确认卖出", type="primary", key="sell_btn"):
                    with st.spinner("执行卖出中..."):
                        msg = sim.sell(sell_code, sell_amt)
                        st.info(msg)
                        st.rerun()
        else:
            st.info("📭 当前无持仓，无法卖出")
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------- 2. K线图表 --------------------
with tab2:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("📈 个股K线图")
    code = st.text_input("股票代码", key="kline_code", placeholder="如600000")
    period = st.selectbox("K线周期", ["日线", "周线", "月线"], index=0)
    period_map = {"日线": "daily", "周线": "weekly", "月线": "monthly"}

    if st.button("📊 加载K线", key="kline_btn"):
        with st.spinner("获取行情数据中..."):
            df = sim.get_kline_data(code, period_map[period])
            if df is not None and not df.empty:
                # 专业K线图（暗黑主题）
                fig = go.Figure(data=[go.Candlestick(
                    x=df["日期"],
                    open=df["开盘"],
                    high=df["最高"],
                    low=df["最低"],
                    close=df["收盘"],
                    name="K线",
                    increasing_line_color="#21C995",
                    decreasing_line_color="#F74747"
                )])
                # 添加MA5/MA10均线
                fig.add_trace(go.Scatter(
                    x=df["日期"], 
                    y=df["收盘"].rolling(5).mean(), 
                    name="MA5", 
                    line=dict(color="#FFA500", width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=df["日期"], 
                    y=df["收盘"].rolling(10).mean(), 
                    name="MA10", 
                    line=dict(color="#1E90FF", width=2)
                ))
                # 图表样式优化
                fig.update_layout(
                    title=f"{code} {period}K线图",
                    xaxis_title="日期",
                    yaxis_title="价格",
                    template="plotly_dark",
                    paper_bgcolor="#1A1D24",
                    plot_bgcolor="#1A1D24",
                    height=550,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 显示当前价格
                price, name, _, _ = sim.get_price(code)
                if price:
                    st.metric(f"{name} 当前价", f"¥{price:.2f}")
            else:
                st.error("❌ 获取K线数据失败，请检查股票代码")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- 3. 止盈止损条件单 --------------------
with tab3:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("⏯ 止盈止损条件单")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("➕ 新增条件单")
        code = st.text_input("股票代码", key="cond_code", placeholder="如600000")
        order_type = st.selectbox("条件单类型", ["止盈", "止损"], key="cond_type")
        trigger_price = st.number_input("触发价格", min_value=0.01, step=0.01, key="cond_price")
        amount = st.number_input("委托股数", min_value=100, step=100, key="cond_amt")
        
        if st.button("✅ 添加条件单", type="primary", key="cond_btn"):
            with st.spinner("添加中..."):
                msg = sim.add_condition_order(code, order_type, trigger_price, amount)
                st.info(msg)
                st.rerun()
    
    with col2:
        st.subheader("📋 当前条件单")
        if sim.condition_orders:
            df_orders = pd.DataFrame(sim.condition_orders)
            st.dataframe(df_orders, use_container_width=True, hide_index=True)
        else:
            st.info("📭 暂无条件单")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- 4. 策略回测 --------------------
with tab4:
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("🧪 交易策略回测")
    st.info("ℹ️ 云端环境限制，回测功能仅作展示，如需完整回测请使用本地版本")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- 5. 持仓/历史 --------------------
with tab5:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="stCard">', unsafe_allow_html=True)
        st.subheader("📦 当前持仓")
        if sim.holdings:
            holdings_data = []
            for code, item in sim.holdings.items():
                price, _, _, _ = sim.get_price(code)
                if not price:
                    price = 0
                profit = (price - item["cost"]) * item["amount"]
                profit_pct = (price - item["cost"]) / item["cost"] * 100
                holdings_data.append({
                    "股票代码": code,
                    "股票名称": item["name"],
                    "持仓股数": item["amount"],
                    "成本价": f"¥{item['cost']:.2f}",
                    "当前价": f"¥{price:.2f}",
                    "持仓盈亏": f"¥{profit:.2f}",
                    "盈亏比例": f"{profit_pct:.2f}%"
                })
            st.dataframe(pd.DataFrame(holdings_data), use_container_width=True, hide_index=True)
        else:
            st.info("📭 当前空仓")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="stCard">', unsafe_allow_html=True)
        st.subheader("📜 交易历史")
        if sim.trade_history:
            history_data = []
            for log in reversed(sim.trade_history[-50:]):
                history_data.append({
                    "交易时间": log["time"],
                    "交易类型": log["type"],
                    "股票代码": log["code"],
                    "股票名称": log["name"],
                    "成交价格": f"¥{log['price']:.2f}",
                    "成交股数": log["amount"],
                    "手续费": f"¥{log['fee']['total']:.2f}"
                })
            st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)
        else:
            st.info("📭 暂无交易记录")
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== 页脚 =======================
st.markdown("<br><br>", unsafe_allow_html=True)
st.caption("📈 专业A股模拟交易系统 | 真实手续费 | T+1交易规则 | 止盈止损 | 多账户管理 | 手机/电脑随时随地使用")
