"""鱼珠木材指数采集器 — 备选数据源

当 AkShare 中木材相关 symbol 不可用时，从鱼珠木材指数公开页面获取数据。
"""

from datetime import date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.collectors.base import AbstractCollector, MaterialDataPoint, SourceStatus
from src.utils.retry import with_retry


class YuzhuCollector(AbstractCollector):
    """从鱼珠中国木材价格指数网获取板材价格指数"""

    source_name = "web_yuzhu"

    # 鱼珠木材价格指数公开页面（URL 需根据实际情况调整）
    INDEX_URL = "http://www.yzforex.com/"

    def collect(self) -> list[MaterialDataPoint]:
        """采集鱼珠木材价格指数"""
        try:
            html = self._fetch_page()
            if not html:
                return []

            data = self._parse_index(html)
            return data
        except Exception as e:
            logger.error(f"[鱼珠] 采集失败: {e}")
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
        try:
            resp = requests.get(self.INDEX_URL, headers=headers, timeout=20)
            if resp.status_code == 200:
                # 鱼珠网站可能用 GB2312/GBK 编码
                resp.encoding = resp.apparent_encoding or "gb2312"
                return resp.text
            logger.warning(f"[鱼珠] HTTP {resp.status_code}")
        except requests.RequestException as e:
            logger.error(f"[鱼珠] 请求异常: {e}")
        return None

    def _parse_index(self, html: str) -> list[MaterialDataPoint]:
        """解析鱼珠木材指数页面

        注：鱼珠网站结构较老，数据呈现在复杂表格中。
        此方法作为框架保留，实际使用时需根据页面结构调整选择器。
        """
        soup = BeautifulSoup(html, "lxml")

        # 尝试查找指数数据区域
        index_div = soup.find("div", class_="index-data")
        if not index_div:
            index_div = soup.find("div", id="index")

        if not index_div:
            logger.warning("[鱼珠] 未找到指数数据区域")
            return []

        results = []
        # 鱼珠指数的典型格式：品种名 + 价格指数（元/张或指数点）
        # 实际选择器需根据页面结构调优
        items = index_div.find_all(["tr", "li"])
        for item in items:
            text = item.get_text(strip=True)
            material = self._parse_item(text)
            if material:
                results.append(material)

        logger.info(f"[鱼珠] 解析到 {len(results)} 条数据")
        return results

    def _parse_item(self, text: str) -> Optional[MaterialDataPoint]:
        """解析单条指数文本"""
        name_map = {
            "刨花板": "刨花板",
            "中纤板": "中纤板MDF",
            "纤维板": "中纤板MDF",
            "细木工板": "细木工板",
        }

        for keyword, material in name_map.items():
            if keyword in text:
                try:
                    # 尝试从文本中提取数字
                    import re
                    numbers = re.findall(r'[\d,.]+', text)
                    if numbers:
                        price = float(numbers[-1].replace(",", ""))
                        return MaterialDataPoint(
                            material_name=material,
                            symbol=f"yuzhu_{keyword}",
                            price=price,
                            price_unit="指数点",
                            price_date=date.today(),
                            source=self.source_name,
                            status=SourceStatus.SUCCESS,
                        )
                except (ValueError, IndexError):
                    pass
        return None
