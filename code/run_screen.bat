@echo off
chcp 65001 >nul
title 价值投资初筛 (1万元)
echo ============================================
echo   价值投资初筛管线 v1.0
echo   (演示级, 非投资建议)
echo ============================================
echo.

cd /d "G:\股市探究\quant-investing\code"

"D:\pyh\python.exe" -X utf8 -E "G:\股市探究\quant-investing\code\run_screen.py" %*

echo.
echo ============================================
echo   完成! 候选清单在 code\output\ 目录
echo ============================================
pause
