"""成本跟盘日报系统 — 主入口

流程编排：采集 → 标准化 → 趋势计算 → 成本映射 → 情报编译 → 报告生成 → 钉钉推送
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logger
from src.utils.cache import cleanup_cache


def main():
    """主流程入口"""
    setup_logger()
    logger.info("=" * 50)
    logger.info(f"成本跟盘日报系统 启动 - {datetime.now().isoformat()}")

    # ---- 0. 交易日判断 ----
    if not _is_trading_day():
        logger.info("[跳过] 非交易日，发送简化版报告")
        _send_holiday_report()
        return

    # ---- 1. 数据采集 ----
    logger.info("--- 阶段1: 数据采集 ---")
    from src.collectors.akshare_spot import AkShareSpotCollector
    from src.collectors.akshare_macro import AkShareMacroCollector
    from src.collectors.akshare_forex import AkShareForexCollector

    # 现货价格
    spot_collector = AkShareSpotCollector()
    raw_data = spot_collector.collect()

    # 宏观指标
    macro_collector = AkShareMacroCollector()
    macro_data = macro_collector.get_all()

    # 汇率
    forex_collector = AkShareForexCollector()
    forex_data = forex_collector.get_usdcny()

    logger.info(f"采集结果: 现货{len(raw_data)}条, 宏观{len(macro_data)}项, 汇率OK={forex_data.rate != 7.25}")

    # ---- 2. 数据标准化 ----
    logger.info("--- 阶段2: 数据标准化 ---")
    from src.processors.normalizer import DataNormalizer
    normalizer = DataNormalizer()
    clean_data = normalizer.normalize(raw_data)

    # ---- 3. 趋势计算 ----
    logger.info("--- 阶段3: 趋势计算 ---")
    from src.processors.trend_calculator import TrendCalculator
    trend_calc = TrendCalculator()
    enriched_data = trend_calc.calculate(clean_data)

    # ---- 4. 成本映射 ----
    logger.info("--- 阶段4: 成本映射 ---")
    from src.processors.cost_mapper import CostMapper
    mapper = CostMapper()
    region_impacts = mapper.map_to_regions(clean_data, enriched_data)

    # ---- 5. 情报编译 ----
    logger.info("--- 阶段5: 情报编译 ---")
    from src.processors.intelligence_compiler import IntelligenceCompiler
    compiler = IntelligenceCompiler()
    intel_report = compiler.compile(
        forex=forex_data,
        ppi=macro_data.get("PPI"),
        cpi=macro_data.get("CPI"),
    )

    # ---- 6. 报告生成 ----
    logger.info("--- 阶段6: 报告生成 ---")
    from src.reporters.md_builder import DailyReportBuilder
    report_date = date.today()
    builder = DailyReportBuilder(report_date=report_date, intelligence=intel_report)

    # 完整明细（写入 reports/ 目录）
    detail_md = builder.build_detail(region_impacts)
    detail_url = _save_and_get_url(detail_md, report_date)

    # 精要播报（替换占位符 URL 后推送钉钉）
    brief_md = builder.build_brief(region_impacts)
    brief_md = brief_md.replace("{DETAIL_URL}", detail_url)

    # ---- 7. 钉钉推送 ----
    logger.info("--- 阶段7: 钉钉推送 ---")
    from src.pushers.dingtalk import DingTalkPusher

    pusher = DingTalkPusher()
    title = f"🏠 家居成本跟盘日报 {report_date.isoformat()}"

    # 发送精要播报
    success = pusher.send_markdown(title=title, text=brief_md)
    if not success:
        logger.error("[钉钉] 精要播报发送失败！")

    # 发送预警 FeedCard（条件触发）
    from src.reporters.feed_card_builder import FeedCardBuilder
    feed_builder = FeedCardBuilder()
    # 复用 md_builder 中的 mover 提取逻辑
    movers = _get_significant_movers(region_impacts)
    alert_cards = feed_builder.build_alert_cards(movers)
    if alert_cards:
        # 替换占位符 URL
        for card in alert_cards:
            if "messageURL" in card:
                card["messageURL"] = card["messageURL"].replace("{DETAIL_URL}", detail_url)
            elif hasattr(card, "message_url"):
                card["messageURL"] = card.message_url.replace("{DETAIL_URL}", detail_url)
        pusher.send_feed_card(alert_cards)

    # ---- 8. 清理 ----
    cleanup_cache(keep_days=35)

    logger.info("=" * 50)
    logger.info(f"成本跟盘日报系统 完成 - 成功={success}")
    return 0 if success else 1


def _is_trading_day() -> bool:
    """判断今天是否为交易日（排除周末和法定节假日）"""
    today = date.today()

    # 周末跳过
    if today.weekday() >= 5:
        logger.info(f"[交易日判断] {today} 是周末，非交易日")
        return False

    # 法定节假日跳过
    try:
        from src.config.settings import get_holidays
        holidays = get_holidays()
        if today.isoformat() in holidays:
            logger.info(f"[交易日判断] {today} 是法定节假日，非交易日")
            return False
    except Exception:
        pass

    return True


def _save_and_get_url(markdown: str, report_date: date) -> str:
    """保存完整明细文件到 reports/ 目录，返回访问 URL"""
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"cost-detail-{report_date.isoformat()}.md"
    filepath = reports_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    # GitHub Actions 环境下，构造 raw URL
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/cost-tracker-daily")
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        return f"https://github.com/{repo}/blob/{branch}/reports/{filename}"
    else:
        # 本地运行，返回文件路径
        return f"file:///{filepath.as_posix()}"


def _get_significant_movers(region_impacts) -> list[tuple]:
    """提取日变幅 >2% 的重点波动项"""
    movers = []
    for region in region_impacts:
        for cat in region.categories:
            for mc in cat.material_changes:
                if mc.change_pct is not None and abs(mc.change_pct) >= 2.0:
                    movers.append((region.region_name, cat.category_name, mc))
    movers.sort(key=lambda x: abs(x[2].change_pct or 0), reverse=True)
    return movers[:10]


def _send_holiday_report():
    """非交易日发送简化版报告（仅汇率+情报，无现货价格）"""
    from src.collectors.akshare_forex import AkShareForexCollector
    from src.pushers.dingtalk import DingTalkPusher

    forex_collector = AkShareForexCollector()
    forex_data = forex_collector.get_usdcny()

    today = date.today()
    text = (
        f"## 🏠 家居成本跟盘日报（休市）\n"
        f"**{today.isoformat()}**\n\n"
        f"今日为非交易日，现货市场休市。以下为实时汇率参考：\n\n"
        f"- 💱 **USD/CNH**：{forex_data.rate:.4f}\n"
        f"- 📅 下一交易日恢复完整日报\n\n"
        f"---\n📌 数据来源：AkShare / 国家统计局"
    )

    pusher = DingTalkPusher()
    pusher.send_markdown(
        title=f"🏠 家居成本跟盘日报 {today.isoformat()}（休市）",
        text=text,
    )


if __name__ == "__main__":
    sys.exit(main())
