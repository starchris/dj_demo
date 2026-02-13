"""
飞书机器人模块 - 处理飞书事件回调和消息收发
Feishu Bot Module - Handle Feishu event callbacks and message sending/receiving

功能：
  1. 接收飞书事件订阅回调（用户发消息给机器人）
  2. 获取 tenant_access_token 用于调用飞书 API
  3. 通过飞书 API 回复消息给用户（支持富文本/Markdown卡片）

飞书机器人配置步骤：
  1. 在飞书开放平台(https://open.feishu.cn)创建应用
  2. 开启"机器人"能力
  3. 在"事件订阅"中添加 im.message.receive_v1 事件
  4. 配置请求地址为: http://<your-domain>/api/feishu/event
  5. 发布应用版本并审批通过
"""

import hashlib
import json
import logging
import time
import threading
from typing import Optional

import requests

from .config import (
    FEISHU_API_BASE,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_ENCRYPT_KEY,
    FEISHU_VERIFICATION_TOKEN,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger("biz_intel_agent.feishu_bot")


class FeishuBot:
    """飞书机器人 - 负责与飞书平台交互"""

    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.verification_token = FEISHU_VERIFICATION_TOKEN
        self.encrypt_key = FEISHU_ENCRYPT_KEY

        # tenant_access_token 缓存
        self._token: Optional[str] = None
        self._token_expire_time: float = 0
        self._token_lock = threading.Lock()

        # 已处理的消息ID集合（防重复处理）
        self._processed_message_ids: set = set()
        self._max_cache_size = 1000

    # ============================================================
    # Token 管理
    # ============================================================

    def _get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token（自动缓存和刷新）

        飞书 API 调用都需要 token 认证，token 有效期 2 小时
        """
        with self._token_lock:
            # 如果 token 未过期，直接返回缓存
            if self._token and time.time() < self._token_expire_time - 300:
                return self._token

            url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            }

            try:
                resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
                data = resp.json()

                if data.get("code") == 0:
                    self._token = data["tenant_access_token"]
                    # token 有效期 2 小时，提前 5 分钟刷新
                    self._token_expire_time = time.time() + data.get("expire", 7200)
                    logger.info("飞书 tenant_access_token 获取成功")
                    return self._token
                else:
                    logger.error(f"获取 tenant_access_token 失败: {data}")
                    raise Exception(f"获取 token 失败: {data.get('msg', 'unknown error')}")
            except requests.RequestException as e:
                logger.error(f"请求 tenant_access_token 异常: {e}")
                raise

    def _get_auth_headers(self) -> dict:
        """获取带认证的请求头"""
        token = self._get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ============================================================
    # 事件处理
    # ============================================================

    def handle_event(self, body: dict) -> dict:
        """
        处理飞书事件回调

        飞书事件订阅有两种场景：
        1. URL 验证（首次配置时）: 返回 challenge
        2. 事件推送（用户发消息等）: 处理事件并返回成功

        Args:
            body: 飞书推送的 JSON body

        Returns:
            需要返回给飞书的响应 dict
        """
        # 场景1: URL 验证请求
        if "challenge" in body:
            logger.info("收到飞书 URL 验证请求")
            return {"challenge": body["challenge"]}

        # 场景2: v2.0 事件格式
        schema = body.get("schema")
        if schema == "2.0":
            return self._handle_v2_event(body)

        # 场景3: v1.0 事件格式（兼容旧版）
        if "event" in body:
            return self._handle_v1_event(body)

        logger.warning(f"未识别的事件格式: {json.dumps(body, ensure_ascii=False)[:200]}")
        return {"code": 0}

    def _handle_v2_event(self, body: dict) -> dict:
        """处理 v2.0 格式的事件"""
        header = body.get("header", {})
        event = body.get("event", {})
        event_type = header.get("event_type", "")

        logger.info(f"收到 v2.0 事件: {event_type}")

        # 处理消息接收事件
        if event_type == "im.message.receive_v1":
            message = event.get("message", {})
            sender = event.get("sender", {})
            return self._handle_message_event(message, sender)

        return {"code": 0}

    def _handle_v1_event(self, body: dict) -> dict:
        """处理 v1.0 格式的事件（兼容旧版）"""
        event = body.get("event", {})
        event_type = event.get("type", "")

        logger.info(f"收到 v1.0 事件: {event_type}")

        if event_type == "message":
            # v1.0 消息格式转换
            message = {
                "message_id": event.get("msg_type", ""),
                "chat_id": event.get("open_chat_id", ""),
                "chat_type": event.get("chat_type", ""),
                "message_type": event.get("msg_type", "text"),
                "content": json.dumps({"text": event.get("text_without_at_bot", event.get("text", ""))}),
            }
            sender = {
                "sender_id": {"open_id": event.get("open_id", "")},
                "sender_type": "user",
            }
            return self._handle_message_event(message, sender)

        return {"code": 0}

    def _handle_message_event(self, message: dict, sender: dict) -> dict:
        """
        处理接收到的用户消息

        提取公司名称并触发分析任务（异步执行）

        Args:
            message: 消息对象
            sender: 发送者对象
        """
        message_id = message.get("message_id", "")
        chat_id = message.get("chat_id", "")
        chat_type = message.get("chat_type", "")
        message_type = message.get("message_type", "")

        # 防重复处理
        if message_id in self._processed_message_ids:
            logger.info(f"消息已处理过，跳过: {message_id}")
            return {"code": 0}

        self._processed_message_ids.add(message_id)
        # 清理缓存，防止内存溢出
        if len(self._processed_message_ids) > self._max_cache_size:
            self._processed_message_ids = set(list(self._processed_message_ids)[-500:])

        # 只处理文本消息
        if message_type != "text":
            self._reply_text(
                message_id,
                "抱歉，目前只支持文本消息。请直接发送公司名称，例如：腾讯"
            )
            return {"code": 0}

        # 提取文本内容
        try:
            content = json.loads(message.get("content", "{}"))
            text = content.get("text", "").strip()
        except (json.JSONDecodeError, AttributeError):
            text = ""

        if not text:
            return {"code": 0}

        # 去除@机器人的文本
        # 飞书在群聊中 @机器人 时，文本中会包含 @_user_1 等标记
        import re
        text = re.sub(r'@_user_\d+', '', text).strip()

        logger.info(f"收到用户消息: '{text}' (chat_id={chat_id}, chat_type={chat_type})")

        # 处理帮助指令
        if text.lower() in ("help", "帮助", "/help", "你好", "hi", "hello"):
            self._send_help_message(message_id)
            return {"code": 0}

        # 将公司名称作为分析任务异步执行
        # 先回复一条"正在分析"的消息
        self._reply_text(
            message_id,
            f"🔍 正在分析「{text}」的企业经营信息和招聘预算，请稍候...\n"
            f"（分析过程约需 30-60 秒）"
        )

        # 异步执行分析任务
        thread = threading.Thread(
            target=self._async_analyze_and_reply,
            args=(text, chat_id, chat_type, message_id),
            daemon=True,
        )
        thread.start()

        return {"code": 0}

    def _async_analyze_and_reply(
        self, company_name: str, chat_id: str, chat_type: str, message_id: str
    ):
        """
        异步执行：分析公司信息并回复结果

        Args:
            company_name: 公司名称
            chat_id: 会话ID
            chat_type: 会话类型 (p2p/group)
            message_id: 原始消息ID（用于回复）
        """
        try:
            # 延迟导入，避免循环依赖
            from .agent import BusinessIntelAgent

            agent = BusinessIntelAgent()
            report = agent.analyze(company_name)

            if report:
                # 使用飞书交互卡片发送报告
                self._send_report_card(chat_id, company_name, report)
            else:
                self._send_message_to_chat(
                    chat_id,
                    "text",
                    {"text": f"抱歉，未能获取到「{company_name}」的相关信息，请检查公司名称是否正确后重试。"}
                )

        except Exception as e:
            logger.error(f"分析任务执行失败 [{company_name}]: {e}", exc_info=True)
            self._send_message_to_chat(
                chat_id,
                "text",
                {"text": f"分析「{company_name}」时出现错误: {str(e)}\n请稍后重试。"}
            )

    # ============================================================
    # 消息发送
    # ============================================================

    def _reply_text(self, message_id: str, text: str) -> bool:
        """
        回复消息（reply 模式，会在原消息下方显示）

        Args:
            message_id: 要回复的消息ID
            text: 回复的文本内容
        """
        url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"
        payload = {
            "content": json.dumps({"text": text}),
            "msg_type": "text",
        }

        try:
            resp = requests.post(
                url, json=payload,
                headers=self._get_auth_headers(),
                timeout=REQUEST_TIMEOUT
            )
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"回复消息成功: {message_id}")
                return True
            else:
                logger.error(f"回复消息失败: {data}")
                return False
        except Exception as e:
            logger.error(f"回复消息异常: {e}")
            return False

    def _send_message_to_chat(
        self, chat_id: str, msg_type: str, content: dict
    ) -> bool:
        """
        向指定会话发送消息

        Args:
            chat_id: 会话ID
            msg_type: 消息类型 (text/interactive)
            content: 消息内容
        """
        url = f"{FEISHU_API_BASE}/im/v1/messages"
        payload = {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps(content) if isinstance(content, dict) else content,
        }
        params = {"receive_id_type": "chat_id"}

        try:
            resp = requests.post(
                url, json=payload, params=params,
                headers=self._get_auth_headers(),
                timeout=REQUEST_TIMEOUT
            )
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"发送消息成功: chat_id={chat_id}")
                return True
            else:
                logger.error(f"发送消息失败: {data}")
                return False
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return False

    def _send_report_card(self, chat_id: str, company_name: str, report: str) -> bool:
        """
        以飞书交互卡片格式发送分析报告

        将 Markdown 格式的报告转换为飞书卡片消息，
        支持富文本排版，阅读体验更好。

        Args:
            chat_id: 会话ID
            company_name: 公司名称
            report: Markdown 格式的报告内容
        """
        from datetime import datetime

        # 将报告按大节拆分，构建卡片元素
        elements = []

        # 摘要信息
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"📊 以下为「**{company_name}**」的企业经营洞察与招聘预算分析报告\n"
                    f"数据来源：公开信息渠道（财报、投融资平台、招聘网站等）"
                ),
            },
        })
        elements.append({"tag": "hr"})

        # 将 Markdown 报告内容直接放入卡片
        # 飞书卡片的 lark_md 有长度限制，需要分段
        sections = self._split_report_to_sections(report)

        for section in sections:
            if section.strip():
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": section.strip(),
                    },
                })

        # 底部注释
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": (
                        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        f" | 企业经营洞察与招聘预算分析 Agent"
                    ),
                }
            ],
        })

        card_content = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📋 {company_name} - 销售拓展洞察报告",
                },
                "template": "blue",
            },
            "elements": elements,
        }

        return self._send_message_to_chat(chat_id, "interactive", card_content)

    @staticmethod
    def _split_report_to_sections(report: str) -> list:
        """
        将报告按二级标题（##）拆分为多个段落

        飞书卡片的单个 lark_md 元素有字符限制，
        按段拆分可以规避限制，同时增加分隔线改善阅读体验。
        """
        import re

        # 按 ## 标题拆分
        sections = re.split(r'\n(?=## )', report)

        result = []
        for section in sections:
            section = section.strip()
            if not section:
                continue

            # 去掉最顶部的一级标题（# xxx），因为已经在卡片 header 中显示
            if section.startswith("# ") and "\n" in section:
                first_line_end = section.index("\n")
                section = section[first_line_end:].strip()
            elif section.startswith("# ") and "\n" not in section:
                continue  # 只有一级标题没有内容，跳过

            if section:
                result.append(section)

        return result if result else [report]

    def _send_help_message(self, message_id: str):
        """发送帮助信息"""
        help_text = (
            "👋 你好！我是企业经营洞察分析助手。\n\n"
            "📌 **使用方法**：直接发送公司名称，我会为你分析：\n"
            "  · 企业财务实力（营收、融资、规模）\n"
            "  · 业务发展方向（核心业务、战略重点）\n"
            "  · 招聘与预算分析（在招职位、薪资水平、人才缺口）\n"
            "  · 销售策略建议（接触点、价值主张）\n\n"
            "📝 **示例**：\n"
            "  · 发送「腾讯」→ 获取腾讯公司分析报告\n"
            "  · 发送「字节跳动」→ 获取字节跳动分析报告\n"
            "  · 发送「宁德时代」→ 获取宁德时代分析报告\n\n"
            "⏱ 分析过程约需 30-60 秒，请耐心等待。"
        )
        self._reply_text(message_id, help_text)

    # ============================================================
    # 事件验证
    # ============================================================

    def verify_event(self, body: dict) -> bool:
        """
        验证飞书事件的合法性

        检查 verification_token 是否匹配，防止伪造请求
        """
        # v2.0 格式
        header = body.get("header", {})
        token = header.get("token", "")

        # v1.0 格式
        if not token:
            token = body.get("token", "")

        if self.verification_token and token != self.verification_token:
            logger.warning(f"事件验证失败: token 不匹配")
            return False

        return True


# 全局单例
_bot_instance: Optional[FeishuBot] = None


def get_bot() -> FeishuBot:
    """获取飞书机器人单例"""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = FeishuBot()
    return _bot_instance
