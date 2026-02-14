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
# CSV 招聘数据配置
# CSV Recruitment Data Configuration
# ============================================================
# 客户职位信息 CSV 文件路径
# 必需列: 客户名称, 渠道, 年薪下限, 年薪上限
# 可选列: 一级职能, 职位名称, 工作地点
# 可通过环境变量或上传文件配置

# 默认路径优先级：
#   1. 环境变量 CSV_FILE_PATH（最高优先级）
#   2. biz_intel_agent/data/客户职位信息.csv（通过 API 上传的位置）
#   3. data/客户职位信息.csv（手动放置到仓库 data 目录）
_CSV_CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "客户职位信息.csv"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "客户职位信息.csv"),
]

def _resolve_csv_path() -> str:
    """按优先级查找可用的 CSV 文件路径"""
    env_path = os.environ.get("CSV_FILE_PATH", "")
    if env_path:
        return env_path
    for p in _CSV_CANDIDATE_PATHS:
        if os.path.exists(p):
            return os.path.abspath(p)
    # 返回默认路径（即使不存在，运行时会 warning）
    return _CSV_CANDIDATE_PATHS[0]

CSV_FILE_PATH = _resolve_csv_path()

# ============================================================
# 日志配置
# Logging Configuration
# ============================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
