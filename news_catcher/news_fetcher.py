"""
新闻抓取模块 - 从多个源获取十五五规划重点行业新闻
News Fetcher Module - Fetch industry news from multiple sources

支持的新闻源：
1. 百度新闻搜索（主要源）
2. Bing 新闻搜索（备用源）
3. 搜狗新闻搜索（补充源）
4. RSS 订阅源
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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

# 新闻时效性：只保留最近 N 天内的新闻（默认 3 天）
NEWS_MAX_AGE_DAYS = 3

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
        """
        抓取单个行业的新闻
        优先级：搜狗（时效性最好）> 百度 > Bing
        所有源都会尝试，最后统一去重+过滤过期新闻
        """
        news_items: list[NewsItem] = []

        # 方法1：搜狗新闻搜索（时效性最好，优先使用）
        try:
            primary_keyword = keywords[0]
            items = self._fetch_from_sogou_news(primary_keyword, industry)
            news_items.extend(items)
            logger.debug(f"  搜狗新闻获取到 {len(items)} 条")
        except Exception as e:
            logger.error(f"搜狗新闻抓取失败 [{keywords[0]}]: {e}")
        time.sleep(1)

        # 方法2：百度新闻搜索
        for keyword in keywords[:2]:  # 每个行业最多使用前2个关键词
            try:
                items = self._fetch_from_baidu_news(keyword, industry)
                news_items.extend(items)
                logger.debug(f"  百度新闻[{keyword}]获取到 {len(items)} 条")
            except Exception as e:
                logger.error(f"百度新闻抓取失败 [{keyword}]: {e}")
            time.sleep(1)

        # 方法3：Bing 新闻搜索（补充国际视角）
        try:
            primary_keyword = keywords[0]
            items = self._fetch_from_bing_news(primary_keyword, industry)
            news_items.extend(items)
            logger.debug(f"  Bing新闻获取到 {len(items)} 条")
        except Exception as e:
            logger.error(f"Bing新闻抓取失败 [{keywords[0]}]: {e}")

        # 去重 + 过滤过期新闻
        unique_news = self._deduplicate(news_items)
        return unique_news

    def _fetch_from_baidu_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从百度新闻搜索抓取新闻（已适配百度改版后的页面结构）"""
        news_items = []
        # 添加 bsst=1 按时间排序，bt/et 限制时间范围为最近 3 天
        now = datetime.now()
        bt = str(int((now - timedelta(days=NEWS_MAX_AGE_DAYS)).timestamp()))
        et = str(int(now.timestamp()))
        search_url = (
            f"https://news.baidu.com/ns?word={quote(keyword)}"
            f"&tn=news&from=news&cl=2&rn=10&ct=1&bsst=1&bt={bt}&et={et}"
        )

        try:
            resp = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"百度新闻请求失败: HTTP {resp.status_code}")
                return news_items

            soup = BeautifulSoup(resp.text, "html.parser")

            # 百度改版后，搜索结果使用 h3 > a 结构
            # 容器选择器优先级：新版 result-op > 旧版 result
            h3_links = soup.select("h3 a")
            if not h3_links:
                logger.debug("百度新闻未找到 h3 a 链接")
                return news_items

            for h3_link in h3_links[:MAX_NEWS_PER_INDUSTRY]:
                try:
                    title = h3_link.get_text(strip=True)
                    url = h3_link.get("href", "")

                    # 清理标题中的HTML标签
                    title = re.sub(r'<[^>]+>', '', title).strip()

                    if not title or len(title) < 4 or not url:
                        continue

                    # 向上查找容器元素（h3 -> div -> 容器 div）
                    container = h3_link.parent
                    if container:
                        container = container.parent

                    summary = ""
                    source_text = "百度新闻"
                    publish_time = ""

                    if container:
                        # 提取摘要（新版结构）
                        content_el = (
                            container.select_one("[class*='content']")
                            or container.select_one("[class*='c-span-last']")
                            or container.select_one("div.c-summary")
                            or container.select_one("div.c-abstract")
                        )
                        if content_el:
                            summary = re.sub(r'<[^>]+>', '', content_el.get_text(strip=True))[:200]

                        # 提取来源（新版结构）
                        source_el = (
                            container.select_one("[class*='news-source']")
                            or container.select_one("[class*='source']")
                            or container.select_one("span.c-color-gray")
                            or container.select_one("p.c-author")
                        )
                        if source_el:
                            source_text = source_el.get_text(strip=True)

                        # 从内容中提取时间
                        full_text = container.get_text(strip=True)
                        publish_time = self._extract_time(full_text)

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                        publish_time=publish_time,
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"解析百度新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"百度新闻请求异常: {e}")

        return news_items

    def _fetch_from_bing_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从Bing新闻搜索抓取新闻（使用国际版 www.bing.com，cn.bing.com 已不稳定）"""
        news_items = []
        # 使用 www.bing.com + setlang=zh-CN + 按时间排序
        search_url = (
            f"https://www.bing.com/news/search"
            f"?q={quote(keyword)}&setlang=zh-CN"
            f"&qft=sortbydate%3d%221%22"
        )

        try:
            resp = self.session.get(search_url, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                logger.warning(f"Bing新闻请求失败: HTTP {resp.status_code}")
                return news_items

            soup = BeautifulSoup(resp.text, "html.parser")

            # 解析 Bing 新闻搜索结果（适配新版页面结构）
            result_items = (
                soup.select("div.news-card")
                or soup.select("div.newsitem")
                or soup.select("div[data-idx]")
            )

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
                        url = urljoin("https://www.bing.com", url)

                    summary_tag = item.select_one("div.snippet") or item.select_one("p")
                    summary = summary_tag.get_text(strip=True) if summary_tag else ""

                    # 提取来源和时间
                    source_div = item.select_one("div.source")
                    source_text = "Bing新闻"
                    publish_time = ""
                    if source_div:
                        spans = source_div.select("span")
                        # 通常第一个有文本的 span 是来源，最后一个是时间
                        text_spans = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]
                        if text_spans:
                            publish_time = text_spans[-1]  # 最后一个 span 通常是"X小时前"
                            # 尝试从非时间的 span 中找来源
                            for t in text_spans:
                                if not re.search(r'\d+\s*(小时|分钟|天|个月|秒)', t):
                                    source_text = t
                                    break

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                        publish_time=publish_time,
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"解析Bing新闻条目失败: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Bing新闻请求异常: {e}")

        return news_items

    def _fetch_from_sogou_news(self, keyword: str, industry: str) -> list[NewsItem]:
        """从搜狗新闻搜索抓取新闻（补充源，按时间排序）"""
        news_items = []
        # sort=1 按时间排序（原 sort=0 为默认排序，无法保证时效性）
        search_url = f"https://news.sogou.com/news?query={quote(keyword)}&mode=1&sort=1"

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

                    # 修复搜狗相对链接（/link?url=... 需要补全域名）
                    if url.startswith("/"):
                        url = urljoin("https://news.sogou.com", url)

                    summary_tag = item.select_one("p.txt-info") or item.select_one("div.news-detail")
                    summary = summary_tag.get_text(strip=True) if summary_tag else ""
                    summary = re.sub(r'<[^>]+>', '', summary)[:200]

                    # 提取来源（第一个 span）和时间（最后一个 span）
                    source_text = "搜狗新闻"
                    publish_time = ""
                    from_tag = item.select_one("p.news-from") or item.select_one("div.news-from")
                    if from_tag:
                        spans = from_tag.select("span")
                        text_spans = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]
                        if text_spans:
                            source_text = text_spans[0]
                        if len(text_spans) > 1:
                            publish_time = text_spans[-1]

                    news_item = NewsItem(
                        title=title,
                        url=url,
                        source=source_text,
                        industry=industry,
                        summary=summary,
                        publish_time=publish_time,
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
        """基于标题相似度去重，并过滤过期新闻"""
        unique_items = []
        for item in news_items:
            if item.uid not in self.seen_uids:
                # 过滤明确过期的新闻（能解析出日期且超过阈值的）
                if self._is_news_too_old(item):
                    logger.debug(f"过滤过期新闻: {item.title} (时间: {item.publish_time})")
                    continue
                self.seen_uids.add(item.uid)
                unique_items.append(item)
        return unique_items

    @staticmethod
    def _is_news_too_old(item: NewsItem) -> bool:
        """
        检查新闻是否过期（超过 NEWS_MAX_AGE_DAYS 天）
        通过 publish_time 和摘要中的日期来判断
        """
        now = datetime.now()
        cutoff = now - timedelta(days=NEWS_MAX_AGE_DAYS)

        # 检查 publish_time 字段
        check_texts = [item.publish_time, item.summary]
        for text in check_texts:
            if not text:
                continue

            # 尝试解析 "YYYY年M月D日" 格式
            match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
            if match:
                try:
                    news_date = datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                    )
                    if news_date < cutoff:
                        return True
                except ValueError:
                    pass

            # 尝试解析 "YYYY-MM-DD" 格式
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
            if match:
                try:
                    news_date = datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                    )
                    if news_date < cutoff:
                        return True
                except ValueError:
                    pass

            # "X天前" 或 "X 天" - 如果超过阈值则过期
            match = re.search(r'(\d+)\s*天', text)
            if match:
                days_ago = int(match.group(1))
                if days_ago > NEWS_MAX_AGE_DAYS:
                    return True

            # "X个月前" 或 "X 个月" - 一定过期
            if re.search(r'\d+\s*个月', text):
                return True

        # 无法判断日期时，保留新闻（宁可多不可少）
        return False

    @staticmethod
    def _extract_time(text: str) -> str:
        """从文本中提取时间信息"""
        # 尝试匹配常见时间格式
        patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{1,2}小时前',
            r'\d{1,2}分钟前',
            r'\d{1,2}天前',
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
