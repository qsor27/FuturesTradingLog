@echo off
REM Check status of Futures Trading Log services
echo Checking Futures Trading Log services status...
echo.

echo === Redis Service ===
sc query FuturesTradingLog-Redis
echo.

echo === Web Service ===
sc query FuturesTradingLog-Web
echo.

echo === Checking if application is responding ===
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:5000/health
echo.

pause
