# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from simulator import StockTradingSimulator

# 页面配置
st.set_page_config(
    page_title="A股交易模拟器",
    page_icon="📈",
    layout="wide"
)

# 初始化模拟器
if 'sim' not in st.session_state:
    st.session_state.sim = StockTradingSimulator(initial_cash=100000.0)
    st.session_state.last_update = datetime.now()

# 获取模拟器实例
sim = st.session_state.sim

# 标题
st.title("📈 A股交易模拟器")
st.caption(f"当前时间: {sim.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 侧边栏 - 控制面板
with st.sidebar:
    st.header("控制面板")
    
    # 时间模拟控制
    st.subheader("时间模拟（调试用）")
    use_real_time = st.checkbox("使用真实时间", value=True)
    
    if not use_real_time:
        mock_date = st.date_input("模拟日期", value=sim.now().date())
        mock_time = st.time_input("模拟时间", value=sim.now().time())
        mock_datetime = datetime.combine(mock_date, mock_time)
        
        if st.button("设置模拟时间"):
            sim.set_mock_time(mock_datetime)
            st.success(f"模拟时间已设置为: {mock_datetime}")
            st.rerun()
        
        if st.button("恢复真实时间"):
            sim.set_mock_time(None)
            st.success("已恢复使用真实时间")
            st.rerun()
    else:
        if st.button("刷新时间"):
            st.rerun()
    
    # 重置模拟器
    st.subheader("系统控制")
    if st.button("重置模拟器"):
        st.session_state.clear()
        st.rerun()
    
    # 手动处理预委托和条件单
    st.subheader("手动处理")
    if st.button("处理预委托单"):
        results = sim.process_pending_orders()
        if results:
            for r in results:
                if r["success"]:
                    st.success(r["message"])
                else:
                    st.error(r["message"])
        else:
            st.info("没有待处理的预委托单")
    
    if st.button("检查条件单"):
        triggered = sim.check_conditional_orders()
        if triggered:
            for t in triggered:
                if t["success"]:
                    st.success(f"条件单触发: {t['message']}")
                else:
                    st.error(f"条件单触发失败: {t['message']}")
        else:
            st.info("没有条件单被触发")
    
    # 清除缓存
    if st.button("清除价格缓存"):
        sim.clear_price_cache()
        st.success("价格缓存已清除")

# 主界面
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 资产概览", "💰 交易", "📋 持仓", "📜 历史记录", "⚙️ 条件单"])

with tab1:
    st.header("资产概览")
    
    # 强制刷新价格缓存，确保显示最新数据
    sim.clear_price_cache()
    
    # 更新持仓可用数量
    sim.update_position_availability()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("现金余额", f"{sim.cash:.2f}元")
    with col2:
        total_assets = sim.get_total_assets()
        st.metric("总资产", f"{total_assets:.2f}元")
    with col3:
        profit = total_assets - 100000.0
        profit_color = "normal" if profit >= 0 else "inverse"
        st.metric("盈亏", f"{profit:.2f}元", delta=f"{profit/1000:.2f}%", delta_color=profit_color)
    
    # 交易时间状态
    is_trading = sim.is_trading_time()
    status_color = "green" if is_trading else "red"
    status_text = "交易时间内" if is_trading else "非交易时间"
    st.markdown(f"交易状态: <span style='color:{status_color};font-weight:bold'>{status_text}</span>", unsafe_allow_html=True)
    
    # 持仓市值分布
    st.subheader("持仓明细")
    if sim.positions:
        position_data = []
        for code, pos in sim.positions.items():
            price = sim.get_price(code, use_cache=False)
            market_value = pos["amount"] * price
            profit_loss = market_value - (pos["amount"] * pos["cost"])
            profit_loss_pct = (profit_loss / (pos["amount"] * pos["cost'])) * 100 if pos["amount"] * pos["cost"] > 0 else 0
            
            position_data.append({
                "股票代码": code,
                "持仓数量": pos["amount"],
                "可用数量": pos["available"],
                "成本价": f"{pos['cost']:.2f}",
                "当前价": f"{price:.2f}",
                "市值": f"{market_value:.2f}",
                "盈亏": f"{profit_loss:.2f}",
                "盈亏%": f"{profit_loss_pct:.2f}%"
            })
        
        df_positions = pd.DataFrame(position_data)
        st.dataframe(df_positions, use_container_width=True)
        
        # 计算持仓比例
        if not df_positions.empty:
            df_positions["市值数值"] = df_positions["市值"].str.replace("元", "").astype(float)
            st.subheader("持仓分布")
            st.pie_chart(df_positions, x="股票代码", y="市值数值")
    else:
        st.info("暂无持仓")

with tab2:
    st.header("股票交易")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("买入")
        buy_code = st.text_input("股票代码 (买入)", value="000001", key="buy_code").strip()
        buy_amount = st.number_input("买入数量", min_value=100, value=100, step=100, key="buy_amount")
        use_limit_price_buy = st.checkbox("指定价格", key="use_limit_buy")
        buy_price = st.number_input("买入价格", min_value=0.01, value=10.0, step=0.01, key="buy_price", disabled=not use_limit_price_buy)
        
        if st.button("买入", type="primary", key="buy_button"):
            with st.spinner("执行中..."):
                # 清除该股票的价格缓存
                sim.clear_price_cache(buy_code)
                
                price = float(buy_price) if use_limit_price_buy else None
                result = sim.buy(buy_code, buy_amount, price)
                
                if result["success"]:
                    st.success(result["message"])
                    # 更新持仓可用数量
                    sim.update_position_availability()
                else:
                    st.error(result["message"])
                
                # 强制刷新页面数据
                st.rerun()
    
    with col2:
        st.subheader("卖出")
        # 获取当前持仓代码
        position_codes = list(sim.positions.keys())
        
        if position_codes:
            sell_code = st.selectbox("选择股票", position_codes, key="sell_code")
            if sell_code in sim.positions:
                pos = sim.positions[sell_code]
                st.info(f"持仓: {pos['amount']}股, 可用: {pos['available']}股, 成本: {pos['cost']:.2f}元")
                
                max_sell = pos["available"]
                sell_amount = st.number_input("卖出数量", min_value=100, max_value=max_sell, value=min(100, max_sell), step=100, key="sell_amount")
                use_limit_price_sell = st.checkbox("指定价格", key="use_limit_sell")
                sell_price = st.number_input("卖出价格", min_value=0.01, value=sim.get_price(sell_code, use_cache=False), step=0.01, key="sell_price", disabled=not use_limit_price_sell)
                
                if st.button("卖出", type="secondary", key="sell_button"):
                    with st.spinner("执行中..."):
                        # 清除该股票的价格缓存
                        sim.clear_price_cache(sell_code)
                        
                        price = float(sell_price) if use_limit_price_sell else None
                        result = sim.sell(sell_code, sell_amount, price)
                        
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["message"])
                        
                        st.rerun()
        else:
            st.info("暂无持仓，无法卖出")

with tab3:
    st.header("持仓详情")
    
    if sim.positions:
        for code, pos in sim.positions.items():
            with st.expander(f"{code} - 持仓 {pos['amount']}股"):
                col1, col2 = st.columns(2)
                
                with col1:
                    current_price = sim.get_price(code, use_cache=False)
                    cost = pos["cost"]
                    profit_per_share = current_price - cost
                    total_profit = profit_per_share * pos["amount"]
                    
                    st.metric("当前价", f"{current_price:.2f}元")
                    st.metric("成本价", f"{cost:.2f}元")
                    st.metric("每股盈亏", f"{profit_per_share:.2f}元", delta=f"{(profit_per_share/cost*100):.2f}%" if cost > 0 else "0%")
                
                with col2:
                    market_value = current_price * pos["amount"]
                    st.metric("持仓市值", f"{market_value:.2f}元")
                    st.metric("总盈亏", f"{total_profit:.2f}元")
                    st.metric("可用数量", f"{pos['available']}股")
    else:
        st.info("暂无持仓")

with tab4:
    st.header("交易历史")
    
    # 显示预委托单
    pending_orders = sim.get_pending_orders()
    if pending_orders:
        st.subheader("预委托单")
        for i, order in enumerate(pending_orders):
            order_type = "买入" if order["type"] == "buy" else "卖出"
            st.info(f"预委托单#{i}: {order_type} {order['code']} {order['amount']}股 @ {order.get('price', '市价')} - 提交时间: {order['timestamp']}")
    
    # 显示交易历史
    trade_history = sim.get_trade_history(limit=100)
    if trade_history:
        # 转换为DataFrame显示
        history_data = []
        for trade in trade_history:
            history_data.append({
                "时间": trade["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(trade["timestamp"], datetime) else trade["timestamp"],
                "类型": "买入" if trade["type"] == "buy" else "卖出",
                "股票": trade["code"],
                "数量": trade["amount"],
                "价格": f"{trade['price']:.2f}",
                "金额": f"{trade['total']:.2f}",
                "现金余额": f"{trade.get('cash_after', 0):.2f}"
            })
        
        df_history = pd.DataFrame(history_data)
        st.dataframe(df_history, use_container_width=True)
        
        # 交易统计
        st.subheader("交易统计")
        buy_count = sum(1 for t in trade_history if t["type"] == "buy")
        sell_count = sum(1 for t in trade_history if t["type"] == "sell")
        total_volume = sum(t["amount"] for t in trade_history)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("买入次数", buy_count)
        with col2:
            st.metric("卖出次数", sell_count)
        with col3:
            st.metric("总交易量", f"{total_volume}股")
    else:
        st.info("暂无交易记录")

with tab5:
    st.header("条件单管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("添加条件单")
        cond_code = st.text_input("股票代码", value="000001", key="cond_code").strip()
        
        cond_type = st.radio("委托类型", ["买入", "卖出"], key="cond_type")
        cond_amount = st.number_input("数量", min_value=100, value=100, step=100, key="cond_amount")
        
        current_price = sim.get_price(cond_code, use_cache=False)
        cond_trigger = st.number_input("触发价格", min_value=0.01, value=current_price, step=0.01, key="cond_trigger")
        
        cond_condition = st.selectbox(
            "触发条件",
            ["gte", "lte"],
            format_func=lambda x: "≥ 触发价" if x == "gte" else "≤ 触发价",
            key="cond_condition"
        )
        
        if st.button("添加条件单", key="add_cond"):
            result = sim.add_conditional_order(
                code=cond_code,
                order_type="buy" if cond_type == "买入" else "sell",
                amount=cond_amount,
                trigger_price=cond_trigger,
                condition=cond_condition
            )
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
            st.rerun()
    
    with col2:
        st.subheader("当前条件单")
        conditional_orders = sim.get_conditional_orders()
        
        if conditional_orders:
            for i, order in enumerate(conditional_orders):
                with st.expander(f"条件单#{i}: {order['code']} {order['type']} {order['amount']}股"):
                    st.write(f"触发价: {order['trigger_price']:.2f}")
                    st.write(f"条件: {'≥' if order['condition'] == 'gte' else '≤'} 触发价")
                    st.write(f"状态: {order['status']}")
                    st.write(f"添加时间: {order['timestamp']}")
                    
                    # 显示当前价格
                    current_price = sim.get_price(order["code"], use_cache=False)
                    st.write(f"当前价: {current_price:.2f}")
                    
                    # 删除按钮
                    if st.button(f"删除条件单#{i}", key=f"del_cond_{i}"):
                        sim.conditional_orders.pop(i)
                        st.success("条件单已删除")
                        st.rerun()
        else:
            st.info("暂无条件单")

# 页面底部状态
st.divider()
st.caption(f"系统最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 自动刷新配置
auto_refresh = st.sidebar.checkbox("自动刷新", value=False)
if auto_refresh:
    refresh_interval = st.sidebar.slider("刷新间隔(秒)", min_value=5, max_value=60, value=10)
    time.sleep(refresh_interval)
    st.rerun()
