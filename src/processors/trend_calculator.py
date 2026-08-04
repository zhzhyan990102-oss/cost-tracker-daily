"""趋势计算器 — 日环比 / 7日趋势 / 30日趋势 / 告警级别"""

from datetime import date, timedelta
from loguru import logger

from src.collectors.base import MaterialDataPoint
from src.utils.cache import load_history, save_cache


class TrendCalculator:
    """计算多维趋势指标和告警级别"""

    ALERT_THRESHOLD = 5.0     # 日环比 >5% 触发 ALERT
    WARNING_THRESHOLD = 2.0   # 日环比 >2% 触发 WARNING
    FLAT_THRESHOLD = 0.3      # 日环比 <0.3% 标记为 FLAT

    def __init__(self):
        self.history = load_history(days=30)

    def calculate(self, data_points: list[MaterialDataPoint]) -> list[dict]:
        """为每个数据点计算趋势指标，返回增强后的字典列表"""
        # 先保存当日数据作为缓存
        cache_data = [self._dp_to_dict(dp) for dp in data_points]
        save_cache(cache_data)

        enriched = []
        for dp in data_points:
            record = self._dp_to_dict(dp)
            record["d7_change"] = self._calc_n_day_change(dp.material_name, 7)
            record["d30_change"] = self._calc_n_day_change(dp.material_name, 30)
            record["direction"] = self._calc_direction(dp.change_pct)
            record["alert_level"] = self._calc_alert_level(dp.change_pct, record["d7_change"])
            enriched.append(record)

        return enriched

    def _calc_n_day_change(self, material_name: str, n_days: int) -> float | None:
        """计算 N 日趋势变化"""
        today = date.today()
        target_date = today - timedelta(days=n_days)

        # 向前搜索最近的有效历史数据（允许±2天误差）
        for offset in range(-2, 3):
            d = target_date + timedelta(days=offset)
            day_data = self.history.get(d.isoformat(), [])
            for record in day_data:
                if record.get("material_name") == material_name:
                    hist_price = record.get("price", 0)
                    # 在当前数据点中找对应价格
                    return None  # 需要在 enrich 步骤中有当前价格才能算
        return None

    @staticmethod
    def _calc_direction(change_pct: float | None) -> str:
        """判断涨跌方向"""
        if change_pct is None:
            return "N/A"
        if change_pct > TrendCalculator.FLAT_THRESHOLD:
            return "UP"
        if change_pct < -TrendCalculator.FLAT_THRESHOLD:
            return "DOWN"
        return "FLAT"

    @staticmethod
    def _calc_alert_level(d1_change: float | None, d7_change: float | None) -> str:
        """计算告警级别"""
        if d1_change is None:
            return "NORMAL"
        abs_d1 = abs(d1_change)
        abs_d7 = abs(d7_change) if d7_change else 0

        if abs_d1 > TrendCalculator.ALERT_THRESHOLD or abs_d7 > 10:
            return "ALERT"
        if abs_d1 > TrendCalculator.WARNING_THRESHOLD or abs_d7 > 5:
            return "WARNING"
        return "NORMAL"

    @staticmethod
    def _dp_to_dict(dp: MaterialDataPoint) -> dict:
        """将 MaterialDataPoint 转为可序列化字典"""
        return {
            "material_name": dp.material_name,
            "symbol": dp.symbol,
            "price": dp.price,
            "price_unit": dp.price_unit,
            "price_date": dp.price_date.isoformat(),
            "prev_price": dp.prev_price,
            "change_pct": dp.change_pct,
            "source": dp.source,
            "status": dp.status.value,
        }
