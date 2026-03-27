import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import pytz

# 强制北京时间
TZ = pytz.timezone("Asia/Shanghai")

def now():
    return datetime.now(TZ)

class StockSimulator:
    def __init__(self, initial_cash=100000):
        self.cash = initial_cash
        self.holdings = {}
        self.trade_history = []
        self.condition_orders = []
        self.t1_lock = {}
        self.pending_orders = []
        self.price_cache = {}  # 价格缓存，解决不显示价格

    def is_trading_time(self):
        now_dt = now()
        weekday = now_dt.weekday()
        if weekday >= 5:
            return False
        h = now_dt.hour
        m = now_dt.minute
        if (h == 9 and m >= 30) or (10 <= h <= 11) or (13 <= h <= 14) or (h == 11 and m <= 30):
            return True
        return False

    def get_price(self, code, use_cache=True):
        if use_cache and code in self.price_cache:
            return self.price_cache[code]
        try:
            df = ak.stock_zh_a_spot_em(symbol=code)
            if df.empty:
                return None, None, None, None
            price = float(df.iloc[0]["最新价"])
            name = df.iloc[0]["名称"]
            limit_up = float(df.iloc[0]["涨停价"])
            limit_down = float(df.iloc[0]["跌停价"])
            self.price_cache[code] = (price, name, limit_up, limit_down)
            return price, name, limit_up, limit_down
        except:
            if code in self.price_cache:
                return self.price_cache[code]
            return None, None, None, None

    def get_kline_data(self, code, period="daily"):
        try:
            end_date = now().strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(symbol=code, period=period, start_date="20240101", end_date=end_date)
            df["日期"] = pd.to_datetime(df["日期"])
            return df
        except:
            return pd.DataFrame()

    def calculate_fee(self, price, amount, trade_type="buy"):
        commission = max(5, price * amount * 0.0003)
        transfer_fee = price * amount * 0.00002
        stamp_tax = price * amount * 0.001 if trade_type == "sell" else 0
        total = commission + transfer_fee + stamp_tax
        return {
            "commission": round(commission, 2),
            "transfer_fee": round(transfer_fee, 2),
            "stamp_tax": round(stamp_tax, 2),
            "total": round(total, 2)
        }

    def check_t1_lock(self, code, amount):
        if code not in self.t1_lock:
            return True
        available = 0
        today = now().date()
        for date_str, vol in self.t1_lock[code].items():
            trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if trade_date <= today - timedelta(days=1):
                available += vol
        return available >= amount

    def buy(self, code, amount):
        if amount % 100 != 0:
            return "❌ 买入必须是100股的整数倍"

        if not self.is_trading_time():
            self.pending_orders.append({
                "type": "buy",
                "code": code,
                "amount": amount,
                "time": now().strftime("%m-%d %H:%M")
            })
            return "⏸️ 休市中，已提交预委托，开盘自动成交"

        price, name, limit_up, limit_down = self.get_price(code)
        if price is None:
            return "⚠️ 行情暂时获取失败，请重试"
        if price >= limit_up:
            return f"❌ {name} 已涨停"

        fee = self.calculate_fee(price, amount, "buy")
        total_cost = price * amount + fee["total"]
        if total_cost > self.cash:
            return "❌ 可用资金不足"

        if code in self.holdings:
            old_amt = self.holdings[code]["amount"]
            old_cost = self.holdings[code]["cost"]
            new_amt = old_amt + amount
            new_cost = (old_cost * old_amt + price * amount) / new_amt
            self.holdings[code]["amount"] = new_amt
            self.holdings[code]["cost"] = new_cost
        else:
            self.holdings[code] = {
                "name": name,
                "amount": amount,
                "cost": price
            }

        today_str = now().strftime("%Y-%m-%d")
        if code not in self.t1_lock:
            self.t1_lock[code] = {}
        self.t1_lock[code][today_str] = self.t1_lock[code].get(today_str, 0) + amount

        self.cash -= total_cost
        self.trade_history.append({
            "time": now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "买入",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })
        return f"✅ 买入成功 {name} {amount}股 ￥{price:.2f}"

    def sell(self, code, amount):
        if code not in self.holdings:
            return "❌ 无此持仓"
        hold = self.holdings[code]
        if amount > hold["amount"] or amount % 100 != 0:
            return "❌ 卖出数量错误"
        if not self.check_t1_lock(code, amount):
            return "❌ T+1 不可卖出当日买入"

        if not self.is_trading_time():
            self.pending_orders.append({
                "type": "sell",
                "code": code,
                "amount": amount,
                "time": now().strftime("%m-%d %H:%M")
            })
            return "⏸️ 休市中，预委托已提交"

        price, name, limit_up, limit_down = self.get_price(code)
        if price is None:
            return "⚠️ 行情获取失败"
        if price <= limit_down:
            return f"❌ {name} 已跌停"

        fee = self.calculate_fee(price, amount, "sell")
        total = price * amount - fee["total"]
        hold["amount"] -= amount
        if hold["amount"] == 0:
            del self.holdings[code]

        self.cash += total
        self.trade_history.append({
            "time": now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "卖出",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })
        return f"✅ 卖出成功 {name} {amount}股 ￥{price:.2f}"

    def process_pending_orders(self):
        if not self.is_trading_time():
            return []
        res = []
        for o in self.pending_orders:
            if o["type"] == "buy":
                r = self.buy(o["code"], o["amount"])
            else:
                r = self.sell(o["code"], o["amount"])
            res.append(r)
        self.pending_orders = []
        return res

    # 补全：add_condition_order 函数（之前漏写，导致报错）
    def add_condition_order(self, code, order_type, trigger_price, amount):
        price, name, _, _ = self.get_price(code)
        if price is None:
            return "❌ 行情获取失败，无法添加条件单"
        if order_type == "止盈" and trigger_price <= price:
            return "❌ 止盈价必须高于当前价格"
        if order_type == "止损" and trigger_price >= price:
            return "❌ 止损价必须低于当前价格"
        if amount % 100 != 0:
            return "❌ 委托数量必须是100股的整数倍"

        self.condition_orders.append({
            "code": code,
            "name": name,
            "type": order_type,
            "trigger_price": trigger_price,
            "amount": amount,
            "status": "待触发",
            "create_time": now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return f"✅ {order_type}条件单添加成功！{name} {amount}股，触发价￥{trigger_price:.2f}"

    def check_condition_orders(self):
        triggered = []
        for o in self.condition_orders:
            if o["status"] != "待触发":
                continue
            p, _, _, _ = self.get_price(o["code"])
            if not p:
                continue
            if o["type"] == "止盈" and p >= o["trigger_price"]:
                r = self.sell(o["code"], o["amount"])
                o["status"] = "已触发"
                triggered.append(f"✅ {o['name']} 止盈触发：{r}")
            if o["type"] == "止损" and p <= o["trigger_price"]:
                r = self.sell(o["code"], o["amount"])
                o["status"] = "已触发"
                triggered.append(f"✅ {o['name']} 止损触发：{r}")
        return triggered

    def get_assets(self):
        total = self.cash
        profit = 0
        for code, item in self.holdings.items():
            p, _, _, _ = self.get_price(code)
            p = p if p is not None else item["cost"]
            mv = p * item["amount"]
            total += mv
            profit += (p - item["cost"]) * item["amount"]
        return {
            "cash": round(self.cash, 2),
            "total": round(total, 2),
            "profit": round(profit, 2)
        }
