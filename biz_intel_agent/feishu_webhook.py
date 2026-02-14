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
    def _md_to_lark_md(text: str) -> str:
        """
        将标准 Markdown 转换为飞书 lark_md 兼容格式

        飞书 lark_md 支持: **粗体**, *斜体*, ~~删除线~~, [链接](url), 换行
        飞书 lark_md 不支持: # 标题, | 表格, > 引用块, ``` 代码块, 有序列表编号

        转换规则:
          - # / ## / ### 标题 → **粗体标题**
          - | 表格 → 逐行 key: value 文本
          - > 引用 → 💡 + 斜体
          - - 列表 → • 圆点
          - ``` 代码块 → 去掉围栏，保留内容
          - ⚠️/> ⚠️ 警告块 → 保留 emoji 文本
        """
        lines = text.split('\n')
        result = []
        in_table = False
        table_headers = []
        table_rows = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # ── 代码块处理（去掉 ``` 围栏，保留内容） ──
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                result.append(line)
                continue

            # ── 表格处理：收集表格行，最后统一转换 ──
            if stripped.startswith('|') and stripped.endswith('|'):
                cols = [c.strip() for c in stripped.strip('|').split('|')]
                # 跳过分隔行（|---|---|）
                if all(re.match(r'^[-:]+$', c) for c in cols):
                    in_table = True
                    continue
                if not in_table:
                    # 第一行是表头
                    table_headers = cols
                    in_table = True
                    continue
                else:
                    table_rows.append(cols)
                    continue
            else:
                # 如果刚从表格切出来，先输出已收集的表格
                if in_table:
                    result.append(FeishuWebhookSender._format_table(table_headers, table_rows))
                    table_headers = []
                    table_rows = []
                    in_table = False

            # ── 空行 ──
            if not stripped:
                result.append('')
                continue

            # ── 标题 → 粗体 ──
            heading_match = re.match(r'^(#{1,4})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2)
                if level == 1:
                    # 一级标题：已在卡片 header 中，跳过
                    continue
                elif level == 2:
                    result.append(f'\n**━━ {title_text} ━━**')
                elif level == 3:
                    result.append(f'\n**▸ {title_text}**')
                else:
                    result.append(f'**{title_text}**')
                continue

            # ── 引用块 → 斜体带 emoji ──
            if stripped.startswith('> '):
                quote_text = stripped[2:]
                # 如果引用中已有 emoji（如 ⚠️），保留原样
                if any(c in quote_text[:3] for c in '⚠️💡📌🔔'):
                    result.append(f'*{quote_text}*')
                else:
                    result.append(f'💡 *{quote_text}*')
                continue

            # ── 无序列表 → 圆点 ──
            list_match = re.match(r'^[-*]\s+(.+)$', stripped)
            if list_match:
                result.append(f'  • {list_match.group(1)}')
                continue

            # ── 有序列表 → 保留数字 ──
            olist_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
            if olist_match:
                result.append(f'  {olist_match.group(1)}. {olist_match.group(2)}')
                continue

            # ── 分隔线 ──
            if stripped == '---' or stripped == '***':
                result.append('─────────────────────')
                continue

            # ── 普通文本保留原样 ──
            result.append(stripped)

        # 如果文件末尾有未输出的表格
        if in_table:
            result.append(FeishuWebhookSender._format_table(table_headers, table_rows))

        return '\n'.join(result)

    @staticmethod
    def _format_table(headers: list, rows: list) -> str:
        """
        将 Markdown 表格转换为 lark_md 兼容的 key-value 文本

        两列表格 → "**key**: value" 格式（更紧凑）
        多列表格 → 表头作为 key，每行一组数据
        """
        if not headers:
            return ''

        lines = []

        if len(headers) == 2:
            # 两列表格：key-value 模式，更紧凑
            for row in rows:
                if len(row) >= 2:
                    key = row[0].strip('*').strip()
                    val = row[1].strip()
                    lines.append(f'  **{key}**：{val}')
                elif len(row) == 1:
                    lines.append(f'  {row[0]}')
        else:
            # 多列表格：每行展示所有字段
            for row in rows:
                parts = []
                for i, col in enumerate(row):
                    if i < len(headers) and col.strip():
                        parts.append(f'{headers[i]}: {col.strip()}')
                if parts:
                    lines.append('  ' + ' | '.join(parts))

        return '\n'.join(lines)

    @staticmethod
    def _split_report_to_sections(report: str) -> list:
        """
        将报告按二级标题（##）拆分为多个段落，并转换为 lark_md 格式

        飞书卡片的单个 lark_md 元素有字符限制（约4000字符），
        按段拆分可以规避限制，同时改善阅读体验。
        """
        # 先转换整个报告为 lark_md 格式
        converted = FeishuWebhookSender._md_to_lark_md(report)

        # 按粗体标题（━━ xxx ━━）拆分段落
        sections = re.split(r'\n(?=\n\*\*━━ )', converted)

        result = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            # 飞书单个元素限制约4000字符，超长则截断
            if len(section) > 3800:
                # 按换行找到合适的截断点
                chunks = []
                current = ''
                for line in section.split('\n'):
                    if len(current) + len(line) + 1 > 3800:
                        chunks.append(current)
                        current = line
                    else:
                        current = current + '\n' + line if current else line
                if current:
                    chunks.append(current)
                result.extend(chunks)
            else:
                result.append(section)

        return result if result else [converted]


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
