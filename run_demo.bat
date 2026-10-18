@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 analyze_orders.py sample_orders.csv --out my_report --demo
) else (
  python analyze_orders.py sample_orders.csv --out my_report --demo
)
if errorlevel 1 (
  echo Failed. Check Python installation and README.md.
  pause
  exit /b 1
)
echo.
echo Opening your updated HTML sales dashboard...
start "" "%~dp0my_report\dashboard.html"
pause
