"""
投融资事件抓取模块 - 从投资界(pedaily.cn)获取最新投融资和IPO动态
Funding & IPO Fetcher - Scrape latest funding rounds and IPO events from pedaily.cn

数据源：
1. 融资快讯  https://www.pedaily.cn/first/t76/
2. IPO 前线  https://www.pedaily.cn/exit/
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import DEFAULT_HEADERS, INDUSTRIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# 投融资事件的时效窗口（天）
FUNDING_MAX_AGE_DAYS = 7


@dataclass
class FundingEvent:
    """投融资/IPO 事件数据类"""
    company: str        # 公司名称
    title: str          # 事件标题
    url: str            # 详情链接
    event_type: str     # 事件类型: "融资" | "IPO"
    round: str = ""     # 融资轮次（如 A轮、Pre-A、D++轮）或 "IPO"
    amount: str = ""    # 金额（如 "超2亿元"、"50.37亿元"）
    industry: str = ""  # 匹配的行业
    publish_time: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "title": self.title,
            "url": self.url,
            "event_type": self.event_type,
            "round": self.round,
            "amount": self.amount,
            "industry": self.industry,
            "publish_time": self.publish_time,
            "summary": self.summary,
        }

    def highlight_text(self) -> str:
        """生成高亮展示文本"""
        parts = [f"💰 {self.company}"]
        if self.event_type == "IPO":
            parts.append("IPO")
            if self.amount:
                parts.append(f"（{self.amount}）")
        else:
            if self.round:
                parts.append(f"完成{self.round}")
            if self.amount:
                parts.append(f"（{self.amount}）")
        return "".join(parts)


class FundingFetcher:
    """投融资事件抓取器 - 从投资界 pedaily.cn 抓取"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_all(self) -> list[FundingEvent]:
        """
        抓取所有最新投融资和IPO事件，并匹配行业
        Returns: [FundingEvent, ...]
        """
        events: list[FundingEvent] = []

        # 1. 抓取融资快讯
        try:
            funding_events = self._fetch_funding_list()
            events.extend(funding_events)
            logger.info(f"💰 融资快讯获取到 {len(funding_events)} 条")
        except Exception as e:
            logger.error(f"融资快讯抓取失败: {e}")

        time.sleep(1)

        # 2. 抓取IPO前线
        try:
            ipo_events = self._fetch_ipo_list()
            events.extend(ipo_events)
            logger.info(f"🔔 IPO前线获取到 {len(ipo_events)} 条")
        except Exception as e:
            logger.error(f"IPO前线抓取失败: {e}")

        # 3. 为每个事件匹配行业
        matched = []
        for event in events:
            industry = self._match_industry(event.title + event.summary + event.company)
            if industry:
                event.industry = industry
                matched.append(event)

        logger.info(f"📊 投融资事件匹配到行业: {len(matched)}/{len(events)} 条")
        return matched

    def _fetch_funding_list(self) -> list[FundingEvent]:
        """从融资快讯页抓取融资事件"""
        events = []
        url = "https://www.pedaily.cn/first/t76/"

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"融资快讯请求失败: HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")

            # 遍历所有 li 中的链接
            for li in soup.select("li"):
                a = li.select_one("a")
                if not a:
                    continue

                title = a.get_text(strip=True)
                href = a.get("href", "")

                # 过滤非融资条目
                if not href or len(title) < 10:
                    continue
                if "news.pedaily.cn" not in href:
                    continue
                if not any(kw in title for kw in ["融资", "轮", "投资"]):
                    continue

                # 提取时间
                spans = li.select("span")
                publish_time = ""
                for span in spans:
                    text = span.get_text(strip=True)
                    if re.match(r"\d{4}-\d{2}-\d{2}", text):
                        publish_time = text
                        break

                # 过滤过期事件
                if publish_time and self._is_too_old(publish_time):
                    continue

                # 解析融资信息
                company, round_info, amount = self._parse_funding_title(title)

                event = FundingEvent(
                    company=company,
                    title=title,
                    url=href,
                    event_type="融资",
                    round=round_info,
                    amount=amount,
                    publish_time=publish_time,
                )
                events.append(event)

        except requests.RequestException as e:
            logger.error(f"融资快讯请求异常: {e}")

        return events

    def _fetch_ipo_list(self) -> list[FundingEvent]:
        """从IPO前线页抓取IPO事件"""
        events = []
        url = "https://www.pedaily.cn/exit/"

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"IPO前线请求失败: HTTP {resp.status_code}")
                return events

            soup = BeautifulSoup(resp.text, "html.parser")

            # IPO页面的链接在 a 标签中
            for a in soup.select("a"):
                title = a.get_text(strip=True)
                href = a.get("href", "")

                if not href or len(title) < 15:
                    continue
                if "news.pedaily.cn" not in href:
                    continue
                if not any(kw in title for kw in ["IPO", "上市", "敲钟", "市值"]):
                    continue

                # 从 URL 中提取日期 (如 /202602/ -> 2026年2月)
                publish_time = self._extract_date_from_url(href)

                # 过滤过期事件
                if publish_time and self._is_too_old(publish_time):
                    continue

                # 解析IPO信息
                company = self._parse_ipo_company(title)
                amount = self._parse_amount(title)

                event = FundingEvent(
                    company=company,
                    title=title,
                    url=href,
                    event_type="IPO",
                    round="IPO",
                    amount=amount,
                    publish_time=publish_time,
                )
                events.append(event)

        except requests.RequestException as e:
            logger.error(f"IPO前线请求异常: {e}")

        return events

    # ================================================================
    # 解析工具方法
    # ================================================================

    @staticmethod
    def _parse_funding_title(title: str) -> tuple[str, str, str]:
        """
        从融资标题中提取公司名、轮次、金额
        例: "算苗科技完成Pre-A轮、Pre-A1轮融资" -> ("算苗科技", "Pre-A轮", "")
        例: "无界动力完成超2亿元天使+轮融资" -> ("无界动力", "天使+轮", "超2亿元")
        """
        company = ""
        round_info = ""
        amount = ""

        # 提取公司名：通常在「」或标题中"完成/获"之前
        # 模式1: 「公司名」
        m = re.search(r'[「"](.*?)[」"]', title)
        if m:
            company = m.group(1)
        else:
            # 模式2: 逗号后 "XXX完成" / "XXX获" (如 "聚焦XXX，箭元科技完成B轮融资")
            m = re.search(r'[，,]\s*(.{2,15}?)(?:完成|获得|获|宣布|拟)', title)
            if m:
                company = m.group(1).strip()
            else:
                # 模式3: 标题开头到 "完成" / "获" / "宣布"
                m = re.match(r'^(.{2,15}?)(?:完成|获得|获|宣布|拟)', title)
                if m:
                    company = m.group(1).strip()
            # 去掉可能的修饰词
            if company:
                company = re.sub(r'^(总额.*?[，,]|半年.*?[，,])', '', company).strip()

        # 提取轮次
        round_patterns = [
            r'((?:Pre-?)?[A-Z]\+*轮)',
            r'(天使[\+]*轮)',
            r'(种子轮)',
            r'(战略融资)',
            r'(股权融资)',
            r'([A-Z]\d*\+*轮)',
        ]
        for pattern in round_patterns:
            m = re.search(pattern, title)
            if m:
                round_info = m.group(1)
                break

        # 提取金额
        amount = FundingFetcher._parse_amount(title)

        return company, round_info, amount

    @staticmethod
    def _parse_amount(title: str) -> str:
        """从标题中提取金额"""
        amount_patterns = [
            r'(超[\d.]+\s*亿[美元人民币]*)',
            r'(近[\d.]+\s*亿[美元人民币]*)',
            r'(近[十百千]\s*亿[美元人民币]*)',
            r'([\d.]+\s*亿[美元人民币]*)',
            r'(数[千百十]万[美元人民币]*)',
            r'(数千万)',
            r'([\d.]+\s*万[美元人民币]*)',
            r'(市值[\d.]+\s*亿)',
        ]
        for pattern in amount_patterns:
            m = re.search(pattern, title)
            if m:
                return m.group(1)
        return ""

    @staticmethod
    def _parse_ipo_company(title: str) -> str:
        """从IPO标题中提取公司名"""
        # 模式1: 「公司名」
        m = re.search(r'[「"](.*?)[」"]', title)
        if m and len(m.group(1)) >= 2:
            return m.group(1)

        # 模式2: "XXX要IPO了" / "XXX敲钟" / "XXX上市" / "XXX赴港"
        patterns = [
            # "昆仑芯赴港上市" -> 昆仑芯（优先匹配标题开头的赴X上市）
            r'^(.{2,8}?)(?:赴港|赴美|赴纽)',
            # "今天智谱IPO敲锣" -> 智谱
            r'今[天日]\s*(.{2,6}?)(?:IPO|上市|敲)',
            # "护家科技要IPO了" -> 护家科技
            r'[，,]\s*(.{2,10}?)(?:要IPO|IPO了|赴港上市|要上市)',
            # "鸣鸣很忙敲钟" -> 鸣鸣很忙
            r'[，,]\s*(.{2,10}?)(?:敲[钟锣])',
            # "电科蓝天市值1000亿" -> 电科蓝天
            r'[，,]\s*(.{2,8}?)(?:市值)',
            # "北芯生命暴涨200%" -> 北芯生命
            r'[：:]\s*(.{2,8}?)(?:暴涨|上涨|大涨|市值)',
        ]
        for pattern in patterns:
            m = re.search(pattern, title)
            if m:
                name = m.group(1).strip()
                # 清理前缀修饰词
                name = re.sub(r'^(今[天年]|首个|航天|医疗|科创板)', '', name).strip()
                if len(name) >= 2:
                    return name

        # 兜底: 匹配常见公司名模式
        m = re.search(
            r'([\u4e00-\u9fff]{2,6}(?:科技|智能|生命|医疗|芯片|半导体|新材料|能源|航天|资本|比萨|集团))',
            title,
        )
        if m:
            return m.group(1)

        # 匹配英文公司名
        m = re.search(r'([A-Z][A-Za-z]{2,15})', title)
        if m:
            return m.group(1)

        return ""

    @staticmethod
    def _extract_date_from_url(url: str) -> str:
        """从 pedaily URL 中提取日期（格式: /YYYYMM/）"""
        m = re.search(r'/(\d{4})(\d{2})/', url)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        return ""

    @staticmethod
    def _is_too_old(publish_time: str) -> bool:
        """判断事件是否过期"""
        now = datetime.now()
        cutoff = now - timedelta(days=FUNDING_MAX_AGE_DAYS)

        # YYYY-MM-DD HH:MM 格式
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', publish_time)
        if m:
            try:
                event_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return event_date < cutoff
            except ValueError:
                pass

        # YYYY-MM 格式（仅年月）
        m = re.match(r'(\d{4})-(\d{2})$', publish_time)
        if m:
            try:
                year, month = int(m.group(1)), int(m.group(2))
                # 如果是当月或上月就保留
                if year == now.year and month >= now.month - 1:
                    return False
                if year == now.year - 1 and now.month == 1 and month == 12:
                    return False
                return True
            except ValueError:
                pass

        return False  # 无法判断时保留

    @staticmethod
    def _match_industry(text: str) -> Optional[str]:
        """根据关键词匹配文本所属行业"""
        for industry, config in INDUSTRIES.items():
            for keyword in config["keywords"]:
                if keyword in text:
                    return industry

        # 补充：投融资领域的扩展匹配
        extended_mapping = {
            "人工智能": ["AI", "大模型", "机器人", "智能体", "算力", "算法", "GPT", "LLM"],
            "半导体与芯片": ["芯片", "半导体", "晶圆", "EDA", "光刻"],
            "新能源": ["电池", "光伏", "风电", "储能", "充电", "新能源车"],
            "生物医药": ["医药", "医疗", "生物", "基因", "药物", "诊断", "疫苗"],
            "航空航天": ["航天", "火箭", "卫星", "无人机", "低空"],
            "高端装备制造": ["机器人", "制造", "自动化", "数控"],
            "量子科技": ["量子"],
            "新材料": ["材料", "碳纤维", "石墨烯", "稀土"],
            "数字经济": ["数字化", "数据", "云计算", "SaaS"],
            "绿色低碳": ["碳中和", "环保", "清洁", "ESG"],
        }
        for industry, keywords in extended_mapping.items():
            for keyword in keywords:
                if keyword in text:
                    return industry

        return None


def fetch_funding_events() -> dict[str, list[FundingEvent]]:
    """
    便捷函数：抓取投融资事件并按行业分组
    Returns: {行业名: [FundingEvent, ...]}
    """
    fetcher = FundingFetcher()
    events = fetcher.fetch_all()

    # 按行业分组
    by_industry: dict[str, list[FundingEvent]] = {}
    for event in events:
        if event.industry:
            by_industry.setdefault(event.industry, []).append(event)

    return by_industry
