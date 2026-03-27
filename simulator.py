# simulator.py
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Optional, Dict, List, Tuple, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockTradingSimulator:
    def __init__(self, initial_cash: float = 100000.0):
        self.cash = initial_cash
        self.positions: Dict[str, Dict] = {}  # {code: {"amount": int, "available": int, "cost": float}}
        self.trade_history: List[Dict] = []
        self.pending_orders: List[Dict] = []  # 预委托单
        self.price_cache: Dict[str, Tuple[float, datetime]] = {}  # 缓存价格和获取时间
        self.conditional_orders: List[Dict] = []  # 条件单
        self.mock_time: Optional[datetime] = None  # 用于测试的时间模拟
        
    def now(self) -> datetime:
        """获取当前时间，如果设置了模拟时间则返回模拟时间"""
        return self.mock_time if self.mock_time else datetime.now()
    
    def set_mock_time(self, mock_time: Optional[datetime] = None):
        """设置模拟时间，用于测试。传入None则使用真实时间"""
        self.mock_time = mock_time
        logger.info(f"模拟时间设置为: {mock_time}")
        
    def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """判断给定时间是否为A股交易时间"""
        if dt is None:
            dt = self.now()
            
        # 判断是否为周末
        if dt.weekday() >= 5:
            return False
        
        hour = dt.hour
        minute = dt.minute
        current_time = hour * 100 + minute
        
        # 上午交易时段: 9:30 - 11:30
        morning_start = 930
        morning_end = 1130
        # 下午交易时段: 13:00 - 15:00
        afternoon_start = 1300
        afternoon_end = 1500
        
        return (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end)
    
    def get_price(self, code: str, use_cache: bool = True) -> float:
        """获取股票当前价格，支持缓存"""
        now = self.now()
        
        # 检查缓存
        if use_cache and code in self.price_cache:
            price, cache_time = self.price_cache[code]
            # 缓存有效期30秒
            if (now - cache_time).total_seconds() < 30:
                return price
        
        try:
            # 使用akshare获取实时数据
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df["代码"] == code]
            if not stock_data.empty:
                price = float(stock_data.iloc[0]["最新价"])
                self.price_cache[code] = (price, now)
                return price
            else:
                logger.error(f"未找到股票代码: {code}")
                return 0.0
        except Exception as e:
            logger.error(f"获取股票价格失败: {e}")
            return 0.0
    
    def clear_price_cache(self, code: Optional[str] = None):
        """清除价格缓存"""
        if code:
            self.price_cache.pop(code, None)
        else:
            self.price_cache.clear()
    
    def get_position(self, code: str) -> Dict:
        """获取持仓信息"""
        return self.positions.get(code, {"amount": 0, "available": 0, "cost": 0.0})
    
    def get_total_assets(self) -> float:
        """计算总资产：现金 + 持仓市值"""
        total = self.cash
        for code, pos in self.positions.items():
            price = self.get_price(code, use_cache=True)
            total += pos["amount"] * price
        return total
    
    def buy(self, code: str, amount: int, price: Optional[float] = None) -> Dict[str, Any]:
        """买入股票"""
        result = {"success": False, "message": "", "order_id": None}
        
        # 获取价格
        if price is None:
            price = self.get_price(code, use_cache=False)
        
        if price <= 0:
            result["message"] = "获取价格失败"
            return result
        
        total_cost = price * amount
        if total_cost > self.cash:
            result["message"] = f"资金不足，需要{total_cost:.2f}元，可用{self.cash:.2f}元"
            return result
        
        # 检查是否在交易时间
        if not self.is_trading_time():
            # 非交易时间，添加到预委托
            order = {
                "type": "buy",
                "code": code,
                "amount": amount,
                "price": price,
                "timestamp": self.now(),
                "status": "pending"
            }
            self.pending_orders.append(order)
            result["success"] = True
            result["message"] = f"已添加预委托买单：{code} 数量{amount}，价格{price:.2f}"
            result["order_id"] = len(self.pending_orders) - 1
            return result
        
        # 执行买入
        self.cash -= total_cost
        if code in self.positions:
            pos = self.positions[code]
            old_value = pos["amount"] * pos["cost"]
            new_amount = pos["amount"] + amount
            new_cost = (old_value + total_cost) / new_amount
            pos["amount"] = new_amount
            pos["available"] = pos["available"]  # T+1规则，今天买入的部分不可用
            pos["cost"] = new_cost
        else:
            self.positions[code] = {
                "amount": amount,
                "available": 0,  # 今天买入的部分今天不可用
                "cost": price
            }
        
        # 记录交易
        trade = {
            "type": "buy",
            "code": code,
            "amount": amount,
            "price": price,
            "total": total_cost,
            "timestamp": self.now(),
            "cash_after": self.cash
        }
        self.trade_history.append(trade)
        
        result["success"] = True
        result["message"] = f"成功买入{code} {amount}股，价格{price:.2f}，总成本{total_cost:.2f}元"
        return result
    
    def sell(self, code: str, amount: int, price: Optional[float] = None) -> Dict[str, Any]:
        """卖出股票"""
        result = {"success": False, "message": "", "order_id": None}
        
        # 获取持仓
        pos = self.positions.get(code)
        if pos is None or pos["available"] < amount:
            result["message"] = f"持仓不足，可用{pos['available'] if pos else 0}股，尝试卖出{amount}股"
            return result
        
        # 获取价格
        if price is None:
            price = self.get_price(code, use_cache=False)
        
        if price <= 0:
            result["message"] = "获取价格失败"
            return result
        
        # 检查是否在交易时间
        if not self.is_trading_time():
            # 非交易时间，添加到预委托
            order = {
                "type": "sell",
                "code": code,
                "amount": amount,
                "price": price,
                "timestamp": self.now(),
                "status": "pending"
            }
            self.pending_orders.append(order)
            result["success"] = True
            result["message"] = f"已添加预委托卖单：{code} 数量{amount}，价格{price:.2f}"
            result["order_id"] = len(self.pending_orders) - 1
            return result
        
        # 执行卖出
        revenue = price * amount
        self.cash += revenue
        
        # 更新持仓
        pos["amount"] -= amount
        pos["available"] -= amount
        
        # 如果持仓为0，删除该股票记录
        if pos["amount"] <= 0:
            self.positions.pop(code, None)
        
        # 记录交易
        trade = {
            "type": "sell",
            "code": code,
            "amount": amount,
            "price": price,
            "total": revenue,
            "timestamp": self.now(),
            "cash_after": self.cash
        }
        self.trade_history.append(trade)
        
        result["success"] = True
        result["message"] = f"成功卖出{code} {amount}股，价格{price:.2f}，总收入{revenue:.2f}元"
        return result
    
    def process_pending_orders(self) -> List[Dict]:
        """处理预委托单，返回处理结果列表"""
        if not self.is_trading_time():
            return []  # 非交易时间不处理
        
        results = []
        # 复制当前待处理订单，然后清空原列表
        orders_to_process = self.pending_orders.copy()
        self.pending_orders.clear()
        
        for order in orders_to_process:
            if order["type"] == "buy":
                result = self.buy(
                    code=order["code"],
                    amount=order["amount"],
                    price=order.get("price")  # 使用委托价格，如果未指定则用None表示市价
                )
            else:  # sell
                result = self.sell(
                    code=order["code"],
                    amount=order["amount"],
                    price=order.get("price")
                )
            result["original_order"] = order
            results.append(result)
        
        return results
    
    def update_position_availability(self):
        """更新持仓可用数量，模拟T+1规则"""
        now = self.now()
        today = now.date()
        
        for code, pos in self.positions.items():
            # 获取今天买入的数量（从交易历史中计算）
            today_buys = 0
            for trade in self.trade_history:
                trade_date = trade["timestamp"].date() if isinstance(trade["timestamp"], datetime) else trade["timestamp"].date()
                if (trade["type"] == "buy" and trade["code"] == code and trade_date == today):
                    today_buys += trade["amount"]
            
            # 可用数量 = 总数量 - 今天买入的数量
            pos["available"] = max(0, pos["amount"] - today_buys)
    
    def add_conditional_order(self, code: str, order_type: str, amount: int, 
                             trigger_price: float, condition: str) -> Dict[str, Any]:
        """添加条件单
        condition: 'gte' (大于等于触发价) 或 'lte' (小于等于触发价)
        """
        order = {
            "code": code,
            "type": order_type,  # 'buy' 或 'sell'
            "amount": amount,
            "trigger_price": trigger_price,
            "condition": condition,
            "timestamp": self.now(),
            "status": "active"
        }
        self.conditional_orders.append(order)
        
        return {
            "success": True,
            "message": f"已添加条件单：{code} {order_type} {amount}股，触发价{trigger_price:.2f}",
            "order_id": len(self.conditional_orders) - 1
        }
    
    def check_conditional_orders(self) -> List[Dict]:
        """检查并触发条件单"""
        triggered = []
        remaining = []
        
        for order in self.conditional_orders:
            if order["status"] != "active":
                remaining.append(order)
                continue
                
            current_price = self.get_price(order["code"], use_cache=False)
            
            # 检查触发条件
            trigger = False
            if order["condition"] == "gte" and current_price >= order["trigger_price"]:
                trigger = True
            elif order["condition"] == "lte" and current_price <= order["trigger_price"]:
                trigger = True
            
            if trigger:
                # 执行条件单
                if order["type"] == "buy":
                    result = self.buy(order["code"], order["amount"])
                else:  # sell
                    result = self.sell(order["code"], order["amount"])
                
                result["conditional_order"] = order
                triggered.append(result)
                order["status"] = "triggered"
            else:
                remaining.append(order)
        
        self.conditional_orders = remaining
        return triggered
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """获取最近的交易记录"""
        return self.trade_history[-limit:] if self.trade_history else []
    
    def get_pending_orders(self) -> List[Dict]:
        """获取预委托单列表"""
        return self.pending_orders
    
    def get_conditional_orders(self) -> List[Dict]:
        """获取条件单列表"""
        return self.conditional_orders
