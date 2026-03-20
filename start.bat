@echo off
echo ========================================
echo 启动股票分析系统
echo ========================================
echo.

echo [1/2] 启动Python数据服务...
start "Python数据服务" cmd /k "python data_service.py"

timeout /t 3 /nobreak >nul

echo [2/2] 启动Node.js前端服务器...
start "Node.js前端" cmd /k "node server.js"

echo.
echo 服务启动中，请稍候...
timeout /t 5 /nobreak >nul

echo 打开浏览器访问: http://localhost:3000
start http://localhost:3000

echo.
echo 按任意键退出...
pause >nul