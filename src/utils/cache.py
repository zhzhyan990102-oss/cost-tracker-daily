"""简易 JSON 文件缓存 - 用于跨日数据对比和趋势计算"""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from loguru import logger

from src.config.settings import CACHE_DIR


def _cache_path(cache_date: date) -> Path:
    """获取指定日期的缓存文件路径"""
    return CACHE_DIR / f"{cache_date.isoformat()}.json"


def save_cache(data: list[dict], cache_date: date = None):
    """保存当日数据到缓存文件

    Args:
        data: DataPoint 字典列表
        cache_date: 缓存日期，默认为今天
    """
    if cache_date is None:
        cache_date = date.today()
    filepath = _cache_path(cache_date)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"[缓存] 已保存 {len(data)} 条数据到 {filepath.name}")


def load_cache(cache_date: date) -> list[dict]:
    """加载指定日期的缓存数据"""
    filepath = _cache_path(cache_date)
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history(days: int = 30) -> dict[str, list[dict]]:
    """加载最近 N 天的历史缓存数据

    Returns:
        { "2026-07-30": [...], "2026-07-29": [...], ... }
    """
    result = {}
    for i in range(1, days + 1):
        d = date.today() - timedelta(days=i)
        data = load_cache(d)
        if data:
            result[d.isoformat()] = data
    return result


def cleanup_cache(keep_days: int = 35):
    """清理超过保留天数的缓存文件"""
    cutoff = date.today() - timedelta(days=keep_days)
    for f in CACHE_DIR.glob("*.json"):
        try:
            file_date = date.fromisoformat(f.stem)
            if file_date < cutoff:
                f.unlink()
                logger.debug(f"[缓存清理] 已删除 {f.name}")
        except (ValueError, OSError):
            pass
