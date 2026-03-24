"""
股票数据服务 - 使用BaoStock获取历史数据，AKShare获取实时股价
运行命令: python data_service.py
端口: 5001
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta
import time
import json
import sys
import urllib3
import threading
import random

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 数据存储路径配置
DATA_DIR = r"D:\zhouyu\word\gupiao\deepseek_gupiao\gpData"
LS_DATA_DIR = r"D:\zhouyu\word\gupiao\deepseek_gupiao\gpLSData"

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LS_DATA_DIR, exist_ok=True)

# 股票名称缓存
STOCK_NAMES = {}

# 请求控制
last_request_time = {}
REQUEST_INTERVAL = 1  # 请求间隔1秒


def ensure_directories():
    """确保数据目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"创建数据目录: {DATA_DIR}")
    if not os.path.exists(LS_DATA_DIR):
        os.makedirs(LS_DATA_DIR)
        logger.info(f"创建本地存储目录: {LS_DATA_DIR}")


def rate_limit(code):
    """请求频率限制"""
    current_time = time.time()
    if code in last_request_time:
        elapsed = current_time - last_request_time[code]
        if elapsed < REQUEST_INTERVAL:
            wait_time = REQUEST_INTERVAL - elapsed
            time.sleep(wait_time)
    last_request_time[code] = time.time()


def load_stock_names():
    """加载股票名称缓存"""
    global STOCK_NAMES
    cache_path = os.path.join(LS_DATA_DIR, "stock_names.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                STOCK_NAMES = json.load(f)
            logger.info(f"加载了 {len(STOCK_NAMES)} 个股票名称缓存")
        except Exception as e:
            logger.error(f"加载股票名称缓存失败: {e}")


def save_stock_names():
    """保存股票名称缓存"""
    cache_path = os.path.join(LS_DATA_DIR, "stock_names.json")
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(STOCK_NAMES, f, ensure_ascii=False, indent=2)
        logger.info(f"保存了 {len(STOCK_NAMES)} 个股票名称缓存")
    except Exception as e:
        logger.error(f"保存股票名称缓存失败: {e}")


def get_stock_name_baostock(code):
    """使用BaoStock获取股票名称"""
    try:
        import baostock as bs
        
        # 转换代码格式
        if code.startswith('6'):
            full_code = f"sh.{code}"
        elif code.startswith('0') or code.startswith('3'):
            full_code = f"sz.{code}"
        else:
            full_code = f"sh.{code}"
        
        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"BaoStock登录失败: {lg.error_msg}")
            return None
        
        # 查询股票信息
        rs = bs.query_stock_basic(code=full_code)
        if rs.error_code == '0' and rs.next():
            stock_info = rs.get_row_data()
            stock_name = stock_info[1]
            bs.logout()
            return stock_name
        
        bs.logout()
        return None
    except Exception as e:
        logger.error(f"获取股票名称失败 {code}: {e}")
        return None


def get_stock_name(code):
    """获取股票名称（带缓存）"""
    if code in STOCK_NAMES:
        return STOCK_NAMES[code]
    
    name = get_stock_name_baostock(code)
    if name:
        STOCK_NAMES[code] = name
        save_stock_names()
        return name
    
    # 默认名称
    default_names = {
        '600519': '贵州茅台', '600905': '三峡能源', '000858': '五粮液',
        '300750': '宁德时代', '000001': '平安银行', '002594': '比亚迪',
        '601318': '中国平安', '600036': '招商银行', '000333': '美的集团',
        '600276': '恒瑞医药', '000568': '泸州老窖', '600887': '伊利股份',
        '601888': '中国中免', '000002': '万科A', '002415': '海康威视',
        '600030': '中信证券', '000651': '格力电器', '601985': '中国核电'
    }
    return default_names.get(code, code)


def fetch_historical_data_baostock(code):
    """使用BaoStock获取上市至今的历史交易数据"""
    try:
        import baostock as bs
        
        # 频率限制
        rate_limit(code)
        
        # 转换代码格式
        if code.startswith('6'):
            full_code = f"sh.{code}"
        elif code.startswith('0') or code.startswith('3'):
            full_code = f"sz.{code}"
        else:
            full_code = f"sh.{code}"
        
        logger.info(f"BaoStock获取历史数据: {full_code}")
        
        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"BaoStock登录失败: {lg.error_msg}")
            return None
        
        # 获取数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '1990-01-01'
        
        rs = bs.query_history_k_data_plus(
            full_code,
            "date,code,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 不复权
        )
        
        if rs.error_code != '0':
            logger.error(f"获取历史数据失败: {rs.error_msg}")
            bs.logout()
            return None
        
        # 收集数据
        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if not data_list:
            logger.warning(f"未获取到数据: {code}")
            return None
        
        # 转换为DataFrame
        columns = ['date', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount']
        df = pd.DataFrame(data_list, columns=columns)
        
        # 数据类型转换
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        
        # 过滤无效数据
        df = df.dropna(subset=['close', 'volume', 'amount'])
        df = df[df['volume'] > 0]
        
        if len(df) == 0:
            logger.warning(f"没有有效交易日数据: {code}")
            return None
        
        logger.info(f"成功获取 {len(df)} 条历史数据，范围: {df['date'].min()} 至 {df['date'].max()}")
        
        return df
        
    except Exception as e:
        logger.error(f"BaoStock获取历史数据失败 {code}: {e}")
        return None


def get_realtime_price_akshare(code):
    """使用AKShare获取实时股价"""
    try:
        import akshare as ak
        
        # 频率限制
        rate_limit(code)
        
        # 添加随机延时，避免高频请求
        time.sleep(random.uniform(0.5, 1.5))
        
        # 获取实时行情
        spot_data = ak.stock_zh_a_spot_em()
        
        # 查找指定股票
        stock_data = spot_data[spot_data['代码'] == code]
        
        if not stock_data.empty:
            row = stock_data.iloc[0]
            current_price = float(row['最新价'])
            logger.info(f"AKShare获取实时价格 {code}: {current_price}")
            return current_price
        else:
            logger.warning(f"AKShare未找到股票: {code}")
            return None
            
    except Exception as e:
        logger.error(f"AKShare获取实时价格失败 {code}: {e}")
        return None


def get_realtime_price_sina(code):
    """备用方法：新浪财经获取实时股价"""
    try:
        import requests
        
        # 频率限制
        rate_limit(code)
        
        if code.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        url = f"http://hq.sinajs.cn/list={market}{code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'gbk'
        
        if response.status_code == 200:
            content = response.text
            if '="' in content:
                data_part = content.split('="')[1].split('"')[0]
                parts = data_part.split(',')
                if len(parts) > 3:
                    current_price = float(parts[3])
                    logger.info(f"新浪财经获取实时价格 {code}: {current_price}")
                    return current_price
        
        return None
    except Exception as e:
        logger.error(f"新浪财经获取实时价格失败 {code}: {e}")
        return None


def get_realtime_price(code):
    """获取实时股价（主方法）"""
    # 优先使用AKShare
    price = get_realtime_price_akshare(code)
    if price is not None:
        return price
    
    # 备用：新浪财经
    logger.info(f"AKShare失败，尝试新浪财经: {code}")
    price = get_realtime_price_sina(code)
    if price is not None:
        return price
    
    logger.error(f"所有接口均无法获取实时价格: {code}")
    return None


def calculate_daily_avg_price(df):
    """计算每个交易日的均价 = 成交额 / 成交量"""
    return df['amount'] / df['volume']


def calculate_period_averages(df, period_type):
    """
    计算周期均价
    period_type: 'week', 'month', 'season', 'year'
    """
    if len(df) == 0:
        return 0
    
    # 复制DataFrame避免修改原数据
    df_copy = df.copy()
    
    # 计算每个交易日的均价
    df_copy['daily_avg'] = calculate_daily_avg_price(df_copy)
    
    # 添加年份和月份列
    df_copy['year'] = df_copy['date'].dt.year
    df_copy['month'] = df_copy['date'].dt.month
    df_copy['week'] = df_copy['date'].dt.isocalendar().week
    df_copy['quarter'] = df_copy['date'].dt.quarter
    
    period_averages = []
    
    if period_type == 'week':
        # 按年、周分组，计算每周均价
        for (year, week), group in df_copy.groupby(['year', 'week']):
            if len(group) > 0:
                week_avg = group['daily_avg'].mean()
                period_averages.append(week_avg)
    
    elif period_type == 'month':
        # 按年、月分组，计算每月均价
        for (year, month), group in df_copy.groupby(['year', 'month']):
            if len(group) > 0:
                month_avg = group['daily_avg'].mean()
                period_averages.append(month_avg)
    
    elif period_type == 'season':
        # 按年、季度分组，计算每季度均价
        for (year, quarter), group in df_copy.groupby(['year', 'quarter']):
            if len(group) > 0:
                season_avg = group['daily_avg'].mean()
                period_averages.append(season_avg)
    
    elif period_type == 'year':
        # 按年分组，计算每年均价
        for year, group in df_copy.groupby(['year']):
            if len(group) > 0:
                year_avg = group['daily_avg'].mean()
                period_averages.append(year_avg)
    
    # 返回所有周期均价的平均值
    if period_averages:
        return sum(period_averages) / len(period_averages)
    return 0


def calculate_all_indicators(df):
    """计算所有历史指标（不包含实时价格）"""
    if df is None or len(df) == 0:
        return None
    
    # 1. 年限（上市至今多少年）
    first_date = df['date'].min()
    today = datetime.now()
    years = (today - first_date).days / 365.25
    
    # 2. 最后交易日（从DataFrame中获取最后一条记录的日期）
    last_date = df['date'].max().strftime('%Y-%m-%d')
    
    # 3. 日均价（上市至今所有交易日日均价的平均值）
    daily_avg_prices = calculate_daily_avg_price(df)
    day_avg = daily_avg_prices.mean()
    
    # 4. 周均价
    week_avg = calculate_period_averages(df, 'week')
    
    # 5. 月均价
    month_avg = calculate_period_averages(df, 'month')
    
    # 6. 季均价
    season_avg = calculate_period_averages(df, 'season')
    
    # 7. 年均价
    year_avg = calculate_period_averages(df, 'year')
    
    # 8. 总均价（五个指标的平均值）
    total_avg = (day_avg + week_avg + month_avg + season_avg + year_avg) / 5
    
    # 9. 最高价和最低价
    high_price = df['high'].max()
    low_price = df['low'].min()
    
    return {
        'years': round(years, 1),
        'last_date': last_date,
        'day_avg': round(day_avg, 2),
        'week_avg': round(week_avg, 2),
        'month_avg': round(month_avg, 2),
        'season_avg': round(season_avg, 2),
        'year_avg': round(year_avg, 2),
        'total_avg': round(total_avg, 2),
        'high': round(high_price, 2),
        'low': round(low_price, 2),
        'data_count': len(df)
    }


def save_stock_data(code, name, df, indicators):
    """保存股票数据到文件"""
    try:
        # 保存历史数据到gpData（新数据覆盖旧数据）
        if df is not None:
            filename = f"{code}_{name}_历史数据.csv"
            filepath = os.path.join(DATA_DIR, filename)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            logger.info(f"历史数据已保存: {filepath}")
        
        # 保存指标数据到gpLSData（新数据覆盖旧数据）
        if indicators:
            indicator_file = os.path.join(LS_DATA_DIR, f"{code}_{name}_indicators.json")
            with open(indicator_file, 'w', encoding='utf-8') as f:
                json.dump(indicators, f, ensure_ascii=False, indent=2)
            logger.info(f"指标数据已保存: {indicator_file}")
            
    except Exception as e:
        logger.error(f"保存数据失败 {code}: {e}")


def load_cached_indicators(code):
    """加载缓存的指标数据"""
    try:
        # 查找指标文件
        for filename in os.listdir(LS_DATA_DIR):
            if filename.startswith(code) and filename.endswith('_indicators.json'):
                filepath = os.path.join(LS_DATA_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None
    except Exception as e:
        logger.error(f"加载缓存指标失败 {code}: {e}")
        return None


@app.route('/api/stock/history', methods=['GET'])
def get_stock_history():
    """获取A股历史数据（完整数据）"""
    code = request.args.get('code')
    force_refresh = request.args.get('force', 'false').lower() == 'true'
    only_price = request.args.get('only_price', 'false').lower() == 'true'
    
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    
    # 验证A股代码格式
    if not code.isdigit() or len(code) != 6:
        return jsonify({'error': '仅支持6位数字A股代码'}), 400
    
    try:
        logger.info(f"获取股票数据: {code}, 强制刷新: {force_refresh}, 仅价格: {only_price}")
        
        # 如果只需要实时价格
        if only_price:
            current_price = get_realtime_price(code)
            if current_price is None:
                return jsonify({'error': '获取实时价格失败'}), 404
            return jsonify({
                'code': code,
                'price': round(current_price, 2)
            })
        
        # 检查缓存（除非强制刷新）
        cached_indicators = None
        if not force_refresh:
            cached_indicators = load_cached_indicators(code)
        
        if cached_indicators and cached_indicators.get('data_count', 0) > 0:
            logger.info(f"使用缓存历史数据: {code}")
            
            # 获取实时价格
            current_price = get_realtime_price(code)
            
            name = get_stock_name(code)
            
            result = {
                'code': code,
                'name': name,
                'price': round(current_price, 2) if current_price else 0,
                'years': cached_indicators.get('years', 0),
                'last_date': cached_indicators.get('last_date', ''),
                'day_avg': cached_indicators.get('day_avg', 0),
                'week_avg': cached_indicators.get('week_avg', 0),
                'month_avg': cached_indicators.get('month_avg', 0),
                'season_avg': cached_indicators.get('season_avg', 0),
                'year_avg': cached_indicators.get('year_avg', 0),
                'total_avg': cached_indicators.get('total_avg', 0),
                'low': cached_indicators.get('low', 0),
                'high': cached_indicators.get('high', 0),
                'data_count': cached_indicators.get('data_count', 0)
            }
            
            return jsonify(result)
        
        # 获取历史数据
        logger.info(f"从BaoStock获取历史数据: {code}")
        df = fetch_historical_data_baostock(code)
        
        if df is None or len(df) < 30:
            error_msg = f'无法获取足够的历史数据，当前数据量: {len(df) if df is not None else 0}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 404
        
        # 计算各项指标（不含实时价格）
        indicators = calculate_all_indicators(df)
        
        if not indicators:
            return jsonify({'error': '数据计算失败'}), 500
        
        # 获取实时价格
        current_price = get_realtime_price(code)
        
        # 获取股票名称
        name = get_stock_name(code)
        
        # 保存数据
        save_stock_data(code, name, df, indicators)
        
        result = {
            'code': code,
            'name': name,
            'price': round(current_price, 2) if current_price else round(df['close'].iloc[-1], 2),
            'years': indicators['years'],
            'last_date': indicators['last_date'],
            'day_avg': indicators['day_avg'],
            'week_avg': indicators['week_avg'],
            'month_avg': indicators['month_avg'],
            'season_avg': indicators['season_avg'],
            'year_avg': indicators['year_avg'],
            'total_avg': indicators['total_avg'],
            'low': indicators['low'],
            'high': indicators['high'],
            'data_count': indicators['data_count']
        }
        
        logger.info(f"✅ {code} {name} 计算完成")
        logger.info(f" 现价={result['price']}, 总均价={result['total_avg']}")
        logger.info(f" 年限={result['years']}年, 最后交易={result['last_date']}, 数据量={result['data_count']}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取股票数据失败 {code}: {str(e)}")
        return jsonify({'error': f'数据获取失败: {str(e)}'}), 500


@app.route('/api/stock/price', methods=['GET'])
def get_stock_price():
    """仅获取实时股价"""
    code = request.args.get('code')
    
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    
    if not code.isdigit() or len(code) != 6:
        return jsonify({'error': '仅支持6位数字A股代码'}), 400
    
    try:
        current_price = get_realtime_price(code)
        if current_price is None:
            return jsonify({'error': '获取实时价格失败'}), 404
        
        return jsonify({
            'code': code,
            'price': round(current_price, 2)
        })
    except Exception as e:
        logger.error(f"获取实时价格失败 {code}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    baostock_available = False
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code == '0':
            baostock_available = True
            bs.logout()
    except:
        pass
    
    akshare_available = False
    try:
        import akshare as ak
        akshare_available = True
    except:
        pass
    
    return jsonify({
        'status': 'ok',
        'service': 'stock_data_service',
        'baostock': baostock_available,
        'akshare': akshare_available,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/api/clear_cache/<code>', methods=['POST'])
def clear_stock_cache(code):
    """清除指定股票的缓存"""
    try:
        # 清除历史数据文件
        import glob
        history_files = glob.glob(os.path.join(DATA_DIR, f"{code}_*_历史数据.csv"))
        for f in history_files:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"删除历史数据文件: {f}")
        
        # 清除指标文件
        indicator_files = glob.glob(os.path.join(LS_DATA_DIR, f"{code}_*_indicators.json"))
        for f in indicator_files:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"删除指标文件: {f}")
        
        return jsonify({'message': f'已清除 {code} 的缓存'})
    except Exception as e:
        logger.error(f"清除缓存失败 {code}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    ensure_directories()
    load_stock_names()
    
    print("=" * 60)
    print("📊 股票数据服务启动")
    print("=" * 60)
    print(f"📁 历史数据目录: {DATA_DIR}")
    print(f"📁 指标数据目录: {LS_DATA_DIR}")
    print("🌐 服务地址: http://localhost:5001")
    print("📈 测试: http://localhost:5001/api/stock/history?code=600519")
    print("💹 健康检查: http://localhost:5001/api/health")
    print("=" * 60)
    print("✅ 数据源: BaoStock (历史数据) + AKShare (实时股价)")
    print("✅ 计算指标: 日均、周均、月均、季均、年均、总均价")
    print("✅ 算法: 基于成交额/成交量的加权均价")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)