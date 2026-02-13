"""
飞书通知模块 - 通过 Webhook 发送新闻到飞书
Feishu Notifier Module - Send news to Feishu via Webhook

支持的消息类型：
1. 富文本消息（post）- 用于详细新闻展示
2. 交互卡片消息（interactive）- 用于美观展示
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime

import requests

from .config import (
    FEISHU_WEBHOOK_SECRET,
    FEISHU_WEBHOOK_URL,
    INDUSTRIES,
    REQUEST_TIMEOUT,
)
from .news_fetcher import NewsItem

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书消息通知器"""

    def __init__(self, webhook_url: str = None, secret: str = None):
        self.webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        self.secret = secret or FEISHU_WEBHOOK_SECRET

        if not self.webhook_url:
            raise ValueError(
                "飞书 Webhook URL 未配置！请设置环境变量 FEISHU_WEBHOOK_URL "
                "或在 config.py 中配置。\n"
                "格式: https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
            )

    def _gen_sign(self, timestamp: str) -> str:
        """
        生成签名（如果配置了签名密钥）
        https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
        """
        if not self.secret:
            return ""

        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _send_request(self, payload: dict) -> bool:
        """发送请求到飞书 Webhook"""
        # 添加签名（如果有密钥）
        if self.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._gen_sign(timestamp)

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )

            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info("飞书消息发送成功")
                return True
            else:
                logger.error(f"飞书消息发送失败: {result}")
                return False

        except requests.RequestException as e:
            logger.error(f"飞书请求异常: {e}")
            return False
        except json.JSONDecodeError:
            logger.error(f"飞书响应解析失败: {resp.text}")
            return False

    def send_news_card(self, news_by_industry: dict[str, list[NewsItem]]) -> bool:
        """
        以交互卡片形式发送新闻到飞书
        每个行业一个区块，包含新闻标题和链接
        """
        if not news_by_industry:
            logger.warning("没有新闻可发送")
            return False

        today = datetime.now().strftime("%Y年%m月%d日")
        total_count = sum(len(items) for items in news_by_industry.values())

        # 构建卡片元素
        elements = []

        # 头部说明
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"📡 今日共捕获 **{total_count}** 条十五五规划重点行业新闻"
            }
        })
        elements.append({"tag": "hr"})

        # 按行业分组展示新闻
        for industry, news_items in news_by_industry.items():
            emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")

            # 行业标题
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{emoji} {industry}**（{len(news_items)} 条）"
                }
            })

            # 新闻列表
            news_lines = []
            for i, item in enumerate(news_items, 1):
                source_info = f"  *{item.source}*" if item.source else ""
                time_info = f"  {item.publish_time}" if item.publish_time else ""
                news_lines.append(
                    f"{i}. [{item.title}]({item.url}){source_info}{time_info}"
                )

            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(news_lines)
                }
            })
            elements.append({"tag": "hr"})

        # 底部信息
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"🕐 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 热点新闻捕捉器"
                }
            ]
        })

        # 构建卡片消息
        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🔥 十五五规划重点行业热点新闻 | {today}"
                    },
                    "template": "red"
                },
                "elements": elements
            }
        }

        return self._send_request(card_payload)

    def send_news_post(self, news_by_industry: dict[str, list[NewsItem]]) -> bool:
        """
        以富文本（post）形式发送新闻到飞书
        作为卡片消息的备选方案
        """
        if not news_by_industry:
            logger.warning("没有新闻可发送")
            return False

        today = datetime.now().strftime("%Y年%m月%d日")
        total_count = sum(len(items) for items in news_by_industry.values())

        # 构建富文本内容
        content = []

        # 头部
        content.append([
            {"tag": "text", "text": f"📡 今日共捕获 {total_count} 条行业新闻\n"}
        ])
        content.append([{"tag": "text", "text": "━" * 30 + "\n"}])

        for industry, news_items in news_by_industry.items():
            emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")

            # 行业标题
            content.append([
                {"tag": "text", "text": f"\n{emoji} "},
                {"tag": "text", "text": f"【{industry}】", "style": ["bold"]},
                {"tag": "text", "text": f"（{len(news_items)} 条）\n"},
            ])

            # 新闻列表
            for i, item in enumerate(news_items, 1):
                line = [
                    {"tag": "text", "text": f"  {i}. "},
                    {"tag": "a", "text": item.title, "href": item.url},
                ]
                if item.source:
                    line.append({"tag": "text", "text": f"  — {item.source}"})
                line.append({"tag": "text", "text": "\n"})
                content.append(line)

            content.append([{"tag": "text", "text": "\n"}])

        # 底部
        content.append([
            {"tag": "text", "text": f"🕐 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"},
            {"tag": "text", "text": "📌 数据来源: 百度新闻/Bing新闻/RSS订阅"},
        ])

        post_payload = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"🔥 十五五规划重点行业热点新闻 | {today}",
                        "content": content
                    }
                }
            }
        }

        return self._send_request(post_payload)

    def send_text(self, text: str) -> bool:
        """发送纯文本消息（用于测试或简单通知）"""
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        return self._send_request(payload)

    def send_news(self, news_by_industry: dict[str, list[NewsItem]], use_card: bool = True) -> bool:
        """
        发送新闻到飞书
        Args:
            news_by_industry: {行业名: [NewsItem, ...]}
            use_card: 是否使用卡片消息（默认True），False则使用富文本
        """
        if use_card:
            # 飞书卡片消息有大小限制，如果内容太多需要分批发送
            total_items = sum(len(v) for v in news_by_industry.values())

            if total_items > 30:
                # 分批发送
                return self._send_in_batches(news_by_industry)
            else:
                success = self.send_news_card(news_by_industry)
                if not success:
                    # 卡片发送失败，回退到富文本
                    logger.warning("卡片消息发送失败，尝试使用富文本格式...")
                    return self.send_news_post(news_by_industry)
                return success
        else:
            return self.send_news_post(news_by_industry)

    def _send_in_batches(self, news_by_industry: dict[str, list[NewsItem]]) -> bool:
        """分批发送新闻（当新闻数量过多时）"""
        industries = list(news_by_industry.items())
        batch_size = 5  # 每批最多5个行业
        all_success = True

        for i in range(0, len(industries), batch_size):
            batch = dict(industries[i:i + batch_size])
            batch_num = i // batch_size + 1
            total_batches = (len(industries) + batch_size - 1) // batch_size

            logger.info(f"正在发送第 {batch_num}/{total_batches} 批新闻...")
            success = self.send_news_card(batch)

            if not success:
                all_success = False
                logger.error(f"第 {batch_num} 批新闻发送失败")

            # 批次间隔
            if i + batch_size < len(industries):
                time.sleep(1)

        return all_success


def send_to_feishu(news_by_industry: dict[str, list[NewsItem]], webhook_url: str = None) -> bool:
    """
    便捷函数：发送新闻到飞书
    Args:
        news_by_industry: {行业名: [NewsItem, ...]}
        webhook_url: 飞书 Webhook URL（可选，不传则使用配置）
    """
    try:
        notifier = FeishuNotifier(webhook_url=webhook_url)
        return notifier.send_news(news_by_industry)
    except ValueError as e:
        logger.error(str(e))
        return False
