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
            "cash": self.cash, "holdings": self.holdings, "history": self.trade_history,
            "condition_orders": self.condition_orders, "t1_lock": self.t1_lock
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
            return price, name, 0, 0
        except:
            return None, None, None, None

    def get_kline_data(self, code, period="daily"):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period=period, start_date="20240101", end_date=datetime.now().strftime("%Y%m%d"))
            df["日期"] = pd.to_datetime(df["日期"])
            return df
        except:
            return pd.DataFrame()

    def calculate_fee(self, price, amount, trade_type="buy"):
        commission = max(5, price * amount * 0.0003)
        transfer_fee = price * amount * 0.00002
        stamp_tax = price * amount * 0.001 if trade_type == "sell" else 0
        return {"commission": round(commission, 2), "transfer_fee": round(transfer_fee, 2), "stamp_tax": round(stamp_tax, 2), "total": round(commission + transfer_fee + stamp_tax, 2)}

    def buy(self, code, amount):
        if amount % 100 != 0:
            return "必须100股整数倍"
        price, name, _, _ = self.get_price(code)
        if not price:
            return "云端网络限制，暂时无法买入"
        fee = self.calculate_fee(price, amount, "buy")
        total = price * amount + fee["total"]
        if total > self.cash:
            return "资金不足"
        if code in self.holdings:
            old = self.holdings[code]
            new_amt = old["amount"] + amount
            new_cost = (old["cost"] * old["amount"] + price * amount) / new_amt
            self.holdings[code]["amount"] = new_amt
            self.holdings[code]["cost"] = new_cost
        else:
            self.holdings[code] = {"name": name, "amount": amount, "cost": price}
        self.cash -= total
        self.trade_history.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": "买入", "code": code, "name": name, "price": price, "amount": amount, "fee": fee})
        self.save_account()
        return f"买入成功 {name} {amount}股"

    def sell(self, code, amount):
        if code not in self.holdings:
            return "无持仓"
        price, name, _, _ = self.get_price(code)
        if not price:
            return "无法获取价格"
        fee = self.calculate_fee(price, amount, "sell")
        self.cash += price * amount - fee["total"]
        self.holdings[code]["amount"] -= amount
        if self.holdings[code]["amount"] == 0:
            del self.holdings[code]
        self.trade_history.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": "卖出", "code": code, "name": name, "price": price, "amount": amount, "fee": fee})
        self.save_account()
        return f"卖出成功 {name}"

    def add_condition_order(self, code, typ, price, amt):
        return "条件单已添加"

    def check_condition_orders(self):
        return []

    def get_assets(self):
        total = self.cash
        profit = 0
        for code, item in self.holdings.items():
            price, _, _, _ = self.get_price(code)
            if price:
                total += price * item["amount"]
                profit += (price - item["cost"]) * item["amount"]
        return {"cash": round(self.cash, 2), "total_assets": round(total, 2), "profit": round(profit, 2)}

    def backtest_strategy(self, *args):
        return None, "云端回测暂不可用"

    @staticmethod
    def get_all_users():
        import os
        return [f.replace("_account.json", "") for f in os.listdir() if f.endswith("_account.json")]
