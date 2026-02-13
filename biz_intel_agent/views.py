"""
Django 视图 - 飞书机器人事件回调接口
Django Views - Feishu Bot Event Callback Endpoint

提供以下接口：
  POST /api/feishu/event   - 飞书事件订阅回调（接收用户消息等）
  GET  /api/feishu/health  - 健康检查接口
"""

import json
import logging

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .feishu_bot import get_bot

logger = logging.getLogger("biz_intel_agent.views")


@csrf_exempt
@require_http_methods(["POST"])
def feishu_event_callback(request):
    """
    飞书事件订阅回调接口

    飞书机器人的所有事件（消息接收、审批等）都会推送到这个接口。

    配置方法：
      1. 在飞书开放平台的应用"事件订阅"页面
      2. 将"请求地址"设置为: https://<your-domain>/api/feishu/event
      3. 添加 im.message.receive_v1 事件

    请求流程：
      1. 飞书首次验证 URL 时发送 challenge 请求，需原样返回
      2. 之后每次有事件触发，飞书都会 POST 事件数据到此接口
      3. 必须在 3 秒内返回 HTTP 200，否则飞书会重试
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"请求体解析失败: {e}")
        return JsonResponse({"code": -1, "msg": "Invalid JSON"}, status=400)

    logger.info(f"收到飞书事件回调: {json.dumps(body, ensure_ascii=False)[:500]}")

    bot = get_bot()

    # 验证事件合法性
    if not bot.verify_event(body):
        logger.warning("事件验证失败，拒绝处理")
        return JsonResponse({"code": -1, "msg": "Verification failed"}, status=403)

    # 处理事件（内部会异步处理耗时任务）
    result = bot.handle_event(body)

    # 必须快速返回 200，否则飞书会重试
    return JsonResponse(result)


@require_http_methods(["GET"])
def health_check(request):
    """
    健康检查接口

    用于检查服务是否正常运行。
    可用于：
      - 负载均衡器健康检查
      - 飞书应用的可用性监控
      - 运维排查
    """
    from .config import (
        FEISHU_APP_ID,
        LLM_API_KEY,
        LLM_MODEL,
        LLM_BASE_URL,
    )

    status = {
        "status": "ok",
        "service": "biz-intel-agent",
        "feishu_app_configured": bool(FEISHU_APP_ID),
        "llm_configured": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL,
        "llm_base_url": LLM_BASE_URL,
    }

    return JsonResponse(status)
