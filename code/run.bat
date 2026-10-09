@echo off
chcp 65001 >nul
title Quant Value Stock System
echo ========================================
echo   A-Share Multi-Factor Value System
echo ========================================
echo.

cd /d "G:\股市探究\quant-investing\code"

"D:\pyh\python.exe" -E "G:\股市探究\quant-investing\code\run.py"

echo.
echo ========================================
echo   Done! Results saved to output/
echo ========================================
pause
