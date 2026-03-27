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

# 自定义CSS样式
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4e8cff;
    }
    .main-header {
        color: #1f3a6d;
        padding-bottom: 10px;
        border-bottom: 2px solid #4e8cff;
    }
    .trade-success {
        color: #28a745;
        font-weight: bold;
    }
    .trade-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown("<h1 class='main-header'>📈 A股交易模拟器</h1>", unsafe_allow_html=True)
st.caption(f"当前时间: {sim.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 侧边栏 - 控制面板
with st.sidebar:
    st.header("控制面板")
    
    # 时间模拟控制
    st.subheader("时间模拟（调试用）")
    use_real_time = st.checkbox("使用真实时间", value=True, key="time_real_check")
    
    if not use_real_time:
        mock_date = st.date_input("模拟日期", value=sim.now().date(), key="mock_date")
        mock_time = st.time_input("模拟时间", value=sim.now().time(), key="mock_time")
        mock_datetime = datetime.combine(mock_date, mock_time)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("设置模拟时间", key="set_mock_time"):
                sim.set_mock_time(mock_datetime)
                st.success(f"模拟时间已设置为: {mock_datetime}")
                st.rerun()
        with col2:
            if st.button("恢复真实时间", key="reset_real_time"):
                sim.set_mock_time(None)
                st.success("已恢复使用真实时间")
                st.rerun()
    else:
        if st.button("刷新当前时间", key="refresh_time"):
            st.rerun()
    
    # 交易时间状态
    st.subheader("交易状态")
    is_trading = sim.is_trading_time()
    status_emoji = "🟢" if is_trading else "🔴"
    status_text = "交易时间内" if is_trading else "非交易时间"
    st.markdown(f"{status_emoji} **{status_text}**")
    
    # 系统控制
    st.subheader("系统控制")
    
    if st.button("处理预委托单", key="process_pending"):
        results = sim.process_pending_orders()
        if results:
            for r in results:
                if r["success"]:
                    st.success(r["message"])
                else:
                    st.error(r["message"])
        else:
            st.info("没有待处理的预委托单")
    
    if st.button("检查条件单", key="check_conditional"):
        triggered = sim.check_conditional_orders()
        if triggered:
            for t in triggered:
                if t["success"]:
                    st.success(f"条件单触发: {t['message']}")
                else:
                    st.error(f"条件单触发失败: {t['message']}")
        else:
            st.info("没有条件单被触发")
    
    if st.button("清除价格缓存", key="clear_cache"):
        sim.clear_price_cache()
        st.success("价格缓存已清除")
    
    if st.button("重置模拟器", key="reset_sim"):
        st.session_state.clear()
        st.success("模拟器已重置")
        st.rerun()
    
    # 自动刷新配置
    st.subheader("自动刷新")
    auto_refresh = st.checkbox("启用自动刷新", value=False, key="auto_refresh")
    if auto_refresh:
        refresh_interval = st.slider("刷新间隔(秒)", min_value=5, max_value=60, value=10, key="refresh_interval")

# 主界面标签页
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 资产概览", "💰 交易", "📋 持仓", "📜 历史记录", "⚙️ 条件单"])

with tab1:
    st.header("资产概览")
    
    # 强制刷新价格缓存，确保显示最新数据
    sim.clear_price_cache()
    
    # 更新持仓可用数量
    sim.update_position_availability()
    
    # 资产概览指标
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("现金余额", f"¥{sim.cash:,.2f}")
    with col2:
        total_assets = sim.get_total_assets()
        st.metric("总资产", f"¥{total_assets:,.2f}")
    with col3:
        initial_cash = 100000.0
        profit = total_assets - initial_cash
        profit_pct = (profit / initial_cash) * 100
        st.metric("总盈亏", f"¥{profit:,.2f}", delta=f"{profit_pct:.2f}%")
    with col4:
        positions_count = len(sim.positions)
        st.metric("持仓数量", positions_count)
    
    # 持仓明细
    st.subheader("持仓明细")
    if sim.positions:
        # 获取持仓汇总
        position_summary = sim.get_position_summary()
        
        if position_summary:
            # 准备显示数据
            display_data = []
            for item in position_summary:
                display_data.append({
                    "股票代码": item["股票代码"],
                    "持仓数量": f"{item['持仓数量']:,}",
                    "可用数量": f"{item['可用数量']:,}",
                    "成本价": f"¥{item['成本价']:.2f}",
                    "当前价": f"¥{item['当前价']:.2f}",
                    "市值": f"¥{item['市值']:,.2f}",
                    "盈亏": f"¥{item['盈亏']:,.2f}",
                    "盈亏%": f"{item['盈亏百分比']:.2f}%"
                })
            
            df_positions = pd.DataFrame(display_data)
            st.dataframe(df_positions, use_container_width=True, hide_index=True)
            
            # 持仓分布饼图
            st.subheader("持仓市值分布")
            chart_data = pd.DataFrame(position_summary)
            if not chart_data.empty and chart_data["市值"].sum() > 0:
                st.pie_chart(chart_data, x="股票代码", y="市值")
        else:
            st.info("暂无持仓明细数据")
    else:
        st.info("当前没有持仓")

with tab2:
    st.header("股票交易")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("买入股票")
        buy_code = st.text_input("股票代码 (6位数字)", value="000001", key="buy_code_input").strip()
        
        if buy_code:
            # 显示股票信息
            current_price = sim.get_price(buy_code, use_cache=False)
            if current_price > 0:
                st.info(f"当前价格: ¥{current_price:.2f}")
            else:
                st.warning("无法获取股票价格，请检查代码是否正确")
        
        buy_amount = st.number_input("买入数量(100股整数倍)", 
                                    min_value=100, 
                                    value=100, 
                                    step=100, 
                                    key="buy_amount_input")
        
        use_limit_price_buy = st.checkbox("指定价格买入", value=False, key="use_limit_buy_check")
        
        if use_limit_price_buy:
            buy_price = st.number_input("买入价格", 
                                      min_value=0.01, 
                                      value=float(current_price) if current_price > 0 else 10.0, 
                                      step=0.01, 
                                      key="buy_price_input")
        else:
            buy_price = None
            st.caption("市价委托，以当前价格买入")
        
        # 计算预估金额
        estimated_cost = buy_amount * (buy_price if buy_price else current_price) if current_price > 0 else 0
        if estimated_cost > 0:
            st.metric("预估金额", f"¥{estimated_cost:,.2f}")
        
        if st.button("买入", type="primary", use_container_width=True, key="buy_execute"):
            with st.spinner("执行买入中..."):
                # 清除该股票的价格缓存
                sim.clear_price_cache(buy_code)
                
                result = sim.buy(buy_code, buy_amount, buy_price)
                
                if result["success"]:
                    st.success(result["message"])
                    # 更新持仓可用数量
                    sim.update_position_availability()
                else:
                    st.error(result["message"])
                
                time.sleep(0.5)
                st.rerun()
    
    with col2:
        st.subheader("卖出股票")
        
        # 获取当前持仓
        position_codes = list(sim.positions.keys())
        
        if position_codes:
            selected_stock = st.selectbox("选择持仓股票", 
                                         position_codes, 
                                         format_func=lambda x: f"{x} (持有{sim.positions[x]['amount']}股)",
                                         key="sell_stock_select")
            
            if selected_stock in sim.positions:
                pos = sim.positions[selected_stock]
                current_price = sim.get_price(selected_stock, use_cache=False)
                
                # 显示持仓信息
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("持仓数量", f"{pos['amount']:,}")
                with col_b:
                    st.metric("可用数量", f"{pos['available']:,}")
                with col_c:
                    st.metric("成本价", f"¥{pos['cost']:.2f}")
                
                # 盈亏计算
                if current_price > 0:
                    profit_per_share = current_price - pos["cost"]
                    total_profit = profit_per_share * pos["amount"]
                    profit_pct = (profit_per_share / pos["cost"]) * 100 if pos["cost"] > 0 else 0
                    
                    st.info(f"当前价: ¥{current_price:.2f} | 每股盈亏: ¥{profit_per_share:.2f} ({profit_pct:.2f}%)")
                
                # 卖出数量输入
                max_sellable = pos["available"]
                sell_amount = st.number_input("卖出数量", 
                                            min_value=100, 
                                            max_value=max_sellable if max_sellable >= 100 else 100,
                                            value=min(100, max_sellable) if max_sellable >= 100 else 100,
                                            step=100,
                                            key="sell_amount_input")
                
                use_limit_price_sell = st.checkbox("指定价格卖出", value=False, key="use_limit_sell_check")
                
                if use_limit_price_sell:
                    sell_price = st.number_input("卖出价格", 
                                               min_value=0.01, 
                                               value=current_price, 
                                               step=0.01, 
                                               key="sell_price_input")
                else:
                    sell_price = None
                    st.caption("市价委托，以当前价格卖出")
                
                # 计算预估收入
                estimated_revenue = sell_amount * (sell_price if sell_price else current_price)
                if estimated_revenue > 0:
                    st.metric("预估收入", f"¥{estimated_revenue:,.2f}")
                
                if st.button("卖出", type="secondary", use_container_width=True, key="sell_execute"):
                    with st.spinner("执行卖出中..."):
                        # 清除该股票的价格缓存
                        sim.clear_price_cache(selected_stock)
                        
                        result = sim.sell(selected_stock, sell_amount, sell_price)
                        
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["message"])
                        
                        time.sleep(0.5)
                        st.rerun()
        else:
            st.info("暂无持仓，无法卖出")
            
            # 演示用卖出界面
            st.caption("示例：有持仓时可在此卖出")

with tab3:
    st.header("持仓详情")
    
    if sim.positions:
        # 更新持仓可用数量
        sim.update_position_availability()
        
        for i, (code, pos) in enumerate(sim.positions.items()):
            with st.expander(f"{code} - 持仓详情", expanded=(i == 0)):
                col1, col2 = st.columns(2)
                
                with col1:
                    current_price = sim.get_price(code, use_cache=False)
                    cost = pos["cost"]
                    market_value = current_price * pos["amount"]
                    profit_per_share = current_price - cost
                    total_profit = profit_per_share * pos["amount"]
                    profit_pct = (profit_per_share / cost) * 100 if cost > 0 else 0
                    
                    st.metric("当前价格", f"¥{current_price:.2f}")
                    st.metric("持仓成本", f"¥{cost:.2f}")
                    st.metric("每股盈亏", f"¥{profit_per_share:.2f}", 
                             delta=f"{profit_pct:.2f}%" if profit_pct >= 0 else f"{profit_pct:.2f}%",
                             delta_color="normal" if profit_pct >= 0 else "inverse")
                
                with col2:
                    st.metric("持仓数量", f"{pos['amount']:,}")
                    st.metric("可用数量", f"{pos['available']:,}")
                    st.metric("持仓市值", f"¥{market_value:,.2f}")
                    st.metric("持仓盈亏", f"¥{total_profit:,.2f}")
                
                # 快速操作按钮
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"买入 {code}", key=f"quick_buy_{code}", use_container_width=True):
                        st.session_state.buy_code_input = code
                        st.rerun()
                with col_b:
                    if st.button(f"卖出 {code}", key=f"quick_sell_{code}", use_container_width=True):
                        st.session_state.sell_stock_select = code
                        st.rerun()
    else:
        st.info("当前没有持仓")
        
        # 示例持仓展示
        st.caption("示例持仓（当有持仓时会显示在这里）")
        sample_data = {
            "股票代码": ["000001", "000858"],
            "股票名称": ["平安银行", "五粮液"],
            "持仓数量": [1000, 500],
            "成本价": [10.50, 150.20],
            "当前价": [11.20, 148.50],
            "市值": [11200.0, 74250.0],
            "盈亏": [700.0, -850.0]
        }
        st.dataframe(pd.DataFrame(sample_data), use_container_width=True)

with tab4:
    st.header("交易记录")
    
    # 显示预委托单
    pending_orders = sim.get_pending_orders()
    if pending_orders:
        st.subheader("待处理预委托单")
        for i, order in enumerate(pending_orders):
            with st.expander(f"预委托单 #{i+1}: {order['type']} {order['code']}", expanded=(i == 0)):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**类型:** {'买入' if order['type'] == 'buy' else '卖出'}")
                    st.write(f"**股票:** {order['code']}")
                with col2:
                    st.write(f"**数量:** {order['amount']}股")
                    st.write(f"**价格:** {order.get('price', '市价')}")
                with col3:
                    st.write(f"**状态:** {order.get('status', '待处理')}")
                    st.write(f"**时间:** {order['timestamp']}")
    
    # 显示条件单
    conditional_orders = sim.get_conditional_orders()
    if conditional_orders:
        st.subheader("激活的条件单")
        for i, order in enumerate(conditional_orders):
            if order["status"] == "active":
                with st.expander(f"条件单 #{i+1}: {order['code']}", expanded=(i == 0)):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**类型:** {'买入' if order['type'] == 'buy' else '卖出'}")
                        st.write(f"**股票:** {order['code']}")
                        st.write(f"**数量:** {order['amount']}股")
                    with col2:
                        st.write(f"**触发价:** ¥{order['trigger_price']:.2f}")
                        st.write(f"**条件:** {'≥' if order['condition'] == 'gte' else '≤'} 触发价")
                        st.write(f"**添加时间:** {order['timestamp']}")
    
    # 显示交易历史
    st.subheader("交易历史")
    trade_history = sim.get_trade_history(limit=100)
    
    if trade_history:
        # 准备历史数据
        history_data = []
        for trade in trade_history:
            # 格式化时间
            if isinstance(trade["timestamp"], datetime):
                trade_time = trade["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            else:
                trade_time = str(trade["timestamp"])
            
            history_data.append({
                "时间": trade_time,
                "类型": "买入" if trade["type"] == "buy" else "卖出",
                "股票代码": trade["code"],
                "数量": f"{trade['amount']:,}",
                "价格": f"¥{trade['price']:.2f}",
                "金额": f"¥{trade['total']:,.2f}",
                "现金余额": f"¥{trade.get('cash_after', 0):,.2f}"
            })
        
        # 显示数据表
        df_history = pd.DataFrame(history_data)
        st.dataframe(df_history, use_container_width=True, hide_index=True)
        
        # 交易统计
        st.subheader("交易统计")
        buy_trades = [t for t in trade_history if t["type"] == "buy"]
        sell_trades = [t for t in trade_history if t["type"] == "sell"]
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总交易次数", len(trade_history))
        with col2:
            st.metric("买入次数", len(buy_trades))
        with col3:
            st.metric("卖出次数", len(sell_trades))
        with col4:
            total_volume = sum(t["amount"] for t in trade_history)
            st.metric("总交易量", f"{total_volume:,}股")
        
        # 交易金额统计
        if trade_history:
            buy_amount = sum(t["total"] for t in buy_trades)
            sell_amount = sum(t["total"] for t in sell_trades)
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("买入总额", f"¥{buy_amount:,.2f}")
            with col_b:
                st.metric("卖出总额", f"¥{sell_amount:,.2f}")
    else:
        st.info("暂无交易记录")

with tab5:
    st.header("条件单管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("添加条件单")
        
        # 选择股票
        cond_code = st.text_input("股票代码", value="000001", key="cond_code_input").strip()
        
        if cond_code:
            current_price = sim.get_price(cond_code, use_cache=False)
            if current_price > 0:
                st.info(f"{cond_code} 当前价格: ¥{current_price:.2f}")
            else:
                st.warning("无法获取股票价格")
        
        # 条件单类型
        cond_type = st.radio("委托类型", ["买入", "卖出"], horizontal=True, key="cond_type_radio")
        
        # 对于卖出条件单，检查持仓
        if cond_type == "卖出":
            pos = sim.positions.get(cond_code)
            if pos:
                max_sellable = pos["available"]
                st.info(f"可用数量: {max_sellable}股")
            else:
                st.warning("没有该股票的持仓")
                max_sellable = 0
        else:
            max_sellable = 10000  # 买入条件单的最大数量限制
        
        # 数量输入
        cond_amount = st.number_input("委托数量(100股整数倍)", 
                                     min_value=100, 
                                     value=100, 
                                     step=100, 
                                     max_value=max_sellable if cond_type == "卖出" else 10000,
                                     key="cond_amount_input")
        
        # 触发价格
        if current_price > 0:
            if cond_type == "买入":
                default_trigger = current_price * 0.95  # 买入条件单通常设低于当前价
            else:  # 卖出
                default_trigger = current_price * 1.05  # 卖出条件单通常设高于当前价
        else:
            default_trigger = 10.0
            
        cond_trigger = st.number_input("触发价格", 
                                      min_value=0.01, 
                                      value=float(default_trigger), 
                                      step=0.01, 
                                      key="cond_trigger_input")
        
        # 触发条件
        if cond_type == "买入":
            cond_condition = st.selectbox(
                "触发条件",
                ["lte", "gte"],
                format_func=lambda x: "≤ 触发价时买入" if x == "lte" else "≥ 触发价时买入",
                key="cond_condition_buy"
            )
        else:  # 卖出
            cond_condition = st.selectbox(
                "触发条件",
                ["gte", "lte"],
                format_func=lambda x: "≥ 触发价时卖出" if x == "gte" else "≤ 触发价时卖出",
                key="cond_condition_sell"
            )
        
        # 条件单说明
        if cond_type == "买入":
            if cond_condition == "lte":
                st.caption(f"当价格 ≤ ¥{cond_trigger:.2f} 时，买入 {cond_amount}股")
            else:
                st.caption(f"当价格 ≥ ¥{cond_trigger:.2f} 时，买入 {cond_amount}股")
        else:
            if cond_condition == "gte":
                st.caption(f"当价格 ≥ ¥{cond_trigger:.2f} 时，卖出 {cond_amount}股")
            else:
                st.caption(f"当价格 ≤ ¥{cond_trigger:.2f} 时，卖出 {cond_amount}股")
        
        if st.button("添加条件单", type="primary", use_container_width=True, key="add_cond_button"):
            with st.spinner("添加条件单中..."):
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
                time.sleep(1)
                st.rerun()
    
    with col2:
        st.subheader("当前条件单")
        conditional_orders = sim.get_conditional_orders()
        
        if conditional_orders:
            active_orders = [o for o in conditional_orders if o["status"] == "active"]
            triggered_orders = [o for o in conditional_orders if o["status"] == "triggered"]
            
            if active_orders:
                st.markdown("**激活中的条件单**")
                for i, order in enumerate(active_orders):
                    with st.expander(f"条件单 #{i+1}: {order['code']} {order['type']}", expanded=(i == 0)):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**类型:** {'买入' if order['type'] == 'buy' else '卖出'}")
                            st.write(f"**股票:** {order['code']}")
                            st.write(f"**数量:** {order['amount']}股")
                        with col_b:
                            st.write(f"**触发价:** ¥{order['trigger_price']:.2f}")
                            st.write(f"**条件:** {'≥' if order['condition'] == 'gte' else '≤'} 触发价")
                            st.write(f"**状态:** {order['status']}")
                        
                        # 显示当前价格和触发状态
                        current_price = sim.get_price(order["code"], use_cache=False)
                        if current_price > 0:
                            st.write(f"当前价格: ¥{current_price:.2f}")
                            
                            # 判断是否接近触发
                            if order["condition"] == "gte" and current_price >= order["trigger_price"] * 0.99:
                                st.warning("⚠️ 接近触发条件")
                            elif order["condition"] == "lte" and current_price <= order["trigger_price"] * 1.01:
                                st.warning("⚠️ 接近触发条件")
                        
                        # 删除按钮
                        if st.button(f"删除此条件单", key=f"del_cond_{i}"):
                            if i < len(conditional_orders):
                                conditional_orders.pop(i)
                                st.success("条件单已删除")
                                st.rerun()
            
            if triggered_orders:
                st.markdown("**已触发的条件单**")
                for i, order in enumerate(triggered_orders):
                    st.info(f"条件单 #{i+1}: {order['code']} {order['type']} 已触发")
        else:
            st.info("暂无条件单")
            
            # 示例条件单
            st.caption("示例条件单")
            sample_orders = [
                {"股票": "000001", "类型": "买入", "触发价": 10.50, "数量": 100, "条件": "≤ 触发价"},
                {"股票": "000858", "类型": "卖出", "触发价": 160.00, "数量": 200, "条件": "≥ 触发价"}
            ]
            st.dataframe(pd.DataFrame(sample_orders), use_container_width=True, hide_index=True)

# 页面底部状态栏
st.divider()
st.caption(f"系统状态: 运行中 | 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 持仓数量: {len(sim.positions)}")

# 自动刷新逻辑
if auto_refresh and st.session_state.get("auto_refresh", False):
    time.sleep(st.session_state.get("refresh_interval", 10))
    st.rerun()
