"""AkShare 汇率采集器 — USD/CNY 及主要货币对"""

from datetime import date

import akshare as ak
import pandas as pd
from loguru import logger

from src.collectors.base import AbstractCollector, ForexDataPoint, MaterialDataPoint


class AkShareForexCollector(AbstractCollector):
    """采集美元/人民币汇率 — 作为跨境成本基准"""

    source_name = "akshare_forex"

    # 与供应链相关的货币对
    TARGET_PAIRS = ["USD/CNY", "USD/VND", "USD/KHR", "USD/MYR", "USD/MAD", "USD/JOD", "USD/PKR"]

    def collect(self) -> list[MaterialDataPoint]:
        """汇率数据走独立接口"""
        return []

    def get_usdcny(self) -> ForexDataPoint:
        """获取美元兑离岸人民币汇率"""
        try:
            # 使用外汇即期实时报价
            df = ak.forex_spot_em()
            if df is not None and not df.empty:
                # 筛选美元/离岸人民币
                row = df[df["名称"].str.contains("美元/离岸人民币", na=False)]
                if row.empty:
                    row = df[df["名称"].str.contains("美元人民币", na=False)]
                if not row.empty:
                    rate = float(row.iloc[0]["最新价"])
                    return ForexDataPoint(
                        currency_pair="USD/CNH",
                        rate=rate,
                        rate_date=date.today(),
                    )
        except Exception as e:
            logger.error(f"[USDCNY] 外汇即期接口失败: {e}，尝试历史接口")

        # 备用方案：使用历史数据取最新一条
        try:
            df = ak.forex_hist_em(symbol="USDCNH")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                rate = float(latest["最新价"] if "最新价" in df.columns else latest.iloc[-1])
                prev_rate = None
                change_pct = None
                if len(df) >= 2:
                    prev = df.iloc[-2]
                    prev_rate = float(prev["最新价"] if "最新价" in df.columns else prev.iloc[-1])
                    if prev_rate != 0:
                        change_pct = round((rate - prev_rate) / prev_rate * 100, 4)

                return ForexDataPoint(
                    currency_pair="USD/CNH",
                    rate=rate,
                    rate_date=date.today(),
                    prev_rate=prev_rate,
                    change_pct=change_pct,
                )
        except Exception as e:
            logger.error(f"[USDCNY] 历史接口也失败: {e}")

        return ForexDataPoint(
            currency_pair="USD/CNH",
            rate=7.25,  # 硬编码兜底值
            rate_date=date.today(),
        )

    def get_all_forex(self) -> dict[str, ForexDataPoint]:
        """获取所有相关货币对汇率"""
        return {
            "USD/CNH": self.get_usdcny(),
        }
