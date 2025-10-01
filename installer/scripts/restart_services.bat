@echo off
REM Restart all Futures Trading Log services
echo Restarting Futures Trading Log services...
echo.

echo Stopping services...
call stop_services.bat

echo.
echo Waiting 5 seconds...
timeout /t 5 /nobreak >nul

echo.
echo Starting services...
call start_services.bat
