@echo off
REM Stop all Futures Trading Log services
echo Stopping Futures Trading Log services...
echo.

echo Stopping Web service...
net stop FuturesTradingLog-Web
if %errorlevel% neq 0 (
    echo Failed to stop Web service
)

echo Stopping Redis service...
net stop FuturesTradingLog-Redis
if %errorlevel% neq 0 (
    echo Failed to stop Redis service
)

echo.
echo All services stopped
echo.
pause
