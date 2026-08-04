"""AkShare 生意社现货价格采集器 — 核心数据源

使用 ak.futures_spot_price() 从生意社(100ppi.com)获取每日现货价格，
自动查找最近交易日，并计算月前（~30天）对比。
"""

from datetime import date, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger

from src.collectors.base import AbstractCollector, MaterialDataPoint, SourceStatus
from src.config.settings import get_collectors_registry, get_anchors
from src.utils.retry import with_retry


class AkShareSpotCollector(AbstractCollector):
    """通过 AkShare futures_spot_price 接口获取生意社每日现货价格"""

    source_name = "akshare_100ppi"

    # 品种代码 → 中文简称映射
    CODE_NAME_MAP = {
        "RB": "螺纹钢", "HC": "热轧卷板", "WR": "线材", "SS": "不锈钢",
        "FB": "纤维板", "BB": "胶合板",
        "PP": "聚丙烯", "L": "聚乙烯", "V": "聚氯乙烯",
        "TA": "PTA", "PF": "短纤", "CF": "棉花", "CY": "棉纱",
        "SP": "纸浆", "RU": "天然橡胶", "FG": "玻璃",
    }

    def __init__(self):
        self.registry = get_collectors_registry()
        self.anchors = {a["material"]: a for a in get_anchors()}

    def collect(self) -> list[MaterialDataPoint]:
        """采集全部品种的现货价格和月前对比"""
        # 确定哪些品种需要从 API 获取
        akshare_codes = []
        for item in self.registry:
            ptype = item.get("primary", {}).get("type", "")
            if ptype == "akshare_futures":
                akshare_codes.append(item["primary"]["code"])

        if not akshare_codes:
            logger.warning("[采集] 没有 ak share_futures 类型的采集项")
            return self._all_anchor()

        # 获取当前数据
        cur_date, df_cur = self._fetch_nearest_data(akshare_codes, date.today())
        if df_cur is None:
            logger.error("[采集] 无法获取当前数据，全部使用锚点")
            return self._all_anchor()

        # 获取月前数据
        m_date, df_m = self._fetch_nearest_data(akshare_codes, date.today() - timedelta(days=30))

        # 解析数据点
        results = []
        for item in self.registry:
            material_name = item["material"]
            primary = item.get("primary", {})

            if primary.get("type") == "anchor":
                logger.info(f"[采集] {material_name} → 锚点")
                results.append(self._fallback_to_anchor(material_name, "锚点模式"))
                continue

            if primary.get("type") != "akshare_futures":
                results.append(self._fallback_to_anchor(material_name, "未知采集类型"))
                continue

            code = primary["code"]
            row_cur = df_cur[df_cur["symbol"] == code]
            if row_cur.empty:
                logger.warning(f"[采集] {material_name}({code}) 当前无数据，使用锚点")
                results.append(self._fallback_to_anchor(material_name, f"{code}无数据"))
                continue

            r = row_cur.iloc[0]
            cur_price = float(r["spot_price"])

            # 月前对比
            prev_price = None
            change_pct = None
            if df_m is not None:
                row_m = df_m[df_m["symbol"] == code]
                if not row_m.empty:
                    prev_price = float(row_m.iloc[0]["spot_price"])
                    if prev_price != 0:
                        change_pct = round((cur_price - prev_price) / prev_price * 100, 2)

            results.append(MaterialDataPoint(
                material_name=material_name,
                symbol=code,
                price=cur_price,
                price_unit="元/吨",
                price_date=cur_date,
                prev_price=prev_price,
                change_pct=change_pct,
                source=self.source_name,
                status=SourceStatus.SUCCESS,
            ))
            logger.info(
                f"[采集] {material_name}({code}) 现货={cur_price:,.0f}"
                + (f" 月变化={change_pct:+.2f}%" if change_pct is not None else "")
            )

        return results

    def _fetch_nearest_data(self, codes: list[str],
                            base_date: date, max_lookback: int = 10
                            ) -> tuple[Optional[date], Optional[pd.DataFrame]]:
        """向前查找最近交易日的数据"""
        for i in range(max_lookback):
            d = base_date - timedelta(days=i)
            try:
                df = ak.futures_spot_price(date=d.strftime("%Y%m%d"), vars_list=codes)
                if df is not None and len(df) > 0:
                    return d, df
            except Exception:
                continue
        return None, None

    def _all_anchor(self) -> list[MaterialDataPoint]:
        """全部使用锚点价格"""
        results = []
        for item in self.registry:
            results.append(self._fallback_to_anchor(item["material"], "全局降级"))
        return results

    def _fallback_to_anchor(self, material_name: str, reason: str) -> MaterialDataPoint:
        """降级到人工价格锚点"""
        anchor = self.anchors.get(material_name)
        if anchor:
            logger.info(f"[降级] {material_name} → 锚点 ({reason})")
            return MaterialDataPoint(
                material_name=material_name,
                symbol="ANCHOR",
                price=anchor["anchor_price"],
                price_unit=anchor.get("unit", "元/吨"),
                price_date=date.today(),
                prev_price=None,
                change_pct=None,
                source="price_anchor",
                status=SourceStatus.FALLBACK_ANCHOR,
            )
        else:
            logger.error(f"[降级] {material_name} 无锚点可用")
            return MaterialDataPoint(
                material_name=material_name,
                symbol="FAILED",
                price=0.0,
                price_unit="元/吨",
                price_date=date.today(),
                source="failed",
                status=SourceStatus.FAILED,
            )
