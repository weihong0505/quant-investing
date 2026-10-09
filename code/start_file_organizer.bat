@echo off
chcp 65001 >nul
rem ========================================
rem  文件整理守护进程 - 开机自启
rem ========================================
title File Organizer Daemon
cd /d "G:\股市探究\quant-investing\code"
set PYTHONIOENCODING=utf-8
"D:\pyh\python.exe" -E "G:\股市探究\quant-investing\code\file_organizer_watch.py"
