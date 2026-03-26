import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

class StockSimulator:
    def __init__(self, initial_cash=100000):
        self.cash = initial_cash
        self.holdings = {}
        self.trade_history = []
        self.condition_orders = []
        self.t1_lock = {}
        # 新增：午间预委托单
        self.pending_orders = []

    def is_trading_time(self):
        """判断当前是否为A股交易时间"""
        now = datetime.now()
        weekday = now.weekday()  # 0=周一, 6=周日
        if weekday >= 5:
            return False
        hour = now.hour
        minute = now.minute
        # 交易时间：9:30-11:30, 13:00-15:00
        if (hour == 9 and minute >= 30) or (10 <= hour <= 11) or (13 <= hour <= 14) or (hour == 11 and minute <= 30):
            return True
        return False

    def get_price(self, code):
        """休市兼容：非交易时间返回最近收盘价/模拟价"""
        try:
            df = ak.stock_zh_a_spot_em(symbol=code)
            if df.empty:
                return None, None, None, None
            price = float(df.iloc[0]["最新价"])
            name = df.iloc[0]["名称"]
            limit_up = float(df.iloc[0]["涨停价"])
            limit_down = float(df.iloc[0]["跌停价"])
            return price, name, limit_up, limit_down
        except:
            return None, None, None, None

    def get_kline_data(self, code, period="daily"):
        try:
            end_date = datetime.now().strftime("%Y%m%d")
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
        today = datetime.now().date()
        for date_str, vol in self.t1_lock[code].items():
            trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if trade_date <= today - timedelta(days=1):
                available += vol
        return available >= amount

    def buy(self, code, amount):
        """核心修复：非交易时间转为预委托单"""
        if amount % 100 != 0:
            return "❌ 买入必须是100股的整数倍"

        # 🔴 关键：判断是否交易时间
        if not self.is_trading_time():
            # 非交易时间：加入预委托
            self.pending_orders.append({
                "type": "buy",
                "code": code,
                "amount": amount,
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return "⏸️ 当前为休市时间，已提交预委托单，13:00开盘后自动成交"

        # 交易时间：正常买入
        price, name, limit_up, limit_down = self.get_price(code)
        if not price:
            return "❌ 获取行情失败，请稍后重试"
        if price >= limit_up:
            return f"❌ {name}已涨停，无法买入"

        fee = self.calculate_fee(price, amount, "buy")
        total_cost = price * amount + fee["total"]
        if total_cost > self.cash:
            return "❌ 可用资金不足"

        # 更新持仓
        if code in self.holdings:
            old_amt = self.holdings[code]["amount"]
            old_cost = self.holdings[code]["cost"]
            new_amt = old_amt + amount
            new_cost = (old_cost*old_amt + price*amount)/new_amt
            self.holdings[code]["amount"] = new_amt
            self.holdings[code]["cost"] = new_cost
        else:
            self.holdings[code] = {"name": name, "amount": amount, "cost": price}

        # T+1
        today = datetime.now().strftime("%Y-%m-%d")
        if code not in self.t1_lock:
            self.t1_lock[code] = {}
        self.t1_lock[code][today] = self.t1_lock[code].get(today, 0) + amount

        self.cash -= total_cost
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "买入",
            "code": code, "name": name,
            "price": price, "amount": amount, "fee": fee
        })
        return f"✅ 买入成功！{name} {amount}股，¥{price:.2f}"

    # sell 函数保留不变（和buy同理，我这里省略，完整版我下面一起给）
    def sell(self, code, amount):
        if code not in self.holdings:
            return "❌ 无该股票持仓"
        hold = self.holdings[code]
        if amount > hold["amount"] or amount % 100 != 0:
            return "❌ 卖出数量错误"
        if not self.check_t1_lock(code, amount):
            return "❌ T+1限制，当日买入不可卖出"
        if not self.is_trading_time():
            self.pending_orders.append({
                "type": "sell", "code": code, "amount": amount,
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return "⏸️ 休市中，已提交预委托，开盘后自动卖出"
        price, name, limit_up, limit_down = self.get_price(code)
        if not price: return "❌ 行情获取失败"
        if price <= limit_down: return f"❌ {name}已跌停"
        fee = self.calculate_fee(price, amount, "sell")
        total = price*amount - fee["total"]
        hold["amount"] -= amount
        if hold["amount"] == 0: del self.holdings[code]
        self.cash += total
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "卖出", "code": code, "name": name,
            "price": price, "amount": amount, "fee": fee
        })
        return f"✅ 卖出成功！{name} {amount}股，¥{price:.2f}"

    def process_pending_orders(self):
        """开盘后自动处理预委托"""
        if not self.is_trading_time():
            return []
        executed = []
        remaining = []
        for order in self.pending_orders:
            if order["type"] == "buy":
                res = self.buy(order["code"], order["amount"])
            else:
                res = self.sell(order["code"], order["amount"])
            executed.append(res)
        self.pending_orders = remaining
        return executed

    # 下面函数不变：add_condition_order, check_condition_orders, get_assets
    def add_condition_order(self, code, order_type, trigger_price, amount):
        price, name, _, _ = self.get_price(code)
        if not price: return "❌ 行情获取失败"
        if order_type == "止盈" and trigger_price <= price:
            return "❌ 止盈价必须>当前价"
        if order_type == "止损" and trigger_price >= price:
            return "❌ 止损价必须<当前价"
        if amount % 100 !=0: return "❌ 股数必须是100整数倍"
        self.condition_orders.append({
            "code":code,"name":name,"type":order_type,
            "trigger_price":trigger_price,"amount":amount,
            "status":"待触发","create_time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return f"✅ {order_type}单已添加：{name} 触发价¥{trigger_price:.2f}"

    def check_condition_orders(self):
        triggered = []
        for o in self.condition_orders:
            if o["status"]!="待触发": continue
            p,_,_,_=self.get_price(o["code"])
            if not p: continue
            if o["type"]=="止盈" and p>=o["trigger_price"]:
                r=self.sell(o["code"],o["amount"])
                o["status"]="已触发"
                triggered.append(f"✅ {o['name']}止盈触发：{r}")
            if o["type"]=="止损" and p<=o["trigger_price"]:
                r=self.sell(o["code"],o["amount"])
                o["status"]="已触发"
                triggered.append(f"✅ {o['name']}止损触发：{r}")
        return triggered

    def get_assets(self):
        total=self.cash
        profit=0
        for c,item in self.holdings.items():
            p,_,_,_=self.get_price(c)
            if p:
                mv=p*item["amount"]
                total+=mv
                profit+=(p-item["cost"])*item["amount"]
        return {"cash":round(self.cash,2),"total":round(total,2),"profit":round(profit,2)}
