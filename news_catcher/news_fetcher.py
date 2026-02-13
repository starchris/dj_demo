"""
新闻抓取模块 - 从多个源获取十五五规划重点行业新闻
News Fetcher Module - Fetch industry news from multiple sources

支持的新闻源：
1. 百度新闻搜索（主要源）
2. Bing 新闻搜索（备用源）
3. RSS 订阅源
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import (
    DEFAULT_HEADERS,
    INDUSTRIES,
    MAX_NEWS_PER_INDUSTRY,
    MAX_TOTAL_NEWS,
    REQUEST_TIMEOUT,
    RSS_FEEDS,
)

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻条目数据类"""
    title: str
    url: str
    source: str  # 新闻来源（如：百度新闻、36氪）
    industry: str  # 所属行业
    summary: str = ""
    publish_time: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def uid(self) -> str:
        """基于标题生成唯一标识，用于去重"""
        return hashlib.md5(self.title.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "industry": self.industry,
            "summary": self.summary,
            "publish_time": self.publish_time,
            "fetched_at": self.fetched_at,
        }


class NewsFetcher:
    """新闻抓取器 - 从多个来源抓取十五五规划相关行业新闻"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.seen_uids: set = set()

    def fetch_all(self) -> dict[str, list[NewsItem]]:
        """
        抓取所有行业新闻
        Returns: {行业名: [NewsItem, ...]}
        """
        all_news: dict[str, list[NewsItem]] = {}
        total_count = 0

        for industry, config in INDUSTRIES.items():
            if total_count >= MAX_TOTAL_NEWS:
                logger.info(f"已达到总新闻数上限 {MAX_TOTAL_NEWS}，停止抓取")
                break

            logger.info(f"正在抓取 [{industry}] 行业新闻...")
            industry_news = self._fetch_industry_news(industry, config["keywords"])

            if industry_news:
                all_news[industry] = industry_news[:MAX_NEWS_PER_INDUSTRY]
                total_count += len(all_news[industry])
                logger.info(f"  [{industry}] 获取到 {len(all_news[industry])} 条新闻")
            else:
                logger.warning(f"  [{industry}] 未获取到新闻")

            # 请求间隔，避免被反爬
            time.sleep(1.5)

        logger.info(f"新闻抓取完成，共 {total_count} 条")
        return all_news

    def _fetch_industry_news(self, industry: str, keywords: list[str]) -> list[NewsItem]:
        """抓取单个行业的新闻"""
        news_items: list[NewsItem] = []

        # 方法1：百度新闻搜索
        for keyword in keywords[:3]:  # 每个行业最多使用前3个关键词搜索
            try:
                items = self._fetch_from_baidu_news(keyword, industry)
                news_items.extend(items)
            except Exception as e:
                logger.error(f"百度新闻抓取失败 [{keyword}]: {e}")
            time.sleep(1)

        # 方法2：Bing 新闻搜索（作为补充）
        if len(news_items) < MAX_NEWS_PER_INDUSTRY:
            try:
                primary_keyword = keywords[0]
                items = self._fetch_from_bing_news(primary_keyword, industry)
                news_items.extend(items)
            except Exception as e:
                logger.error(f"Bing新闻抓取失败 [{keywords[0]}]: {e}")

        # 方法3：搜狗新闻搜索（进一步补充）
        if len(news_items) < MAX_NEWS_PER_INDUSTRY:
            try:
                primary_keyword = keywords[0]
                items = self._fetch_from_sogou_news(primary_keyword, industry)
                news_items.extend(items)
            except Exception as e:
                logger.error(f"搜狗新闻抓取失败 [{keywords[0]}]: {e}")

        # 去重
        unique_news = self._deduplicate(news_items)
        return unique_news

    def _fetch_from_baidu_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从百度新闻搜索抓取新闻"""
        news_items = []
        search_url = f"https://news.baidu.com/ns?word={quote(keyword)}&tn=news&from=news&cl=2&rn=10&ct=1"

        try:
            resp = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"百度新闻请求失败: HTTP {resp.status_code}")
                return news_items

            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析搜索结果
            result_items = soup.select("div.result")
            if not result_items:
                # 尝试其他选择器
                result_items = soup.select("div[class*='result']")

            for item in result_items[:MAX_NEWS_PER_INDUSTRY]:
                try:
                    # 提取标题和链接
                    title_tag = item.select_one("h3 a") or item.select_one("a")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    url = title_tag.get("href", "")

                    # 清理标题中的HTML标签
                    title = re.sub(r'<[^>]+>', '', title).strip()

                    if not title or len(title) < 4 or not url:
                        continue

                    # 提取摘要
                    summary_tag = item.select_one("div.c-summary") or item.select_one("div.c-abstract") or item.select_one("p")
                    summary = summary_tag.get_text(strip=True) if summary_tag else ""
                    summary = re.sub(r'<[^>]+>', '', summary)[:200]

                    # 提取来源和时间
                    source_tag = item.select_one("span.c-color-gray") or item.select_one("p.c-author")
                    source_text = source_tag.get_text(strip=True) if source_tag else "百度新闻"

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                        publish_time=self._extract_time(source_text),
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"解析百度新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"百度新闻请求异常: {e}")

        return news_items

    def _fetch_from_bing_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从Bing新闻搜索抓取新闻"""
        news_items = []
        search_url = f"https://cn.bing.com/news/search?q={quote(keyword)}&FORM=HDRSC6&cc=cn"

        try:
            resp = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"Bing新闻请求失败: HTTP {resp.status_code}")
                return news_items

            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析 Bing 新闻搜索结果
            result_items = soup.select("div.news-card") or soup.select("div.newsitem") or soup.select("div[data-idx]")

            for item in result_items[:MAX_NEWS_PER_INDUSTRY]:
                try:
                    title_tag = item.select_one("a.title") or item.select_one("a[href]")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    url = title_tag.get("href", "")

                    if not title or not url:
                        continue

                    # 补全相对链接
                    if url.startswith("/"):
                        url = urljoin("https://cn.bing.com", url)

                    summary_tag = item.select_one("div.snippet") or item.select_one("p")
                    summary = summary_tag.get_text(strip=True) if summary_tag else ""

                    source_tag = item.select_one("div.source span") or item.select_one("span.source")
                    source_text = source_tag.get_text(strip=True) if source_tag else "Bing新闻"

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"解析Bing新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Bing新闻请求异常: {e}")

        return news_items

    def _fetch_from_sogou_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从搜狗新闻搜索抓取新闻（补充源）"""
        news_items = []
        search_url = f"https://news.sogou.com/news?query={quote(keyword)}&mode=1&sort=0"

        try:
            resp = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"搜狗新闻请求失败: HTTP {resp.status_code}")
                return news_items

            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析搜狗新闻搜索结果
            result_items = soup.select("div.news-list li") or soup.select("div.results div.vrwrap")

            for item in result_items[:MAX_NEWS_PER_INDUSTRY]:
                try:
                    title_tag = item.select_one("h3 a") or item.select_one("a[href]")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    url = title_tag.get("href", "")

                    title = re.sub(r'<[^>]+>', '', title).strip()

                    if not title or len(title) < 4 or not url:
                        continue

                    summary_tag = item.select_one("p.txt-info") or item.select_one("div.news-detail")
                    summary = summary_tag.get_text(strip=True) if summary_tag else ""
                    summary = re.sub(r'<[^>]+>', '', summary)[:200]

                    source_tag = item.select_one("p.news-from span") or item.select_one("span.news-from")
                    source_text = source_tag.get_text(strip=True) if source_tag else "搜狗新闻"

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"解析搜狗新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"搜狗新闻请求异常: {e}")

        return news_items

    def fetch_from_rss(self) -> list[NewsItem]:
        """从RSS订阅源抓取新闻，并根据关键词匹配行业"""
        all_items = []

        for source_name, feed_url in RSS_FEEDS.items():
            try:
                logger.info(f"正在抓取RSS源: {source_name}")
                feed = feedparser.parse(feed_url)

                if feed.bozo and not feed.entries:
                    logger.warning(f"RSS源解析失败: {source_name} - {feed.bozo_exception}")
                    continue

                for entry in feed.entries[:20]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    published = entry.get("published", "")

                    if not title or not link:
                        continue

                    # 清理HTML标签
                    summary = re.sub(r'<[^>]+>', '', summary)[:200]

                    # 匹配行业
                    matched_industry = self._match_industry(title + summary)
                    if matched_industry:
                        news_item = NewsItem(
                            title=title,
                            url=link,
                            source=source_name,
                            industry=matched_industry,
                            summary=summary,
                            publish_time=published,
                        )
                        all_items.append(news_item)

            except Exception as e:
                logger.error(f"RSS源抓取失败 [{source_name}]: {e}")
                continue

            time.sleep(0.5)

        return self._deduplicate(all_items)

    def _match_industry(self, text: str) -> Optional[str]:
        """根据关键词匹配文本所属行业"""
        for industry, config in INDUSTRIES.items():
            for keyword in config["keywords"]:
                if keyword in text:
                    return industry
        return None

    def _deduplicate(self, news_items: list[NewsItem]) -> list[NewsItem]:
        """基于标题相似度去重"""
        unique_items = []
        for item in news_items:
            if item.uid not in self.seen_uids:
                self.seen_uids.add(item.uid)
                unique_items.append(item)
        return unique_items

    @staticmethod
    def _extract_time(text: str) -> str:
        """从文本中提取时间信息"""
        # 尝试匹配常见时间格式
        patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{1,2}小时前',
            r'\d{1,2}分钟前',
            r'今天\s*\d{2}:\d{2}',
            r'昨天\s*\d{2}:\d{2}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return ""


def fetch_news() -> dict[str, list[NewsItem]]:
    """
    便捷函数：抓取所有行业新闻
    Returns: {行业名: [NewsItem, ...]}
    """
    fetcher = NewsFetcher()

    # 从搜索引擎抓取
    search_news = fetcher.fetch_all()

    # 从RSS源抓取
    try:
        rss_news = fetcher.fetch_from_rss()
        for item in rss_news:
            if item.industry in search_news:
                if len(search_news[item.industry]) < MAX_NEWS_PER_INDUSTRY:
                    search_news[item.industry].append(item)
            else:
                search_news[item.industry] = [item]
    except Exception as e:
        logger.error(f"RSS新闻抓取失败: {e}")

    return search_news
