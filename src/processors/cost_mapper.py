"""成本映射器 — 将原材料价格变化映射到产地/品类的成本影响"""

from dataclasses import dataclass, field
from loguru import logger

from src.collectors.base import MaterialDataPoint
from src.config.settings import get_mappings


@dataclass
class MaterialChange:
    """单个原材料的变化信息"""
    material_name: str
    price: float
    price_unit: str
    change_pct: float | None
    direction: str           # UP / DOWN / FLAT / N/A
    alert_level: str         # NORMAL / WARNING / ALERT


@dataclass
class CategoryImpact:
    """某个品类在某个产地受所有原材料变化的影响"""
    category_name: str
    material_changes: list[MaterialChange] = field(default_factory=list)
    total_cost_impact: float = 0.0  # 综合成本影响 (%)


@dataclass
class RegionCostImpact:
    """某个产地的成本影响汇总"""
    region_name: str
    categories: list[CategoryImpact] = field(default_factory=list)


class CostMapper:
    """将原材料价格数据映射到各地供应链成本影响"""

    def __init__(self):
        self.mappings = get_mappings()
        self._material_index = self._build_index()

    def _build_index(self) -> dict[str, list]:
        """构建原材料名 → 映射条目 的索引"""
        index: dict[str, list] = {}
        for m in self.mappings:
            mat = m["material"]
            if mat not in index:
                index[mat] = []
            index[mat].append(m)
        return index

    def map_to_regions(self, data_points: list[MaterialDataPoint],
                       enriched: list[dict]) -> list[RegionCostImpact]:
        """将原材料数据映射为按产地分组的成本影响报告

        Args:
            data_points: 原始采集数据
            enriched: 经过 TrendCalculator 增强的数据（含 direction/alert_level）

        Returns:
            按产地区域分组的成本影响列表
        """
        # 构建 material_name → enriched_record 查找表
        enriched_lookup = {e["material_name"]: e for e in enriched}

        # 按产地聚合
        region_map: dict[str, dict[str, CategoryImpact]] = {}

        for dp in data_points:
            rec = enriched_lookup.get(dp.material_name, {})
            change = MaterialChange(
                material_name=dp.material_name,
                price=dp.price,
                price_unit=dp.price_unit,
                change_pct=dp.change_pct,
                direction=rec.get("direction", "N/A"),
                alert_level=rec.get("alert_level", "NORMAL"),
            )

            # 查找该原材料影响的所有产地和品类
            entries = self._material_index.get(dp.material_name, [])
            for entry in entries:
                for affect in entry.get("affects", []):
                    category_name = affect["category"]
                    weight = affect.get("cost_weight", 0.0)

                    for region in affect.get("regions", []):
                        if region not in region_map:
                            region_map[region] = {}

                        if category_name not in region_map[region]:
                            region_map[region][category_name] = CategoryImpact(
                                category_name=category_name
                            )

                        cat_impact = region_map[region][category_name]
                        cat_impact.material_changes.append(change)

                        # 计算该原材料对品类成本的加权影响
                        if dp.change_pct is not None:
                            cat_impact.total_cost_impact += dp.change_pct * weight

        # 转为列表并按告警严重性排序
        result = []
        for region_name, cats in region_map.items():
            categories = list(cats.values())
            # 按成本影响绝对值降序
            categories.sort(key=lambda c: abs(c.total_cost_impact), reverse=True)

            result.append(RegionCostImpact(
                region_name=region_name,
                categories=categories,
            ))

        # 有告警的产地排前面
        result.sort(key=self._region_alert_score, reverse=True)
        return result

    @staticmethod
    def _region_alert_score(region: RegionCostImpact) -> float:
        """计算产地的告警评分（用于排序）"""
        score = 0.0
        for cat in region.categories:
            for mc in cat.material_changes:
                if mc.alert_level == "ALERT":
                    score += 3.0
                elif mc.alert_level == "WARNING":
                    score += 1.0
            score += abs(cat.total_cost_impact) * 0.1
        return score
