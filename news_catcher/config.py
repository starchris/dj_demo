"""
配置文件 - 热点新闻捕捉器
Configuration for Hot News Catcher

十五五规划重点行业关键词和飞书Webhook配置
"""

import os

# ============================================================
# 飞书 Webhook 配置
# Feishu Webhook Configuration
# ============================================================
# 请将飞书自定义机器人的 Webhook URL 设置为环境变量
# 或直接在此处填写（不推荐提交到版本控制）
FEISHU_WEBHOOK_URL = os.environ.get(
    "FEISHU_WEBHOOK_URL",
    ""  # 通过环境变量或 GitHub Secrets 配置
)

# 飞书 Webhook 签名密钥（可选，如果机器人设置了签名校验）
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

# ============================================================
# 十五五规划重点行业关键词
# Key Industries & Keywords for 15th Five-Year Plan
# ============================================================
INDUSTRIES = {
    "人工智能": {
        "keywords": ["人工智能", "AI大模型", "深度学习", "机器学习", "AIGC", "生成式AI", "智能算力", "大语言模型"],
        "emoji": "🤖"
    },
    "半导体与芯片": {
        "keywords": ["半导体", "芯片", "集成电路", "光刻机", "EDA", "先进封装", "晶圆", "国产芯片"],
        "emoji": "💾"
    },
    "新能源": {
        "keywords": ["新能源", "光伏", "风电", "储能", "氢能", "新能源汽车", "动力电池", "充电桩"],
        "emoji": "⚡"
    },
    "生物医药": {
        "keywords": ["生物医药", "创新药", "基因治疗", "细胞治疗", "mRNA", "医疗器械", "精准医疗"],
        "emoji": "💊"
    },
    "数字经济": {
        "keywords": ["数字经济", "数字化转型", "工业互联网", "数据要素", "智慧城市", "数字基建", "数字产业"],
        "emoji": "📊"
    },
    "高端装备制造": {
        "keywords": ["智能制造", "工业机器人", "高端装备", "数控机床", "3D打印", "机器人产业", "柔性制造"],
        "emoji": "🏭"
    },
    "航空航天": {
        "keywords": ["航空航天", "商业航天", "卫星互联网", "低空经济", "无人机", "大飞机", "航空发动机"],
        "emoji": "🚀"
    },
    "新材料": {
        "keywords": ["新材料", "碳纤维", "石墨烯", "稀土", "先进陶瓷", "超导材料", "纳米材料", "新材料产业"],
        "emoji": "🧪"
    },
    "绿色低碳": {
        "keywords": ["绿色低碳", "碳中和", "碳达峰", "碳交易", "新能源 碳排放", "ESG", "清洁能源", "节能减排"],
        "emoji": "🌿"
    },
    "量子科技": {
        "keywords": ["量子计算", "量子通信", "量子科技", "量子芯片", "量子计算机", "量子技术"],
        "emoji": "⚛️"
    },
}

# ============================================================
# 新闻源配置
# News Source Configuration
# ============================================================

# 每个行业抓取的最大新闻数
MAX_NEWS_PER_INDUSTRY = 5

# 总共发送的最大新闻条数
MAX_TOTAL_NEWS = 50

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

# RSS 新闻源列表
# 注意：rsshub.app 公共实例不稳定，优先使用官方 RSS 源
RSS_FEEDS = {
    "36氪": "https://36kr.com/feed",
    "IT之家": "https://www.ithome.com/rss/",
    "cnBeta": "https://www.cnbeta.com.tw/backend.php",
    "少数派": "https://sspai.com/feed",
}

# ============================================================
# 定时任务配置
# Scheduling Configuration
# ============================================================

# 每日执行时间（24小时制，北京时间）
SCHEDULE_HOUR = 9
SCHEDULE_MINUTE = 30

# 时区
TIMEZONE = "Asia/Shanghai"

# ============================================================
# LLM 配置（用于行业动态总结）
# LLM Configuration for Industry Summary Generation
# ============================================================
# 支持所有兼容 OpenAI API 格式的服务：DeepSeek / Moonshot / OpenAI / 智谱 等
# 默认使用 DeepSeek（性价比高、中文能力强）

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.moonshot.cn/v1")  # Kimi (Moonshot)
LLM_MODEL = os.environ.get("LLM_MODEL", "kimi-k2.5")

# 常见配置示例：
#   Kimi:       LLM_BASE_URL=https://api.moonshot.cn/v1       LLM_MODEL=kimi-k2.5
#   DeepSeek:   LLM_BASE_URL=https://api.deepseek.com         LLM_MODEL=deepseek-chat
#   Moonshot:   LLM_BASE_URL=https://api.moonshot.cn/v1       LLM_MODEL=moonshot-v1-8k
#   OpenAI:     LLM_BASE_URL=https://api.openai.com/v1        LLM_MODEL=gpt-4o-mini
#   智谱:       LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4   LLM_MODEL=glm-4-flash

# ============================================================
# 日志配置
# Logging Configuration
# ============================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
