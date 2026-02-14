"""
飞书 Webhook 通知模块 - 通过自定义机器人 Webhook 发送分析报告到飞书群
Feishu Webhook Module - Send analysis reports to Feishu group via custom bot webhook

与 news_catcher/feishu_notifier.py 采用完全一致的 Webhook 接入方式：
  1. 在飞书群聊中添加"自定义机器人"
  2. 获取 Webhook URL
  3. 通过 POST 请求发送消息

无需创建飞书开放平台应用，无需审批，配置简单。

消息格式：
  - 文本消息：纯文本通知（如"正在分析..."）
  - 交互卡片：富文本分析报告（表格、分段、颜色标签）
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests

from .config import (
    FEISHU_WEBHOOK_SECRET,
    FEISHU_WEBHOOK_URL,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger("biz_intel_agent.feishu_webhook")


class FeishuWebhookSender:
    """
    飞书 Webhook 消息发送器

    通过飞书群自定义机器人的 Webhook URL 发送消息，
    支持纯文本和交互卡片两种格式。
    """

    def __init__(self, webhook_url: str = None, secret: str = None):
        self.webhook_url = webhook_url or FEISHU_WEBHOOK_URL
        self.secret = secret or FEISHU_WEBHOOK_SECRET

        if not self.webhook_url:
            raise ValueError(
                "飞书 Webhook URL 未配置！\n"
                "请设置环境变量 FEISHU_WEBHOOK_URL\n"
                "获取方式：飞书群设置 → 群机器人 → 添加机器人 → 自定义机器人\n"
                "格式: https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
            )

    def _gen_sign(self, timestamp: str) -> str:
        """
        生成签名（与 news_catcher 的签名方式完全一致）

        仅在自定义机器人开启了"签名校验"时才需要
        """
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
    # 文本消息
    # ================================================================

    def send_text(self, text: str) -> bool:
        """发送纯文本消息"""
        payload = {"msg_type": "text", "content": {"text": text}}
        return self._send_request(payload)

    # ================================================================
    # 分析报告卡片
    # ================================================================

    def send_report(self, company_name: str, report: str) -> bool:
        """
        发送双报告到飞书（完整报告 + 销售简报）

        如果 report 包含分隔符 "---"，则拆分为两张卡片：
        1. 完整招聘预算分析报告（蓝色卡片）
        2. 销售简报（橙色卡片，30秒速览）

        Args:
            company_name: 公司名称
            report: Markdown 格式的双报告（用 --- 分隔）

        Returns:
            是否发送成功
        """
        # 尝试拆分双报告
        parts = report.split("\n\n---\n\n", 1)
        full_report = parts[0]
        sales_brief = parts[1] if len(parts) > 1 else ""

        # 发送完整报告
        success1 = self._send_report_card(
            company_name, full_report,
            header_text=f"📋 {company_name} - 完整招聘预算分析报告",
            header_color="blue",
            subtitle="数据来源：公开信息渠道（财报、投融资平台、招聘网站等）",
        )

        # 发送销售简报（如果有）
        success2 = True
        if sales_brief:
            import time as _time
            _time.sleep(1)  # 避免飞书限流
            success2 = self._send_report_card(
                company_name, sales_brief,
                header_text=f"⚡ {company_name} - 销售简报（30秒速览）",
                header_color="orange",
                subtitle="关键数字 + 行动建议，适合快速决策",
            )

        return success1 and success2

    def _send_report_card(
        self, company_name: str, report_content: str,
        header_text: str = "", header_color: str = "blue",
        subtitle: str = "",
    ) -> bool:
        """
        发送单张报告卡片

        Args:
            company_name: 公司名称
            report_content: Markdown 报告内容
            header_text: 卡片标题
            header_color: 卡片颜色 (blue/orange/red/green)
            subtitle: 副标题描述

        Returns:
            是否发送成功
        """
        elements = []

        # ── 头部摘要 ──
        if subtitle:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📊 {subtitle}",
                },
            })
            elements.append({"tag": "hr"})

        # ── 报告正文（按 ## 分段） ──
        sections = self._split_report_to_sections(report_content)
        for section in sections:
            if section.strip():
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": section.strip(),
                    },
                })

        # ── 底部注释 ──
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": (
                        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        f" | 企业招聘预算分析 Agent"
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
                        "content": header_text or f"📋 {company_name} - 分析报告",
                    },
                    "template": header_color,
                },
                "elements": elements,
            },
        }

        return self._send_request(card_payload)

    def send_analyzing_notice(self, company_name: str) -> bool:
        """
        发送"正在分析"的提示通知

        在分析任务开始时先发一条提示，让用户知道系统已经收到请求
        """
        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🔍 正在分析「{company_name}」...",
                    },
                    "template": "wathet",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"正在采集「**{company_name}**」的企业经营信息和招聘预算数据\n"
                                f"⏱ 预计需要 30-60 秒，请稍候..."
                            ),
                        },
                    },
                ],
            },
        }
        return self._send_request(card_payload)

    def send_error_notice(self, company_name: str, error_msg: str) -> bool:
        """发送分析失败的错误通知"""
        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"❌ 分析「{company_name}」失败",
                    },
                    "template": "red",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"错误信息：{error_msg}\n\n请检查公司名称是否正确，稍后重试。",
                        },
                    },
                ],
            },
        }
        return self._send_request(card_payload)

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def _split_report_to_sections(report: str) -> list:
        """
        将报告按二级标题（##）拆分为多个段落

        飞书卡片的单个 lark_md 元素有字符限制（约4000字符），
        按段拆分可以规避限制，同时改善阅读体验。
        """
        # 按 ## 标题拆分
        sections = re.split(r'\n(?=## )', report)

        result = []
        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 去掉最顶部的一级标题（# xxx），因为已在卡片 header 中显示
            if section.startswith("# ") and "\n" in section:
                first_line_end = section.index("\n")
                section = section[first_line_end:].strip()
            elif section.startswith("# ") and "\n" not in section:
                continue

            if section:
                result.append(section)

        return result if result else [report]


# ================================================================
# 便捷函数
# ================================================================

def send_report_to_feishu(
    company_name: str,
    report: str,
    webhook_url: str = None,
) -> bool:
    """
    便捷函数：将分析报告发送到飞书群

    Args:
        company_name: 公司名称
        report: Markdown 格式的分析报告
        webhook_url: 飞书 Webhook URL（可选，默认从配置读取）

    Returns:
        是否发送成功
    """
    try:
        sender = FeishuWebhookSender(webhook_url=webhook_url)
        return sender.send_report(company_name, report)
    except ValueError as e:
        logger.error(str(e))
        return False


def test_webhook_connection(webhook_url: str = None) -> bool:
    """
    测试飞书 Webhook 连接

    Args:
        webhook_url: 飞书 Webhook URL（可选，默认从配置读取）

    Returns:
        连接是否正常
    """
    try:
        sender = FeishuWebhookSender(webhook_url=webhook_url)
        return sender.send_text(
            f"🔔 企业经营洞察 Agent 测试消息\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"状态: Webhook 连接正常 ✅"
        )
    except ValueError as e:
        logger.error(str(e))
        return False
