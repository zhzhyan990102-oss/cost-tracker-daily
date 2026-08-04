"""指数退避重试装饰器 + 通用重试工具"""

import time
import functools
from loguru import logger


def with_retry(max_attempts: int = 3, base_delay: float = 2.0,
               backoff_factor: float = 2.0, exceptions: tuple = (Exception,)):
    """指数退避重试装饰器

    Args:
        max_attempts: 最大尝试次数（含首次）
        base_delay: 基础等待秒数
        backoff_factor: 退避因子（延迟 = base_delay * factor^(attempt-1)）
        exceptions: 需要捕获重试的异常类型

    重试模式：第1次失败等2秒 → 第2次失败等4秒 → 第3次失败抛出
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            f"[重试] {func.__name__} 第{attempt}次失败: {e}, "
                            f"{delay:.1f}秒后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[重试耗尽] {func.__name__} 已达最大重试次数{max_attempts}: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


def safe_call(func, default=None, **kwargs):
    """安全调用函数，发生异常时返回默认值"""
    try:
        return func(**kwargs)
    except Exception as e:
        logger.error(f"[安全调用失败] {func.__name__}: {e}")
        return default
