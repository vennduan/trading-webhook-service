@echo off
:: Trading Webhook Service 启动脚本
:: 用法: run.bat
:: 前提: 设置 FXCM_USERNAME, FXCM_PASSWORD, WEBHOOK_TOKEN 环境变量

echo ========================================
echo  Trading Webhook Service
echo ========================================
echo.

:: 检查环境变量
if "%FXCM_USERNAME%"=="" (
    echo [ERROR] FXCM_USERNAME is not set
    echo Set it before starting: set FXCM_USERNAME=your_username
    exit /b 1
)

if "%FXCM_PASSWORD%"=="" (
    echo [ERROR] FXCM_PASSWORD is not set
    echo Set it before starting: set FXCM_PASSWORD=your_password
    exit /b 1
)

if "%WEBHOOK_TOKEN%"=="" (
    echo [ERROR] WEBHOOK_TOKEN is not set
    echo Set it before starting: set WEBHOOK_TOKEN=your_token
    exit /b 1
)

echo [*] FXCM Username: %FXCM_USERNAME%
echo [*] Connection  : Demo
echo [*] Port        : 5000
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
