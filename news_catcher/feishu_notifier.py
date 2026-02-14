"""
飞书通知模块 - 通过 Webhook 发送新闻到飞书
Feishu Notifier Module - Send news to Feishu via Webhook

消息格式：
  每个行业 = 动态总结（文字要点） + 新闻链接列表
  先读总结，感兴趣再点链接
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
        """生成签名"""
        if not self.secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _send_request(self, payload: dict) -> bool:
        """发送请求到飞书 Webhook"""
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

    # ================================================================
    # 带总结的新版卡片（主要入口）
    # ================================================================

    def send_news_card_with_summary(
        self,
        news_by_industry: dict[str, list[NewsItem]],
        summaries: dict[str, str],
        funding_by_industry: dict = None,
    ) -> bool:
        """
        以交互卡片发送新闻 + 行业总结 + 投融资高亮

        布局（每个行业）：
          ── 行业标题 ──
          🔥 投融资/IPO 高亮（如有）
          📝 动态总结（3~6 行文字要点）
          📎 相关新闻链接
        """
        if not news_by_industry:
            logger.warning("没有新闻可发送")
            return False

        funding_by_industry = funding_by_industry or {}
        today = datetime.now().strftime("%Y年%m月%d日")
        total_count = sum(len(items) for items in news_by_industry.values())
        industry_count = len(news_by_industry)
        funding_total = sum(len(v) for v in funding_by_industry.values())

        elements = []

        # ── 头部 ──
        header_text = (
            f"📡 今日覆盖 **{industry_count}** 个行业，"
            f"共捕获 **{total_count}** 条新闻"
        )
        if funding_total > 0:
            header_text += f"，**{funding_total}** 条投融资/IPO 事件"
        header_text += "\n以下为各行业动态要点总结，可直接阅读；如需详情请点击新闻链接 👇"

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": header_text,
            },
        })
        elements.append({"tag": "hr"})

        # ── 逐行业：投融资高亮 + 总结 + 链接 ──
        for industry, news_items in news_by_industry.items():
            emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
            summary_text = summaries.get(industry, "")
            funding_events = funding_by_industry.get(industry, [])

            # 行业标题（有投融资事件时加🔥标记）
            title_suffix = " 🔥" if funding_events else ""
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{emoji} {industry}{title_suffix}**",
                },
            })

            # 投融资/IPO 高亮区域（置顶）
            if funding_events:
                funding_lines = []
                for evt in funding_events:
                    line = f"🔥 **{evt.company}**"
                    if evt.event_type == "IPO":
                        line += " IPO"
                    elif evt.round:
                        line += f" 完成{evt.round}"
                    if evt.amount:
                        line += f"（{evt.amount}）"
                    if evt.url:
                        line += f" [详情]({evt.url})"
                    funding_lines.append(line)

                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "\n".join(funding_lines),
                    },
                })

            # 动态总结
            if summary_text:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": summary_text,
                    },
                })

            # 新闻链接列表（紧凑格式）
            link_lines = []
            for i, item in enumerate(news_items, 1):
                source = f" *{item.source}*" if item.source else ""
                link_lines.append(f"[{i}. {item.title}]({item.url}){source}")

            if link_lines:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "📎 **相关新闻**\n" + "\n".join(link_lines),
                    },
                })

            elements.append({"tag": "hr"})

        # ── 底部 ──
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": (
                        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        f" | 十五五规划重点行业热点新闻捕捉器"
                    ),
                }
            ],
        })

        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🔥 十五五规划重点行业动态速览 | {today}",
                    },
                    "template": "red",
                },
                "elements": elements,
            },
        }

        return self._send_request(card_payload)

    # ================================================================
    # 分批发送（内容过长时自动拆分）
    # ================================================================

    def send_news_with_summary(
        self,
        news_by_industry: dict[str, list[NewsItem]],
        summaries: dict[str, str],
        funding_by_industry: dict = None,
    ) -> bool:
        """
        智能发送：内容过多时自动分批，每批最多 4 个行业
        """
        if not news_by_industry:
            logger.warning("没有新闻可发送")
            return False

        funding_by_industry = funding_by_industry or {}
        industries = list(news_by_industry.keys())
        batch_size = 4  # 飞书卡片有大小限制，每批 4 个行业比较安全

        if len(industries) <= batch_size:
            return self.send_news_card_with_summary(
                news_by_industry, summaries, funding_by_industry
            )

        # 分批
        all_success = True
        for i in range(0, len(industries), batch_size):
            batch_keys = industries[i : i + batch_size]
            batch_news = {k: news_by_industry[k] for k in batch_keys}
            batch_funding = {k: funding_by_industry[k] for k in batch_keys if k in funding_by_industry}
            batch_num = i // batch_size + 1
            total_batches = (len(industries) + batch_size - 1) // batch_size

            logger.info(f"正在发送第 {batch_num}/{total_batches} 批（{', '.join(batch_keys)}）")
            success = self.send_news_card_with_summary(batch_news, summaries, batch_funding)

            if not success:
                all_success = False
                logger.error(f"第 {batch_num} 批发送失败")

            if i + batch_size < len(industries):
                time.sleep(1)

        return all_success

    # ================================================================
    # 旧版兼容 & 工具方法
    # ================================================================

    def send_news_card(self, news_by_industry: dict[str, list[NewsItem]]) -> bool:
        """旧版：仅链接的卡片（无总结时的回退）"""
        # 生成空总结，复用新版格式
        empty_summaries = {k: "" for k in news_by_industry}
        return self.send_news_card_with_summary(news_by_industry, empty_summaries)

    def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        payload = {"msg_type": "text", "content": {"text": text}}
        return self._send_request(payload)

    def send_news(
        self,
        news_by_industry: dict[str, list[NewsItem]],
        summaries: dict[str, str] = None,
        funding_by_industry: dict = None,
    ) -> bool:
        """
        统一发送入口
        Args:
            news_by_industry: {行业名: [NewsItem, ...]}
            summaries: {行业名: "总结文本"}  可选
            funding_by_industry: {行业名: [FundingEvent, ...]}  可选
        """
        if summaries:
            return self.send_news_with_summary(
                news_by_industry, summaries, funding_by_industry
            )
        else:
            return self.send_news_card(news_by_industry)


def send_to_feishu(
    news_by_industry: dict[str, list[NewsItem]],
    summaries: dict[str, str] = None,
    funding_by_industry: dict = None,
    webhook_url: str = None,
) -> bool:
    """
    便捷函数：发送新闻到飞书（含投融资高亮）
    """
    try:
        notifier = FeishuNotifier(webhook_url=webhook_url)
        return notifier.send_news(
            news_by_industry,
            summaries=summaries,
            funding_by_industry=funding_by_industry,
        )
    except ValueError as e:
        logger.error(str(e))
        return False
