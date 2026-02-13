"""
Django 视图 - 企业经营洞察 Agent 的 Web 接口
Django Views - Web interface for Business Intelligence Agent

提供以下接口：
  GET  /analyze           - 网页表单（输入公司名称）
  POST /analyze           - 提交分析请求（表单提交或 API 调用）
  POST /api/analyze       - JSON API 接口（程序调用）
  GET  /api/feishu/health - 健康检查

交互流程：
  1. 用户访问 /analyze 页面，输入公司名称
  2. 提交后异步执行分析，页面显示"正在分析"
  3. 分析完成后，报告通过 Webhook 推送到飞书群
  4. 同时网页上也展示分析结果
"""

import json
import logging
import threading

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger("biz_intel_agent.views")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def analyze_view(request):
    """
    分析页面 - 统一处理 GET 和 POST

    GET  /analyze            → 显示输入表单
    GET  /analyze?company=xx → 显示表单（可通过 JS 自动触发分析）
    POST /analyze            → 提交分析请求，异步推送结果到飞书
    """
    # GET: 展示表单页面
    if request.method == "GET":
        context = {
            "company": request.GET.get("company", ""),
        }
        return render(request, "biz_intel/analyze.html", context)

    # POST: 处理分析请求
    company_name = _extract_company_name(request)

    if not company_name:
        return JsonResponse({
            "success": False,
            "message": "请输入公司名称",
        }, status=400)

    logger.info(f"收到分析请求: {company_name}")

    # 发送"正在分析"提示到飞书
    _send_analyzing_notice(company_name)

    # 异步执行分析任务
    thread = threading.Thread(
        target=_async_analyze_and_send,
        args=(company_name,),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        "success": True,
        "message": f"已开始分析「{company_name}」，结果将推送到飞书群",
        "company": company_name,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze(request):
    """
    JSON API 接口 - 触发分析并推送到飞书

    POST /api/analyze
    Content-Type: application/json
    Body: {"company": "腾讯"}

    用于程序化调用（curl/脚本/其他系统集成）
    """
    try:
        body = json.loads(request.body)
        company_name = body.get("company", "").strip()
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({
            "success": False,
            "message": "请求体必须是合法 JSON，格式: {\"company\": \"公司名称\"}",
        }, status=400)

    if not company_name:
        return JsonResponse({
            "success": False,
            "message": "请在 JSON 中提供 company 字段",
        }, status=400)

    logger.info(f"API 收到分析请求: {company_name}")

    # 发送"正在分析"提示到飞书
    _send_analyzing_notice(company_name)

    # 异步执行分析任务
    thread = threading.Thread(
        target=_async_analyze_and_send,
        args=(company_name,),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        "success": True,
        "message": f"已开始分析「{company_name}」，结果将推送到飞书群",
        "company": company_name,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze_sync(request):
    """
    同步 API 接口 - 分析并直接返回结果（不推送飞书）

    POST /api/analyze/sync
    Content-Type: application/json
    Body: {"company": "腾讯", "send_feishu": true}

    - 同步等待分析完成，直接返回报告内容
    - 可选参数 send_feishu: 是否同时推送到飞书（默认 true）
    - 注意：此接口耗时较长（30-60秒），适合后台调用
    """
    try:
        body = json.loads(request.body)
        company_name = body.get("company", "").strip()
        send_feishu = body.get("send_feishu", True)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({
            "success": False,
            "message": "请求体必须是合法 JSON",
        }, status=400)

    if not company_name:
        return JsonResponse({
            "success": False,
            "message": "请在 JSON 中提供 company 字段",
        }, status=400)

    logger.info(f"同步 API 收到分析请求: {company_name}")

    try:
        from .agent import BusinessIntelAgent

        agent = BusinessIntelAgent()
        report = agent.analyze(company_name)

        if not report:
            return JsonResponse({
                "success": False,
                "message": f"未能获取到「{company_name}」的相关信息",
                "company": company_name,
            })

        # 可选推送到飞书
        feishu_sent = False
        if send_feishu:
            feishu_sent = _send_report_to_feishu(company_name, report)

        return JsonResponse({
            "success": True,
            "company": company_name,
            "report": report,
            "feishu_sent": feishu_sent,
        })

    except ValueError as e:
        return JsonResponse({
            "success": False,
            "message": f"配置错误: {str(e)}",
        }, status=500)
    except Exception as e:
        logger.error(f"同步分析失败 [{company_name}]: {e}", exc_info=True)
        return JsonResponse({
            "success": False,
            "message": f"分析失败: {str(e)}",
        }, status=500)


@require_http_methods(["GET"])
def health_check(request):
    """
    健康检查接口

    GET /api/feishu/health

    返回服务状态和配置信息
    """
    from .config import (
        FEISHU_WEBHOOK_URL,
        LLM_API_KEY,
        LLM_MODEL,
        LLM_BASE_URL,
    )

    status = {
        "status": "ok",
        "service": "biz-intel-agent",
        "mode": "webhook",
        "feishu_webhook_configured": bool(FEISHU_WEBHOOK_URL),
        "llm_configured": bool(LLM_API_KEY),
        "llm_model": LLM_MODEL,
        "llm_base_url": LLM_BASE_URL,
    }

    return JsonResponse(status)


# ================================================================
# 内部辅助函数
# ================================================================

def _extract_company_name(request) -> str:
    """从请求中提取公司名称（支持表单和 JSON 格式）"""
    # 优先尝试 JSON 格式
    content_type = request.content_type or ""
    if "json" in content_type:
        try:
            body = json.loads(request.body)
            return body.get("company", "").strip()
        except (json.JSONDecodeError, ValueError):
            pass

    # 尝试表单格式
    company = request.POST.get("company", "").strip()
    return company


def _send_analyzing_notice(company_name: str):
    """发送"正在分析"提示到飞书"""
    try:
        from .feishu_webhook import FeishuWebhookSender
        sender = FeishuWebhookSender()
        sender.send_analyzing_notice(company_name)
    except Exception as e:
        # 提示发送失败不影响主流程
        logger.warning(f"发送分析提示失败（不影响主流程）: {e}")


def _send_report_to_feishu(company_name: str, report: str) -> bool:
    """发送报告到飞书"""
    try:
        from .feishu_webhook import send_report_to_feishu
        return send_report_to_feishu(company_name, report)
    except Exception as e:
        logger.error(f"发送报告到飞书失败: {e}")
        return False


def _async_analyze_and_send(company_name: str):
    """
    异步执行：分析公司信息并通过 Webhook 发送到飞书群

    Args:
        company_name: 公司名称
    """
    try:
        from .agent import BusinessIntelAgent
        from .feishu_webhook import FeishuWebhookSender

        agent = BusinessIntelAgent()
        report = agent.analyze(company_name)

        sender = FeishuWebhookSender()

        if report:
            sender.send_report(company_name, report)
            logger.info(f"「{company_name}」分析报告已推送到飞书")
        else:
            sender.send_error_notice(
                company_name,
                "未能获取到相关信息，请检查公司名称是否正确。"
            )

    except ValueError as e:
        logger.error(f"配置错误: {e}")
        try:
            from .feishu_webhook import FeishuWebhookSender
            sender = FeishuWebhookSender()
            sender.send_error_notice(company_name, str(e))
        except Exception:
            pass

    except Exception as e:
        logger.error(f"分析任务执行失败 [{company_name}]: {e}", exc_info=True)
        try:
            from .feishu_webhook import FeishuWebhookSender
            sender = FeishuWebhookSender()
            sender.send_error_notice(company_name, str(e))
        except Exception:
            pass
