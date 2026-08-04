"""采集器抽象基类 + 统一数据模型"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class SourceStatus(Enum):
    """数据获取状态"""
    SUCCESS = "success"           # 正常获取
    STALE = "stale"               # 数据未更新（非交易日，使用最近数据）
    FALLBACK_ANCHOR = "anchor"    # 降级使用人工锚点
    FAILED = "failed"             # 采集完全失败


@dataclass
class MaterialDataPoint:
    """单一原材料在一个日期的数据点"""
    material_name: str                       # 原材料名称 e.g. "冷轧板卷"
    symbol: str                              # AkShare symbol
    price: float                             # 当日价格（已标准化单位）
    price_unit: str                          # 单位 e.g. "元/吨"
    price_date: date                         # 价格日期
    prev_price: Optional[float] = None       # 前一交易日价格
    change_pct: Optional[float] = None       # 环比变幅 (%)
    source: str = ""                         # 数据来源标识
    status: SourceStatus = SourceStatus.SUCCESS


@dataclass
class ForexDataPoint:
    """汇率数据点"""
    currency_pair: str                       # e.g. "USD/CNY"
    rate: float
    rate_date: date
    prev_rate: Optional[float] = None
    change_pct: Optional[float] = None


@dataclass
class MacroDataPoint:
    """宏观指标数据点"""
    indicator_name: str                      # e.g. "PPI", "CPI"
    value: float
    period: str                              # e.g. "2026-06"
    yoy_change: Optional[float] = None       # 同比增长率


class AbstractCollector(ABC):
    """所有采集器的抽象基类"""

    @abstractmethod
    def collect(self) -> list[MaterialDataPoint]:
        """执行采集，返回标准化数据点列表"""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源标识名"""
        ...

    def health_check(self) -> bool:
        """数据源连通性检测（可选覆盖）"""
        return True
