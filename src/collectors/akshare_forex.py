"""AkShare 汇率采集器 — USD/CNY 及主要货币对"""

import math
from datetime import date

import akshare as ak
import pandas as pd
from loguru import logger

from src.collectors.base import AbstractCollector, ForexDataPoint, MaterialDataPoint

# USD/CNH 合理波动区间（防止API返回异常数据）
USDCNY_MIN = 6.50
USDCNY_MAX = 8.50


def _is_valid_rate(rate: float) -> bool:
    """校验汇率是否在合理范围内"""
    if rate is None or math.isnan(rate) or math.isinf(rate):
        return False
    return USDCNY_MIN <= rate <= USDCNY_MAX


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
        # 方案1：外汇即期实时报价
        try:
            df = ak.forex_spot_em()
            if df is not None and not df.empty:
                row = df[df["名称"].str.contains("美元/离岸人民币", na=False)]
                if row.empty:
                    row = df[df["名称"].str.contains("美元人民币", na=False)]
                if not row.empty:
                    rate = float(row.iloc[0]["最新价"])
                    if _is_valid_rate(rate):
                        logger.info(f"[USDCNY] 即期报价: {rate:.4f}")
                        return ForexDataPoint(
                            currency_pair="USD/CNH",
                            rate=rate,
                            rate_date=date.today(),
                        )
                    else:
                        logger.warning(f"[USDCNY] 即期报价异常({rate:.4f})，不在合理区间[{USDCNY_MIN}-{USDCNY_MAX}]，尝试备用方案")
        except Exception as e:
            logger.warning(f"[USDCNY] 外汇即期接口失败: {e}，尝试历史接口")

        # 方案2：历史数据取最新一条
        try:
            df = ak.forex_hist_em(symbol="USDCNH")
            if df is not None and not df.empty:
                # 从后往前找第一条有效汇率
                for i in range(len(df) - 1, max(len(df) - 10, -1), -1):
                    row = df.iloc[i]
                    raw_rate = row["最新价"] if "最新价" in df.columns else row.iloc[-1]
                    rate = float(raw_rate)
                    if _is_valid_rate(rate):
                        prev_rate = None
                        change_pct = None
                        if i >= 1:
                            prev_raw = df.iloc[i - 1]["最新价"] if "最新价" in df.columns else df.iloc[i - 1, -1]
                            prev_rate = float(prev_raw)
                            if _is_valid_rate(prev_rate) and prev_rate != 0:
                                change_pct = round((rate - prev_rate) / prev_rate * 100, 4)

                        logger.info(f"[USDCNY] 历史数据: {rate:.4f} (日变动{change_pct or 0:.4f}%)")
                        return ForexDataPoint(
                            currency_pair="USD/CNH",
                            rate=rate,
                            rate_date=date.today(),
                            prev_rate=prev_rate,
                            change_pct=change_pct,
                        )

                logger.warning(f"[USDCNY] 近10条历史数据均不在合理区间，全部丢弃")
        except Exception as e:
            logger.error(f"[USDCNY] 历史接口也失败: {e}")

        # 方案3：返回标记值，由上层决定是否跳过展示
        logger.warning("[USDCNY] 所有汇率方案均失败，返回兜底标记值")
        return ForexDataPoint(
            currency_pair="USD/CNH",
            rate=7.25,  # 兜底值 — 上层通过 rate==7.25 判断有效性
            rate_date=date.today(),
        )

    def get_all_forex(self) -> dict[str, ForexDataPoint]:
        """获取所有相关货币对汇率"""
        return {
            "USD/CNH": self.get_usdcny(),
        }
