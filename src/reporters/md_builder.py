"""Markdown 日报构造器 — 精要播报 + 完整明细"""

from datetime import date, timedelta
from pathlib import Path
from loguru import logger

from src.collectors.base import ForexDataPoint, MacroDataPoint
from src.processors.cost_mapper import RegionCostImpact, MaterialChange
from src.processors.intelligence_compiler import IntelligenceReport


class DailyReportBuilder:
    """构造精要版钉钉日报 + 完整明细 Markdown 文件"""

    def __init__(self, report_date: date, intelligence: IntelligenceReport):
        self.report_date = report_date
        self.intelligence = intelligence
        # 计算月前日期
        self.month_ago = report_date - timedelta(days=30)

    def build_brief(self, region_impacts: list[RegionCostImpact]) -> str:
        """构建精要播报（钉钉群主消息）

        结构：宏观 → 重点原材料波动 → 国际形势研判 → 完整明细链接
        """
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[self.report_date.weekday()]

        lines = [
            f"## 🏠 家居类目成本跟盘日报",
            f"**{self.report_date.isoformat()}（{weekday}）**  |  对比基准：{self.month_ago.isoformat()}（30天前）",
            "",
        ]

        # 一、宏观大盘（有效数据才显示）
        macro_line = self._build_macro_line()
        if macro_line and macro_line != "暂无宏观数据（API受限）":
            lines.append("### 📊 宏观大盘")
            lines.append(macro_line)
            lines.append("")

        # 二、重点原材料波动（较30天前 >2%）
        lines.append("### ⚡ 重点原材料月波动（较30天前）")
        movers = self._collect_significant_movers(region_impacts)
        if movers:
            for m in movers[:8]:
                lines.append(self._format_mover_line(m))
        else:
            lines.append("> 近30天无显著原材料波动（变幅均 < 2%）")
        lines.append("")

        # 三、国际形势与趋势研判
        lines.append("### 🌍 国际形势与趋势研判")
        geo_lines = self._build_geo_section()
        if geo_lines:
            lines.extend(geo_lines)
        lines.append("")

        # 四、完整明细链接
        lines.append("### 📎 完整明细")
        lines.append("> [点击查看全部产地×品类材料变动明细]({DETAIL_URL})")
        lines.append("")

        lines.append("---")
        lines.append("📌 数据来源：生意社(100ppi.com) / AkShare")
        lines.append("💰 价格基准：较30天前对比  |  🔴预警(>±5%) 🟡关注(>±2%) 🟢平稳(<±2%)")
        lines.append("⚓ 锚点标记：API不可用时使用人工基准价，需每月更新")

        return "\n".join(lines)

    def build_detail(self, region_impacts: list[RegionCostImpact]) -> str:
        """构建完整明细 Markdown 文件"""
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[self.report_date.weekday()]

        lines = [
            f"# 家居类目成本跟盘 — 完整明细",
            f"**日期：{self.report_date.isoformat()}（{weekday}）**  |  对比基准：{self.month_ago.isoformat()}（30天前）",
            "",
            "---",
            "",
        ]

        # 宏观数据
        macro = self._build_macro_detail()
        if macro:
            lines.append("## 📊 宏观指标")
            lines.append(macro)
            lines.append("")

        # 国内产地
        domestic = [r for r in region_impacts
                    if r.region_name in ["广东", "广西", "福建", "江苏", "浙江", "山东", "天津"]]
        if domestic:
            lines.append("## 🇨🇳 国内产地成本变动")
            lines.append("")
            for region in domestic:
                lines.extend(self._build_region_detail(region))

        # 海外产地
        overseas = [r for r in region_impacts
                    if r.region_name not in ["广东", "广西", "福建", "江苏", "浙江", "山东", "天津"]]
        if overseas:
            lines.append("## 🌏 海外产地成本参考")
            lines.append("")
            for region in overseas:
                lines.extend(self._build_region_detail(region))

        # 趋势研判
        lines.append("---")
        lines.append("## 🌍 国际形势与趋势研判")
        geo = self._build_geo_detail()
        if geo:
            lines.extend(geo)

        # 状态标记
        lines.append("---")
        lines.append("### 数据状态标记")
        lines.append("| 标记 | 含义 |")
        lines.append("|------|------|")
        lines.append("| ✅ 实时 | 生意社每日现货价（自动采集） |")
        lines.append("| ⚓ 锚点 | 使用人工基准价格（API不可用品种） |")
        lines.append("| - | 无变化数据（锚点品种） |")

        return "\n".join(lines)

    # ====== 宏观 ======

    def _build_macro_line(self) -> str:
        """宏观一行摘要（只显示有效数据，过滤历史异常）"""
        parts = []
        if self.intelligence.ppi and self.intelligence.ppi.value != 0.0 and self.intelligence.ppi.period:
            if self.intelligence.ppi.period[:4] in ("2025", "2026"):
                parts.append(f"PPI {self.intelligence.ppi.value:+.1f}%")
        if self.intelligence.cpi and self.intelligence.cpi.value != 0.0 and self.intelligence.cpi.period:
            if self.intelligence.cpi.period[:4] in ("2025", "2026"):
                parts.append(f"CPI {self.intelligence.cpi.value:+.1f}%")
        if self.intelligence.forex and self.intelligence.forex.rate != 7.25:
            parts.append(f"USDCNH {self.intelligence.forex.rate:.4f}")
        return " | ".join(parts) if parts else ""

    def _build_macro_detail(self) -> str:
        """宏观指标详情"""
        lines = []
        if self.intelligence.ppi and self.intelligence.ppi.value != 0.0 and self.intelligence.ppi.period:
            if self.intelligence.ppi.period[:4] in ("2025", "2026"):
                lines.append(f"- **PPI**（{self.intelligence.ppi.period}）：同比 {self.intelligence.ppi.value:+.1f}%")
        if self.intelligence.cpi and self.intelligence.cpi.value != 0.0 and self.intelligence.cpi.period:
            if self.intelligence.cpi.period[:4] in ("2025", "2026"):
                lines.append(f"- **CPI**（{self.intelligence.cpi.period}）：同比 {self.intelligence.cpi.value:+.1f}%")
        if self.intelligence.forex and self.intelligence.forex.rate != 7.25:
            direction = "↑" if self.intelligence.forex.change_pct and self.intelligence.forex.change_pct > 0 else "↓" if self.intelligence.forex.change_pct else ""
            lines.append(f"- **USD/CNH**：{self.intelligence.forex.rate:.4f} {direction}")
        return "\n".join(lines) if lines else ""

    # ====== 波动项 ======

    def _collect_significant_movers(self, region_impacts: list[RegionCostImpact]) -> list[tuple]:
        """收集较30天前变幅 >2% 的显著波动项"""
        movers = []
        for region in region_impacts:
            for cat in region.categories:
                for mc in cat.material_changes:
                    if mc.change_pct is not None and abs(mc.change_pct) >= 2.0:
                        movers.append((region.region_name, cat.category_name, mc))
        movers.sort(key=lambda x: abs(x[2].change_pct or 0), reverse=True)
        return movers[:10]

    def _format_mover_line(self, mover: tuple) -> str:
        """格式化一条重点波动"""
        region, category, mc = mover
        direction = "↑" if (mc.change_pct or 0) > 0 else "↓"
        alert_icon = {"ALERT": "🔴", "WARNING": "🟡"}.get(mc.alert_level, "🟢")
        return (
            f"- {alert_icon} **{mc.material_name}** {direction}"
            f"{abs(mc.change_pct):.2f}%（较30天前） "
            f"| 现价 {mc.price:,.0f} {mc.price_unit} "
            f"| 影响：{region}·{category}"
        )

    # ====== 国际形势研判（精要版） ======

    def _build_geo_section(self) -> list[str]:
        """构建国际形势研判段落（精要版）"""
        lines = []
        for item in self.intelligence.items:
            icon = {"alert": "🔴", "warning": "🟡", "info": "ℹ️"}.get(item.severity, "ℹ️")
            lines.append(f"{icon} **{item.title}**")
            if item.summary:
                lines.append(f"  {item.summary}")
            lines.append("")
        if not lines:
            lines.append("> 今日暂无重大国际形势与政策变动")
        return lines

    # ====== 国际形势研判（详细版） ======

    def _build_geo_detail(self) -> list[str]:
        """构建国际形势研判详细版"""
        lines = []
        for item in self.intelligence.items:
            lines.append(f"### {item.title}")
            lines.append(f"")
            lines.append(item.summary)
            if item.source_url:
                lines.append(f"  [来源]({item.source_url})")
            lines.append("")
        if not lines:
            lines.append("> 今日暂无重大国际形势与政策变动")
        return lines

    # ====== 产地明细 ======

    def _build_region_detail(self, region: RegionCostImpact) -> list[str]:
        """构建单个产地的完整明细"""
        lines = [f"### {region.region_name}", ""]
        for cat in region.categories:
            impact_str = f"{cat.total_cost_impact:+.2f}%" if cat.total_cost_impact != 0 else "持平"
            lines.append(f"#### {cat.category_name}（综合成本影响：{impact_str}）")
            lines.append("")
            lines.append("| 原材料 | 现价 | 单位 | 较30天前 | 趋势 | 告警 |")
            lines.append("|--------|------|------|----------|------|------|")

            for mc in cat.material_changes:
                direction_symbol = {"UP": "↑", "DOWN": "↓", "FLAT": "→", "N/A": "-"}.get(mc.direction, "-")
                alert_label = {"ALERT": "🔴预警", "WARNING": "🟡关注", "NORMAL": "🟢正常"}.get(mc.alert_level, "-")
                if mc.change_pct is not None:
                    change_str = f"{mc.change_pct:+.2f}%"
                else:
                    change_str = "-"
                lines.append(
                    f"| {mc.material_name} | {mc.price:,.0f} | {mc.price_unit} "
                    f"| {change_str} | {direction_symbol} | {alert_label} |"
                )
            lines.append("")
        return lines
