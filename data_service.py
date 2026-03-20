"""
股票数据服务 - 使用新浪财经API获取真实A股数据
运行命令: python data_service_new.py
端口: 5001
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import re
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_stock_name(code):
    """获取股票名称"""
    name_map = {
        '600519': '贵州茅台', '600905': '三峡能源', '000858': '五粮液',
        '000001': '平安银行', '300750': '宁德时代', '002594': '比亚迪',
        '601318': '中国平安', '600036': '招商银行', '000333': '美的集团',
        '600276': '恒瑞医药', '000002': '万科A', '002415': '海康威视',
        '600030': '中信证券', '000651': '格力电器', '002475': '立讯精密'
    }
    return name_map.get(code, code)

def get_sina_format(code):
    """转换为新浪财经格式"""
    if code.startswith('6'):
        return f"sh{code}"
    elif code.startswith('0') or code.startswith('3'):
        return f"sz{code}"
    else:
        return None

@app.route('/api/stock/history', methods=['GET'])
def get_stock_history():
    """
    获取A股历史数据（使用新浪财经API）
    """
    code = request.args.get('code')
    days = int(request.args.get('days', 365))
    
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    
    # 只支持A股
    if not code.isdigit() or (not code.startswith('6') and not code.startswith('0') and not code.startswith('3')):
        return jsonify({'error': '仅支持A股（6位数字代码）'}), 400
    
    try:
        logger.info(f"获取历史数据: {code}, 天数: {days}")
        
        sina_code = get_sina_format(code)
        if not sina_code:
            return jsonify({'error': '不支持的股票代码格式'}), 400
        
        # 使用新浪财经API获取历史数据
        # 获取最近500天的数据
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            'symbol': sina_code,
            'scale': '240',  # 日线
            'ma': 'no',
            'datalen': min(days + 100, 1023)  # 最多1023条
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            # 备用方案：使用腾讯财经API
            return get_tencent_history(code, days)
        
        # 解析数据
        data = response.text
        # 新浪返回的是JSON格式的字符串
        if data.startswith('['):
            klines = json.loads(data)
        else:
            return get_tencent_history(code, days)
        
        if not klines:
            return get_tencent_history(code, days)
        
        # 提取数据
        dates = []
        prices = []
        volumes = []
        highs = []
        lows = []
        opens = []
        
        for k in klines[:days]:
            dates.append(k.get('day', ''))
            prices.append(float(k.get('close', 0)))
            volumes.append(float(k.get('volume', 0)))
            highs.append(float(k.get('high', 0)))
            lows.append(float(k.get('low', 0)))
            opens.append(float(k.get('open', 0)))
        
        if not prices:
            return jsonify({'error': '未获取到数据'}), 404
        
        current_price = prices[0]
        name = get_stock_name(code)
        
        # 计算均线
        stats = calculate_indicators(prices)
        
        return jsonify({
            'code': code,
            'name': name,
            'price': current_price,
            'prices': prices,
            'dates': dates,
            'volumes': volumes,
            'highs': highs,
            'lows': lows,
            'opens': opens,
            'data_count': len(prices),
            'indicators': stats
        })
        
    except Exception as e:
        logger.error(f"获取股票数据失败 {code}: {str(e)}")
        return jsonify({'error': f'数据获取失败: {str(e)}'}), 500

def get_tencent_history(code, days):
    """备用方案：使用腾讯财经API"""
    try:
        logger.info(f"使用腾讯API获取: {code}")
        
        if code.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        # 腾讯财经API
        url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            'param': f'{market}{code},day,,,{days + 50}',
            '_var': 'kline_dayqfq'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.qq.com'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'error': '无法获取数据'}), 500
        
        # 解析腾讯返回的数据
        text = response.text
        # 提取JSON部分
        match = re.search(r'kline_dayqfq="(.*?)"', text)
        if not match:
            return jsonify({'error': '数据格式错误'}), 500
        
        data_str = match.group(1)
        data = json.loads(data_str)
        
        if 'data' not in data or market+code not in data['data']:
            return jsonify({'error': '未找到股票数据'}), 404
        
        klines = data['data'][market+code]['qfqday']
        
        if not klines:
            return jsonify({'error': '无历史数据'}), 404
        
        dates = []
        prices = []
        
        for k in klines[:days]:
            # 格式: "2024-03-20", 170.5, 171.2, 169.8, 170.8, 12345678
            parts = k.split(',')
            if len(parts) >= 5:
                dates.append(parts[0])
                prices.append(float(parts[4]))  # 收盘价
        
        if not prices:
            return jsonify({'error': '数据解析失败'}), 500
        
        current_price = prices[0]
        name = get_stock_name(code)
        stats = calculate_indicators(prices)
        
        return jsonify({
            'code': code,
            'name': name,
            'price': current_price,
            'prices': prices,
            'dates': dates,
            'data_count': len(prices),
            'indicators': stats
        })
        
    except Exception as e:
        logger.error(f"腾讯API失败 {code}: {str(e)}")
        return jsonify({'error': f'所有数据源均失败: {str(e)}'}), 500

def calculate_indicators(prices):
    """计算技术指标"""
    if not prices or len(prices) < 5:
        return {
            'ma5': 0, 'ma10': 0, 'ma20': 0, 'ma30': 0,
            'ma60': 0, 'ma120': 0, 'ma250': 0,
            'high': 0, 'low': 0
        }
    
    def ma(data, n):
        if len(data) < n:
            return 0
        return sum(data[:n]) / n
    
    ma5 = ma(prices, min(5, len(prices)))
    ma10 = ma(prices, min(10, len(prices)))
    ma20 = ma(prices, min(20, len(prices)))
    ma30 = ma(prices, min(30, len(prices)))
    ma60 = ma(prices, min(60, len(prices)))
    ma120 = ma(prices, min(120, len(prices)))
    ma250 = ma(prices, min(250, len(prices)))
    
    high = max(prices)
    low = min(prices)
    
    return {
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'ma30': round(ma30, 2),
        'ma60': round(ma60, 2),
        'ma120': round(ma120, 2),
        'ma250': round(ma250, 2),
        'high': round(high, 2),
        'low': round(low, 2)
    }

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'sina_finance',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    print("=" * 60)
    print("📊 股票数据服务启动 (新浪财经API)")
    print("=" * 60)
    print("🌐 服务地址: http://localhost:5001")
    print("📈 测试A股: http://localhost:5001/api/stock/history?code=600519")
    print("💹 健康检查: http://localhost:5001/api/health")
    print("=" * 60)
    print("✅ 仅支持A股（6位数字代码）")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=True)