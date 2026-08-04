"""钉钉群聊机器人推送器 — Markdown 消息 + FeedCard 预警"""

import os
import hmac
import hashlib
import base64
import time
import urllib.parse as urlparse
from typing import Optional

import requests
from loguru import logger

# dingtalkchatbot 库内部使用的 API 端点
DINGTALK_API = "https://oapi.dingtalk.com/robot/send"


class DingTalkPusher:
    """钉钉群聊机器人推送封装

    支持两种模式：
    1. dingtalkchatbot 库（高级消息：Markdown, FeedCard）
    2. 纯 requests（签名URL + JSON body，降低依赖风险）
    """

    def __init__(self, webhook: Optional[str] = None, secret: Optional[str] = None):
        self.webhook = webhook or os.environ.get("DINGTALK_WEBHOOK", "")
        self.secret = secret or os.environ.get("DINGTALK_SECRET", "")

        if not self.webhook:
            logger.warning("[钉钉] webhook URL 未配置！将跳过消息发送")

    def _build_signed_url(self) -> str:
        """构建带签名的完整请求 URL"""
        if not self.secret:
            return self.webhook

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urlparse.quote_plus(base64.b64encode(hmac_code))

        separator = "&" if "?" in self.webhook else "?"
        return f"{self.webhook}{separator}timestamp={timestamp}&sign={sign}"

    def send_markdown(self, title: str, text: str) -> bool:
        """发送 Markdown 消息

        Args:
            title: 消息标题（显示在通知栏）
            text: Markdown 格式正文

        Returns:
            是否发送成功
        """
        if not self.webhook:
            logger.warning("[钉钉] 跳过发送（webhook 未配置）")
            return False

        url = self._build_signed_url()
        # 钉钉 Markdown 内容限制约 4096 字节，超长自动分段
        chunks = self._chunk_text(text, max_bytes=3800)

        for i, chunk in enumerate(chunks):
            chunk_title = f"{title} ({i+1}/{len(chunks)})" if len(chunks) > 1 else title
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": chunk_title,
                    "text": chunk,
                },
            }

            try:
                resp = requests.post(url, json=payload, timeout=15)
                result = resp.json()
                if result.get("errcode") != 0:
                    logger.error(f"[钉钉] Markdown 发送失败: {result}")
                    return False
                logger.info(f"[钉钉] Markdown 发送成功 ({i+1}/{len(chunks)})")
            except Exception as e:
                logger.error(f"[钉钉] Markdown 发送异常: {e}")
                return False

        return True

    def send_feed_card(self, links: list[dict]) -> bool:
        """发送 FeedCard 预警消息

        Args:
            links: [{title, messageURL, picURL}, ...] 最多5条

        Returns:
            是否发送成功
        """
        if not self.webhook or not links:
            return False

        url = self._build_signed_url()
        payload = {
            "msgtype": "feedCard",
            "feedCard": {
                "links": links[:5],  # 钉钉限制最多5条
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=15)
            result = resp.json()
            if result.get("errcode") != 0:
                logger.error(f"[钉钉] FeedCard 发送失败: {result}")
                return False
            logger.info(f"[钉钉] FeedCard 发送成功 ({len(links[:5])}条)")
            return True
        except Exception as e:
            logger.error(f"[钉钉] FeedCard 发送异常: {e}")
            return False

    def send_text(self, content: str) -> bool:
        """发送纯文本消息（用于告警通知）"""
        if not self.webhook:
            return False

        url = self._build_signed_url()
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }

        try:
            resp = requests.post(url, json=payload, timeout=15)
            result = resp.json()
            return result.get("errcode") == 0
        except Exception as e:
            logger.error(f"[钉钉] Text 发送异常: {e}")
            return False

    @staticmethod
    def _chunk_text(text: str, max_bytes: int = 3800) -> list[str]:
        """按段落边界智能分段，避免截断表格或链接"""
        if len(text.encode("utf-8")) <= max_bytes:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current = ""

        for para in paragraphs:
            test = current + ("\n\n" if current else "") + para
            if len(test.encode("utf-8")) <= max_bytes:
                current = test
            else:
                if current:
                    chunks.append(current)
                # 如果单个段落仍超长，按行拆分
                if len(para.encode("utf-8")) > max_bytes:
                    for sub_chunk in DingTalkPusher._split_long_paragraph(para, max_bytes):
                        chunks.append(sub_chunk)
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return chunks or [text]

    @staticmethod
    def _split_long_paragraph(para: str, max_bytes: int) -> list[str]:
        """对超长单段落按行拆分，行仍超长则按字符硬切"""
        result = []
        current = ""
        for line in para.split("\n"):
            test = current + ("\n" if current else "") + line
            if len(test.encode("utf-8")) <= max_bytes:
                current = test
            else:
                if current:
                    result.append(current)
                # 行仍超长，按字符硬切
                if len(line.encode("utf-8")) > max_bytes:
                    result.extend(DingTalkPusher._hard_split(line, max_bytes))
                    current = ""
                else:
                    current = line
        if current:
            result.append(current)
        return result

    @staticmethod
    def _hard_split(text: str, max_bytes: int) -> list[str]:
        """按字节数硬切文本（最后手段）"""
        chunks = []
        encoded = text.encode("utf-8")
        pos = 0
        while pos < len(encoded):
            chunk_bytes = encoded[pos:pos + max_bytes]
            chunks.append(chunk_bytes.decode("utf-8", errors="ignore"))
            pos += max_bytes
        return chunks
