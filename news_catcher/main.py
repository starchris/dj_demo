"""
主程序 - 热点新闻捕捉器
Main Entry - Hot News Catcher for 15th Five-Year Plan Industries

流程：
  1. 抓取新闻  ->  2. 生成行业动态总结  ->  3. 发送到飞书

使用方式：
    python -m news_catcher --run-once        # 立即运行一次
    python -m news_catcher --schedule         # 启动定时任务
    python -m news_catcher --test             # 测试模式（不发送飞书）
    python -m news_catcher --test-feishu      # 测试飞书连接
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import schedule
import time

from .config import (
    LOG_DIR,
    LOG_LEVEL,
    LLM_API_KEY,
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    TIMEZONE,
    INDUSTRIES,
)
from .feishu_notifier import FeishuNotifier, send_to_feishu
from .funding_fetcher import FundingEvent, fetch_funding_events
from .news_fetcher import NewsFetcher, fetch_news
from .summarizer import generate_summaries


# ============================================================
# 日志配置
# ============================================================
def setup_logging():
    """配置日志"""
    os.makedirs(LOG_DIR, exist_ok=True)

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    log_file = os.path.join(LOG_DIR, f"news_catcher_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    root_logger = logging.getLogger("news_catcher")
    root_logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return root_logger


logger = None


# ============================================================
# 核心任务
# ============================================================
def run_news_job(test_mode: bool = False) -> bool:
    """
    执行一次完整的新闻抓取 -> 总结 -> 发送流程
    """
    global logger
    if logger is None:
        logger = setup_logging()

    logger.info("=" * 60)
    logger.info("🔥 热点新闻捕捉器 - 开始执行")
    logger.info(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  模式: {'测试模式' if test_mode else '正式模式'}")
    logger.info(f"  LLM 总结: {'已配置' if LLM_API_KEY else '未配置（将使用标题摘要模式）'}")
    logger.info("=" * 60)

    try:
        # ── Step 1: 抓取新闻 ──
        logger.info("\n📡 Step 1/4: 抓取行业新闻...")
        news_by_industry = fetch_news()

        if not news_by_industry:
            logger.warning("未获取到任何新闻，任务结束")
            return False

        total_count = sum(len(items) for items in news_by_industry.values())
        logger.info(f"\n📊 抓取结果统计:")
        for industry, items in news_by_industry.items():
            emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
            logger.info(f"  {emoji} {industry}: {len(items)} 条")
        logger.info(f"  ────────────────")
        logger.info(f"  📰 总计: {total_count} 条")

        # ── Step 2: 抓取投融资/IPO 事件 ──
        logger.info("\n💰 Step 2/4: 抓取投融资/IPO 事件...")
        funding_by_industry: dict[str, list[FundingEvent]] = {}
        try:
            funding_by_industry = fetch_funding_events()
            funding_total = sum(len(v) for v in funding_by_industry.values())
            logger.info(f"  💰 投融资事件: {funding_total} 条（覆盖 {len(funding_by_industry)} 个行业）")
            for industry, events in funding_by_industry.items():
                emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
                for evt in events:
                    logger.info(f"    {emoji} {evt.highlight_text()}")
        except Exception as e:
            logger.error(f"投融资抓取失败（不影响主流程）: {e}")

        # ── Step 3: 生成行业动态总结 ──
        logger.info("\n🧠 Step 3/4: 生成行业动态总结...")
        summaries = generate_summaries(news_by_industry, funding_by_industry)

        logger.info(f"\n📝 总结生成完成，共 {len(summaries)} 个行业：")
        for industry, summary in summaries.items():
            emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
            # 显示总结的前两行
            preview_lines = summary.strip().split("\n")[:2]
            preview = " / ".join(line.strip() for line in preview_lines)
            if len(summary.strip().split("\n")) > 2:
                preview += " ..."
            logger.info(f"  {emoji} {industry}: {preview}")

        # 保存到本地（备份，含总结）
        save_news_to_file(news_by_industry, summaries, funding_by_industry)

        # ── Step 4: 发送到飞书 ──
        if test_mode:
            logger.info("\n🧪 测试模式：跳过飞书发送")
            logger.info("\n" + "─" * 50)
            logger.info("📋 以下为各行业完整总结：")
            logger.info("─" * 50)
            for industry, summary in summaries.items():
                emoji = INDUSTRIES.get(industry, {}).get("emoji", "📰")
                logger.info(f"\n{emoji} 【{industry}】")
                # 显示投融资高亮
                if industry in funding_by_industry:
                    for evt in funding_by_industry[industry]:
                        logger.info(f"  🔥 {evt.highlight_text()}")
                for line in summary.strip().split("\n"):
                    logger.info(f"  {line}")
                logger.info(f"  （{len(news_by_industry.get(industry, []))} 条相关新闻）")
            logger.info("─" * 50)
            return True
        else:
            logger.info("\n📤 Step 4/4: 发送到飞书...")
            success = send_to_feishu(
                news_by_industry,
                summaries=summaries,
                funding_by_industry=funding_by_industry,
            )

            if success:
                logger.info("✅ 行业动态速览已成功发送到飞书！")
            else:
                logger.error("❌ 飞书发送失败")
            return success

    except Exception as e:
        logger.error(f"❌ 任务执行失败: {e}", exc_info=True)
        return False
    finally:
        logger.info("=" * 60)
        logger.info("任务执行完毕\n")


def save_news_to_file(
    news_by_industry: dict,
    summaries: dict[str, str] = None,
    funding_by_industry: dict = None,
) -> None:
    """保存新闻、总结和投融资事件到本地 JSON（备份）"""
    global logger
    if logger is None:
        logger = setup_logging()

    try:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)

        filename = f"news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(data_dir, filename)

        serializable = {}
        for industry, items in news_by_industry.items():
            industry_data = {
                "summary": summaries.get(industry, "") if summaries else "",
                "news": [item.to_dict() for item in items],
            }
            # 附加投融资事件
            if funding_by_industry and industry in funding_by_industry:
                industry_data["funding_events"] = [
                    evt.to_dict() for evt in funding_by_industry[industry]
                ]
            serializable[industry] = industry_data

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

        logger.info(f"📁 新闻已保存到: {filepath}")
    except Exception as e:
        logger.error(f"保存新闻文件失败: {e}")


# ============================================================
# 定时任务
# ============================================================
def start_scheduler():
    """启动定时任务"""
    global logger
    if logger is None:
        logger = setup_logging()

    schedule_time = f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}"
    logger.info(f"⏰ 定时任务已启动，每日 {schedule_time} 执行")
    logger.info(f"   时区: {TIMEZONE}")
    logger.info(f"   按 Ctrl+C 停止\n")

    schedule.every().day.at(schedule_time).do(run_news_job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("\n⏹ 定时任务已停止")


def test_feishu_connection():
    """测试飞书 Webhook 连接"""
    global logger
    if logger is None:
        logger = setup_logging()

    logger.info("🧪 测试飞书 Webhook 连接...")
    try:
        notifier = FeishuNotifier()
        success = notifier.send_text(
            f"🔔 热点新闻捕捉器测试消息\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"状态: 连接正常 ✅\n"
            f"LLM 总结: {'已配置' if LLM_API_KEY else '未配置'}\n"
            f"覆盖行业: {', '.join(INDUSTRIES.keys())}"
        )
        if success:
            logger.info("✅ 飞书连接测试成功！")
        else:
            logger.error("❌ 飞书连接测试失败")
        return success
    except Exception as e:
        logger.error(f"❌ 飞书连接测试异常: {e}")
        return False


# ============================================================
# 命令行入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="🔥 热点新闻捕捉器 - 十五五规划重点行业动态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m news_catcher --run-once        # 立即运行一次
  python -m news_catcher --schedule         # 启动定时任务
  python -m news_catcher --test             # 测试模式（不发送飞书）
  python -m news_catcher --test-feishu      # 测试飞书连接

环境变量:
  FEISHU_WEBHOOK_URL     飞书自定义机器人 Webhook URL
  FEISHU_WEBHOOK_SECRET  飞书签名密钥（可选）
  LLM_API_KEY            LLM API 密钥（DeepSeek/Moonshot/OpenAI）
  LLM_BASE_URL           LLM API 地址（默认 https://api.deepseek.com）
  LLM_MODEL              LLM 模型名（默认 deepseek-chat）
  LOG_LEVEL              日志级别（默认 INFO）
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-once", action="store_true", help="立即执行一次")
    group.add_argument("--schedule", action="store_true", help="启动每日定时任务")
    group.add_argument("--test", action="store_true", help="测试模式（不发送飞书）")
    group.add_argument("--test-feishu", action="store_true", help="测试飞书连接")

    parser.add_argument("--webhook-url", type=str, help="指定飞书 Webhook URL")
    parser.add_argument("--llm-key", type=str, help="指定 LLM API Key")

    args = parser.parse_args()

    if args.webhook_url:
        os.environ["FEISHU_WEBHOOK_URL"] = args.webhook_url
    if args.llm_key:
        os.environ["LLM_API_KEY"] = args.llm_key

    if args.run_once:
        success = run_news_job(test_mode=False)
        sys.exit(0 if success else 1)
    elif args.schedule:
        start_scheduler()
    elif args.test:
        success = run_news_job(test_mode=True)
        sys.exit(0 if success else 1)
    elif args.test_feishu:
        success = test_feishu_connection()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
