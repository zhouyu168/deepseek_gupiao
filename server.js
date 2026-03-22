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

// 内存缓存
let memoryCache = {};
const CACHE_TIME = 60 * 1000; // 1分钟缓存

// 加载持久化缓存
function loadPersistentCache() {
    try {
        if (fs.existsSync(CACHE_FILE)) {
            const data = fs.readFileSync(CACHE_FILE, 'utf-8');
            const cached = JSON.parse(data);
            // 过滤过期缓存
            const now = Date.now();
            Object.keys(cached).forEach(key => {
                if (now - cached[key].time < CACHE_TIME * 24) { // 24小时
                    memoryCache[key] = cached[key];
                }
            });
            console.log(`📦 加载了 ${Object.keys(memoryCache).length} 条持久化缓存`);
        }
    } catch (error) {
        console.error("加载持久化缓存失败:", error);
    }
}

// 保存持久化缓存
function savePersistentCache() {
    try {
        fs.writeFileSync(CACHE_FILE, JSON.stringify(memoryCache, null, 2), 'utf-8');
    } catch (error) {
        console.error("保存持久化缓存失败:", error);
    }
}

// 保存股票列表
function saveStocksList(stocks) {
    const stocksFile = path.join(LS_DATA_DIR, "stocks_list.json");
    try {
        fs.writeFileSync(stocksFile, JSON.stringify(stocks, null, 2), 'utf-8');
        console.log(`💾 保存了 ${stocks.length} 只股票到本地`);
    } catch (error) {
        console.error("保存股票列表失败:", error);
    }
}

// 加载股票列表
function loadStocksList() {
    const stocksFile = path.join(LS_DATA_DIR, "stocks_list.json");
    try {
        if (fs.existsSync(stocksFile)) {
            const data = fs.readFileSync(stocksFile, 'utf-8');
            return JSON.parse(data);
        }
    } catch (error) {
        console.error("加载股票列表失败:", error);
    }
    return null;
}

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get("/api/stock", async (req, res) => {
    const code = req.query.code;
    const force = req.query.force === 'true';
    
    if (!code) {
        return res.status(400).json({ error: "缺少股票代码" });
    }
    
    // 验证A股代码
    if (!/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "仅支持6位数字A股代码" });
    }
    
    // 检查内存缓存
    if (!force && memoryCache[code] && Date.now() - memoryCache[code].time < CACHE_TIME) {
        console.log(`✅ 缓存命中: ${code}`);
        return res.json(memoryCache[code].data);
    }
    
    try {
        console.log(`📊 获取股票数据: ${code}`);
        
        const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/history`, {
            params: { code: code, force: force },
            timeout: 30000
        });
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        
        const data = response.data;
        
        // 计算差价
        const diff = data.price - data.total_avg;
        
        // 构建返回结果
        const result = {
            code: data.code,
            name: data.name,
            price: data.price,
            years: data.years,
            day_avg: data.day_avg,
            week_avg: data.week_avg,
            month_avg: data.month_avg,
            season_avg: data.season_avg,
            year_avg: data.year_avg,
            total_avg: data.total_avg,
            low: data.low,
            high: data.high,
            diff: diff,
            diff_sign: diff >= 0 ? '+' : '',
            diff_class: diff >= 0 ? 'green' : 'red',
            data_count: data.data_count
        };
        
        // 存入缓存
        memoryCache[code] = {
            time: Date.now(),
            data: result
        };
        
        // 保存持久化缓存
        savePersistentCache();
        
        console.log(`✅ 成功获取: ${code} - ${data.name}`);
        console.log(`  现价: ${result.price} | 总均价: ${result.total_avg}`);
        console.log(`  差价: ${result.diff_sign}${result.diff.toFixed(2)} | 年限: ${result.years}年`);
        
        res.json(result);
        
    } catch (error) {
        console.error(`❌ 获取失败 ${code}:`, error.message);
        
        // 尝试返回过期缓存
        if (memoryCache[code]) {
            console.log(`📦 返回过期缓存: ${code}`);
            return res.json(memoryCache[code].data);
        }
        
        res.status(500).json({ 
            error: "获取失败", 
            message: error.message,
            code: code
        });
    }
});

app.post("/api/stocks", async (req, res) => {
    const { stocks } = req.body;
    
    if (!stocks || !Array.isArray(stocks)) {
        return res.status(400).json({ error: "无效的股票列表" });
    }
    
    // 保存股票列表
    saveStocksList(stocks);
    
    res.json({ message: "股票列表已保存", count: stocks.length });
});

app.get("/api/stocks", (req, res) => {
    const stocks = loadStocksList();
    res.json({ stocks: stocks || [] });
});

app.post("/api/stock/clear", (req, res) => {
    const count = Object.keys(memoryCache).length;
    memoryCache = {};
    savePersistentCache();
    console.log(`🗑️ 清除了 ${count} 条缓存`);
    res.json({ message: "缓存已清除", count: count });
});

app.post("/api/stock/clear/:code", (req, res) => {
    const code = req.params.code;
    if (memoryCache[code]) {
        delete memoryCache[code];
        savePersistentCache();
        console.log(`🗑️ 清除了 ${code} 的缓存`);
        res.json({ message: `已清除 ${code} 的缓存` });
    } else {
        res.json({ message: `未找到 ${code} 的缓存` });
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
    console.log("  • 上海: 6开头，如 600519, 600905");
    console.log("  • 深圳: 0/3开头，如 000001, 300750");
    console.log("=".repeat(60));
    console.log("📊 计算指标说明:");
    console.log("  • 日均: 上市至今所有交易日加权均价（成交额/成交量）");
    console.log("  • 周均: 每周加权均价的平均值");
    console.log("  • 月均: 每月加权均价的平均值");
    console.log("  • 季均: 每季加权均价的平均值");
    console.log("  • 年均: 每年加权均价的平均值");
    console.log("  • 总均价: 上述5个指标的平均值");
    console.log("=".repeat(60) + "\n");
});