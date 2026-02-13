"""
企业经营洞察分析 Agent - 核心分析引擎
Business Intelligence Analysis Agent - Core Analysis Engine

基于 SKILL.md 定义的"商业情报分析师 & 资深猎头"角色，
通过 LLM + 公开信息采集，生成企业经营与招聘预算分析报告。

分析维度（来自 SKILL.md）：
  1. 客户财务实力（营收、利润、融资、规模）
  2. 业务机会（核心业务、战略方向、重大成果）
  3. 招聘预算分析（职位数量、薪资范围、人才缺口、招聘紧迫度）
  4. 销售策略匹配（决策人、竞争格局、风险评估）

两种工作模式：
  模式A（推荐）: LLM 自带联网搜索（如 Kimi K2.5）
    -> 直接让 LLM 搜索并分析，效果最佳
  模式B（回退）: 先通过 company_researcher 采集信息，再喂给 LLM 分析
    -> 适用于不支持联网搜索的 LLM
"""

import logging
import re

from openai import OpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .company_researcher import CompanyResearcher

logger = logging.getLogger("biz_intel_agent.agent")

# ============================================================
# Prompt 模板 - 基于 SKILL.md 的角色定义
# ============================================================

SYSTEM_PROMPT = """你是一位拥有10年经验的商业情报分析师和资深猎头，擅长通过公开渠道（财报、投融资平台、企业官网、招聘网站）提供以销售为导向的企业洞察。

你的核心能力：
1. 通过公开信息识别商业机会和客户潜力
2. 分析企业的人才预算和招聘策略
3. 为销售团队提供可执行的拓展建议

分析原则：
- 所有分析必须基于公开可查证的信息
- 提及具体数字、企业名称、产品名称时务必准确
- 如果某项信息无法确认，明确标注"待确认"而非编造
- 重点关注对销售团队有价值的信息"""

# 模式A: LLM 联网搜索模式的 prompt
ANALYSIS_PROMPT_WITH_SEARCH = """请对「{company_name}」进行全面的企业经营洞察分析。

**请通过联网搜索获取以下信息，并生成分析报告：**

### 需要搜索和分析的维度：

1. **客户财务实力**
   - 如果是上市公司：搜索最新财报，关注营收增长率、利润率、财务稳定性
   - 如果是非上市公司：搜索融资轮次、投资金额、投资方质量，评估现金流和预算能力
   - 估算公司规模（员工人数）和增长轨迹

2. **业务机会**
   - 识别核心业务领域和近期扩张/新产品发布
   - 分析战略方向（国际化、AI转型、成本优化等）
   - 搜索重大业务成果和市场地位

3. **招聘预算分析**（重点）
   - 搜索该公司在各大招聘平台（Boss直聘、猎聘、前程无忧等）的在招职位
   - 分析职位数量、薪资范围、重点招聘部门
   - 评估招聘预算水平和人才缺口
   - 判断招聘紧迫度

4. **销售策略匹配**
   - 识别关键决策人（HR负责人、业务主管）
   - 分析竞争格局，定位独特价值主张
   - 评估风险因素和决策周期

### 输出格式要求：

请严格按以下 Markdown 格式输出报告：

# {company_name} - 销售拓展洞察报告

## 核心客户信息
| 指标 | 详情 |
|------|------|
| 公司规模 | XX万人 |
| 融资/财务状况 | XX轮融资，XX亿元；营收增长XX% |
| 核心业务 | 业务1、业务2、业务3 |
| 近期重大成果 | 成果1、成果2 |

## 招聘与预算分析
| 维度 | 信息 |
|------|------|
| 在招职位数量 | XX个 |
| 重点招聘部门 | 部门1、部门2 |
| 招聘预算评估 | 高薪岗位占比XX%，预算充足/一般/紧张 |
| 人才缺口 | 岗位1、岗位2 |
| 薪资水平 | 核心岗位月薪XX-XX万 |
| 招聘紧迫度 | 高/中/低 |

## 业务发展方向
- 战略重点：XX、XX、XX
- 扩张领域：XX、XX、XX
- 合作机会：XX、XX

## 销售策略建议
- 接触点：XX、XX
- 价值主张：XX
- 竞争优势：XX
- 最佳切入时机：XX

## 风险评估
| 维度 | 评级 | 说明 |
|------|------|------|
| 财务风险 | 低/中/高 | 简要说明 |
| 决策周期 | 短/中/长 | 简要说明 |
| 预算确定性 | 高/中/低 | 简要说明 |
"""

# 模式B: 带采集数据的分析 prompt
ANALYSIS_PROMPT_WITH_DATA = """请基于以下采集到的公开信息，对「{company_name}」进行全面的企业经营洞察分析。

---
{research_data}
---

### 分析要求：

1. **客户财务实力**：基于搜索到的财务/融资信息，评估企业的资金实力和预算能力
2. **业务机会**：识别核心业务、战略方向、重大成果
3. **招聘预算分析**（重点）：基于招聘信息，分析职位数量、薪资水平、人才缺口、招聘紧迫度
4. **销售策略建议**：识别接触点、价值主张、切入时机

### 输出格式要求：

请严格按以下 Markdown 格式输出报告：

# {company_name} - 销售拓展洞察报告

## 核心客户信息
| 指标 | 详情 |
|------|------|
| 公司规模 | XX万人 |
| 融资/财务状况 | XX轮融资，XX亿元；营收增长XX% |
| 核心业务 | 业务1、业务2、业务3 |
| 近期重大成果 | 成果1、成果2 |

## 招聘与预算分析
| 维度 | 信息 |
|------|------|
| 在招职位数量 | XX个 |
| 重点招聘部门 | 部门1、部门2 |
| 招聘预算评估 | 高薪岗位占比XX%，预算充足/一般/紧张 |
| 人才缺口 | 岗位1、岗位2 |
| 薪资水平 | 核心岗位月薪XX-XX万 |
| 招聘紧迫度 | 高/中/低 |

## 业务发展方向
- 战略重点：XX、XX、XX
- 扩张领域：XX、XX、XX
- 合作机会：XX、XX

## 销售策略建议
- 接触点：XX、XX
- 价值主张：XX
- 竞争优势：XX
- 最佳切入时机：XX

## 风险评估
| 维度 | 评级 | 说明 |
|------|------|------|
| 财务风险 | 低/中/高 | 简要说明 |
| 决策周期 | 短/中/长 | 简要说明 |
| 预算确定性 | 高/中/低 | 简要说明 |

**重要**：
- 所有分析必须基于上方提供的搜索结果信息
- 无法确认的信息请标注"待确认"
- 不要编造数据或信息
"""


def _clean_thinking_tags(text: str) -> str:
    """
    清除 LLM 返回内容中的思考标签

    Kimi K2.5 等思考模型会在回复中包含 <think>...</think> 标签，
    需要去除思考过程，只保留最终输出
    """
    # 移除 <think>...</think> 块
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 移除可能残留的未闭合 <think> 标签
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    # 移除 markdown 代码块包裹
    cleaned = re.sub(r'^```[a-z]*\n?', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```$', '', cleaned.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def _is_search_capable_model(model: str) -> bool:
    """
    判断 LLM 模型是否支持联网搜索

    支持联网搜索的模型可以直接让 LLM 搜索最新信息，
    效果通常优于我们自行采集后再喂给 LLM
    """
    model_lower = model.lower()
    # Kimi K2.5 / Kimi 系列支持联网搜索
    if "kimi" in model_lower:
        return True
    # 有些模型名包含 search 或 online 标识
    if "search" in model_lower or "online" in model_lower:
        return True
    return False


class BusinessIntelAgent:
    """
    企业经营洞察分析 Agent

    核心分析引擎，接收公司名称，输出完整的分析报告。
    自动选择最优的工作模式：
    - 如果 LLM 支持联网搜索，直接让 LLM 搜索并分析
    - 否则先通过 CompanyResearcher 采集信息，再交给 LLM 分析
    """

    def __init__(self):
        if not LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY 未配置！请设置环境变量 LLM_API_KEY。\n"
                "推荐使用 Kimi K2.5（支持联网搜索，效果最佳）。\n"
                "获取 API Key: https://platform.moonshot.cn"
            )

        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL
        self.use_search = _is_search_capable_model(self.model)
        self.researcher = CompanyResearcher()

        logger.info(
            f"BusinessIntelAgent 初始化完成 "
            f"(model={self.model}, search_mode={'LLM联网搜索' if self.use_search else '手动采集+LLM分析'})"
        )

    def analyze(self, company_name: str) -> str:
        """
        分析指定公司的经营信息和招聘预算

        Args:
            company_name: 公司名称

        Returns:
            Markdown 格式的分析报告；分析失败返回空字符串
        """
        logger.info(f"开始分析「{company_name}」...")

        try:
            if self.use_search:
                # 模式A: LLM 联网搜索模式
                report = self._analyze_with_search(company_name)
            else:
                # 模式B: 手动采集 + LLM 分析
                report = self._analyze_with_research(company_name)

            if report:
                logger.info(f"「{company_name}」分析完成，报告长度: {len(report)} 字")
            else:
                logger.warning(f"「{company_name}」分析未生成有效报告")

            return report

        except Exception as e:
            logger.error(f"分析「{company_name}」失败: {e}", exc_info=True)
            return ""

    def _analyze_with_search(self, company_name: str) -> str:
        """
        模式A: 使用 LLM 联网搜索能力直接分析

        适用于 Kimi K2.5 等支持联网搜索的模型，
        由 LLM 自行搜索最新信息并生成报告
        """
        logger.info(f"使用 LLM 联网搜索模式分析「{company_name}」")

        user_prompt = ANALYSIS_PROMPT_WITH_SEARCH.format(company_name=company_name)

        # 构建请求参数
        create_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
        }

        # Kimi K2.5 是思考模型，temperature 必须为 1
        model_lower = self.model.lower()
        is_thinking_model = ("kimi" in model_lower and "k2" in model_lower)

        if is_thinking_model:
            create_kwargs["temperature"] = 1.0
            create_kwargs["max_tokens"] = 8192  # 思考过程 + 搜索 + 回答需要更多空间
        else:
            create_kwargs["temperature"] = 0.3

        # 为 Kimi 模型启用联网搜索工具
        if "kimi" in model_lower:
            create_kwargs["tools"] = [{"type": "web_search"}]

        response = self.client.chat.completions.create(**create_kwargs)
        raw_content = response.choices[0].message.content or ""

        report = _clean_thinking_tags(raw_content)
        return report

    def _analyze_with_research(self, company_name: str) -> str:
        """
        模式B: 先手动采集信息，再交给 LLM 分析

        1. 通过 CompanyResearcher 从搜索引擎采集各维度信息
        2. 将采集结果作为上下文喂给 LLM
        3. LLM 基于采集数据生成分析报告
        """
        logger.info(f"使用手动采集+LLM分析模式处理「{company_name}」")

        # Step 1: 采集企业信息
        research_data = self.researcher.research(company_name)

        if not research_data.has_data:
            logger.warning(f"「{company_name}」未采集到有效信息")
            # 仍然尝试让 LLM 基于自身知识分析
            research_text = f"未能从搜索引擎采集到「{company_name}」的相关信息。请基于你的知识库进行分析，并明确标注哪些信息需要进一步确认。"
        else:
            research_text = research_data.to_prompt_text()

        # Step 2: LLM 分析
        user_prompt = ANALYSIS_PROMPT_WITH_DATA.format(
            company_name=company_name,
            research_data=research_text,
        )

        create_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.3,
        }

        # 处理思考模型
        model_lower = self.model.lower()
        is_thinking_model = (
            ("kimi" in model_lower and "k2" in model_lower) or
            ("deepseek" in model_lower and "reasoner" in model_lower)
        )
        if is_thinking_model:
            create_kwargs["temperature"] = 1.0
            create_kwargs["max_tokens"] = 8192

        response = self.client.chat.completions.create(**create_kwargs)
        raw_content = response.choices[0].message.content or ""

        report = _clean_thinking_tags(raw_content)
        return report
