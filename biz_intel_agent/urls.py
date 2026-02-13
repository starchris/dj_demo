"""
URL 路由配置 - 企业经营洞察 Agent
URL Configuration for Business Intelligence Agent

路由表：
  POST /api/feishu/event   -> 飞书事件订阅回调
  GET  /api/feishu/health  -> 健康检查
"""

from django.urls import path

from . import views

# app_name 用于 URL 反向解析的命名空间
app_name = "biz_intel_agent"

urlpatterns = [
    # 飞书事件订阅回调（核心接口）
    path("api/feishu/event", views.feishu_event_callback, name="feishu_event"),

    # 健康检查
    path("api/feishu/health", views.health_check, name="health_check"),
]
