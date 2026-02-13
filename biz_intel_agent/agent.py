"""
企业招聘预算分析 Agent - 核心分析引擎
Company Recruitment Analyst Agent - Core Analysis Engine

基于 SKILL.md (company-recruitment-analyst) 定义的角色：
  资深商业情报分析师 + 招聘预算专家

通过 LLM + 公开信息采集，生成双报告输出：
  1. 完整招聘预算分析报告（商业背景 + 招聘数据 + 销售策略）
  2. 销售简报（30秒速览，关键数字 + 行动建议）

核心分析维度（来自 SKILL.md）：
  - 融资分析（轮次、金额、资金用途 → 人才招聘方向）
  - 招聘预算分析（渠道分布、薪资、猎聘占比、HR潜在预算）
  - 商业洞察与招聘关联（业务发展 ↔ 人才需求映射）
  - 销售策略建议（价值主张、行动计划、预期收益）
"""

import logging
import re

from openai import OpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .company_researcher import CompanyResearcher
from .csv_analyzer import CSVAnalyzer

logger = logging.getLogger("biz_intel_agent.agent")

# ============================================================
# Prompt 模板 - 对齐 SKILL.md (company-recruitment-analyst)
# ============================================================

SYSTEM_PROMPT = """你是一位资深商业情报分析师和招聘预算专家，擅长将公开商业信息与招聘数据结合，为销售团队提供全面的客户分析。

你的核心能力：
1. 深度分析企业融资信息，推断资金用途与人才招聘方向的关联
2. 评估企业招聘预算规模、渠道分布、猎聘占比
3. 为销售团队提供可执行的拓展策略和预期收益分析

融资→人才方向分析框架：
- 研发扩张 → 算法工程师、科学家、硬件工程师
- 市场扩张 → 销售、市场营销、BD
- 产品发布 → 产品经理、设计师、运营
- 地域扩张 → 本地化人才、运营管理
- 并购整合 → 整合专家、管理人才
- 产能建设 → 生产制造、供应链人才

分析原则：
- 所有分析必须基于公开可查证的信息
- 融资用途与人才需求的关联分析需标注"基于业务动态推断"
- 无法确认的信息明确标注"待确认"，不编造数据
- 重点关注对猎头销售团队有价值的信息"""

# ============================================================
# 完整分析报告 Prompt
# ============================================================

FULL_REPORT_PROMPT = """请基于以下采集到的公开信息，对「{company_name}」进行全面的招聘预算分析。

---
{research_data}
---

### 分析要求：

请严格按以下结构输出**完整招聘预算分析报告**：

# {company_name} - 完整招聘预算分析报告

## 一、公司商业背景

### 基本信息
| 指标 | 详情 |
|------|------|
| 公司规模 | XX人 |
| 所属行业 | XX |
| 成立时间 | XX年 |
| 总部地点 | XX |

### 融资情况与人才战略
| 融资轮次 | 金额 | 时间 | 投资方 | 资金用途 | 对应人才需求 |
|----------|------|------|--------|----------|--------------|
| X轮 | XX亿 | 20XX年X月 | XX基金/企业 | R&D/市场扩张/产品发布 | XX类人才 |

**融资用途与人才需求分析**（基于业务动态推断）：
- **技术研发方向** → 算法工程师、硬件工程师等（基于技术岗位占比推断）
- **市场扩张方向** → 销售、市场人才（基于业务拓展动态推断）
- **产能建设方向** → 生产、制造人才（基于订单/产能需求推断）
- **组织建设方向** → HR、财务等职能人才（基于团队规模推断）

> ⚠️ **说明**：以上分析为基于公开业务动态的行业推断，非企业官方披露数据，仅供参考。

### 核心业务
- （列出核心业务领域）

### 近期重大成果
- （列出近期重要里程碑、订单、合作等）

### 战略发展方向
- （分析未来发展方向和扩张领域）

## 二、招聘预算分析

### 总体规模
| 维度 | 数据 |
|------|------|
| 在招职位总数 | XX个 |
| 招聘薪酬预算（年） | 约XX亿元（估算） |
| 重点招聘部门 | XX、XX、XX |
| 核心人才缺口 | XX、XX |

### 渠道分布分析
| 渠道 | 职位数 | 占比 | 预算占比 |
|------|--------|------|----------|
| BOSS直聘 | XX | XX% | XX% |
| 猎聘 | XX | XX% | XX% |
| 其他渠道 | XX | XX% | XX% |

### 薪资预算分析
| 薪资段 | 职位数 | 占比 | 说明 |
|--------|--------|------|------|
| 50K+ | XX | XX% | 高端人才 |
| 30-50K | XX | XX% | 中高端人才 |
| 15-30K | XX | XX% | 中端人才 |
| 15K以下 | XX | XX% | 基础岗位 |

### 猎聘占比分析
| 维度 | 数值 |
|------|------|
| 猎聘职位占比 | XX% |
| 猎聘预算占比 | XX% |
| HR潜在预算（估算） | 约XX万元（计算方式：2个月月薪） |

### 职能分布
| 职能方向 | 职位数 | 占比 | 对应融资方向 |
|----------|--------|------|-------------|
| 技术研发 | XX | XX% | 研发投入 |
| 销售市场 | XX | XX% | 市场扩张 |
| 生产制造 | XX | XX% | 产能建设 |
| 职能支持 | XX | XX% | 组织建设 |

## 三、商业洞察与招聘关联

### 招聘与业务发展关联
- **融资驱动**：XX轮融资XX亿到位 → XX方向的人才需求激增
- **业务扩张**：XX业务线扩展 → 需要XX类人才
- **产能扩张**：XX订单/项目 → 需要XX类人才

### 招聘紧迫度评估
| 维度 | 评级 | 依据 |
|------|------|------|
| 资金到位情况 | ⭐⭐⭐⭐⭐ | 最近融资，资金充裕 |
| 业务扩张速度 | ⭐⭐⭐⭐ | XX业务快速增长 |
| 职位空缺规模 | ⭐⭐⭐⭐ | XX个职位同时招聘 |
| 综合紧迫度 | 高/中/低 | — |

## 四、销售策略建议

### 价值主张
- （针对该客户的核心价值主张）

### 行动计划
| 阶段 | 行动 | 目标 |
|------|------|------|
| 第1周 | XX | XX |
| 第2-4周 | XX | XX |
| 第2-3月 | XX | XX |

### 预期收益
| 时间维度 | 目标 |
|----------|------|
| 短期（1-3月） | XX |
| 中期（3-6月） | XX |
| 长期（6月+） | XX |

## 五、风险评估
| 维度 | 评级 | 说明 |
|------|------|------|
| 财务风险 | 低/中/高 | XX |
| 决策周期 | 短/中/长 | XX |
| 预算确定性 | 高/中/低 | XX |
| 竞争强度 | 低/中/高 | XX |

**重要提示**：
- 融资用途分析为基于公开业务动态的行业推断，非企业官方披露
- 招聘预算为基于公开招聘信息的估算，实际金额可能有差异
- 所有"待确认"项需通过销售拜访进一步核实
"""

# ============================================================
# 销售简报 Prompt
# ============================================================

SALES_BRIEF_PROMPT = """基于以下完整分析报告，为销售团队生成一份**销售简报**（30秒速览版）。

---
{full_report}
---

### 输出要求：

请严格按以下格式生成简洁的销售简报，控制在1页以内：

# {company_name} - 销售简报

## 关键信息（30秒速览）
| 维度 | 关键数据 |
|------|----------|
| 公司规模 | XX人 |
| 融资情况 | X轮，XX亿（时间） |
| **融资人才方向** | **XX方向（研发/市场/产能/组织）** |
| 招聘薪酬预算 | XX亿 |
| HR潜在预算（估算） | 约XX万 |
| 猎聘占比 | XX%（职位数）/ XX%（预算） |
| 核心需求 | XX类人才 |
| 销售机会 | ⭐⭐⭐⭐⭐ 极高 / ⭐⭐⭐⭐ 高 / ⭐⭐⭐ 中 |

## 为什么现在跟进？

### 融资驱动的人才需求
💰 **融资资金用途与招聘关联**（基于业务动态推断）：
- **技术研发** → 急需XX类技术人才
- **市场扩张** → 急需XX类商业人才
- **产能建设** → 急需XX类制造人才

> ⚠️ 以上为基于公开信息的行业推断，非官方披露。

### 业务扩张信号
✅ （列出3-5个关键业务扩张信号，每条一行）

## 怎么打？
🎯 **接触点**：XX + XX
🎯 **价值主张**：XX
🎯 **竞争策略**：XX

## 预期收益
💰 **短期**：XX
💰 **中期**：XX
💰 **长期**：XX

注意：
- 简报必须精炼，每条信息一行
- 数字要突出，便于快速扫读
- 重点突出"为什么现在"和"预期收益"
"""

# ============================================================
# 联网搜索模式 Prompt（模式A保留）
# ============================================================

ANALYSIS_PROMPT_WITH_SEARCH = """请对「{company_name}」进行全面的招聘预算分析。

**请通过联网搜索获取以下信息并生成分析报告：**

### 搜索维度：
1. **融资信息**（最关键）：融资轮次、金额、时间、投资方、资金用途
2. **企业基本面**：规模、行业、核心业务、战略方向
3. **招聘数据**：各平台在招职位数、薪资范围、重点部门
4. **近期动态**：重大成果、订单、合作、扩张计划

### 融资→人才方向分析框架：
- 研发扩张 → 工程师、科学家
- 市场扩张 → 销售、BD
- 产品发布 → 产品经理、设计师
- 产能建设 → 制造、供应链
- 组织建设 → HR、财务

""" + FULL_REPORT_PROMPT.split("请严格按以下结构输出**完整招聘预算分析报告**：")[1]


def _clean_thinking_tags(text: str) -> str:
    """
    清除 LLM 返回内容中的思考标签和重复噪音文本

    Kimi K2.5 等思考模型可能：
    1. 包含 <think>...</think> 标签
    2. 在联网搜索模式下，将思考过程混入 content 中

    清理策略：提取 Markdown 报告正文部分，丢弃无关文本
    """
    # 1. 移除 <think>...</think> 块
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)

    # 2. 移除 markdown 代码块包裹
    cleaned = re.sub(r'^```[a-z]*\n?', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```$', '', cleaned.strip(), flags=re.MULTILINE)

    # 3. 提取 Markdown 报告正文（以 # 开头的标题）
    report_match = re.search(r'^(#\s+.+)$', cleaned, flags=re.MULTILINE)
    if report_match:
        cleaned = cleaned[report_match.start():]

    # 4. 去重复的思考状态行
    lines = cleaned.split('\n')
    seen_lines = set()
    deduped_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(('#', '|', '-', '*', '>', '⚠', '✅', '💰', '🎯', '⭐')) and len(stripped) < 80:
            if stripped in seen_lines:
                continue
            seen_lines.add(stripped)
        deduped_lines.append(line)
    cleaned = '\n'.join(deduped_lines)

    return cleaned.strip()


def _is_search_capable_model(model: str) -> bool:
    """判断是否使用内置联网搜索模式"""
    model_lower = model.lower()
    if "search" in model_lower or "online" in model_lower:
        return True
    return False


class BusinessIntelAgent:
    """
    企业招聘预算分析 Agent

    核心引擎，接收公司名称，输出双报告：
    1. 完整招聘预算分析报告
    2. 销售简报（30秒速览）

    工作模式：
    - 模式A: LLM 联网搜索（适用于带 search 标识的模型）
    - 模式B: company_researcher 采集 → LLM 分析（默认，更稳定）
    """

    def __init__(self):
        if not LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY 未配置！请设置环境变量 LLM_API_KEY。\n"
                "推荐使用 Kimi K2.5（中文分析能力强）。\n"
                "获取 API Key: https://platform.moonshot.cn"
            )

        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL
        self.use_search = _is_search_capable_model(self.model)
        self.researcher = CompanyResearcher()
        self.csv_analyzer = CSVAnalyzer()

        csv_status = "已加载" if self.csv_analyzer.is_available else "未配置"
        logger.info(
            f"BusinessIntelAgent 初始化完成 "
            f"(model={self.model}, mode={'联网搜索' if self.use_search else '采集+分析'}, "
            f"CSV={csv_status})"
        )

    def analyze(self, company_name: str) -> str:
        """
        分析指定公司，返回完整报告 + 销售简报

        Args:
            company_name: 公司名称

        Returns:
            Markdown 格式的双报告（完整报告 + 销售简报）；失败返回空字符串
        """
        logger.info(f"开始分析「{company_name}」...")

        try:
            # Step 1: 生成完整分析报告
            if self.use_search:
                full_report = self._analyze_with_search(company_name)
            else:
                full_report = self._analyze_with_research(company_name)

            if not full_report:
                logger.warning(f"「{company_name}」未生成有效报告")
                return ""

            logger.info(f"「{company_name}」完整报告生成完成，{len(full_report)} 字")

            # Step 2: 基于完整报告生成销售简报
            sales_brief = self._generate_sales_brief(company_name, full_report)

            # Step 3: 合并输出
            combined = full_report
            if sales_brief:
                combined += "\n\n---\n\n" + sales_brief

            logger.info(f"「{company_name}」双报告生成完成，总计 {len(combined)} 字")
            return combined

        except Exception as e:
            logger.error(f"分析「{company_name}」失败: {e}", exc_info=True)
            return ""

    def _generate_sales_brief(self, company_name: str, full_report: str) -> str:
        """
        基于完整报告生成销售简报（30秒速览版）

        销售简报从完整报告中提炼关键数字和行动建议，
        控制在1页以内，便于销售人员快速扫读。
        """
        logger.info(f"正在生成「{company_name}」销售简报...")

        user_prompt = SALES_BRIEF_PROMPT.format(
            company_name=company_name,
            full_report=full_report,
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

        try:
            response = self.client.chat.completions.create(**create_kwargs)
            raw = response.choices[0].message.content or ""
            brief = _clean_thinking_tags(raw)
            logger.info(f"销售简报生成完成，{len(brief)} 字")
            return brief
        except Exception as e:
            logger.error(f"销售简报生成失败: {e}")
            return ""

    def _analyze_with_search(self, company_name: str) -> str:
        """模式A: LLM 联网搜索直接分析"""
        logger.info(f"使用联网搜索模式分析「{company_name}」")

        user_prompt = ANALYSIS_PROMPT_WITH_SEARCH.format(company_name=company_name)
        model_lower = self.model.lower()
        is_thinking_model = ("kimi" in model_lower and "k2" in model_lower)
        use_builtin_search = ("kimi" in model_lower or "moonshot" in model_lower)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        base_kwargs = {
            "model": self.model,
            "max_tokens": 8192 if is_thinking_model else 4096,
            "temperature": 1.0 if is_thinking_model else 0.3,
        }

        if use_builtin_search:
            base_kwargs["tools"] = [{
                "type": "builtin_function",
                "function": {"name": "$web_search"},
            }]

        max_rounds = 5
        for round_num in range(max_rounds):
            logger.info(f"  LLM 调用第 {round_num + 1} 轮...")
            response = self.client.chat.completions.create(messages=messages, **base_kwargs)
            choice = response.choices[0]
            assistant_msg = choice.message

            if choice.finish_reason != "tool_calls":
                raw_content = assistant_msg.content or ""
                return _clean_thinking_tags(raw_content)

            logger.info(f"  搜索中（{len(assistant_msg.tool_calls)} 次）...")
            assistant_dict = {
                "role": "assistant",
                "content": assistant_msg.content or "",
                "reasoning_content": " ",
                "tool_calls": [
                    {"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in assistant_msg.tool_calls
                ],
            }
            messages.append(assistant_dict)
            for tool_call in assistant_msg.tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": tool_call.function.arguments,
                })

        raw_content = response.choices[0].message.content or ""
        return _clean_thinking_tags(raw_content)

    def _analyze_with_research(self, company_name: str) -> str:
        """
        模式B: 网络采集 + CSV数据 + LLM 分析

        三步流程：
        1. 网络采集：通过搜索引擎获取企业背景、融资、新闻等定性信息
        2. CSV分析：从内部客户职位数据库获取精确的招聘数据（渠道/薪资/HR预算）
        3. LLM合成：将两个数据源的信息合并，生成完整分析报告
        """
        logger.info(f"使用采集+分析模式处理「{company_name}」")

        # Step 1: 网络采集企业信息（定性数据）
        research_data = self.researcher.research(company_name)

        if not research_data.has_data:
            logger.warning(f"「{company_name}」网络采集未获取到有效信息")
            research_text = (
                f"未能从搜索引擎采集到「{company_name}」的相关信息。"
                f"请基于你的知识库进行分析，并明确标注需要确认的信息。"
            )
        else:
            research_text = research_data.to_prompt_text()

        # Step 2: CSV 分析招聘数据（定量数据）
        csv_text = ""
        if self.csv_analyzer.is_available:
            logger.info(f"  📊 正在分析 CSV 招聘数据...")
            csv_result = self.csv_analyzer.analyze(company_name)
            if csv_result.found:
                csv_text = csv_result.to_prompt_text()
                logger.info(
                    f"  CSV 数据: {csv_result.total_positions}个职位, "
                    f"总预算{csv_result.total_budget:.1f}万, "
                    f"HR预算{csv_result.total_hr_budget:.1f}万"
                )
            else:
                logger.info(f"  CSV 中未找到「{company_name}」的数据")
        else:
            logger.info(f"  CSV 文件未配置，跳过内部数据分析")

        # Step 3: 合并两个数据源
        combined_data = research_text
        if csv_text:
            combined_data += "\n\n" + csv_text
            combined_data += (
                "\n\n> **重要提示**：上方「内部招聘数据分析」部分包含精确的渠道分布、薪资预算、"
                "HR潜在预算数据，在报告中请优先使用这些数据，而非估算值。\n"
            )

        # Step 4: LLM 分析生成完整报告
        user_prompt = FULL_REPORT_PROMPT.format(
            company_name=company_name,
            research_data=combined_data,
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
        return _clean_thinking_tags(raw_content)
