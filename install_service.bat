@echo off
:: NSSM Windows 服务安装脚本
:: 用法:
::   install_service.bat install    - 安装服务
::   install_service.bat uninstall  - 卸载服务
::   install_service.bat start      - 启动服务
::   install_service.bat stop       - 停止服务
::   install_service.bat restart    - 重启服务
::
:: 前置条件: 下载 NSSM (https://nssm.cc/download)
:: 将 nssm.exe 放到本目录或系统 PATH

set SERVICE_NAME=TradingWebhookService
set SERVICE_DISPLAY=TradingView Webhook Service
set EXE_PATH=%~dp0webhook_server.py
set NSSM=nssm

if "%1"=="" (
    echo Usage: install_service.bat [install^|uninstall^|start^|stop^|restart]
    exit /b 1
)

if "%1"=="install" (
    echo Installing %SERVICE_NAME%...
    %NSSM% install %SERVICE_NAME% "%~dp0python.exe" "%EXE_PATH%"
    %NSSM% set %SERVICE_NAME% DisplayName "%SERVICE_DISPLAY%"
    %NSSM% set %SERVICE_NAME% Description "Receives TradingView webhooks and executes FXCM trades"
    %NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START
    %NSSM% set %SERVICE_NAME% AppEnvironment "PYTHONPATH=%~dp0"
    echo NOTE: Set FXCM_USERNAME, FXCM_PASSWORD, WEBHOOK_TOKEN environment variables
    echo       before the service can connect to FXCM.
    echo.
    echo Service installed. Start with: install_service.bat start
    exit /b 0
)

if "%1"=="uninstall" (
    echo Uninstalling %SERVICE_NAME%...
    %NSSM% stop %SERVICE_NAME% 2>nul
    %NSSM% remove %SERVICE_NAME% confirm
    echo Service uninstalled.
    exit /b 0
)

if "%1"=="start" (
    echo Starting %SERVICE_NAME%...
    %NSSM% start %SERVICE_NAME%
    exit /b 0
)

if "%1"=="stop" (
    echo Stopping %SERVICE_NAME%...
    %NSSM% stop %SERVICE_NAME%
    exit /b 0
)

if "%1"=="restart" (
    echo Restarting %SERVICE_NAME%...
    %NSSM% stop %SERVICE_NAME% 2>nul
    timeout /t 2 /nobreak >nul
    %NSSM% start %SERVICE_NAME%
    exit /b 0
)

echo Unknown command: %1
echo Usage: install_service.bat [install^|uninstall^|start^|stop^|restart]
exit /b 1
