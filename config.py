# config.py
import os

# 数据源配置
DATA_SOURCES = {
    'akshare_primary': True,
    'tencent_finance': True,
    'sina_finance': True,
    'fallback_to_mock': True  # 如果所有源都失败，使用模拟数据
}

# 缓存配置
CACHE_CONFIG = {
    'price_cache_seconds': 30,
    'max_cache_size': 1000
}

# 交易配置
TRADING_CONFIG = {
    'trading_hours': {
        'morning_start': 930,
        'morning_end': 1130,
        'afternoon_start': 1300,
        'afternoon_end': 1500
    },
    'min_trade_units': 100,
    't_plus_one': True
}
