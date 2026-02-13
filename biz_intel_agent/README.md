# 企业经营洞察与招聘预算分析 Agent

嵌入飞书的智能分析 Agent，用户在飞书中输入客户名称，自动采集企业经营信息并分析招聘预算，输出结构化的销售拓展洞察报告。

## 功能特性

- **飞书机器人集成**：直接在飞书中与 Agent 对话，输入公司名称即可获取分析报告
- **多维度信息采集**：自动从搜索引擎、新闻、招聘平台等公开渠道采集企业信息
- **LLM 智能分析**：基于采集数据，由大语言模型生成专业的分析报告
- **招聘预算分析**：重点分析企业招聘需求、薪资水平、人才缺口等信息
- **飞书卡片消息**：以精美的飞书交互卡片形式展示报告，阅读体验好

## 分析维度

基于 SKILL.md 定义的分析框架：

| 维度 | 内容 |
|------|------|
| 客户财务实力 | 营收增长率、利润率、融资轮次、投资金额、公司规模 |
| 业务机会 | 核心业务、战略方向、新产品发布、重大成果 |
| 招聘预算分析 | 在招职位数、薪资范围、重点部门、人才缺口、招聘紧迫度 |
| 销售策略建议 | 关键决策人、竞争格局、价值主张、风险评估 |

## 架构设计

```
用户 (飞书) → 飞书开放平台 → Django 事件回调接口
                                    ↓
                              feishu_bot.py (事件处理)
                                    ↓
                              agent.py (分析引擎)
                              ├── 模式A: LLM 联网搜索 (推荐，如 Kimi K2.5)
                              └── 模式B: company_researcher.py 采集 → LLM 分析
                                    ↓
                              飞书卡片消息 → 用户 (飞书)
```

### 模块说明

| 文件 | 功能 |
|------|------|
| `config.py` | 配置管理（飞书凭证、LLM 参数、搜索配置） |
| `feishu_bot.py` | 飞书机器人（事件接收、消息发送、卡片消息） |
| `company_researcher.py` | 企业信息采集（搜索引擎、新闻、招聘信息） |
| `agent.py` | 核心分析引擎（LLM 分析、报告生成） |
| `views.py` | Django 视图（HTTP 接口） |
| `urls.py` | URL 路由配置 |

## 部署步骤

### 1. 安装依赖

```bash
pip install -r biz_intel_agent/requirements.txt
```

### 2. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app) 创建一个企业自建应用
2. 在"应用能力"中开启 **机器人** 能力
3. 在"事件订阅"中：
   - 设置请求地址为: `https://<your-domain>/api/feishu/event`
   - 添加事件: `im.message.receive_v1`（接收消息）
4. 在"权限管理"中，开通以下权限：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message:send_as_bot`（以应用的身份发送消息）
5. 发布应用版本并完成审批

### 3. 配置环境变量

```bash
# 飞书应用凭证（必填）
export FEISHU_APP_ID="cli_xxxxx"
export FEISHU_APP_SECRET="xxxxx"
export FEISHU_VERIFICATION_TOKEN="xxxxx"

# 飞书事件加密密钥（可选）
export FEISHU_ENCRYPT_KEY=""

# LLM API 配置（必填）
# 推荐使用 Kimi K2.5（支持联网搜索，效果最佳）
export LLM_API_KEY="sk-xxxxx"
export LLM_BASE_URL="https://api.moonshot.cn/v1"
export LLM_MODEL="kimi-k2.5"

# 其他 LLM 选项：
# DeepSeek:
#   export LLM_BASE_URL="https://api.deepseek.com"
#   export LLM_MODEL="deepseek-chat"
# OpenAI:
#   export LLM_BASE_URL="https://api.openai.com/v1"
#   export LLM_MODEL="gpt-4o-mini"
```

### 4. 启动服务

```bash
python manage.py runserver 0.0.0.0:80
```

### 5. 验证

- 健康检查: `curl http://localhost/api/feishu/health`
- 在飞书中找到你的机器人，发送一个公司名称（如"腾讯"），等待分析报告返回

## 使用方法

在飞书中与机器人对话：

1. **私聊**：直接发送公司名称
   - 示例：`腾讯`
   - 示例：`字节跳动`

2. **群聊**：@机器人 + 公司名称
   - 示例：`@分析助手 宁德时代`

3. **帮助**：发送 `帮助` 或 `help` 查看使用说明

## 输出示例

```
📋 腾讯公司 - 销售拓展洞察报告

┌─────────────────────────────────────┐
│ 核心客户信息                         │
├──────────────┬──────────────────────┤
│ 公司规模      │ 约10万人              │
│ 财务状况      │ 2024年营收6603亿元    │
│ 核心业务      │ 社交、游戏、金融科技   │
│ 近期重大成果  │ AI大模型发布、海外扩张 │
├──────────────┴──────────────────────┤
│ 招聘与预算分析                       │
├──────────────┬──────────────────────┤
│ 在招职位数量  │ 500+ 个               │
│ 重点招聘部门  │ AI研发、国际化业务     │
│ 招聘预算评估  │ 预算充足，高薪岗位多   │
│ 人才缺口      │ 算法工程师、产品经理   │
└──────────────┴──────────────────────┘
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/feishu/event` | POST | 飞书事件订阅回调 |
| `/api/feishu/health` | GET | 健康检查 |

## 技术栈

- **后端框架**: Django
- **LLM**: Kimi K2.5 / DeepSeek / OpenAI（兼容 OpenAI API 格式）
- **信息采集**: BeautifulSoup + Requests
- **飞书集成**: 飞书开放平台 API v2
