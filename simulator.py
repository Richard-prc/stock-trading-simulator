import json
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

class StockSimulator:
    def __init__(self, user_id="user1", initial_cash=100000):
        self.user_id = user_id
        self.initial_cash = initial_cash
        self.load_account()

    def load_account(self):
        try:
            with open(f"{self.user_id}_account.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.cash = data["cash"]
                self.holdings = data["holdings"]
                self.trade_history = data["history"]
                self.condition_orders = data.get("condition_orders", [])
                self.t1_lock = data.get("t1_lock", {})
        except:
            self.cash = self.initial_cash
            self.holdings = {}
            self.trade_history = []
            self.condition_orders = []
            self.t1_lock = {}

    def save_account(self):
        data = {
            "cash": self.cash,
            "holdings": self.holdings,
            "history": self.trade_history,
            "condition_orders": self.condition_orders,
            "t1_lock": self.t1_lock
        }
        with open(f"{self.user_id}_account.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
        except:
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
        except:
            return None

    def calculate_fee(self, price, amount, trade_type="buy"):
        commission = price * amount * 0.0003
        commission = max(5, commission)
        transfer_fee = price * amount * 0.00002 if trade_type == "buy" else price * amount * 0.00002
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
            return "买入必须是100股整数倍"

        price, name, limit_up, limit_down = self.get_price(code)
        if not price:
            return "获取股价失败"
        if price >= limit_up:
            return f"{name}已涨停，无法买入"

        fee = self.calculate_fee(price, amount, "buy")
        total = price * amount + fee["total"]

        if total > self.cash:
            return "资金不足"

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

        today = datetime.now().strftime("%Y-%m-%d")
        if code not in self.t1_lock:
            self.t1_lock[code] = {}
        if today in self.t1_lock[code]:
            self.t1_lock[code][today] += amount
        else:
            self.t1_lock[code][today] = amount

        self.cash -= total
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "买入",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })
        self.save_account()
        return f"买入成功！{name} {amount}股，成本价{price:.2f}，手续费{fee['total']:.2f}元"

    def sell(self, code, amount):
        if code not in self.holdings:
            return "无此持仓"

        holding = self.holdings[code]
        if amount > holding["amount"] or amount % 100 != 0:
            return "卖出数量错误"

        if not self.check_t1_lock(code, amount):
            return "T+1交易规则限制，当日买入的股票无法卖出"

        price, name, limit_up, limit_down = self.get_price(code)
        if not price:
            return "获取股价失败"
        if price <= limit_down:
            return f"{name}已跌停，无法卖出"

        fee = self.calculate_fee(price, amount, "sell")
        total = price * amount - fee["total"]

        holding["amount"] -= amount
        if holding["amount"] == 0:
            del self.holdings[code]

        self.cash += total
        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "卖出",
            "code": code,
            "name": name,
            "price": price,
            "amount": amount,
            "fee": fee
        })
        self.save_account()
        return f"卖出成功！{name} {amount}股，成交价{price:.2f}，手续费{fee['total']:.2f}元"

    def add_condition_order(self, code, order_type, trigger_price, amount):
        price, name, _, _ = self.get_price(code)
        if not price:
            return "获取股价失败"
        if order_type == "止盈" and trigger_price <= price:
            return "止盈价必须高于当前价"
        if order_type == "止损" and trigger_price >= price:
            return "止损价必须低于当前价"
        if amount % 100 != 0:
            return "委托数量必须是100股整数倍"

        self.condition_orders.append({
            "code": code,
            "name": name,
            "type": order_type,
            "trigger_price": trigger_price,
            "amount": amount,
            "status": "待触发",
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_account()
        return f"{order_type}条件单添加成功！{name} {amount}股，触发价{trigger_price:.2f}"

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
                triggered.append(f"{order['name']}止盈触发：{res}")
            elif order["type"] == "止损" and price <= order["trigger_price"]:
                res = self.sell(order["code"], order["amount"])
                order["status"] = "已触发"
                order["trigger_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                triggered.append(f"{order['name']}止损触发：{res}")
        self.save_account()
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

    def backtest_strategy(self, code, start_date, end_date, initial_cash=100000, strategy="ma_cross"):
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
        if df.empty:
            return None, "获取历史数据失败"

        df["日期"] = pd.to_datetime(df["日期"])
        df["MA5"] = df["收盘"].rolling(5).mean()
        df["MA10"] = df["收盘"].rolling(10).mean()

        cash = initial_cash
        holdings = 0
        cost = 0
        portfolio = []
        trades = []

        for i, row in df.iterrows():
            date = row["日期"]
            price = row["收盘"]
            ma5 = row["MA5"]
            ma10 = row["MA10"]

            if strategy == "ma_cross":
                if i > 0:
                    prev_ma5 = df.iloc[i-1]["MA5"]
                    prev_ma10 = df.iloc[i-1]["MA10"]
                    if prev_ma5 < prev_ma10 and ma5 > ma10 and cash >= price * 100:
                        amount = int(cash / (price * 100)) * 100
                        fee = self.calculate_fee(price, amount, "buy")["total"]
                        cash -= price * amount + fee
                        holdings += amount
                        cost = (cost * (holdings - amount) + price * amount) / holdings if holdings > 0 else price
                        trades.append({"date": date.strftime("%Y-%m-%d"), "type": "买入", "price": price, "amount": amount})
                    elif prev_ma5 > prev_ma10 and ma5 < ma10 and holdings > 0:
                        fee = self.calculate_fee(price, holdings, "sell")["total"]
                        cash += price * holdings - fee
                        trades.append({"date": date.strftime("%Y-%m-%d"), "type": "卖出", "price": price, "amount": holdings})
                        holdings = 0
                        cost = 0

            total_value = cash + holdings * price
            portfolio.append({"date": date, "total_value": total_value, "cash": cash, "holdings": holdings})

        portfolio_df = pd.DataFrame(portfolio)
        total_return = (portfolio_df.iloc[-1]["total_value"] - initial_cash) / initial_cash * 100
        max_drawdown = ((portfolio_df["total_value"].cummax() - portfolio_df["total_value"]) / portfolio_df["total_value"].cummax()).max() * 100

        return {
            "portfolio": portfolio_df,
            "trades": trades,
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "initial_cash": initial_cash,
            "final_value": round(portfolio_df.iloc[-1]["total_value"], 2)
        }, "回测完成"

    @staticmethod
    def get_all_users():
        import os
        users = []
        for file in os.listdir("."):
            if file.endswith("_account.json"):
                user_id = file.replace("_account.json", "")
                users.append(user_id)
        return users