"""
配置文件 - 企业经营洞察与招聘预算分析 Agent
Configuration for Business Intelligence Agent

飞书 Webhook 配置 + LLM 配置 + 搜索配置

与 news_catcher 模块采用相同的 Webhook 方式接入飞书，
只需在飞书群中添加"自定义机器人"即可，无需创建飞书开放平台应用。
"""

import os

# ============================================================
# 飞书 Webhook 配置（与 news_catcher 保持一致的接入方式）
# Feishu Webhook Configuration
# ============================================================
# 在飞书群聊中添加"自定义机器人"，获取 Webhook URL
# 步骤：群设置 → 群机器人 → 添加机器人 → 自定义机器人

FEISHU_WEBHOOK_URL = os.environ.get(
    "FEISHU_WEBHOOK_URL",
    ""  # 通过环境变量配置，格式: https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx
)

# 飞书 Webhook 签名密钥（可选，在自定义机器人设置中的"安全设置"开启签名校验后获取）
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

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
