# -*- coding: utf-8 -*-
"""
文件整理守护进程 — 持续监听 _inbox 目录，新文件出现自动归类
============================================================
- 监听 G:\股市探究\quant-investing\_inbox\ 目录
- 新文件放入后自动按规范归类（无需人工指令）
- 同时每 30 分钟扫描一次库根散落文件

用法：
  D:/pyh/python.exe -E G:/股市探究/quant-investing/code/file_organizer_watch.py
"""
import os
import sys
import io
import time
import threading
import datetime
import subprocess

# 修复 Windows GBK 控制台编码
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = r'G:\股市探究\quant-investing'
INBOX = os.path.join(ROOT, '_inbox')          # 用户放入的文件
HERMES_OUT = os.path.join(ROOT, '_hermes_out')  # Hermes 产出的文件
ORGANIZER = os.path.join(ROOT, 'code', 'file_organizer.py')
PYTHON = r'D:\pyh\python.exe'

SCAN_INTERVAL = 1800  # 30分钟扫描一次
INBOX_CHECK_INTERVAL = 5  # 5秒检查一次


def run_organizer(dry_run=False):
    """调用整理脚本"""
    cmd = [PYTHON, '-E', ORGANIZER]
    if dry_run:
        cmd.append('--dry-run')
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           encoding='utf-8', errors='ignore')
        return r.stdout
    except Exception as e:
        return f'整理脚本执行失败: {e}'


def watch_dirs():
    """持续监听 inbox + hermes_out：有文件就调用整理器"""
    while True:
        try:
            for watch_dir, tag in ((INBOX, '用户'), (HERMES_OUT, 'Hermes')):
                if os.path.isdir(watch_dir):
                    files = [f for f in os.listdir(watch_dir)
                             if os.path.isfile(os.path.join(watch_dir, f)) and not f.startswith('.')]
                    if files:
                        print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
                              f'📥 发现 {len(files)} 个文件({tag}目录)，调用整理器...')
                        output = run_organizer()
                        print(output[-800:] if output else '')
        except Exception as e:
            print(f'监听异常: {e}')
        time.sleep(INBOX_CHECK_INTERVAL)


def periodic_scan():
    """定期扫描根目录"""
    while True:
        time.sleep(SCAN_INTERVAL)
        print(f'[{datetime.datetime.now().strftime("%H:%M:%S")}] '
              f'⏰ 定时扫描根目录散落文件...')
        output = run_organizer()
        if output:
            print(output[-500:] if output else '')


if __name__ == '__main__':
    print('=' * 60)
    print('  文件整理守护进程')
    print(f'  监听: _inbox/ (用户) + _hermes_out/ (Hermes)')
    print(f'  扫描间隔: 每30分钟 / inbox 5秒')
    print('  按 Ctrl+C 停止')
    print('=' * 60)

    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(HERMES_OUT, exist_ok=True)

    t1 = threading.Thread(target=watch_dirs, daemon=True)
    t2 = threading.Thread(target=periodic_scan, daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n停止文件整理守护进程')
