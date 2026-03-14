#!/usr/bin/env python3
"""
播客数据分析 Agent - 基于 Claude AI 的智能分析助手

支持两种使用模式：
  1. 交互式对话模式（默认）
  2. 单次查询模式

用法：
  python podcast_agent.py                    # 交互式对话
  python podcast_agent.py "哪个播客增长最快？"  # 单次查询
  python podcast_agent.py --analyze          # 自动生成今日数据洞察
"""

import json
import sys
import argparse
import os
from datetime import date
from pathlib import Path

import anthropic

from data_manager import PodcastDataManager

# ─────────────────────────────────────────────
# 工具定义
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_all_podcasts",
        "description": "获取配置文件中所有播客的信息列表，包括名称、分类、基金公司、是否启用等。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_all_latest_data",
        "description": "从数据库获取所有播客的最新数据快照，包含订阅数、最新单集标题、播放量、评论数、点赞数、收藏数等指标。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_comparison_report",
        "description": "获取今日与昨日的对比报告，展示每个播客的订阅数变化、是否有新单集等信息。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_trend_data",
        "description": "获取指定播客的历史趋势数据，可查看订阅数和单集数据的变化趋势。",
        "input_schema": {
            "type": "object",
            "properties": {
                "podcast_id": {
                    "type": "string",
                    "description": "播客的24位十六进制ID"
                },
                "days": {
                    "type": "integer",
                    "description": "查看历史天数，默认7天",
                    "default": 7
                }
            },
            "required": ["podcast_id"]
        }
    },
    {
        "name": "get_podcast_snapshot",
        "description": "获取指定播客的最新数据快照详情。",
        "input_schema": {
            "type": "object",
            "properties": {
                "podcast_id": {
                    "type": "string",
                    "description": "播客的24位十六进制ID"
                }
            },
            "required": ["podcast_id"]
        }
    }
]

# ─────────────────────────────────────────────
# 工具执行
# ─────────────────────────────────────────────

def _load_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def execute_tool(name: str, tool_input: dict, db: PodcastDataManager) -> str:
    """执行工具调用并返回 JSON 字符串结果。"""
    try:
        if name == "get_all_podcasts":
            config = _load_config()
            podcasts = config.get("podcasts", [])
            result = [
                {
                    "name": p.get("name"),
                    "podcast_id": p.get("podcast_id", ""),
                    "category": p.get("category"),
                    "fund_company_name": p.get("fund_company_name"),
                    "enabled": p.get("enabled", True)
                }
                for p in podcasts
            ]
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif name == "get_all_latest_data":
            snapshots = db.get_all_latest_snapshots()
            if not snapshots:
                return json.dumps({"message": "数据库暂无数据，请先运行 python main.py 爬取数据。"}, ensure_ascii=False)
            return json.dumps(snapshots, ensure_ascii=False, indent=2, default=str)

        elif name == "get_comparison_report":
            report = db.get_comparison_report()
            if not report:
                return json.dumps({"message": "暂无对比数据，可能今日或昨日数据缺失。"}, ensure_ascii=False)
            return json.dumps(report, ensure_ascii=False, indent=2, default=str)

        elif name == "get_trend_data":
            podcast_id = tool_input.get("podcast_id")
            days = tool_input.get("days", 7)
            trend = db.get_history_trend(podcast_id, days)
            if not trend:
                return json.dumps({"message": f"播客 {podcast_id} 暂无历史数据。"}, ensure_ascii=False)
            return json.dumps(trend, ensure_ascii=False, indent=2, default=str)

        elif name == "get_podcast_snapshot":
            podcast_id = tool_input.get("podcast_id")
            snapshot = db.get_latest_snapshot(podcast_id)
            if not snapshot:
                return json.dumps({"message": f"播客 {podcast_id} 暂无数据。"}, ensure_ascii=False)
            return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)

        else:
            return json.dumps({"error": f"未知工具：{name}"}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ─────────────────────────────────────────────
# Agent 核心逻辑
# ─────────────────────────────────────────────

SYSTEM_PROMPT = f"""你是一个专业的公募基金播客数据分析助手，服务于基金行业研究人员。

你的能力：
- 查询和分析小宇宙平台上公募基金公司的播客数据
- 对比播客订阅数变化趋势，发现高增长播客
- 分析单集互动数据（播放量、评论、点赞、收藏）
- 识别哪些基金公司的播客内容运营更活跃
- 今天的日期是 {date.today().strftime('%Y年%m月%d日')}

数据说明：
- 数据来自小宇宙（xiaoyuzhoufm.com）平台
- 播客分为"公募基金"和"泛财经"两个分类
- 订阅数反映节目受众规模，互动指标（点赞+收藏）反映内容质量

回答风格：
- 使用中文回答，语言专业、简洁
- 数据分析时提供具体数字和百分比
- 发现异常或亮点时主动点评
- 如果数据库为空，请指导用户先运行 python main.py
"""


def run_agent(user_message: str, db: PodcastDataManager, stream_output: bool = True) -> str:
    """
    运行一次 Agent 对话，自动处理工具调用循环。
    返回最终的文本回答。
    """
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]
    final_text = ""

    while True:
        if stream_output:
            # 流式输出，实时显示
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            print(event.delta.text, end="", flush=True)

                response = stream.get_final_message()
        else:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

        # 提取文本块
        for block in response.content:
            if block.type == "text":
                final_text = block.text

        # 检查是否需要调用工具
        if response.stop_reason != "tool_use":
            break

        # 收集所有工具调用
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        # 将 assistant 回复加入消息历史
        messages.append({"role": "assistant", "content": response.content})

        # 执行工具并收集结果
        tool_results = []
        for tool_use in tool_use_blocks:
            if stream_output:
                print(f"\n\n[调用工具: {tool_use.name}]", flush=True)

            result_content = execute_tool(tool_use.name, tool_use.input, db)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_content,
            })

        messages.append({"role": "user", "content": tool_results})

        if stream_output:
            print()  # 换行，准备显示下一轮回答

    if stream_output:
        print()  # 最终换行

    return final_text


# ─────────────────────────────────────────────
# 预设分析任务
# ─────────────────────────────────────────────

ANALYZE_PROMPT = """请帮我对今日的公募基金播客数据进行全面分析，包括：

1. **整体概况**：共监控多少个播客，今日有数据的有多少个
2. **订阅数排行**：列出订阅数 Top 5 的播客
3. **今日更新**：哪些播客今日发布了新单集
4. **互动亮点**：互动指标（点赞+收藏）最高的单集是哪个
5. **环比变化**：与昨日相比，订阅数增长最明显的播客
6. **内容运营活跃度**：哪些基金公司的播客运营最活跃

请基于实际数据给出具体数字和简要点评。"""


# ─────────────────────────────────────────────
# 交互式 REPL
# ─────────────────────────────────────────────

def interactive_mode(db: PodcastDataManager):
    """交互式对话模式。"""
    print("=" * 60)
    print("  公募基金播客数据分析 Agent")
    print(f"  今日日期：{date.today().strftime('%Y年%m月%d日')}")
    print("=" * 60)
    print("输入问题开始对话，输入 'quit' 或 'exit' 退出")
    print("输入 'analyze' 自动生成今日数据洞察\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "退出"):
            print("再见！")
            break
        if user_input.lower() == "analyze":
            user_input = ANALYZE_PROMPT

        print("\nAgent: ", end="", flush=True)
        run_agent(user_input, db, stream_output=True)
        print()


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="公募基金播客数据分析 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python podcast_agent.py                          # 交互式对话
  python podcast_agent.py "哪个播客订阅数最高？"    # 单次查询
  python podcast_agent.py --analyze                # 生成今日数据洞察
        """
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="单次查询内容（不提供则进入交互模式）"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="自动生成今日播客数据全面分析报告"
    )
    parser.add_argument(
        "--db",
        default="data/podcast_monitor.db",
        help="数据库路径（默认：data/podcast_monitor.db）"
    )

    args = parser.parse_args()

    # 检查 API Key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("错误：未设置 ANTHROPIC_API_KEY 环境变量")
        print("请执行：export ANTHROPIC_API_KEY='your-api-key'")
        sys.exit(1)

    # 初始化数据库连接
    db = PodcastDataManager(args.db)

    if args.analyze:
        print("Agent: ", end="", flush=True)
        run_agent(ANALYZE_PROMPT, db, stream_output=True)
    elif args.query:
        print("Agent: ", end="", flush=True)
        run_agent(args.query, db, stream_output=True)
    else:
        interactive_mode(db)


if __name__ == "__main__":
    main()
