@echo off
:: Trading Webhook Service 启动脚本
:: 用法: run.bat
:: 环境变量直接写在这里，确保任何方式启动都能读到

set FXCM_USERNAME=D103538839
set FXCM_PASSWORD=Rlit6
set FXCM_CONNECTION=Demo
set FXCM_URL=www.fxcorporate.com/Hosts.jsp
set WEBHOOK_TOKEN=fdadfb2d9e06a3b856b2252e1dd74d0367d4da1a396bb5db900ed8935386b1f5

echo ========================================
echo  Trading Webhook Service
echo ========================================
echo.
echo [*] FXCM Username: %FXCM_USERNAME%
echo [*] Connection  : %FXCM_CONNECTION%
echo [*] Port        : 80
echo [*] Log dir     : logs\
echo.
echo Starting server...
echo.

:: 启动 Flask
python webhook_server.py

:: 如果出错，保留窗口
if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with code %errorlevel%
    pause
)
