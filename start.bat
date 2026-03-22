@echo off
chcp 65001 >nul
echo ========================================
echo 启动股票分析系统
echo ========================================
echo.

echo [1/3] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ 未找到Python，请安装Python 3.7+
    pause
    exit /b 1
)
echo ✓ Python环境正常

echo [2/3] 启动Python数据服务...
start "Python数据服务" cmd /k "python data_service.py"

timeout /t 3 /nobreak >nul

echo [3/3] 启动Node.js前端服务器...
start "Node.js前端" cmd /k "node server.js"

echo.
echo 服务启动中，请稍候...
timeout /t 5 /nobreak >nul

echo 打开浏览器访问: http://localhost:3000
start http://localhost:3000

echo.
echo 数据存储位置:
echo   - 历史数据: D:\zhouyu\word\gupiao\deepseek_gupiao\gpData
echo   - 本地数据: D:\zhouyu\word\gupiao\deepseek_gupiao\gpLSData
echo.
echo 按任意键退出...
pause >nul