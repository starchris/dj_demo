"""
配置文件 - 企业经营洞察与招聘预算分析 Agent
Configuration for Business Intelligence Agent

飞书机器人配置 + LLM 配置 + 搜索配置
"""

import os

# ============================================================
# 飞书应用配置 (Feishu/Lark App Configuration)
# ============================================================
# 在飞书开放平台创建应用后获取: https://open.feishu.cn/app
# 需要开启"机器人"能力，并配置事件订阅

# 飞书应用凭证
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# 飞书事件订阅验证 Token（在"事件订阅"页面获取）
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

# 飞书事件订阅加密密钥（可选，在"事件订阅"页面设置）
FEISHU_ENCRYPT_KEY = os.environ.get("FEISHU_ENCRYPT_KEY", "")

# 飞书 API 基础地址
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

# ============================================================
# LLM 配置（用于企业分析报告生成）
# LLM Configuration for Business Intelligence Analysis
# ============================================================
# 支持所有兼容 OpenAI API 格式的服务
# 推荐使用 Kimi K2.5（支持联网搜索）或 DeepSeek

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.moonshot.cn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "kimi-k2.5")

# 常见配置示例：
#   Kimi K2.5:  LLM_BASE_URL=https://api.moonshot.cn/v1       LLM_MODEL=kimi-k2.5
#   DeepSeek:   LLM_BASE_URL=https://api.deepseek.com         LLM_MODEL=deepseek-chat
#   OpenAI:     LLM_BASE_URL=https://api.openai.com/v1        LLM_MODEL=gpt-4o-mini
#   智谱:       LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4   LLM_MODEL=glm-4-flash

# ============================================================
# 搜索配置
# Search Configuration
# ============================================================

# 请求超时时间（秒）
REQUEST_TIMEOUT = 15

# 请求头配置
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 每个搜索维度最大结果数
MAX_SEARCH_RESULTS = 10

# ============================================================
# 日志配置
# Logging Configuration
# ============================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
