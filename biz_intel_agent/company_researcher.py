"""
企业信息采集模块 - 通过公开渠道搜索企业经营信息和招聘信息
Company Researcher Module - Gather company info from public channels

采集维度：
  1. 企业基本信息与财务状况（搜索引擎 + 企业信息平台）
  2. 业务发展动态（新闻搜索）
  3. 招聘信息与人才需求（招聘平台搜索）

注意：此模块通过搜索引擎间接获取公开信息，作为 LLM 分析的补充输入。
     当 LLM 本身支持联网搜索时（如 Kimi K2.5），此模块的结果作为额外参考。
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .config import DEFAULT_HEADERS, MAX_SEARCH_RESULTS, REQUEST_TIMEOUT

logger = logging.getLogger("biz_intel_agent.researcher")


@dataclass
class SearchResult:
    """搜索结果数据类"""
    title: str
    url: str
    snippet: str = ""
    source: str = ""


@dataclass
class CompanyResearchData:
    """
    企业调研数据 - 包含从各渠道收集的原始信息

    六个采集维度（对齐 SKILL.md 的分析框架）：
    1. 企业基本信息
    2. 融资信息（关键维度：轮次、金额、资金用途 → 人才方向）
    3. 财务/经营信息
    4. 业务发展/新闻动态
    5. 招聘信息与人才需求
    6. 行业竞争/市场信息
    """
    company_name: str
    # 企业基本信息
    basic_info: list[SearchResult] = field(default_factory=list)
    # 融资信息（专项采集：轮次、金额、投资方、资金用途）
    funding_info: list[SearchResult] = field(default_factory=list)
    # 财务/经营信息
    financial_info: list[SearchResult] = field(default_factory=list)
    # 业务发展/新闻动态
    business_news: list[SearchResult] = field(default_factory=list)
    # 招聘信息
    recruitment_info: list[SearchResult] = field(default_factory=list)
    # 行业竞争/市场信息
    market_info: list[SearchResult] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """
        将所有采集到的信息格式化为 LLM 可读的文本

        按维度组织，融资信息放在靠前的位置（最关键的分析维度）
        """
        sections = []

        sections.append(f"# 关于「{self.company_name}」的公开信息采集结果\n")

        if self.basic_info:
            sections.append("## 一、企业基本信息")
            for i, item in enumerate(self.basic_info, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        # 融资信息放在前面（SKILL.md 标注为 Critical）
        if self.funding_info:
            sections.append("## 二、融资信息（关键维度）")
            sections.append("请重点分析：融资轮次、金额、投资方、资金用途 → 对应的人才招聘方向")
            for i, item in enumerate(self.funding_info, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        if self.financial_info:
            sections.append("## 三、财务与经营信息")
            for i, item in enumerate(self.financial_info, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        if self.business_news:
            sections.append("## 四、业务发展与新闻动态")
            for i, item in enumerate(self.business_news, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        if self.recruitment_info:
            sections.append("## 五、招聘信息与人才需求")
            sections.append("请重点分析：各平台职位数量、薪资范围、渠道分布、猎聘占比")
            for i, item in enumerate(self.recruitment_info, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        if self.market_info:
            sections.append("## 六、行业竞争与市场信息")
            for i, item in enumerate(self.market_info, 1):
                sections.append(f"{i}. 【{item.title}】")
                if item.snippet:
                    sections.append(f"   {item.snippet}")
            sections.append("")

        return "\n".join(sections)

    @property
    def has_data(self) -> bool:
        """是否采集到了有效数据"""
        return bool(
            self.basic_info or self.funding_info or self.financial_info or
            self.business_news or self.recruitment_info or self.market_info
        )


class CompanyResearcher:
    """
    企业信息调研器

    通过多个搜索引擎和公开渠道采集企业信息，
    为 LLM 分析提供数据支撑
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def research(self, company_name: str) -> CompanyResearchData:
        """
        对指定公司进行全方位信息采集

        Args:
            company_name: 公司名称

        Returns:
            CompanyResearchData: 采集到的各维度信息
        """
        logger.info(f"开始采集「{company_name}」的企业信息...")
        data = CompanyResearchData(company_name=company_name)

        # 1. 企业基本信息
        logger.info(f"  📋 采集企业基本信息...")
        data.basic_info = self._search_basic_info(company_name)
        time.sleep(1)

        # 2. 融资信息（SKILL.md 标注为 Critical）
        logger.info(f"  🏦 采集融资信息（关键维度）...")
        data.funding_info = self._search_funding_info(company_name)
        time.sleep(1)

        # 3. 财务/经营信息
        logger.info(f"  💰 采集财务经营信息...")
        data.financial_info = self._search_financial_info(company_name)
        time.sleep(1)

        # 4. 业务发展与新闻
        logger.info(f"  📰 采集业务发展动态...")
        data.business_news = self._search_business_news(company_name)
        time.sleep(1)

        # 5. 招聘信息（含渠道分布、薪资）
        logger.info(f"  👥 采集招聘信息...")
        data.recruitment_info = self._search_recruitment_info(company_name)
        time.sleep(1)

        # 6. 市场竞争信息
        logger.info(f"  📊 采集市场竞争信息...")
        data.market_info = self._search_market_info(company_name)

        total = (
            len(data.basic_info) + len(data.funding_info) +
            len(data.financial_info) + len(data.business_news) +
            len(data.recruitment_info) + len(data.market_info)
        )
        logger.info(f"「{company_name}」信息采集完成，共获取 {total} 条结果")

        return data

    # ============================================================
    # 各维度搜索
    # ============================================================

    def _search_basic_info(self, company_name: str) -> list[SearchResult]:
        """搜索企业基本信息（规模、主营业务等）"""
        queries = [
            f"{company_name} 公司简介 规模 主营业务",
            f"{company_name} 企业信息 成立时间 员工人数",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    def _search_funding_info(self, company_name: str) -> list[SearchResult]:
        """
        搜索融资信息（SKILL.md 标注为 Critical 维度）

        重点采集：融资轮次、金额、时间、投资方、资金用途
        """
        queries = [
            f"{company_name} 融资 轮次 金额 投资方 2024 2025",
            f"{company_name} 融资 资金用途 扩张 研发",
            f"{company_name} 获投 估值 融资历史",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    def _search_financial_info(self, company_name: str) -> list[SearchResult]:
        """搜索财务和经营信息"""
        queries = [
            f"{company_name} 营收 利润 财报 2024 2025",
            f"{company_name} 业绩 增长 市值",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    def _search_business_news(self, company_name: str) -> list[SearchResult]:
        """搜索业务发展和新闻动态"""
        queries = [
            f"{company_name} 最新动态 业务发展 战略",
            f"{company_name} 新产品 业务扩张 合作",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu_news(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    def _search_recruitment_info(self, company_name: str) -> list[SearchResult]:
        """
        搜索招聘信息和人才需求

        重点采集：各平台职位数量、薪资范围、渠道分布、猎聘占比
        """
        queries = [
            f"{company_name} 招聘 职位 薪资 2025",
            f"{company_name} BOSS直聘 猎聘 招聘 在招职位数",
            f"{company_name} 社招 人才需求 高薪 技术",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    def _search_market_info(self, company_name: str) -> list[SearchResult]:
        """搜索市场竞争信息"""
        queries = [
            f"{company_name} 行业地位 竞争 市场份额",
        ]
        results = []
        for query in queries:
            results.extend(self._search_baidu(query))
            if len(results) >= MAX_SEARCH_RESULTS:
                break
            time.sleep(0.5)
        return results[:MAX_SEARCH_RESULTS]

    # ============================================================
    # 搜索引擎接口
    # ============================================================

    def _search_baidu(self, query: str) -> list[SearchResult]:
        """
        百度网页搜索

        Args:
            query: 搜索关键词

        Returns:
            搜索结果列表
        """
        results = []
        url = f"https://www.baidu.com/s?wd={quote(query)}&rn=10"

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"百度搜索请求失败: HTTP {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析搜索结果
            items = soup.select("div.result") or soup.select("div[class*='result']")

            for item in items[:MAX_SEARCH_RESULTS]:
                try:
                    title_tag = item.select_one("h3 a") or item.select_one("a")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")

                    # 清理标题
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if not title or len(title) < 4:
                        continue

                    # 提取摘要
                    snippet_tag = (
                        item.select_one("div.c-summary") or
                        item.select_one("div.c-abstract") or
                        item.select_one("span.content-right_8Zs40") or
                        item.select_one("p")
                    )
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    snippet = re.sub(r'<[^>]+>', '', snippet)[:300]

                    results.append(SearchResult(
                        title=title,
                        url=href,
                        snippet=snippet,
                        source="百度搜索",
                    ))
                except Exception as e:
                    logger.debug(f"解析百度搜索条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"百度搜索请求异常: {e}")

        return results

    def _search_baidu_news(self, query: str) -> list[SearchResult]:
        """
        百度新闻搜索

        Args:
            query: 搜索关键词

        Returns:
            搜索结果列表
        """
        results = []
        url = f"https://news.baidu.com/ns?word={quote(query)}&tn=news&from=news&cl=2&rn=10&ct=1"

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"百度新闻请求失败: HTTP {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div.result") or soup.select("div[class*='result']")

            for item in items[:MAX_SEARCH_RESULTS]:
                try:
                    title_tag = item.select_one("h3 a") or item.select_one("a")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")

                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if not title or len(title) < 4:
                        continue

                    snippet_tag = (
                        item.select_one("div.c-summary") or
                        item.select_one("div.c-abstract") or
                        item.select_one("p")
                    )
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    snippet = re.sub(r'<[^>]+>', '', snippet)[:300]

                    source_tag = item.select_one("span.c-color-gray") or item.select_one("p.c-author")
                    source = source_tag.get_text(strip=True) if source_tag else "百度新闻"

                    results.append(SearchResult(
                        title=title,
                        url=href,
                        snippet=snippet,
                        source=source,
                    ))
                except Exception as e:
                    logger.debug(f"解析百度新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"百度新闻请求异常: {e}")

        return results

    def _search_bing(self, query: str) -> list[SearchResult]:
        """
        Bing 网页搜索（百度搜索的备用方案）

        Args:
            query: 搜索关键词

        Returns:
            搜索结果列表
        """
        results = []
        url = f"https://cn.bing.com/search?q={quote(query)}&cc=cn"

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"Bing搜索请求失败: HTTP {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.b_algo")

            for item in items[:MAX_SEARCH_RESULTS]:
                try:
                    title_tag = item.select_one("h2 a")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")

                    if not title or not href:
                        continue

                    snippet_tag = item.select_one("p") or item.select_one("div.b_caption p")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    results.append(SearchResult(
                        title=title,
                        url=href,
                        snippet=snippet[:300],
                        source="Bing搜索",
                    ))
                except Exception as e:
                    logger.debug(f"解析Bing搜索条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Bing搜索请求异常: {e}")

        return results
