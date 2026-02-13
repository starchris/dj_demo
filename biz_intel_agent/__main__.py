"""
命令行入口 - 企业经营洞察与招聘预算分析 Agent
CLI Entry - Business Intelligence & Recruitment Budget Analysis Agent

使用方式（独立运行，不需要 Django 环境）：
    python -m biz_intel_agent --analyze 腾讯          # 分析并推送到飞书
    python -m biz_intel_agent --analyze 腾讯 --no-feishu  # 分析但不推送飞书
    python -m biz_intel_agent --research 字节跳动     # 仅采集信息（不调用 LLM）
    python -m biz_intel_agent --test-webhook          # 测试飞书 Webhook 连接
"""

import argparse
import logging
import sys


def setup_logging():
    """配置日志"""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def cmd_analyze(company_name: str, send_feishu: bool = True):
    """执行完整的企业分析"""
    from .agent import BusinessIntelAgent

    print(f"\n{'='*60}")
    print(f"🔍 开始分析「{company_name}」")
    print(f"{'='*60}\n")

    try:
        agent = BusinessIntelAgent()
        report = agent.analyze(company_name)

        if not report:
            print(f"\n❌ 未能生成分析报告")
            return 1

        print(f"\n{'='*60}")
        print(f"📋 分析报告")
        print(f"{'='*60}\n")
        print(report)
        print(f"\n{'='*60}")
        print(f"✅ 分析完成，报告长度: {len(report)} 字")

        # 推送到飞书
        if send_feishu:
            print(f"\n📤 正在推送报告到飞书群...")
            from .feishu_webhook import send_report_to_feishu
            success = send_report_to_feishu(company_name, report)
            if success:
                print(f"✅ 报告已推送到飞书群！")
            else:
                print(f"⚠️ 飞书推送失败（报告已在上方展示）")
        else:
            print(f"\n（已跳过飞书推送）")

    except ValueError as e:
        print(f"\n❌ 配置错误: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        return 1

    return 0


def cmd_research(company_name: str):
    """仅执行信息采集（不调用 LLM）"""
    from .company_researcher import CompanyResearcher

    print(f"\n{'='*60}")
    print(f"🔍 开始采集「{company_name}」的公开信息")
    print(f"{'='*60}\n")

    researcher = CompanyResearcher()
    data = researcher.research(company_name)

    if data.has_data:
        print(f"\n{'='*60}")
        print(f"📋 采集结果")
        print(f"{'='*60}\n")
        print(data.to_prompt_text())
        print(f"\n统计:")
        print(f"  基本信息: {len(data.basic_info)} 条")
        print(f"  财务融资: {len(data.financial_info)} 条")
        print(f"  业务新闻: {len(data.business_news)} 条")
        print(f"  招聘信息: {len(data.recruitment_info)} 条")
        print(f"  市场竞争: {len(data.market_info)} 条")
    else:
        print(f"\n⚠️ 未采集到有效信息")

    return 0


def cmd_test_webhook():
    """测试飞书 Webhook 连接"""
    from .config import FEISHU_WEBHOOK_URL, FEISHU_WEBHOOK_SECRET

    print(f"\n🧪 测试飞书 Webhook 连接...")
    print(f"   Webhook URL: {'已配置' if FEISHU_WEBHOOK_URL else '❌ 未配置'}")
    print(f"   签名密钥:    {'已配置' if FEISHU_WEBHOOK_SECRET else '未配置（可选）'}")

    if not FEISHU_WEBHOOK_URL:
        print(f"\n❌ FEISHU_WEBHOOK_URL 未配置。请设置环境变量:")
        print(f"   export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx'")
        print(f"\n   获取方式：飞书群设置 → 群机器人 → 添加机器人 → 自定义机器人")
        return 1

    from .feishu_webhook import test_webhook_connection
    success = test_webhook_connection()

    if success:
        print(f"\n✅ 飞书 Webhook 连接测试成功！消息已发送到飞书群。")
    else:
        print(f"\n❌ 飞书 Webhook 连接测试失败，请检查 URL 是否正确。")

    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(
        description="📊 企业经营洞察与招聘预算分析 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m biz_intel_agent --analyze 腾讯              # 分析并推送到飞书群
  python -m biz_intel_agent --analyze 字节跳动 --no-feishu  # 仅在终端展示
  python -m biz_intel_agent --research 宁德时代         # 仅采集公开信息
  python -m biz_intel_agent --test-webhook              # 测试飞书 Webhook

环境变量:
  FEISHU_WEBHOOK_URL     飞书自定义机器人 Webhook URL（必填）
  FEISHU_WEBHOOK_SECRET  Webhook 签名密钥（可选）
  LLM_API_KEY            LLM API 密钥（必填）
  LLM_BASE_URL           LLM API 地址（默认 Kimi）
  LLM_MODEL              LLM 模型名（默认 kimi-k2.5）
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--analyze", type=str, metavar="公司名称",
                       help="分析指定公司并推送到飞书")
    group.add_argument("--research", type=str, metavar="公司名称",
                       help="仅采集公司信息（不调用 LLM）")
    group.add_argument("--test-webhook", action="store_true",
                       help="测试飞书 Webhook 连接")

    parser.add_argument("--no-feishu", action="store_true",
                        help="不推送到飞书（仅在终端展示）")

    args = parser.parse_args()
    setup_logging()

    if args.analyze:
        exit_code = cmd_analyze(args.analyze, send_feishu=not args.no_feishu)
    elif args.research:
        exit_code = cmd_research(args.research)
    elif args.test_webhook:
        exit_code = cmd_test_webhook()
    else:
        parser.print_help()
        exit_code = 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
