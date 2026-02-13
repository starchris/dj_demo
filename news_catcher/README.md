# 🔥 热点新闻捕捉器 - 十五五规划重点行业动态

每日自动捕捉中国十五五规划重点行业的热点新闻，**生成行业动态要点总结**，并通过飞书 Webhook 推送至指定群聊。

## 📋 功能特性

- **多源抓取**：从百度新闻、Bing 新闻、搜狗新闻、RSS 订阅等多个来源抓取新闻
- **AI 行业总结**：基于 LLM（DeepSeek/Moonshot/OpenAI）自动生成各行业动态要点
  - 覆盖维度：投融资动态、产品发布、技术突破、市场趋势、政策法规、人事变动
  - 无 LLM 时自动回退为标题摘要模式
- **智能匹配**：基于关键词自动匹配十五五规划重点行业
- **自动去重**：基于标题相似度自动去除重复新闻
- **飞书推送**：交互卡片格式，先看总结再点链接
- **定时执行**：支持每日定时自动执行
- **本地备份**：自动将新闻和总结保存为 JSON 文件

## 🏭 覆盖行业（十五五规划重点方向）

| 行业 | 关键词示例 |
|------|-----------|
| 🤖 人工智能 | AI大模型、深度学习、AIGC、生成式AI |
| 💾 半导体与芯片 | 半导体、芯片、集成电路、光刻机、EDA |
| ⚡ 新能源 | 光伏、风电、储能、氢能、动力电池 |
| 💊 生物医药 | 创新药、基因治疗、细胞治疗、mRNA |
| 📊 数字经济 | 数字化转型、工业互联网、数据要素 |
| 🏭 高端装备制造 | 智能制造、工业机器人、数控机床 |
| 🚀 航空航天 | 商业航天、卫星互联网、低空经济 |
| 🧪 新材料 | 碳纤维、石墨烯、稀土、超导材料 |
| 🌿 绿色低碳 | 碳中和、碳达峰、碳交易、ESG |
| ⚛️ 量子科技 | 量子计算、量子通信、量子芯片 |

## 📱 飞书消息效果

发送到飞书的消息以**交互卡片**形式展示，每个行业包含：

```
🤖 人工智能
· OpenAI 发布 GPT-5，推理能力大幅提升，已向企业客户开放测试
· 百度文心一言4.5上线，多模态能力对标GPT-4o
· 国内AI算力投资持续升温，多地发布智算中心建设规划
· 工信部发布AI+制造业指导意见，推动大模型在工业场景落地
📎 相关新闻
  1. OpenAI发布GPT-5...（来源）
  2. ...
```

**先看总结了解全貌，感兴趣再点链接看详情。**

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r news_catcher/requirements.txt
```

### 2. 配置飞书 Webhook

在飞书群聊中添加自定义机器人，获取 Webhook URL。

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook_id"
```

### 3. 配置 LLM（推荐，可选）

配置 LLM API 后总结效果会显著提升。推荐使用 [DeepSeek](https://platform.deepseek.com/)（便宜、中文好）。

```bash
# DeepSeek（默认，推荐）
export LLM_API_KEY="sk-你的deepseek密钥"

# 或 Moonshot（月之暗面）
export LLM_API_KEY="sk-你的moonshot密钥"
export LLM_BASE_URL="https://api.moonshot.cn/v1"
export LLM_MODEL="moonshot-v1-8k"

# 或 OpenAI
export LLM_API_KEY="sk-你的openai密钥"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"

# 或 智谱 GLM
export LLM_API_KEY="你的智谱密钥"
export LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export LLM_MODEL="glm-4-flash"
```

> 不配置 LLM 也能用，程序会自动回退为标题摘要模式。

### 4. 运行

```bash
# 测试模式（仅抓取和总结，不发送飞书）
python3 -m news_catcher --test

# 正式运行一次（抓取 + 总结 + 发送飞书）
python3 -m news_catcher --run-once

# 测试飞书连接
python3 -m news_catcher --test-feishu

# 启动定时任务（每日自动执行）
python3 -m news_catcher --schedule

# 命令行指定参数
python3 -m news_catcher --run-once --llm-key "sk-xxx" --webhook-url "https://..."
```

## ⏰ 定时任务

### 方式一：使用内置调度器

```bash
python3 -m news_catcher --schedule
```

默认每日 8:30 执行，可在 `config.py` 中修改。

### 方式二：Crontab（推荐）

```bash
crontab -e

# 每天 8:30 执行
30 8 * * * cd /path/to/project && LLM_API_KEY="sk-xxx" FEISHU_WEBHOOK_URL="https://..." /usr/bin/python3 -m news_catcher --run-once >> /var/log/news_catcher.log 2>&1
```

## 📁 项目结构

```
news_catcher/
├── __init__.py          # 包初始化
├── __main__.py          # python -m 入口
├── config.py            # 配置（行业、飞书、LLM、定时等）
├── news_fetcher.py      # 新闻抓取（百度/Bing/搜狗/RSS）
├── summarizer.py        # 行业动态总结（LLM / 回退摘要）
├── feishu_notifier.py   # 飞书通知（交互卡片）
├── main.py              # 主程序
├── requirements.txt     # 依赖
├── data/                # 新闻备份（自动生成）
└── logs/                # 日志（自动生成）
```

## ⚙️ 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | 是 |
| `FEISHU_WEBHOOK_SECRET` | 飞书签名密钥 | 否 |
| `LLM_API_KEY` | LLM API 密钥 | 否（推荐） |
| `LLM_BASE_URL` | LLM API 地址 | 否（默认 DeepSeek） |
| `LLM_MODEL` | LLM 模型名 | 否（默认 deepseek-chat） |
| `LOG_LEVEL` | 日志级别 | 否（默认 INFO） |

## 📄 License

MIT
