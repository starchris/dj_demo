"""
命令行入口 - 企业经营洞察与招聘预算分析 Agent
CLI Entry - Business Intelligence & Recruitment Budget Analysis Agent

使用方式（独立运行，不需要飞书环境）：
    python -m biz_intel_agent --analyze 腾讯          # 分析指定公司
    python -m biz_intel_agent --research 字节跳动     # 仅采集信息（不调用 LLM）
    python -m biz_intel_agent --test-feishu           # 测试飞书连接
"""

import argparse
import json
import logging
import os
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


def cmd_analyze(company_name: str):
    """执行完整的企业分析"""
    from .agent import BusinessIntelAgent

    print(f"\n{'='*60}")
    print(f"🔍 开始分析「{company_name}」")
    print(f"{'='*60}\n")

    try:
        agent = BusinessIntelAgent()
        report = agent.analyze(company_name)

        if report:
            print(f"\n{'='*60}")
            print(f"📋 分析报告")
            print(f"{'='*60}\n")
            print(report)
            print(f"\n{'='*60}")
            print(f"✅ 分析完成，报告长度: {len(report)} 字")
        else:
            print(f"\n❌ 未能生成分析报告")
            return 1

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


def cmd_test_feishu():
    """测试飞书机器人连接"""
    from .feishu_bot import FeishuBot
    from .config import FEISHU_APP_ID, FEISHU_APP_SECRET

    print(f"\n🧪 测试飞书连接...")
    print(f"   APP_ID: {'已配置' if FEISHU_APP_ID else '❌ 未配置'}")
    print(f"   APP_SECRET: {'已配置' if FEISHU_APP_SECRET else '❌ 未配置'}")

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print(f"\n❌ 飞书凭证未配置。请设置环境变量:")
        print(f"   export FEISHU_APP_ID='cli_xxxxx'")
        print(f"   export FEISHU_APP_SECRET='xxxxx'")
        return 1

    try:
        bot = FeishuBot()
        token = bot._get_tenant_access_token()
        print(f"   Token: 获取成功 ({token[:10]}...)")
        print(f"\n✅ 飞书连接测试成功！")
        return 0
    except Exception as e:
        print(f"\n❌ 飞书连接测试失败: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="📊 企业经营洞察与招聘预算分析 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m biz_intel_agent --analyze 腾讯          # 完整分析
  python -m biz_intel_agent --analyze 字节跳动      # 完整分析
  python -m biz_intel_agent --research 宁德时代     # 仅信息采集
  python -m biz_intel_agent --test-feishu           # 测试飞书连接

环境变量:
  FEISHU_APP_ID          飞书应用 App ID
  FEISHU_APP_SECRET      飞书应用 App Secret
  FEISHU_VERIFICATION_TOKEN  飞书事件订阅验证 Token
  LLM_API_KEY            LLM API 密钥
  LLM_BASE_URL           LLM API 地址（默认 Kimi）
  LLM_MODEL              LLM 模型名（默认 kimi-k2.5）
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--analyze", type=str, metavar="公司名称", help="分析指定公司（完整流程）")
    group.add_argument("--research", type=str, metavar="公司名称", help="仅采集公司信息（不调用 LLM）")
    group.add_argument("--test-feishu", action="store_true", help="测试飞书连接")

    args = parser.parse_args()
    setup_logging()

    if args.analyze:
        exit_code = cmd_analyze(args.analyze)
    elif args.research:
        exit_code = cmd_research(args.research)
    elif args.test_feishu:
        exit_code = cmd_test_feishu()
    else:
        parser.print_help()
        exit_code = 0

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
