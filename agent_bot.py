#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent模式Telegram Bot - 使用Anthropic SDK实现工具调用和决策循环
100% 虚拟机运行，使用Sonnet 4.5
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import anthropic
from pyrogram import Client

# 日志配置
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('agent_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== 配置 =====
TELEGRAM_TOKEN = "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4"
SEARCH_BOT_USERNAME = "openaiw_bot"

# Claude API配置
try:
    CLAUDE_CLIENT = anthropic.Anthropic(
        auth_token=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
        base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    )
    logger.info("✅ Claude Agent客户端初始化成功")
except Exception as e:
    logger.error(f"❌ Claude客户端初始化失败: {e}")
    CLAUDE_CLIENT = None

# ===== 工具定义 =====
TOOLS = [
    {
        "name": "search_telegram_groups",
        "description": "在Telegram中搜索群组。当用户想要查找群组、频道或者需要搜索特定关键词时使用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，例如 'AI'、'翻译'、'编程' 等"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["groups", "text", "human", "topchat"],
                    "description": "搜索类型：groups=群组名称，text=讨论内容，human=用户，topchat=热门分类",
                    "default": "groups"
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "get_cached_results",
        "description": "从数据库获取已缓存的搜索结果。用于快速返回之前搜索过的内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "搜索命令，如 'search'、'text' 等"
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词"
                }
            },
            "required": ["command", "keyword"]
        }
    }
]

# ===== Agent决策引擎 =====
class ClaudeAgent:
    """Claude Agent - 带工具调用和决策循环"""

    def __init__(self):
        self.client = CLAUDE_CLIENT
        self.model = "claude-sonnet-4-5-20250929"
        self.max_tokens = 2048
        self.conversations: Dict[int, List[Dict]] = {}  # 用户对话历史
        self.max_history = 10
        logger.info("✅ Claude Agent引擎初始化完成")

    def get_history(self, user_id: int) -> List[Dict]:
        """获取用户对话历史"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id][-self.max_history:]

    def add_to_history(self, user_id: int, role: str, content: Any):
        """添加到对话历史"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append({"role": role, "content": content})

    async def think_and_act(self, user_id: int, user_message: str) -> Dict[str, Any]:
        """
        决策循环：思考 -> 选择工具 -> 执行 -> 返回结果

        返回:
            {
                "response": "AI回复文本",
                "tools_used": [{"name": "tool_name", "input": {...}, "result": ...}],
                "buttons": [{"text": "...", "callback_data": "..."}]
            }
        """
        logger.info(f"[Agent] 用户 {user_id} 发起对话: {user_message}")

        # 构建消息历史
        history = self.get_history(user_id)
        messages = history + [{"role": "user", "content": user_message}]

        try:
            # 第一轮：调用Claude获取决策
            logger.info(f"[Agent] 调用Claude API（带工具）")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                tools=TOOLS,
                messages=messages
            )

            logger.info(f"[Agent] Claude响应类型: {response.stop_reason}")

            # 处理工具调用
            tools_used = []
            final_text = ""

            if response.stop_reason == "tool_use":
                # Claude决定使用工具
                logger.info(f"[Agent] Claude决定使用工具")

                # 提取工具调用和文本
                tool_results = []
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text
                    elif block.type == "tool_use":
                        logger.info(f"[Agent] 工具调用: {block.name} - {block.input}")

                        # 执行工具
                        tool_result = await self._execute_tool(block.name, block.input)
                        tools_used.append({
                            "name": block.name,
                            "input": block.input,
                            "result": tool_result
                        })

                        # 准备工具结果给Claude
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })

                # 第二轮：将工具结果返回给Claude
                if tool_results:
                    logger.info(f"[Agent] 将工具结果返回给Claude")
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                    # 再次调用Claude获取最终回复
                    final_response = self.client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        tools=TOOLS,
                        messages=messages
                    )

                    # 提取最终文本
                    for block in final_response.content:
                        if block.type == "text":
                            final_text += block.text

            else:
                # 直接回复，无需工具
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text

            # 保存对话历史
            self.add_to_history(user_id, "user", user_message)
            self.add_to_history(user_id, "assistant", final_text)

            # 提取按钮
            buttons = self._extract_buttons(final_text)

            logger.info(f"[Agent] ✅ 完成决策循环，使用了 {len(tools_used)} 个工具")

            return {
                "response": final_text,
                "tools_used": tools_used,
                "buttons": buttons
            }

        except Exception as e:
            logger.error(f"[Agent] ❌ 决策失败: {e}")
            return {
                "response": f"抱歉，我遇到了一些问题：{str(e)}",
                "tools_used": [],
                "buttons": []
            }

    async def _execute_tool(self, tool_name: str, tool_input: Dict) -> Any:
        """执行工具调用"""
        logger.info(f"[工具执行] {tool_name}({tool_input})")

        if tool_name == "search_telegram_groups":
            keyword = tool_input.get("keyword", "")
            search_type = tool_input.get("search_type", "groups")

            # 调用实际搜索（通过Pyrogram镜像）
            result = await self._perform_telegram_search(keyword, search_type)
            return result

        elif tool_name == "get_cached_results":
            command = tool_input.get("command", "")
            keyword = tool_input.get("keyword", "")

            # 从数据库获取缓存
            # TODO: 实际连接数据库
            return {
                "status": "success",
                "cached": True,
                "results": []
            }

        return {"status": "unknown_tool"}

    async def _perform_telegram_search(self, keyword: str, search_type: str) -> Dict:
        """执行Telegram搜索（镜像openaiw_bot）"""
        # TODO: 实际通过Pyrogram发送搜索命令
        logger.info(f"[搜索] 类型={search_type}, 关键词={keyword}")

        # 模拟返回结果
        return {
            "status": "success",
            "keyword": keyword,
            "search_type": search_type,
            "results_count": 5,
            "message": f"搜索 '{keyword}' 完成"
        }

    def _extract_buttons(self, text: str) -> List[Dict[str, str]]:
        """从AI回复中提取可点击按钮"""
        buttons = []

        # 提取命令格式：/search xxx, /text xxx
        import re
        patterns = [
            r'/search\s+(\S+)',
            r'/text\s+(\S+)',
            r'/human\s+(\S+)',
            r'/topchat'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if pattern == r'/topchat':
                    buttons.append({
                        "text": "🔥 热门分类",
                        "callback_data": "cmd_topchat"
                    })
                else:
                    cmd = pattern.split('\\s')[0].replace('/', '')
                    buttons.append({
                        "text": f"🔍 {cmd} {match}",
                        "callback_data": f"cmd_{cmd}_{match}"[:64]
                    })

        return buttons

# ===== Bot处理器 =====
class AgentBot:
    """Agent模式Telegram Bot"""

    def __init__(self):
        self.agent = ClaudeAgent()
        self.app = None
        logger.info("✅ Agent Bot初始化完成")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user_id = update.effective_user.id
        logger.info(f"[命令] 用户 {user_id} 启动Bot")

        welcome = (
            "👋 你好！我是AI Agent Bot\n\n"
            "💡 我可以帮你：\n"
            "- 🔍 智能搜索Telegram群组\n"
            "- 💬 自然语言对话\n"
            "- 🤖 自动选择合适的工具\n\n"
            "直接告诉我你想做什么吧！"
        )
        await update.message.reply_text(welcome)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息 - Agent决策入口"""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"[消息] 用户 {user_id}: {user_message}")

        # 调用Agent决策循环
        result = await self.agent.think_and_act(user_id, user_message)

        # 构建回复
        response_text = result["response"]
        buttons = result["buttons"]
        tools_used = result["tools_used"]

        # 添加工具使用信息
        if tools_used:
            tool_info = "\n\n🔧 使用的工具:\n"
            for tool in tools_used:
                tool_info += f"- {tool['name']}\n"
            response_text += tool_info

        # 发送回复（带按钮）
        if buttons:
            keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])]
                       for btn in buttons]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                response_text,
                reply_markup=reply_markup
            )
            logger.info(f"[回复] 已发送（带 {len(buttons)} 个按钮）")
        else:
            await update.message.reply_text(response_text)
            logger.info(f"[回复] 已发送")

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮点击"""
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        logger.info(f"[按钮] 用户点击: {callback_data}")

        # 解析按钮命令
        if callback_data.startswith("cmd_"):
            parts = callback_data[4:].split("_")
            command = parts[0]
            keyword = "_".join(parts[1:]) if len(parts) > 1 else ""

            # 将按钮点击转换为消息，重新进入Agent决策
            user_message = f"/{command} {keyword}".strip()
            user_id = query.from_user.id

            logger.info(f"[按钮->命令] 转换为消息: {user_message}")

            result = await self.agent.think_and_act(user_id, user_message)

            await query.message.reply_text(result["response"])

    def run(self):
        """启动Bot"""
        logger.info("🚀 启动Agent Bot...")

        # 创建Application
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()

        # 注册处理器
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.handle_button))

        # 启动轮询
        logger.info("✅ Agent Bot已启动，等待用户消息...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

# ===== 主入口 =====
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 Claude Agent Bot - 启动中")
    logger.info(f"📅 时间: {datetime.now()}")
    logger.info(f"🔑 Auth Token: {os.environ.get('ANTHROPIC_AUTH_TOKEN', 'NOT SET')[:20]}...")
    logger.info(f"🌐 Base URL: {os.environ.get('ANTHROPIC_BASE_URL', 'NOT SET')}")
    logger.info("=" * 60)

    if not CLAUDE_CLIENT:
        logger.error("❌ Claude客户端未初始化，无法启动")
        exit(1)

    bot = AgentBot()
    bot.run()
