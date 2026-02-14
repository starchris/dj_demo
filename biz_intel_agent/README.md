# 企业经营洞察与招聘预算分析 Agent

基于飞书 Webhook 的智能分析 Agent。用户通过**网页**或 **API** 输入客户名称，Agent 自动采集企业经营信息并分析招聘预算，将结构化的报告卡片推送到**飞书群**。

与 `news_catcher` 模块采用完全一致的飞书 Webhook 接入方式——只需在飞书群中添加一个自定义机器人，无需创建飞书开放平台应用，无需审批。

## 功能特性

- **Webhook 推送**：通过飞书群自定义机器人 Webhook 推送分析报告卡片，配置简单
- **网页表单**：访问 `/analyze` 页面，输入公司名称即可触发分析
- **API 接口**：支持 `POST /api/analyze` 程序化调用
- **命令行工具**：`python -m biz_intel_agent --analyze 公司名称` 直接在终端使用
- **LLM 智能分析**：基于采集数据，由大语言模型生成专业分析报告
- **联网搜索**：推荐使用 Kimi K2.5，支持联网搜索最新企业信息

## 分析维度

| 维度 | 内容 |
|------|------|
| 客户财务实力 | 营收增长率、利润率、融资轮次、投资金额、公司规模 |
| 业务机会 | 核心业务、战略方向、新产品发布、重大成果 |
| 招聘预算分析 | 在招职位数、薪资范围、重点部门、人才缺口、招聘紧迫度 |
| 销售策略建议 | 关键决策人、竞争格局、价值主张、风险评估 |

## 架构设计

```
                   ┌─────────────────────┐
                   │   用户输入公司名称    │
                   └─────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        网页 /analyze    API /api/analyze   命令行 CLI
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                    agent.py (分析引擎)
                    ├── 模式A: LLM 联网搜索 (Kimi K2.5)
                    └── 模式B: company_researcher 采集 → LLM 分析
                             │
                             ▼
                  feishu_webhook.py (Webhook 推送)
                             │
                             ▼
                     飞书群 (卡片消息)
```

### 模块说明

| 文件 | 功能 |
|------|------|
| `config.py` | 配置管理（Webhook URL、LLM 参数、搜索配置） |
| `feishu_webhook.py` | 飞书 Webhook 发送（文本消息、报告卡片、状态通知） |
| `company_researcher.py` | 企业信息采集（搜索引擎、新闻、招聘信息） |
| `agent.py` | 核心分析引擎（LLM 分析、报告生成） |
| `views.py` | Django 视图（网页表单 + API 接口） |
| `urls.py` | URL 路由配置 |
| `__main__.py` | 命令行工具 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r biz_intel_agent/requirements.txt
```

### 2. 在飞书群添加自定义机器人

1. 打开飞书，进入一个群聊
2. 点击群设置 → 群机器人 → 添加机器人 → **自定义机器人**
3. 填写机器人名称（如"企业分析助手"）
4. 复制 **Webhook 地址**（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx`）
5. 如需安全校验，可开启"签名校验"并记下密钥

### 3. 配置环境变量

```bash
# 飞书 Webhook（必填）
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"

# LLM API（必填，推荐 Kimi K2.5）
export LLM_API_KEY="sk-xxxxx"
export LLM_BASE_URL="https://api.moonshot.cn/v1"
export LLM_MODEL="kimi-k2.5"
```

### 4. 测试 Webhook 连接

```bash
python -m biz_intel_agent --test-webhook
```

如果飞书群收到了测试消息，说明配置正确。

### 5. 使用

有三种使用方式：

#### 方式一：命令行

```bash
# 分析并推送到飞书群
python -m biz_intel_agent --analyze 腾讯

# 仅在终端展示（不推送飞书）
python -m biz_intel_agent --analyze 字节跳动 --no-feishu

# 仅采集公开信息（不调用 LLM）
python -m biz_intel_agent --research 宁德时代
```

#### 方式二：网页表单

```bash
# 启动 Django 服务
python manage.py runserver 0.0.0.0:80

# 浏览器访问
open http://localhost/analyze
```

在页面输入公司名称，点击"开始分析"，报告会推送到飞书群。

#### 方式三：API 调用

```bash
# 异步分析（立即返回，结果推送飞书）
curl -X POST http://localhost/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"company": "腾讯"}'

# 同步分析（等待结果返回）
curl -X POST http://localhost/api/analyze/sync \
  -H "Content-Type: application/json" \
  -d '{"company": "腾讯", "send_feishu": true}'
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/analyze` | GET | 网页表单页面 |
| `/analyze` | POST | 提交分析请求（异步） |
| `/api/analyze` | POST | JSON API，异步分析 |
| `/api/analyze/sync` | POST | JSON API，同步返回结果 |
| `/api/feishu/health` | GET | 健康检查 |

## 飞书卡片效果

分析完成后，飞书群中会收到一张精美的交互卡片：

```
┌──────────────────────────────────────────┐
│ 📋 腾讯公司 - 销售拓展洞察报告             │
├──────────────────────────────────────────┤
│ 📊 以下为「腾讯公司」的企业经营洞察...      │
├──────────────────────────────────────────┤
│ ## 核心客户信息                            │
│ | 公司规模 | 约10万人 |                    │
│ | 财务状况 | 2024年营收6603亿元 |          │
│ | 核心业务 | 社交、游戏、金融科技 |          │
├──────────────────────────────────────────┤
│ ## 招聘与预算分析                          │
│ | 在招职位 | 500+ 个 |                    │
│ | 薪资水平 | 核心岗位月薪3-8万 |           │
│ | 人才缺口 | 算法工程师、产品经理 |          │
├──────────────────────────────────────────┤
│ ## 业务发展方向                            │
│ - 战略重点：AI大模型、国际化               │
├──────────────────────────────────────────┤
│ ## 销售策略建议                            │
│ - 接触点：HR VP、技术总监                  │
├──────────────────────────────────────────┤
│ 🕐 2025-02-13 12:00:00 | Agent           │
└──────────────────────────────────────────┘
```

## 技术栈

- **后端框架**: Django 3.2
- **LLM**: Kimi K2.5 / DeepSeek / OpenAI（兼容 OpenAI API 格式）
- **信息采集**: BeautifulSoup + Requests（百度搜索 + 百度新闻）
- **飞书集成**: 自定义机器人 Webhook（与 news_catcher 一致）
