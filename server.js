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
const CACHE_TIME = 60 * 1000;

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 只支持A股
app.get("/api/stock", async (req, res) => {
    const code = req.query.code;
    if (!code) {
        return res.status(400).json({ error: "缺少股票代码" });
    }
    
    // 只处理A股（6位数字）
    if (!/^\d{6}$/.test(code)) {
        return res.status(400).json({ error: "仅支持A股（6位数字代码）" });
    }

    if (cache[code] && Date.now() - cache[code].time < CACHE_TIME) {
        console.log(`✅ 缓存命中: ${code}`);
        return res.json(cache[code].data);
    }

    try {
        console.log(`📊 获取股票数据: ${code}`);
        
        const response = await axios.get(`${PYTHON_SERVICE_URL}/api/stock/history`, {
            params: { code: code, days: 365 },
            timeout: 15000
        });
        
        if (response.data.error) {
            throw new Error(response.data.error);
        }
        
        const data = response.data;
        const indicators = data.indicators;
        
        const dayAvg = indicators.ma30 || 0;
        const monthAvg = indicators.ma60 || 0;
        const yearAvg = indicators.ma250 || 0;
        const totalAvg = (dayAvg + monthAvg + yearAvg) / 3;
        
        const result = {
            code: code,
            name: data.name,
            price: data.price,
            dayAvg: dayAvg,
            monthAvg: monthAvg,
            yearAvg: yearAvg,
            totalAvg: totalAvg,
            high: indicators.high,
            low: indicators.low,
            years: (data.data_count / 250).toFixed(1),
            ma5: indicators.ma5,
            ma10: indicators.ma10,
            ma20: indicators.ma20
        };
        
        cache[code] = {
            time: Date.now(),
            data: result
        };
        
        console.log(`✅ 成功获取: ${code} - ${data.name}`);
        res.json(result);
        
    } catch (e) {
        console.error(`❌ 获取失败 ${code}:`, e.message);
        res.status(500).json({ 
            error: "获取失败", 
            message: e.message,
            code: code
        });
    }
});

app.post("/api/stock/clear", (req, res) => {
    Object.keys(cache).forEach(key => delete cache[key]);
    res.json({ message: "缓存已清除" });
});

app.get("/api/health", async (req, res) => {
    try {
        const pythonHealth = await axios.get(`${PYTHON_SERVICE_URL}/api/health`, { timeout: 5000 });
        res.json({
            status: "ok",
            node: "running",
            python: pythonHealth.data
        });
    } catch (error) {
        res.json({
            status: "degraded",
            node: "running",
            python: "disconnected"
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
    console.log("=".repeat(60) + "\n");
});