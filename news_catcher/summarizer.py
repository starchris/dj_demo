"""
行业动态总结模块 - 基于 LLM 对抓取的新闻生成简短行业总结
Industry Summarizer - Uses LLM to generate concise industry briefings

总结维度：
- 重点企业 / 新兴企业动态
- 投融资动态
- 产品与技术动态
- 市场与政策动态
- 人员与组织动态
"""

import logging
import re
from datetime import datetime

from openai import OpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, INDUSTRIES
from .news_fetcher import NewsItem

logger = logging.getLogger(__name__)

# ============================================================
# Prompt 模板
# ============================================================

SYSTEM_PROMPT = """你是一位资深的产业研究分析师，擅长从新闻快讯中快速提炼行业动态要点。
你的任务是根据提供的新闻标题和摘要，为指定行业生成一段**简洁、专业、信息密度高**的动态总结。

写作要求：
1. 用 3~6 个要点概括当前行业最值得关注的动态，每个要点一行，以「·」开头
2. 要点应涵盖以下维度（有则写，无则跳过）：
   - 重点企业 / 新兴企业的关键动作
   - 投融资事件（金额、轮次、投资方）
   - 新产品发布、技术突破
   - 市场趋势、行业数据
   - 政策法规、标准制定
   - 重要人事变动、组织调整
3. 每个要点控制在 30~60 字，点到为止，不要展开论述
4. 提及具体企业名、数字、产品名时要保留，这些是信息密度的核心
5. 如果新闻内容不足以提炼有价值的要点，就据实总结，不要编造
6. 直接输出要点列表，不要输出标题、前言、总结性段落"""

USER_PROMPT_TEMPLATE = """以下是【{industry}】行业今日抓取的 {count} 条新闻：

{news_text}

请根据以上新闻，输出该行业今日动态要点总结（3~6 个要点，以「·」开头）："""


def _build_news_text(news_items: list[NewsItem]) -> str:
    """将新闻列表格式化为 LLM 输入文本"""
    lines = []
    for i, item in enumerate(news_items, 1):
        line = f"{i}. 【{item.title}】"
        if item.summary:
            line += f"\n   摘要：{item.summary[:150]}"
        if item.source:
            line += f"\n   来源：{item.source}"
        lines.append(line)
    return "\n\n".join(lines)


def _summarize_with_llm(industry: str, news_items: list[NewsItem]) -> str:
    """调用 LLM 生成单个行业的动态总结"""
    news_text = _build_news_text(news_items)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        industry=industry,
        count=len(news_items),
        news_text=news_text,
    )

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    # 构建请求参数（部分模型如 Kimi K2.5 不支持自定义 temperature）
    create_kwargs = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 500,
    }

    # Kimi K2.5 是思考模型：仅允许 temperature=1，需要更多 token 空间
    model_lower = LLM_MODEL.lower()
    is_thinking_model = ("kimi" in model_lower and "k2" in model_lower)

    if is_thinking_model:
        create_kwargs["temperature"] = 1.0
        create_kwargs["max_tokens"] = 2048  # 思考过程+回答需要更多空间
    else:
        create_kwargs["temperature"] = 0.3

    response = client.chat.completions.create(**create_kwargs)

    raw_content = response.choices[0].message.content or ""

    # Kimi K2.5 等思考模型会在回复中包含 <think>...</think> 标签
    # 需要去除思考过程，只保留最终输出
    summary = _clean_thinking_tags(raw_content)
    return summary


def _clean_thinking_tags(text: str) -> str:
    """清除 LLM 返回内容中的思考标签（<think>...</think>）"""
    # 移除 <think>...</think> 块（可能跨多行）
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 移除可能残留的未闭合 <think> 标签
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    # 移除 markdown 代码块包裹（部分模型会把结果放在代码块里）
    cleaned = re.sub(r'^```[a-z]*\n?', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```$', '', cleaned.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def _summarize_fallback(industry: str, news_items: list[NewsItem]) -> str:
    """
    回退方案：当 LLM 不可用时，基于新闻标题生成简要总结
    直接列出新闻标题要点，不做智能摘要
    """
    lines = []
    for item in news_items[:5]:
        title = item.title.strip()
        if len(title) > 50:
            title = title[:48] + "..."
        source = f"（{item.source}）" if item.source else ""
        lines.append(f"· {title}{source}")
    return "\n".join(lines)


def generate_summaries(
    news_by_industry: dict[str, list[NewsItem]],
) -> dict[str, str]:
    """
    为每个行业生成动态总结

    Args:
        news_by_industry: {行业名: [NewsItem, ...]}

    Returns:
        {行业名: "总结文本"}  每个行业一段 3~6 行的要点总结
    """
    summaries: dict[str, str] = {}
    use_llm = bool(LLM_API_KEY)

    if not use_llm:
        logger.warning(
            "LLM_API_KEY 未配置，将使用标题摘要模式（建议配置 DeepSeek API 以获得更好的总结效果）"
        )

    for industry, news_items in news_by_industry.items():
        if not news_items:
            continue

        emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
        logger.info(f"  {emoji} 正在总结 [{industry}] ...")

        try:
            if use_llm:
                summary = _summarize_with_llm(industry, news_items)
            else:
                summary = _summarize_fallback(industry, news_items)

            summaries[industry] = summary
            logger.info(f"  {emoji} [{industry}] 总结完成")

        except Exception as e:
            logger.error(f"  [{industry}] 总结生成失败: {e}")
            # LLM 失败时回退
            try:
                summaries[industry] = _summarize_fallback(industry, news_items)
                logger.info(f"  [{industry}] 已使用回退方案生成摘要")
            except Exception as e2:
                logger.error(f"  [{industry}] 回退方案也失败: {e2}")
                summaries[industry] = "（总结生成失败，请查看下方新闻链接）"

    return summaries
