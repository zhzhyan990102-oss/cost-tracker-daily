"""跨境情报聚合器 — 按国际形势研判格式组织

数据驱动项（自动采集）：
  汇率变化、BDI运价、原油价格（可选）
人工研判项（需定期维护）：
  地缘政治、贸易政策、行业动态
"""

import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Union

import akshare as ak
import pandas as pd
from loguru import logger

from src.collectors.base import ForexDataPoint, MacroDataPoint

# 原油 API 超时（秒）— ak.futures_global_spot_em() 在网络受限时可能耗时 60s+
_OIL_API_TIMEOUT = 20


def _is_valid_number(val) -> bool:
    """检查值是否为有效数值（非 None、非 NaN、非 Inf）"""
    if val is None:
        return False
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return False
        return True
    except (ValueError, TypeError):
        return False


def _safe_float(val, default=0.0) -> float:
    """安全转换为 float，异常时返回默认值"""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


# USD/CNH 合理区间
_USDCNY_MIN = 6.50
_USDCNY_MAX = 8.50
# BDI 合理区间（历史极低约 290，正常 1000-12000）
_BDI_MIN = 100


@dataclass
class IntelligenceItem:
    """单条情报 — 按研判格式组织"""
    category: str              # 能源/运价/汇率/政策/行业
    title: str
    summary: str
    source_url: Optional[str] = None
    severity: str = "info"     # info / warning / alert


@dataclass
class IntelligenceReport:
    """情报汇总"""
    date: date
    items: list[IntelligenceItem] = field(default_factory=list)
    forex: Optional[ForexDataPoint] = None
    ppi: Optional[MacroDataPoint] = None
    cpi: Optional[MacroDataPoint] = None


class IntelligenceCompiler:
    """聚合多渠道情报，生成 🌍 国际形势与趋势研判 板块

    核心原则：
    1. 只展示成功获取且数值合理的指标，不展示报错信息
    2. 原油为可选指标（API受限频繁），静默跳过
    3. 所有数值格式化前必须通过 _is_valid_number 校验
    """

    def compile(self, forex: ForexDataPoint,
                ppi: MacroDataPoint,
                cpi: MacroDataPoint) -> IntelligenceReport:
        """编译情报汇总"""
        items: list[IntelligenceItem] = []

        # ① 能源价格（原油）— 可选，失败静默跳过
        oil = self._compile_oil()
        if oil is not None:
            items.append(oil)

        # ② 汇率走势 — 有效数据才展示
        forex_item = self._compile_forex(forex)
        if forex_item is not None:
            items.append(forex_item)

        # ③ 海运运价（BDI）
        freight = self._compile_freight()
        if freight is not None:
            items.append(freight)

        # ④ 宏观政策
        macro = self._compile_macro(ppi, cpi)
        if macro is not None:
            items.append(macro)

        # ⑤ 贸易政策（预留人工维护接口）
        items.extend(self._compile_policy_snapshot())

        # 按严重性排序
        severity_order = {"alert": 0, "warning": 1, "info": 2}
        items.sort(key=lambda x: severity_order.get(x.severity, 2))

        return IntelligenceReport(
            date=date.today(),
            items=items[:8],
            forex=forex,
            ppi=ppi,
            cpi=cpi,
        )

    # ====== ① 能源价格（可选） ======

    def _compile_oil(self) -> Optional[IntelligenceItem]:
        """获取国际原油价格 — 失败时静默返回 None，不在报告中展示报错"""
        try:
            # 用线程超时保护，避免 API 调用阻塞过长时间
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(ak.futures_global_spot_em)
                df = future.result(timeout=_OIL_API_TIMEOUT)

            if df is not None and not df.empty:
                name_col = next((c for c in df.columns
                                if "名称" in str(c) or "name" in str(c).lower()), df.columns[0])
                wti = df[df[name_col].str.contains("WTI|美原油", na=False, case=False)]
                if wti.empty:
                    wti = df[df[name_col].str.contains("原油", na=False)]
                if not wti.empty:
                    row = wti.iloc[0]
                    price = _safe_float(row.get("最新价", row.iloc[2]) if "最新价" in df.columns else _safe_float(row.iloc[2]))
                    change_pct = _safe_float(row.get("涨跌幅", 0.0) if "涨跌幅" in df.columns else 0.0)

                    if price > 0:
                        direction = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
                        impact = ("油价上行将推高塑料(PP/PE/PVC)、化纤(涤纶)等石化原料成本"
                                  if change_pct > 0 else "油价下行利好石化原料采购成本")
                        return IntelligenceItem(
                            category="能源",
                            title=f"① WTI原油 {price:.2f}美元/桶 {direction}{abs(change_pct):.2f}%",
                            summary=f"WTI原油报{price:.2f}美元/桶，较前日{direction}{abs(change_pct):.2f}%。{impact}",
                            severity="warning" if abs(change_pct) > 3 else "info",
                        )
        except (FuturesTimeoutError, TimeoutError):
            logger.warning(f"[情报] 国际原油API超时(>{_OIL_API_TIMEOUT}s)，静默跳过")
        except Exception as e:
            logger.warning(f"[情报] 国际原油数据获取失败: {e}")

        # 备用：国内原油期货
        try:
            df = ak.futures_spot_price(
                date=date.today().strftime("%Y%m%d"),
                vars_list=["SC"]
            )
            if df is not None and not df.empty:
                row = df.iloc[0]
                price = _safe_float(row.get("spot_price", 0))
                if price > 0:
                    return IntelligenceItem(
                        category="能源",
                        title=f"① 上海原油 {price:.0f}元/桶",
                        summary=f"上海INE原油期货现货参考价{price:.0f}元/桶。"
                                f"原油为塑料(PP/PE/PVC)、化纤(涤纶)上游原料，价格波动将逐步传导至家居原材料成本。",
                        severity="info",
                    )
        except Exception as e:
            logger.warning(f"[情报] 国内原油数据也失败: {e}")

        # 两项都失败：静默跳过，不展示
        logger.info("[情报] 原油数据全部不可用，已跳过（不影响其他指标）")
        return None

    # ====== ② 汇率走势 ======

    def _compile_forex(self, forex: ForexDataPoint) -> Optional[IntelligenceItem]:
        """编译汇率研判 — 仅当数据有效时返回"""
        if not _is_valid_number(forex.rate):
            logger.warning("[情报] 汇率数据无效，跳过")
            return None

        rate = float(forex.rate)

        # 兜底值（恰好为 7.25 且无变动数据 = 采集失败）
        if rate == 7.25 and forex.change_pct is None:
            logger.info("[情报] 汇率数据为兜底值，跳过展示")
            return None

        # 范围校验
        if rate < _USDCNY_MIN or rate > _USDCNY_MAX:
            logger.warning(f"[情报] 汇率{rate:.4f}超出合理区间[{_USDCNY_MIN}-{_USDCNY_MAX}]，跳过")
            return None

        change_pct = _safe_float(forex.change_pct) if forex.change_pct is not None else 0.0
        direction = "贬值" if change_pct > 0 else "升值" if change_pct < 0 else "持平"
        abs_pct = abs(change_pct)

        impact = (
            "人民币贬值利好出口，提高跨境产品价格竞争力"
            if direction == "贬值"
            else "人民币升值利好进口采购，降低海外原材料成本"
            if direction == "升值"
            else "人民币汇率基本持平，对跨境成本影响中性"
        )

        return IntelligenceItem(
            category="汇率",
            title=f"② USD/CNH {rate:.4f}（日{direction}{abs_pct:.2f}%）" if abs_pct > 0.001
            else f"② USD/CNH {rate:.4f}（日变动<0.01%）",
            summary=f"离岸人民币兑美元报{rate:.4f}。{impact}。"
                    f"关注汇率对越南、柬埔寨、马来西亚等产地的人民币计价成本影响。",
            severity="warning" if abs_pct > 1 else "info",
        )

    # ====== ③ 海运运价 ======

    def _compile_freight(self) -> Optional[IntelligenceItem]:
        """获取 BDI 波罗的海干散货指数"""
        try:
            df = ak.spot_goods(symbol="波罗的海干散货指数")
            if df is not None and not df.empty:
                latest = df.iloc[-1]

                # 用列名定位（避免 iloc[-1] 取到涨跌幅列）
                price = None
                for col_name in ["价格", "指数", "value", "price"]:
                    for c in df.columns:
                        if col_name in str(c):
                            price = _safe_float(latest[c])
                            break
                    if price and price > _BDI_MIN:
                        break

                # 列名匹配失败，尝试按位置取第一个数值>100的列
                if not price or price <= _BDI_MIN:
                    for c in df.columns:
                        val = _safe_float(latest[c])
                        if val > _BDI_MIN:
                            price = val
                            break

                if not price or price <= _BDI_MIN:
                    logger.warning(f"[情报] BDI 值异常({price})，跳过")
                    return None

                # 日期
                date_val = str(latest.iloc[0])[:10]

                # 月变化（约22个交易日）
                change_str = ""
                change_num = 0.0
                if len(df) >= 22:
                    prev_row = df.iloc[-22]
                    for c in df.columns:
                        prev_price = _safe_float(prev_row[c])
                        if prev_price > _BDI_MIN:
                            change_num = (price - prev_price) / prev_price * 100
                            direction = "↑" if change_num > 0 else "↓" if change_num < 0 else ""
                            change_str = f" {direction}{abs(change_num):.1f}%"
                            break

                summary = f"BDI报{price:.0f}点{change_str}。"
                if change_str:
                    if "↓" in change_str:
                        summary += "海运成本下行利好跨境物流。"
                    elif "↑" in change_str:
                        summary += "海运成本上行，关注对越南、柬埔寨、马来西亚等产地的物流成本影响。"

                return IntelligenceItem(
                    category="运价",
                    title=f"③ BDI波罗的海干散货指数 {price:.0f}点{change_str}",
                    summary=summary,
                    severity="warning" if change_str and "↑" in change_str and change_num > 10 else "info",
                )
        except Exception as e:
            logger.warning(f"[情报] BDI数据获取失败: {e}")

        return None

    # ====== ④ 宏观政策 ======

    def _compile_macro(self, ppi: MacroDataPoint, cpi: MacroDataPoint) -> Optional[IntelligenceItem]:
        """编译宏观政策摘要 — 仅当数据有效"""
        parts = []

        if ppi and _is_valid_number(ppi.value) and ppi.value != 0.0 and ppi.period:
            if ppi.period[:4] in ("2025", "2026"):
                parts.append(f"PPI同比{ppi.value:+.1f}%")

        if cpi and _is_valid_number(cpi.value) and cpi.value != 0.0 and cpi.period:
            if cpi.period[:4] in ("2025", "2026"):
                parts.append(f"CPI同比{cpi.value:+.1f}%")

        if parts:
            detail = "、".join(parts)
            direction = "上行通道" if (ppi and ppi.value > 0) else "下行通道"
            return IntelligenceItem(
                category="宏观",
                title=f"④ 宏观指标：{detail}",
                summary=f"{detail}，原材料价格整体处于{direction}。"
                        f"关注国内制造业PMI及房地产政策对家具需求端的影响。",
                severity="info",
            )
        return None

    # ====== ⑤ 贸易政策（人工维护） ======

    def _compile_policy_snapshot(self) -> list[IntelligenceItem]:
        """贸易政策快照 — 需定期维护

        此方法返回手动维护的政策/行业动态条目。
        修改 src/config/policy_snapshot.yaml 即可更新内容。

        格式：
        - title: ⑤ 美对华家具关税复审启动
          summary: USTR启动301关税四年复审，涉及木质家具、床垫等品类...
          severity: warning
        """
        try:
            import yaml
            from pathlib import Path
            config_path = Path(__file__).parent.parent / "config" / "policy_snapshot.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                policies = data.get("policies") or []
                items = []
                for entry in policies:
                    items.append(IntelligenceItem(
                        category="政策",
                        title=entry.get("title", ""),
                        summary=entry.get("summary", ""),
                        source_url=entry.get("source_url"),
                        severity=entry.get("severity", "info"),
                    ))
                return items
        except Exception as e:
            logger.warning(f"[情报] 政策快照读取失败: {e}")
        return []
