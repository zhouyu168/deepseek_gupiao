"""
股票数据服务 - 使用新浪财经API获取真实A股数据
运行命令: python data_service.py
端口: 5001
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from datetime import datetime
import json
import re
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 股票名称映射
STOCK_NAMES = {
    '600519': '贵州茅台', '600905': '三峡能源', '000858': '五粮液',
    '300750': '宁德时代', '000001': '平安银行', '002594': '比亚迪',
    '601318': '中国平安', '600036': '招商银行', '000333': '美的集团',
    '600276': '恒瑞医药', '000568': '泸州老窖', '600887': '伊利股份',
    '601888': '中国中免', '000002': '万科A', '002415': '海康威视',
    '600030': '中信证券', '000651': '格力电器'
}

def get_realtime_price(code):
    """获取实时价格 - 使用新浪财经"""
    try:
        # 获取市场前缀
        if code.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        # 新浪实时行情接口
        url = f"http://hq.sinajs.cn/list={market}{code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'
        
        if response.status_code == 200:
            content = response.text
            # 格式: var hq_str_sh600905="三峡能源,4.33,4.33,4.32,4.34,4.31,4.33,...";
            if '="' in content:
                data_part = content.split('="')[1].split('"')[0]
                parts = data_part.split(',')
                if len(parts) > 3:
                    # 当前价通常是第4个字段（索引3）
                    current_price = float(parts[3])
                    logger.info(f"实时价格 {code}: {current_price}")
                    return current_price
        
        return None
    except Exception as e:
        logger.error(f"获取实时价格失败 {code}: {str(e)}")
        return None

def fetch_historical_prices(code, days=1000):
    """获取历史收盘价 - 使用新浪财经"""
    try:
        if code.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        # 新浪财经历史数据接口
        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            'symbol': f"{market}{code}",
            'scale': '240',  # 日线
            'ma': 'no',
            'datalen': days
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"新浪API返回状态码: {response.status_code}")
            return None
        
        # 解析JSON数据
        try:
            data = json.loads(response.text)
        except:
            logger.warning(f"解析JSON失败: {response.text[:100]}")
            return None
        
        if not data or len(data) == 0:
            logger.warning(f"未获取到数据: {code}")
            return None
        
        # 新浪返回的是从新到旧，需要反转成从旧到新
        data.reverse()
        
        prices = []
        for item in data:
            try:
                price = float(item.get('close', 0))
                if price > 0:
                    prices.append(price)
            except:
                continue
        
        if len(prices) < 30:
            logger.warning(f"数据不足: {code}, 仅{len(prices)}条")
            return None
        
        logger.info(f"成功获取 {code} 历史数据: {len(prices)}条")
        return prices
        
    except Exception as e:
        logger.error(f"获取历史数据异常 {code}: {str(e)}")
        return None

def calculate_all_indicators(code, prices, current_price):
    """计算所有指标"""
    n = len(prices)
    
    if n == 0:
        return None
    
    # 1. 日均价（所有日数据的平均值）
    day_avg = sum(prices) / n
    
    # 2. 周均价（每周最后一个交易日的平均值，5天为一周）
    week_prices = []
    for i in range(4, n, 5):
        if i < n:
            week_prices.append(prices[i])
    week_avg = sum(week_prices) / len(week_prices) if week_prices else day_avg
    
    # 3. 月均价（每月最后一个交易日的平均值，20天为一月）
    month_prices = []
    for i in range(19, n, 20):
        if i < n:
            month_prices.append(prices[i])
    month_avg = sum(month_prices) / len(month_prices) if month_prices else day_avg
    
    # 4. 季均价（每季度最后一个交易日的平均值，60天为一季）
    season_prices = []
    for i in range(59, n, 60):
        if i < n:
            season_prices.append(prices[i])
    season_avg = sum(season_prices) / len(season_prices) if season_prices else day_avg
    
    # 5. 年均价（每年最后一个交易日的平均值，250天为一年）
    year_prices = []
    for i in range(249, n, 250):
        if i < n:
            year_prices.append(prices[i])
    year_avg = sum(year_prices) / len(year_prices) if year_prices else day_avg
    
    # 6. 总均价（五个指标的平均值）
    total_avg = (day_avg + week_avg + month_avg + season_avg + year_avg) / 5
    
    # 7. 年限（上市年数）
    years = n / 250
    
    # 8. 最低价和最高价
    low_price = min(prices)
    high_price = max(prices)
    
    result = {
        'code': code,
        'name': STOCK_NAMES.get(code, code),
        'price': round(current_price, 2) if current_price else round(prices[-1], 2),
        'years': round(years, 1),
        'day_avg': round(day_avg, 2),
        'week_avg': round(week_avg, 2),
        'month_avg': round(month_avg, 2),
        'season_avg': round(season_avg, 2),
        'year_avg': round(year_avg, 2),
        'total_avg': round(total_avg, 2),
        'low': round(low_price, 2),
        'high': round(high_price, 2),
        'data_count': n
    }
    
    return result

@app.route('/api/stock/history', methods=['GET'])
def get_stock_history():
    """获取A股历史数据"""
    code = request.args.get('code')
    days = int(request.args.get('days', 1000))
    
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    
    # 验证A股代码格式
    if not code.isdigit() or len(code) != 6:
        return jsonify({'error': '仅支持6位数字A股代码'}), 400
    
    try:
        logger.info(f"获取股票数据: {code}")
        
        # 获取历史数据
        prices = fetch_historical_prices(code, days)
        
        if not prices or len(prices) < 30:
            error_msg = f'无法获取足够的历史数据，当前数据量: {len(prices) if prices else 0}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 404
        
        logger.info(f"成功获取 {len(prices)} 条历史数据")
        
        # 获取实时价格
        current_price = get_realtime_price(code)
        
        # 如果获取不到实时价格，使用最新历史价格
        if not current_price:
            current_price = prices[-1]
            logger.info(f"使用最新历史价格: {current_price}")
        
        # 计算各项指标
        result = calculate_all_indicators(code, prices, current_price)
        
        if not result:
            return jsonify({'error': '数据计算失败'}), 500
        
        logger.info(f"✅ {code} {result['name']} 计算完成")
        logger.info(f"   现价={result['price']}, 日均={result['day_avg']}")
        logger.info(f"   总均价={result['total_avg']}, 年限={result['years']}年")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取股票数据失败 {code}: {str(e)}")
        return jsonify({'error': f'数据获取失败: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'stock_data_service',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/test/<code>', methods=['GET'])
def test_stock(code):
    """测试接口"""
    try:
        prices = fetch_historical_prices(code, 100)
        if prices:
            return jsonify({
                'code': code,
                'data_count': len(prices),
                'latest_price': prices[-1],
                'first_price': prices[0],
                'prices_sample': prices[:10]
            })
        else:
            return jsonify({'error': '获取失败'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("📊 股票数据服务启动")
    print("=" * 60)
    print("🌐 服务地址: http://localhost:5001")
    print("📈 测试: http://localhost:5001/api/stock/history?code=600519")
    print("🔧 调试: http://localhost:5001/api/test/600905")
    print("💹 健康检查: http://localhost:5001/api/health")
    print("=" * 60)
    print("✅ 数据源: 新浪财经API")
    print("✅ 使用真实价格（不复权）")
    print("✅ 计算指标: 日均、周均、月均、季均、年均、总均价")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)