"""FeedCard 预警卡片构造器 — 当出现高优先级告警时生成醒目提醒"""


class FeedCardBuilder:
    """构建钉钉 FeedCard 类型的预警卡片"""

    def build_alert_cards(self, movers: list[tuple]) -> list[dict]:
        """根据重点波动项构建 FeedCard 列表

        Args:
            movers: (region, category, material_change) 元组列表
        Returns:
            dict 列表 (title, messageURL, picURL)
        """
        cards = []
        for region, category, mc in movers:
            if mc.alert_level not in ("ALERT", "WARNING"):
                continue

            direction = "大涨" if (mc.change_pct or 0) > 0 else "大跌"
            icon = "🔴" if mc.alert_level == "ALERT" else "🟡"

            cards.append({
                "title": f"{icon} 成本预警 {mc.material_name} {direction} {abs(mc.change_pct):.1f}%",
                "messageURL": "{DETAIL_URL}",
                "picURL": "",
            })

        return cards[:5]
