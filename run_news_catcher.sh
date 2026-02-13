#!/bin/bash
# 热点新闻捕捉器 - 运行脚本
# Hot News Catcher - Run Script

# 使用方式:
#   ./run_news_catcher.sh test          # 测试模式（仅抓取不发送）
#   ./run_news_catcher.sh run           # 立即运行一次
#   ./run_news_catcher.sh schedule      # 启动定时任务
#   ./run_news_catcher.sh test-feishu   # 测试飞书连接

# 切换到项目目录
cd "$(dirname "$0")"

# 检查 Python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "错误: 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

# 检查依赖
$PYTHON -c "import requests, bs4, feedparser, schedule" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    $PYTHON -m pip install -r news_catcher/requirements.txt
fi

# 运行
MODE=${1:-test}
case $MODE in
    test)
        echo "🧪 测试模式 - 仅抓取新闻不发送"
        $PYTHON -m news_catcher --test
        ;;
    run)
        echo "🚀 正式模式 - 抓取并发送到飞书"
        $PYTHON -m news_catcher --run-once
        ;;
    schedule)
        echo "⏰ 启动定时任务"
        $PYTHON -m news_catcher --schedule
        ;;
    test-feishu)
        echo "🔗 测试飞书连接"
        $PYTHON -m news_catcher --test-feishu
        ;;
    *)
        echo "用法: $0 {test|run|schedule|test-feishu}"
        echo "  test        - 测试模式（仅抓取不发送）"
        echo "  run         - 立即运行一次"
        echo "  schedule    - 启动定时任务"
        echo "  test-feishu - 测试飞书连接"
        exit 1
        ;;
esac
