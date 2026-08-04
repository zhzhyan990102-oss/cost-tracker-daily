"""AkShare 宏观指标采集器 — PPI / CPI / 企业商品价格指数"""

from datetime import date

import akshare as ak
from loguru import logger

from src.collectors.base import AbstractCollector, MacroDataPoint, MaterialDataPoint


class AkShareMacroCollector(AbstractCollector):
    """采集国家统计局宏观经济指标（月度更新，作为成本趋势基准）"""

    source_name = "akshare_macro"

    def collect(self) -> list[MaterialDataPoint]:
        """宏观数据不返回 MaterialDataPoint，走独立接口"""
        return []

    def get_ppi(self) -> MacroDataPoint:
        """获取 PPI 当月同比增长（自动过滤年份＜2025的异常数据）"""
        try:
            df = ak.macro_china_ppi()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                period = str(latest.iloc[0])
                value = float(latest.iloc[-1])
                # 过滤异常历史数据
                if period.startswith("2025") or period.startswith("2026"):
                    return MacroDataPoint(
                        indicator_name="PPI",
                        value=value,
                        period=period,
                    )
                else:
                    logger.warning(f"[PPI] 数据日期{period}异常(早于2025)，忽略")
        except Exception as e:
            logger.error(f"[PPI] 采集失败: {e}")
        return MacroDataPoint(indicator_name="PPI", value=0.0, period="")

    def get_cpi(self) -> MacroDataPoint:
        """获取 CPI 当月同比增长（自动过滤年份＜2025的异常数据）"""
        try:
            df = ak.macro_china_cpi()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                period = str(latest.iloc[0])
                value = float(latest.iloc[-1])
                if period.startswith("2025") or period.startswith("2026"):
                    return MacroDataPoint(
                        indicator_name="CPI",
                        value=value,
                        period=period,
                    )
                else:
                    logger.warning(f"[CPI] 数据日期{period}异常(早于2025)，忽略")
        except Exception as e:
            logger.error(f"[CPI] 采集失败: {e}")
        return MacroDataPoint(indicator_name="CPI", value=0.0, period="")

    def get_all(self) -> dict[str, MacroDataPoint]:
        """获取所有宏观指标"""
        return {
            "PPI": self.get_ppi(),
            "CPI": self.get_cpi(),
        }
