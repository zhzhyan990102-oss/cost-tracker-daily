"""Mysteel 钢材公开页面采集器 — 备选数据源

当 AkShare 中钢材 symbol 不可用时，从 Mysteel 公开指数页面获取数据。
"""

from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.collectors.base import AbstractCollector, MaterialDataPoint, SourceStatus
from src.utils.retry import with_retry


class MysteelCollector(AbstractCollector):
    """从 mySteel 公开页面抓取钢材价格指数"""

    source_name = "web_mysteel"

    # Mysteel 普钢绝对价格指数页面
    INDEX_URL = "https://index.mysteel.com/"

    def collect(self) -> list[MaterialDataPoint]:
        """采集 Mysteel 钢材指数"""
        try:
            html = self._fetch_page()
            if not html:
                return []

            data = self._parse_index(html)
            return data
        except Exception as e:
            logger.error(f"[Mysteel] 采集失败: {e}")
            return []

    @with_retry(max_attempts=2, base_delay=3.0)
    def _fetch_page(self) -> Optional[str]:
        """获取指数页面 HTML"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(self.INDEX_URL, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"[Mysteel] HTTP {resp.status_code}")
        return None

    def _parse_index(self, html: str) -> list[MaterialDataPoint]:
        """解析指数页面表格数据

        注：Mysteel 页面常通过 JS 动态渲染，静态 HTML 可能不含数据表格。
        此方法作为框架保留，实际使用时可能需要调整选择器或改用 API。
        """
        soup = BeautifulSoup(html, "lxml")

        # 尝试查找价格指数表格（选择器需根据实际页面结构调优）
        table = soup.find("table", class_="price-table")
        if not table:
            table = soup.find("table")

        if not table:
            logger.warning("[Mysteel] 未找到价格指数表格")
            return []

        results = []
        rows = table.find_all("tr")[1:]  # 跳过表头
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                name = cells[0].get_text(strip=True)
                try:
                    price = float(cells[2].get_text(strip=True).replace(",", ""))
                except (ValueError, IndexError):
                    continue

                # 映射 Mysteel 品种名到系统内部名
                material_name = self._map_name(name)
                if material_name:
                    results.append(MaterialDataPoint(
                        material_name=material_name,
                        symbol=f"mysteel_{name}",
                        price=price,
                        price_unit="指数点",
                        price_date=date.today(),
                        source=self.source_name,
                        status=SourceStatus.SUCCESS,
                    ))

        logger.info(f"[Mysteel] 解析到 {len(results)} 条数据")
        return results

    @staticmethod
    def _map_name(mysteel_name: str) -> Optional[str]:
        """将 Mysteel 品种名映射到系统内部原材料名"""
        mapping = {
            "冷轧": "冷轧板卷",
            "热轧": "热轧板卷",
            "螺纹": "螺纹钢",
            "管材": "管材",
            "线材": "线材",
            "中板": "中厚板",
        }
        for key, val in mapping.items():
            if key in mysteel_name:
                return val
        return None
