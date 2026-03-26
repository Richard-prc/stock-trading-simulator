import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

class StockSimulator:
    def __init__(self, initial_cash=100000):
        # 用内存存储，不依赖本地文件，适配云端
        self.cash = initial_cash
        self.holdings = {}  # {code: {"name": name, "amount": amount, "cost": cost}}
        self.trade_history = []
        self.condition_orders = []
        self.t1_lock = {}  # {code: {date: volume}}

    def get_price(self, code):
        try:
            df = ak.stock_zh_a_spot_em(symbol=code)
            if df.empty:
                return None, None, None, None
            price = float(df.iloc[0]["最新价"])
            name = df.iloc[0]["名称"]
            limit_up = float(df.iloc[0]["涨停价"])
            limit_down = float(df.iloc[0]["跌停价"])
            return price, name, limit_up, limit_down
        except Exception as e:
            print(f"获取价格失败: {e}")
            return None, None, None, None

    def get_kline_data(self, code, period="daily"):
        try:
            if period == "daily":
                df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101", end_date=datetime.now().strftime("%Y%m%d"))
            elif period == "weekly":
                df = ak.stock_zh_a_hist(symbol=code, period="weekly", start_date="20240101", end_date=datetime.now().strftime("%Y%m%d"))
            elif period == "monthly":
                df = ak.stock_zh_a_hist(symbol=code, period="monthly", start_date="20240101", end_date=datetime.now().strftime("%Y%m%d"))
            df["日期"] = pd.to_datetime(df["日期"])
            return df
        except Exception as e:
            print(f"获取K线失败: {e}")
            return pd.DataFrame()

    def calculate_fee(self, price, amount, trade_type="buy"):
        commission = price * amount * 0.0003
        commission = max(5, commission)
        transfer_fee = price * amount * 0.00002
        stamp_tax = price * amount * 0.001 if trade_type == "sell" else 0
        total_fee = commission + transfer_fee + stamp_tax
        return {
            "commission": round(commission, 2),
            "transfer_fee": round(transfer_fee, 2),
            "stamp_tax": round(stamp_tax, 2),
            "total": round(total_fee, 2)
        }

    def check_t1_lock(self, code, amount):
        if code not in self.t1_lock:
            return True
        available = 0
        today = datetime.now().date()
        for date_str, vol in self.t1_lock[code].items():
            trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if trade_date <= today - timedelta(days=1):
                available += vol
        return available >= amount

    def buy(self, code, amount):
        if amount % 100 != 0:
            return "❌ 买入必须是100股的整数倍"

        price, name, limit_up, limit_down = self.get_price(code)
        if not price:
            return "❌ 获取股票价格失败，请检查代码或网络"
        if price >= limit_up:
            return f"❌ {name}已涨停，无法买入"

        fee = self.calculate_fee(price, amount, "buy")
        total_cost = price * amount + fee["total"]

        if total_cost > self.cash:
            return "❌ 可用资金不足，无法买入"

        # 更新持仓
        if code in self.holdings:
            old_amount = self.holdings[code]["amount"]
            old_cost = self.holdings[code]["cost"]
            new_amount = old_amount + amount
            new_cost = (old_cost * old_amount + price * amount) / new_amount
            self.holdings[code]["amount"] = new_amount
            self.holdings[code]["cost"] = new_cost
        else:
            self.holdings[code] = {
                "name": name,
                "amount": amount,
                "cost": price
            }

        # 更新T+1锁仓
        today = datetime.now().strftime("%Y-%m-%d")
        if code not in self.t1_lock:
            self.t1_lock[code] = {}
        if today in self.t1_lock[code]:
            self.t1_lock[code][today] += amount
        else:
            self.t1_lock[code][today] = amount

        # 扣减资金
        self.cash -= total_cost

        # 记录交易
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "买入",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })

        return f"✅ 买入成功！{name} {amount}股，成交价¥{price:.2f}，手续费¥{fee['total']:.2f}"

    def sell(self, code, amount):
        if code not in self.holdings:
            return "❌ 无该股票持仓，无法卖出"

        holding = self.holdings[code]
        if amount > holding["amount"] or amount % 100 != 0:
            return "❌ 卖出数量错误（必须100股整数倍，且不超过持仓）"

        if not self.check_t1_lock(code, amount):
            return "❌ T+1交易规则限制，当日买入的股票无法卖出"

        price, name, limit_up, limit_down = self.get_price(code)
        if not price:
            return "❌ 获取股票价格失败"
        if price <= limit_down:
            return f"❌ {name}已跌停，无法卖出"

        fee = self.calculate_fee(price, amount, "sell")
        total_income = price * amount - fee["total"]

        # 更新持仓
        holding["amount"] -= amount
        if holding["amount"] == 0:
            del self.holdings[code]

        # 增加资金
        self.cash += total_income

        # 记录交易
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "卖出",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })

        return f"✅ 卖出成功！{name} {amount}股，成交价¥{price:.2f}，手续费¥{fee['total']:.2f}"

    def add_condition_order(self, code, order_type, trigger_price, amount):
        price, name, _, _ = self.get_price(code)
        if not price:
            return "❌ 获取股票价格失败"
        if order_type == "止盈" and trigger_price <= price:
            return "❌ 止盈价必须高于当前价格"
        if order_type == "止损" and trigger_price >= price:
            return "❌ 止损价必须低于当前价格"
        if amount % 100 != 0:
            return "❌ 委托数量必须是100股整数倍"

        self.condition_orders.append({
            "code": code,
            "name": name,
            "type": order_type,
            "trigger_price": trigger_price,
            "amount": amount,
            "status": "待触发",
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return f"✅ {order_type}条件单添加成功！{name} {amount}股，触发价¥{trigger_price:.2f}"

    def check_condition_orders(self):
        triggered = []
        for order in self.condition_orders:
            if order["status"] != "待触发":
                continue
            price, _, _, _ = self.get_price(order["code"])
            if not price:
                continue
            if order["type"] == "止盈" and price >= order["trigger_price"]:
                res = self.sell(order["code"], order["amount"])
                order["status"] = "已触发"
                order["trigger_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                triggered.append(f"✅ {order['name']}止盈触发：{res}")
            elif order["type"] == "止损" and price <= order["trigger_price"]:
                res = self.sell(order["code"], order["amount"])
                order["status"] = "已触发"
                order["trigger_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                triggered.append(f"✅ {order['name']}止损触发：{res}")
        return triggered

    def get_assets(self):
        total = self.cash
        profit = 0
        for code, item in self.holdings.items():
            price, _, _, _ = self.get_price(code)
            if price:
                market_value = price * item["amount"]
                total += market_value
                profit += (price - item["cost"]) * item["amount"]
        return {
            "cash": round(self.cash, 2),
            "total_assets": round(total, 2),
            "profit": round(profit, 2)
        }
