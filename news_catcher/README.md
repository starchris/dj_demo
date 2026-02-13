# 🔥 热点新闻捕捉器 - 十五五规划重点行业动态

每日自动捕捉中国十五五规划重点行业的热点新闻，并通过飞书 Webhook 推送至指定群聊。

## 📋 功能特性

- **多源抓取**：从百度新闻、Bing 新闻、RSS 订阅等多个来源抓取新闻
- **智能匹配**：基于关键词自动匹配十五五规划重点行业
- **自动去重**：基于标题相似度自动去除重复新闻
- **飞书推送**：支持交互卡片和富文本两种消息格式
- **定时执行**：支持每日定时自动执行
- **本地备份**：自动将抓取的新闻保存为 JSON 文件

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

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r news_catcher/requirements.txt
```

### 2. 配置飞书 Webhook

在飞书群聊中添加自定义机器人，获取 Webhook URL。

**方式一：环境变量（推荐）**

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook_id"
# 可选：如果设置了签名校验
export FEISHU_WEBHOOK_SECRET="你的签名密钥"
```

**方式二：修改配置文件**

编辑 `news_catcher/config.py`，填写 `FEISHU_WEBHOOK_URL`。

### 3. 运行

```bash
# 测试模式（仅抓取新闻，不发送到飞书）
python -m news_catcher --test

# 立即运行一次（抓取 + 发送到飞书）
python -m news_catcher --run-once

# 测试飞书连接
python -m news_catcher --test-feishu

# 启动定时任务（每日自动执行）
python -m news_catcher --schedule

# 指定 Webhook URL 运行
python -m news_catcher --run-once --webhook-url "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

## ⏰ 定时任务配置

### 方式一：使用内置调度器

```bash
python -m news_catcher --schedule
```

默认每日 8:30 执行，可在 `config.py` 中修改 `SCHEDULE_HOUR` 和 `SCHEDULE_MINUTE`。

### 方式二：使用系统 Crontab（推荐生产环境）

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天早上 8:30 执行）
30 8 * * * cd /path/to/project && /path/to/python -m news_catcher --run-once >> /var/log/news_catcher.log 2>&1
```

### 方式三：使用 Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY news_catcher/ ./news_catcher/
RUN pip install -r news_catcher/requirements.txt
ENV FEISHU_WEBHOOK_URL=""
CMD ["python", "-m", "news_catcher", "--schedule"]
```

## 📁 项目结构

```
news_catcher/
├── __init__.py          # 包初始化
├── __main__.py          # 入口（python -m news_catcher）
├── config.py            # 配置文件（行业关键词、飞书Webhook等）
├── news_fetcher.py      # 新闻抓取模块
├── feishu_notifier.py   # 飞书通知模块
├── main.py              # 主程序（调度、命令行）
├── requirements.txt     # Python 依赖
├── README.md            # 说明文档
├── data/                # 新闻数据备份（自动生成）
└── logs/                # 运行日志（自动生成）
```

## ⚙️ 配置说明

### 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `FEISHU_WEBHOOK_URL` | 飞书自定义机器人 Webhook URL | 是 |
| `FEISHU_WEBHOOK_SECRET` | 飞书签名密钥 | 否 |
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR） | 否（默认 INFO） |

### 自定义行业关键词

编辑 `config.py` 中的 `INDUSTRIES` 字典，可以自由添加、删除或修改行业及其关键词。

### 自定义新闻源

编辑 `config.py` 中的 `RSS_FEEDS` 字典，添加新的 RSS 订阅源。

## 📱 飞书消息效果

发送到飞书的消息以**交互卡片**形式展示，包含：

- 📋 新闻标题（可点击跳转原文）
- 📰 新闻来源
- 🕐 发布时间
- 📊 行业分类统计

## ❗ 注意事项

1. 首次使用请先运行 `--test` 模式确认新闻抓取正常
2. 然后运行 `--test-feishu` 确认飞书 Webhook 连接正常
3. 新闻抓取依赖网络，如遇访问限制，程序会自动跳过失败的源
4. RSS 源基于 RSSHub，如 RSSHub 不可用可自行部署或替换为其他源
5. 建议在服务器上使用 crontab 部署，稳定性优于内置调度器

## 📄 License

MIT
