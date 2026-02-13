"""
URL 路由配置 - 企业经营洞察 Agent
URL Configuration for Business Intelligence Agent

路由表：
  GET  /analyze            -> 网页表单（输入公司名称）
  POST /analyze            -> 提交分析请求（表单/Ajax）
  POST /api/analyze        -> JSON API（程序调用，异步）
  POST /api/analyze/sync   -> JSON API（同步，直接返回结果）
  GET  /api/feishu/health  -> 健康检查
"""

from django.urls import path

from . import views

# app_name 用于 URL 反向解析的命名空间
app_name = "biz_intel_agent"

urlpatterns = [
    # 网页分析页面（GET 展示表单，POST 提交分析）
    path("analyze", views.analyze_view, name="analyze"),

    # JSON API - 异步分析（结果推送飞书）
    path("api/analyze", views.api_analyze, name="api_analyze"),

    # JSON API - 同步分析（直接返回结果）
    path("api/analyze/sync", views.api_analyze_sync, name="api_analyze_sync"),

    # 健康检查
    path("api/feishu/health", views.health_check, name="health_check"),
]
