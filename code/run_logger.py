# -*- coding: utf-8 -*-
"""
运行日志工具 run_logger.py
==========================
SOP §3.4：每次运行写日志 logs/run_{时间戳}.log（相对 BASE_DIR 的 logs/ 目录，自动创建）。

用法（在 run_full_pipeline / run.py 入口调用）：
    from run_logger import get_run_logger, log_path
    log = get_run_logger()
    log.info('...')
    log.warning('...')
    log.exception('...')   # 在 except 块中输出异常堆栈

日志文件：{BASE_DIR}/logs/run_{YYYYMMDD_HHMMSS}.log
- 同一进程内多次调用返回同一 logger 实例（单例），不会重复建文件/重复挂 handler
- 同时向 root logger 挂一个文件 handler：data_fetcher 等子模块的 logger.info
  （缓存命中/降级/失败详情）也会落入本日志文件

状态标注：S3 验收产物（2026-08-22）——运行日志基础设施，无策略逻辑，无需审批/检验。
"""
import os
import sys
import logging
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

_logger = None
_log_path = None

_FMT = logging.Formatter('[%(asctime)s %(levelname)s] %(message)s', datefmt='%H:%M:%S')


def get_run_logger():
    """返回单例运行日志 logger（首次调用时创建 logs/run_{时间戳}.log）。"""
    global _logger, _log_path
    if _logger is not None:
        return _logger

    os.makedirs(LOGS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    _log_path = os.path.join(LOGS_DIR, f'run_{ts}.log')

    logger = logging.getLogger('run_logger')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    fh = logging.FileHandler(_log_path, encoding='utf-8')
    fh.setFormatter(_FMT)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(_FMT)
    logger.addHandler(sh)

    # root 文件 handler：让 data_fetcher 等子模块的日志也落入本文件（带标记防重复挂载）
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [h for h in root.handlers if not getattr(h, '_run_logger_root', False)]
    rf = logging.FileHandler(_log_path, encoding='utf-8')
    rf.setFormatter(_FMT)
    rf._run_logger_root = True
    root.addHandler(rf)

    _logger = logger
    return logger


def log_path():
    """当前运行的日志文件绝对路径（未初始化时为 None）。"""
    return _log_path
