const express = require("express");
const axios = require("axios");
const cors = require("cors");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = 3000;
const PYTHON_SERVICE_URL = "http://127.0.0.1:5001";

// 数据存储路径
const LS_DATA_DIR = "D:\\zhouyu\\word\\gupiao\\deepseek_gupiao\\gpLSData";

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 确保数据目录存在
if (!fs.existsSync(LS_DATA_DIR)) {
    fs.mkdirSync(LS_DATA_DIR, { recursive: true });
}

// 缓存文件路径
const CACHE_FILE = path.join(LS_DATA_DIR, "stocks_cache.json");
const STOCKS_LIST_FILE = path.join(LS_DATA_DIR, "stocks_list.json");

// 内存缓存 - 仅用于历史数据缓存，现价数据不缓存
let memoryCache = {};

// 加载持久化缓存
function loadPersistentCache() {
    try {
        if (fs.existsSync(CACHE_FILE)) {
            const data = fs.readFileSync(CACHE_FILE, 'utf-8');
            const cached = JSON.parse(data);
            // 只保留当天的缓存，过期缓存直接丢弃
            const now = new Date();
            const today = now.toDateString();
            Object.keys(cached).forEach(key => {
                const cacheDate = new Date(cached[key].time).toDateString();
                if (cacheDate === today) {
                    memoryCache[key] = cached[key];
                }
            });
            console.log(`📦 加载了 ${Object.keys(memoryCache).length} 条今日缓存`);
        }
    } catch (error) {
        console.error("加载持久化缓存失败:", error);
    }
}

// 保存持久化缓存 - 只保存当天的数据
function savePersistentCache() {
    try {
        const now = new Date();
        const today = now.toDateString();
        // 只保存今天的缓存
        const todayCache = {};
        Object.keys(memoryCache).forEach(key => {
            const cacheDate = new Date(memoryCache[key].time).toDateString();
            if (cacheDate === today) {
                todayCache[key] = memoryCache[key];
            }
        });
        fs.writeFileSync(CACHE_FILE, JSON.stringify(todayCache, null, 2), 'utf-8');
    } catch (error) {
        console.error("保存持久化缓存失败:", error);
    }
}

// 保存股票列表
function saveStocksList(stocks) {
    const stocksFile = STOCKS_LIST_FILE;
    try {
        const dir = path.dirname(stocksFile);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(stocksFile, JSON.stringify(stocks, null, 2), 'utf-8');
        console.log(`💾 保存了 ${stocks.length} 只股票到本地: ${stocksFile}`);
        return true;
    } catch (error) {
        console.error("保存股票列表失败:", error);
        return false;
    }
}

// 加载股票列表
function loadStocksList() {
    const stocksFile = STOCKS_LIST_FILE;
    try {
        if (fs.existsSync(stocksFile)) {
            const data = fs.readFileSync(stocksFile, 'utf-8');
            const stocks = JSON.parse(data);
            console.log(`📂 加载了 ${stocks.length} 只股票从: ${stocksFile}`);
            return stocks;
        } else {
            console.log(`⚠️ 股票列表文件不存在: ${stocksFile}`);
        }
    } catch (error) {
        console.error("加载股票列表失败:", error);
    }
    return null;
}

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 提供图片服务
app.get('/images/:filename', (req, res) => {
    const filename = req.params.filename;
    const imagePath = path.join("D:\\zhouyu\\word\\gupiao\\deepseek_gupiao", filename);
    
    if (fs.existsSync(imagePath)) {
        res.sendFile(imagePath);
    } else {
        console.log(`图片不存在: ${imagePath}`);
        res.status(404).send('Image not found');
    }
});

// 获取完整股票数据（历史+实时）
app.get("/api/stock", async (req, res) => {
    const code = req.query.code;
    const force = req.query.force === 'true';
    
    if (!code) {
        return res.status(400).json({ error: "缺少股票代码" });
    }
    
    if (!/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "仅支持6位数字A股代码" });
    }
    
    try {
        console.log(`📊 获取股票完整数据: ${code}`);
        
        const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/history`, {
            params: { code: code, force: force },
            timeout: 30000
        });
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        
        const data = response.data;
        
        // 计算差价
        let diff = null;
        if (data.price !== null && data.price !== undefined && data.total_avg) {
            diff = data.price - data.total_avg;
        }
        
        // 构建返回结果
        const result = {
            code: data.code,
            name: data.name,
            price: data.price,
            years: data.years,
            last_date: data.last_date,
            day_avg: data.day_avg,
            week_avg: data.week_avg,
            month_avg: data.month_avg,
            season_avg: data.season_avg,
            year_avg: data.year_avg,
            total_avg: data.total_avg,
            low: data.low,
            high: data.high,
            diff: diff,
            diff_sign: diff !== null ? (diff >= 0 ? '+' : '') : '',
            diff_class: diff !== null ? (diff >= 0 ? 'red' : 'green') : '',
            data_count: data.data_count
        };
        
        // 存入缓存（仅缓存历史数据，现价不缓存）
        memoryCache[code] = {
            time: Date.now(),
            data: result
        };
        
        // 保存持久化缓存
        savePersistentCache();
        
        console.log(`✅ 成功获取: ${code} - ${data.name}`);
        console.log(` 现价: ${result.price} | 总均价: ${result.total_avg}`);
        console.log(` 差价: ${result.diff_sign}${result.diff?.toFixed(2)} | 年限: ${result.years}年 | 最后交易: ${result.last_date}`);
        
        res.json(result);
        
    } catch (error) {
        console.error(`❌ 获取失败 ${code}:`, error.message);
        
        // 检查是否为无缓存错误
        if (error.response && error.response.data && error.response.data.no_cache) {
            console.log(`❌ ${code} 无可用缓存，需要手动刷新`);
            return res.status(404).json({ 
                error: "获取失败，无可用缓存", 
                message: error.message,
                code: code,
                no_cache: true
            });
        }
        
        // 其他错误，返回错误信息
        res.status(500).json({ 
            error: "获取失败", 
            message: error.message,
            code: code
        });
    }
});

// 单只股票历史数据更新
app.post("/api/stock/single_update", async (req, res) => {
    const { code } = req.body;
    
    if (!code || !/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "无效的股票代码" });
    }
    
    try {
        console.log(`🔄 单只股票历史数据更新: ${code}`);
        
        const response = await axios.post(`${PYTHON_SERVICE_URL}/api/stock/single_update`, {
            code: code
        }, {
            timeout: 30000
        });
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        
        const data = response.data;
        
        // 计算差价
        let diff = null;
        if (data.price !== null && data.price !== undefined && data.total_avg) {
            diff = data.price - data.total_avg;
        }
        
        const result = {
            code: data.code,
            name: data.name,
            price: data.price,
            years: data.years,
            last_date: data.last_date,
            day_avg: data.day_avg,
            week_avg: data.week_avg,
            month_avg: data.month_avg,
            season_avg: data.season_avg,
            year_avg: data.year_avg,
            total_avg: data.total_avg,
            low: data.low,
            high: data.high,
            diff: diff,
            diff_sign: diff !== null ? (diff >= 0 ? '+' : '') : '',
            diff_class: diff !== null ? (diff >= 0 ? 'red' : 'green') : '',
            data_count: data.data_count
        };
        
        // 更新缓存
        memoryCache[code] = {
            time: Date.now(),
            data: result
        };
        savePersistentCache();
        
        console.log(`✅ 单只股票更新完成: ${code} ${data.name}`);
        res.json(result);
        
    } catch (error) {
        console.error(`单只股票更新失败 ${code}:`, error.message);
        res.status(500).json({ 
            error: "更新失败", 
            message: error.message,
            code: code
        });
    }
});

// 仅获取实时价格（强制实时获取，不使用缓存）
app.get("/api/stock/price", async (req, res) => {
    const code = req.query.code;
    
    if (!code || !/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "无效的股票代码" });
    }
    
    try {
        const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/price`, {
            params: { code: code },
            timeout: 10000
        });
        
        if (response.data && response.data.price !== undefined) {
            res.json(response.data);
        } else {
            res.status(404).json({ error: "获取实时价格失败" });
        }
    } catch (error) {
        console.error(`获取实时价格失败 ${code}:`, error.message);
        res.status(500).json({ error: "获取实时价格失败", message: error.message });
    }
});

// 批量更新实时价格
app.post("/api/stock/prices", async (req, res) => {
    const { codes } = req.body;
    
    if (!codes || !Array.isArray(codes)) {
        return res.status(400).json({ error: "无效的股票代码列表" });
    }
    
    const results = {};
    const errors = [];
    
    for (const code of codes) {
        try {
            const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/price`, {
                params: { code: code },
                timeout: 10000
            });
            if (response.data && response.data.price !== undefined) {
                results[code] = response.data.price;
            } else {
                results[code] = null;
                errors.push(code);
            }
            // 请求间隔
            await new Promise(resolve => setTimeout(resolve, 1000));
        } catch (error) {
            console.error(`获取价格失败 ${code}:`, error.message);
            results[code] = null;
            errors.push(code);
        }
    }
    
    res.json({ prices: results, errors: errors });
});

// 保存股票列表
app.post("/api/stocks", async (req, res) => {
    const { stocks } = req.body;
    
    if (!stocks || !Array.isArray(stocks)) {
        return res.status(400).json({ error: "无效的股票列表" });
    }
    
    // 限制最多300只
    const limitedStocks = stocks.slice(0, 300);
    
    // 保存股票列表
    const success = saveStocksList(limitedStocks);
    
    if (success) {
        console.log(`✅ 股票列表已保存，共 ${limitedStocks.length} 只`);
        res.json({ message: "股票列表已保存", count: limitedStocks.length });
    } else {
        res.status(500).json({ error: "保存股票列表失败" });
    }
});

// 加载股票列表
app.get("/api/stocks", (req, res) => {
    const stocks = loadStocksList();
    console.log(`📋 返回股票列表，共 ${stocks ? stocks.length : 0} 只`);
    res.json({ stocks: stocks || [] });
});

app.post("/api/stock/clear", (req, res) => {
    const count = Object.keys(memoryCache).length;
    memoryCache = {};
    savePersistentCache();
    console.log(`🗑️ 清除了 ${count} 条缓存`);
    res.json({ message: "缓存已清除", count: count });
});

app.post("/api/stock/clear/:code", async (req, res) => {
    const code = req.params.code;
    
    try {
        // 清除内存缓存
        if (memoryCache[code]) {
            delete memoryCache[code];
        }
        
        // 调用Python服务清除文件缓存
        await axios.post(`${PYTHON_SERVICE_URL}/api/clear_cache/${code}`);
        
        savePersistentCache();
        console.log(`🗑️ 清除了 ${code} 的缓存`);
        res.json({ message: `已清除 ${code} 的缓存` });
    } catch (error) {
        console.error(`清除缓存失败 ${code}:`, error.message);
        res.status(500).json({ error: "清除缓存失败" });
    }
});

app.get("/api/health", async (req, res) => {
    try {
        const pythonHealth = await axios.get(`${PYTHON_SERVICE_URL}/api/health`, { timeout: 5000 });
        res.json({
            status: "ok",
            node: "running",
            python: "connected",
            baostock: pythonHealth.data.baostock,
            akshare: pythonHealth.data.akshare,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.log("⚠️ Python服务未连接");
        res.json({
            status: "degraded",
            node: "running",
            python: "disconnected",
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// 加载持久化缓存
loadPersistentCache();

app.listen(PORT, () => {
    console.log("\n" + "=".repeat(60));
    console.log("🚀 A股分析系统启动成功");
    console.log("=".repeat(60));
    console.log(`📱 前端访问: http://localhost:${PORT}`);
    console.log(`🔧 API测试: http://localhost:${PORT}/api/stock?code=600519`);
    console.log(`📁 数据存储: ${LS_DATA_DIR}`);
    console.log("=".repeat(60));
    console.log("📌 支持的股票类型: A股（6位数字代码）");
    console.log(" • 上海: 6开头，如 600519, 601985");
    console.log(" • 深圳: 0/3开头，如 000001, 300750");
    console.log("=".repeat(60) + "\n");
});