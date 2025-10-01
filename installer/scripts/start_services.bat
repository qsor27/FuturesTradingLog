@echo off
REM Start all Futures Trading Log services
echo Starting Futures Trading Log services...
echo.

echo Starting Redis service...
net start FuturesTradingLog-Redis
if %errorlevel% neq 0 (
    echo Failed to start Redis service
    pause
    exit /b 1
)

echo Starting Web service...
net start FuturesTradingLog-Web
if %errorlevel% neq 0 (
    echo Failed to start Web service
    pause
    exit /b 1
)

echo.
echo All services started successfully!
echo You can now access the application at: http://localhost:5000
echo.
pause
