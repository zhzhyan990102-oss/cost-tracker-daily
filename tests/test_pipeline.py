"""集成测试：验证完整 Pipeline 各阶段"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date
from loguru import logger


def test_config_loading():
    """测试1：配置文件完整性"""
    from src.config.settings import get_anchors, get_mappings, get_collectors_registry, get_holidays

    anchors = get_anchors()
    assert len(anchors) == 15, f"锚点数量应为15，实际{len(anchors)}"
    for a in anchors:
        assert "material" in a, f"锚点缺少material字段"
        assert "anchor_price" in a, f"{a['material']}缺少anchor_price"

    mappings = get_mappings()
    assert len(mappings) == 15, f"映射数量应为15，实际{len(mappings)}"

    registry = get_collectors_registry()
    assert len(registry) == 15, f"采集器注册数量应为15，实际{len(registry)}"

    print("✅ 测试1通过：配置文件完整")


def test_cost_mapper():
    """测试2：成本映射器"""
    from src.processors.cost_mapper import CostMapper
    from src.collectors.base import MaterialDataPoint, SourceStatus

    mapper = CostMapper()

    # 模拟采集数据
    test_data = [
        MaterialDataPoint("冷轧板卷", "冷轧板", 4520, "元/吨", date.today(),
                          prev_price=4400, change_pct=2.73, source="test", status=SourceStatus.SUCCESS),
        MaterialDataPoint("TDI", "TDI", 17680, "元/吨", date.today(),
                          prev_price=16800, change_pct=5.24, source="test", status=SourceStatus.SUCCESS),
        MaterialDataPoint("刨花板", "刨花板", 1850, "元/立方米", date.today(),
                          prev_price=1860, change_pct=-0.54, source="test", status=SourceStatus.SUCCESS),
    ]

    # 模拟 enriched 数据
    enriched = [
        {"material_name": "冷轧板卷", "direction": "UP", "alert_level": "WARNING"},
        {"material_name": "TDI", "direction": "UP", "alert_level": "ALERT"},
        {"material_name": "刨花板", "direction": "DOWN", "alert_level": "NORMAL"},
    ]

    regions = mapper.map_to_regions(test_data, enriched)
    assert len(regions) > 0, "应至少有一个产地区域"

    # 验证广东有置物架品类
    gd = next((r for r in regions if r.region_name == "广东"), None)
    assert gd is not None, "应该有广东产地"
    assert any(c.category_name == "置物架" for c in gd.categories), "广东应该有置物架"

    # 验证天津有海绵床垫
    tj = next((r for r in regions if r.region_name == "天津"), None)
    assert tj is not None, "应该有天津产地"

    print(f"✅ 测试2通过：成本映射器 — {len(regions)} 个产地")
    for r in regions[:3]:
        cats = ", ".join(c.category_name for c in r.categories)
        print(f"   {r.region_name}: {cats}")


def test_report_builder():
    """测试3：报告生成器"""
    from src.reporters.md_builder import DailyReportBuilder
    from src.processors.intelligence_compiler import IntelligenceReport
    from src.collectors.base import ForexDataPoint, MacroDataPoint

    # 模拟情报
    intel = IntelligenceReport(
        date=date.today(),
        items=[],
        forex=ForexDataPoint("USD/CNH", 7.2510, date.today(), 7.2400, 0.15),
        ppi=MacroDataPoint("PPI", -1.2, "2026-06"),
        cpi=MacroDataPoint("CPI", 0.9, "2026-06"),
    )

    builder = DailyReportBuilder(report_date=date.today(), intelligence=intel)

    # 测试精要播报
    brief = builder.build_brief([])
    assert "宏观大盘" in brief, "精要播报应包含宏观大盘"
    assert "{DETAIL_URL}" in brief, "精要播报应包含详情链接占位符"

    # 测试完整明细
    detail = builder.build_detail([])
    assert "宏观指标" in detail, "完整明细应包含宏观指标"

    print("✅ 测试3通过：报告生成器")
    print(f"   精要播报长度: {len(brief)}字符")
    print(f"   完整明细长度: {len(detail)}字符")


def test_dingtalk_pusher():
    """测试4：钉钉推送器（不发送）"""
    from src.pushers.dingtalk import DingTalkPusher

    # 无 webhook 环境下的初始化
    import os
    old_webhook = os.environ.pop("DINGTALK_WEBHOOK", None)
    old_secret = os.environ.pop("DINGTALK_SECRET", None)

    pusher = DingTalkPusher(webhook="", secret="")
    assert not pusher.send_markdown("test", "test"), "无webhook时应返回False"

    # 恢复环境变量
    if old_webhook:
        os.environ["DINGTALK_WEBHOOK"] = old_webhook
    if old_secret:
        os.environ["DINGTALK_SECRET"] = old_secret

    print("✅ 测试4通过：钉钉推送器（无webhook环境安全处理）")


def test_chunk_text():
    """测试5：Markdown 智能分段"""
    from src.pushers.dingtalk import DingTalkPusher

    pusher = DingTalkPusher(webhook="", secret="")

    # 短文本不分段
    short = "短文本测试"
    chunks = pusher._chunk_text(short, max_bytes=100)
    assert len(chunks) == 1, f"短文本不应分段，实际{len(chunks)}段"

    # 长文本分段
    long_text = "A" * 5000
    chunks = pusher._chunk_text(long_text, max_bytes=100)
    assert len(chunks) > 1, f"长文本应分段，实际{len(chunks)}段"

    print(f"✅ 测试5通过：Markdown 分段 — 短文本{len(short)}字不分段，超长文本分{len(chunks)}段")


def run_all():
    print("=" * 50)
    print("成本跟盘日报系统 — 集成测试")
    print("=" * 50)
    test_config_loading()
    test_cost_mapper()
    test_report_builder()
    test_dingtalk_pusher()
    test_chunk_text()
    print("=" * 50)
    print("🎉 全部测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    run_all()
