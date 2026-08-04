"""数据标准化器 — 单位统一 / 异常值过滤 / 状态标记"""

from datetime import date
from loguru import logger

from src.collectors.base import MaterialDataPoint, SourceStatus


class DataNormalizer:
    """对采集到的原始数据进行标准化处理"""

    # 异常值阈值：单日变幅超过此值标记为可疑
    ANOMALY_THRESHOLD = 15.0  # ±15%

    def normalize(self, data_points: list[MaterialDataPoint]) -> list[MaterialDataPoint]:
        """标准化处理全部数据点

        Returns:
            标准化后的数据点列表（已过滤完全无效的数据）
        """
        valid = []
        for dp in data_points:
            if dp.status == SourceStatus.FAILED and dp.price == 0.0:
                logger.warning(f"[标准化] {dp.material_name} 完全无效，跳过")
                continue

            # 异常值检测
            if dp.change_pct is not None and abs(dp.change_pct) > self.ANOMALY_THRESHOLD:
                logger.warning(
                    f"[异常值] {dp.material_name} 日变幅 {dp.change_pct:+.2f}%，超过阈值{self.ANOMALY_THRESHOLD}%"
                )
                dp.status = SourceStatus.STALE  # 标记为过期，非报异常

            valid.append(dp)

        logger.info(f"[标准化] 输入{len(data_points)}条 → 有效{len(valid)}条")
        return valid
