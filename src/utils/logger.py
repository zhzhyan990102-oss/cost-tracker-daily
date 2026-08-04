"""结构化日志配置"""

import sys
from loguru import logger


def setup_logger():
    """配置 loguru 日志输出"""
    logger.remove()  # 移除默认 handler

    # 标准输出 - 带颜色
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # 文件输出 - 保留完整信息
    logger.add(
        "cost_tracker.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )

    return logger
