"""跨境情报聚合器 — 按国际形势研判格式组织

数据驱动项（自动采集）：
  原油价格、BDI运价、汇率变化
人工研判项（需定期维护）：
  地缘政治、贸易政策、行业动态
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger

from src.collectors.base import ForexDataPoint, MacroDataPoint


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
    """聚合多渠道情报，生成 🌍 国际形势与趋势研判 板块"""

    def compile(self, forex: ForexDataPoint,
                ppi: MacroDataPoint,
                cpi: MacroDataPoint) -> IntelligenceReport:
        """编译情报汇总"""
        items: list[IntelligenceItem] = []

        # ① 能源价格（原油）
        items.append(self._compile_oil())

        # ② 汇率走势
        if forex.rate != 7.25:
            items.append(self._compile_forex(forex))

        # ③ 海运运价（BDI）
        items.append(self._compile_freight())

        # ④ 宏观政策
        items.append(self._compile_macro(ppi, cpi))

        # ⑤ 贸易政策（预留人工维护接口）
        items.extend(self._compile_policy_snapshot())

        # 过滤空项，按严重性排序
        items = [i for i in items if i is not None]
        severity_order = {"alert": 0, "warning": 1, "info": 2}
        items.sort(key=lambda x: severity_order.get(x.severity, 2))

        return IntelligenceReport(
            date=date.today(),
            items=items[:8],
            forex=forex,
            ppi=ppi,
            cpi=cpi,
        )

    # ====== ① 能源价格 ======

    def _compile_oil(self) -> Optional[IntelligenceItem]:
        """获取国际原油价格"""
        try:
            # 国际期货全量数据 → 筛选WTI原油
            df = ak.futures_global_spot_em()
            if df is not None and not df.empty:
                # 查找WTI原油行（名称列可能包含"WTI"或"原油"）
                name_col = next((c for c in df.columns if "名称" in str(c) or "name" in str(c).lower()), df.columns[0])
                wti = df[df[name_col].str.contains("WTI|美原油", na=False, case=False)]
                if wti.empty:
                    wti = df[df[name_col].str.contains("原油", na=False)]
                if not wti.empty:
                    row = wti.iloc[0]
                    price = float(row["最新价"]) if "最新价" in df.columns else float(row.iloc[2])
                    change_pct = float(row["涨跌幅"]) if "涨跌幅" in df.columns else 0.0

                    direction = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
                    return IntelligenceItem(
                        category="能源",
                        title=f"① WTI原油 {price:.2f}美元/桶 {direction}{abs(change_pct):.2f}%",
                        summary=f"WTI原油报{price:.2f}美元/桶，较前日{direction}{abs(change_pct):.2f}%。"
                                f"{'油价上行将推高塑料、化纤等石化原料成本' if change_pct > 0 else '油价下行利好石化原料采购成本'}",
                        severity="warning" if abs(change_pct) > 3 else "info",
                    )
        except Exception as e:
            logger.warning(f"[情报] 原油数据获取失败: {e}")

        # 备用：用国内原油期货
        try:
            df = ak.futures_spot_price(
                date=date.today().strftime("%Y%m%d"),
                vars_list=["SC"]
            )
            if df is not None and not df.empty:
                row = df.iloc[0]
                price = float(row["spot_price"])
                return IntelligenceItem(
                    category="能源",
                    title=f"① 上海原油 {price:.0f}元/桶",
                    summary=f"上海INE原油期货现货参考价{price:.0f}元/桶。原油为塑料(PP/PE/PVC)、化纤(涤纶)上游原料，价格波动将逐步传导至家居原材料成本。",
                    severity="info",
                )
        except Exception as e:
            logger.warning(f"[情报] 国内原油数据也失败: {e}")

        return IntelligenceItem(
            category="能源",
            title="① 原油价格（数据暂不可用）",
            summary="今日未能获取原油价格数据（API受限）。原油为塑料、化纤等家居原材料的上游核心，建议关注WTI/布伦特走势。",
            severity="info",
        )

    # ====== ② 汇率走势 ======

    def _compile_forex(self, forex: ForexDataPoint) -> IntelligenceItem:
        """编译汇率研判"""
        direction = "贬值" if forex.change_pct and forex.change_pct > 0 else "升值"
        abs_pct = abs(forex.change_pct) if forex.change_pct else 0

        impact = (
            "人民币贬值利好出口，提高跨境产品价格竞争力"
            if direction == "贬值"
            else "人民币升值利好进口采购，降低海外原材料成本"
        )

        return IntelligenceItem(
            category="汇率",
            title=f"② USD/CNH {forex.rate:.4f}（月{direction}{abs_pct:.2f}%）",
            summary=f"离岸人民币兑美元报{forex.rate:.4f}。{impact}。关注汇率对越南、柬埔寨、马来西亚等产地的人民币计价成本影响。",
            severity="warning" if abs_pct > 1 else "info",
        )

    # ====== ③ 海运运价 ======

    def _compile_freight(self) -> Optional[IntelligenceItem]:
        """获取 BDI 波罗的海干散货指数"""
        try:
            df = ak.spot_goods(symbol="波罗的海干散货指数")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                # 列名可能是 ['日期', '价格']
                price = float(latest.iloc[-1])
                date_val = str(latest.iloc[0])[:10]

                # 计算月变化
                change_str = ""
                if len(df) >= 22:
                    prev = df.iloc[-22]
                    prev_price = float(prev.iloc[-1])
                    if prev_price != 0:
                        change = (price - prev_price) / prev_price * 100
                        direction = "↑" if change > 0 else "↓"
                        change_str = f" {direction}{abs(change):.1f}%"

                summary = f"BDI报{price:.0f}点{change_str}。"
                if change_str and "↓" in change_str:
                    summary += "海运成本下行利好跨境物流。"
                elif change_str and "↑" in change_str:
                    summary += "海运成本上行，关注对越南、柬埔寨、马来西亚等产地的物流成本影响。"

                return IntelligenceItem(
                    category="运价",
                    title=f"③ BDI波罗的海干散货指数 {price:.0f}点{change_str}",
                    summary=summary,
                    severity="info",
                )
        except Exception as e:
            logger.warning(f"[情报] BDI数据获取失败: {e}")

        return IntelligenceItem(
            category="运价",
            title="③ BDI运价指数（数据暂不可用）",
            summary="今日未能获取BDI波罗的海干散货指数。BDI反映全球海运散货运价，直接影响海外产地物流成本。",
            severity="info",
        )

    # ====== ④ 宏观政策 ======

    def _compile_macro(self, ppi: MacroDataPoint, cpi: MacroDataPoint) -> Optional[IntelligenceItem]:
        """编译宏观政策摘要"""
        parts = []
        if ppi.value != 0.0 and ppi.period:
            p = ppi.period or ""
            if p.startswith("2025") or p.startswith("2026"):
                parts.append(f"PPI同比{ppi.value:+.1f}%")
        if cpi.value != 0.0 and cpi.period:
            p = cpi.period or ""
            if p.startswith("2025") or p.startswith("2026"):
                parts.append(f"CPI同比{cpi.value:+.1f}%")

        if parts:
            detail = "、".join(parts)
            direction = "上行通道" if ppi.value > 0 else "下行通道"
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
