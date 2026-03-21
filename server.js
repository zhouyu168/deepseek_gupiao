const express = require("express");
const axios = require("axios");
const cors = require("cors");
const path = require("path");

const app = express();
const PORT = 3000;
const PYTHON_SERVICE_URL = "http://127.0.0.1:5001";

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const cache = {};
const CACHE_TIME = 60 * 1000; // 1分钟缓存

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get("/api/stock", async (req, res) => {
    const code = req.query.code;
    
    if (!code) {
        return res.status(400).json({ error: "缺少股票代码" });
    }
    
    // 验证A股代码
    if (!/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "仅支持6位数字A股代码" });
    }

    // 检查缓存
    if (cache[code] && Date.now() - cache[code].time < CACHE_TIME) {
        console.log(`✅ 缓存命中: ${code}`);
        return res.json(cache[code].data);
    }

    try {
        console.log(`📊 获取股票数据: ${code}`);
        
        const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/history`, {
            params: { code: code, days: 1000 },
            timeout: 15000
        });
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        
        const data = response.data;
        
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
            data_count: data.data_count
        };
        
        // 存入缓存
        cache[code] = {
            time: Date.now(),
            data: result
        };
        
        console.log(`✅ 成功获取: ${code} - ${data.name}`);
        console.log(`   现价: ${result.price} | 日均: ${result.day_avg}`);
        console.log(`   总均价: ${result.total_avg} | 年限: ${result.years}年`);
        
        res.json(result);
        
    } catch (error) {
        console.error(`❌ 获取失败 ${code}:`, error.message);
        res.status(500).json({ 
            error: "获取失败", 
            message: error.message,
            code: code
        });
    }
});

app.post("/api/stock/clear", (req, res) => {
    Object.keys(cache).forEach(key => delete cache[key]);
    console.log("🗑️ 缓存已清除");
    res.json({ message: "缓存已清除" });
});

app.get("/api/health", async (req, res) => {
    try {
        const pythonHealth = await axios.get(`${PYTHON_SERVICE_URL}/api/health`, { timeout: 5000 });
        res.json({
            status: "ok",
            node: "running",
            python: "connected",
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.log("⚠️ Python服务未连接");
        res.json({
            status: "degraded",
            node: "running",
            python: "disconnected",
            error: error.message
        });
    }
});

app.listen(PORT, () => {
    console.log("\n" + "=".repeat(60));
    console.log("🚀 A股分析系统启动成功");
    console.log("=".repeat(60));
    console.log(`📱 前端访问: http://localhost:${PORT}`);
    console.log(`🔧 API测试: http://localhost:${PORT}/api/stock?code=600519`);
    console.log("=".repeat(60));
    console.log("📌 支持的股票类型: A股（6位数字代码）");
    console.log("   • 上海: 6开头，如 600519, 600905");
    console.log("   • 深圳: 0/3开头，如 000001, 300750");
    console.log("=".repeat(60));
    console.log("📊 计算指标说明:");
    console.log("   • 日均: 上市至今所有交易日的平均价");
    console.log("   • 周均: 每周最后一个交易日的平均价");
    console.log("   • 月均: 每月最后一个交易日的平均价");
    console.log("   • 季均: 每季度最后一个交易日的平均价");
    console.log("   • 年均: 每年最后一个交易日的平均价");
    console.log("   • 总均价: 上述5个指标的平均值");
    console.log("=".repeat(60) + "\n");
});