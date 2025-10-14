#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一Telegram Bot - 整合所有功能
- Anthropic SDK直接调用Claude
- Pyrogram镜像搜索@openaiw_bot
- 自动翻页抓取2-10页
- SQLite缓存管理
- 智能按钮生成
"""

import os
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pyrogram import Client
from pyrogram.errors import FloodWait
import sqlite3
import anthropic

# ===== 配置 =====
TELEGRAM_TOKEN = "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4"
SEARCH_BOT_USERNAME = "openaiw_bot"

# Pyrogram配置
API_ID = 29648923
API_HASH = "8fd250a5459ebb547c4c3985ad15bd32"
PROXY = {"scheme": "socks5", "hostname": "127.0.0.1", "port": 1080}

# 日志配置
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('unified_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== 数据库管理 =====
class Database:
    """SQLite缓存数据库"""

    def __init__(self, db_path='cache.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT,
                keyword TEXT,
                page INTEGER,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search ON cache(command, keyword, page)')
        conn.commit()
        conn.close()
        logger.info("✅ 数据库初始化完成")

    def get_cache(self, command: str, keyword: str, page: int = 1) -> Optional[str]:
        """获取缓存结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查是否有30天内的缓存
        cursor.execute('''
            SELECT content FROM cache
            WHERE command = ? AND keyword = ? AND page = ?
            AND timestamp > datetime('now', '-30 days')
            ORDER BY timestamp DESC LIMIT 1
        ''', (command, keyword, page))

        result = cursor.fetchone()
        conn.close()

        if result:
            logger.info(f"[缓存] 命中: {command} {keyword} 第{page}页")
            return result[0]
        return None

    def save_cache(self, command: str, keyword: str, page: int, content: str):
        """保存缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO cache (command, keyword, page, content)
            VALUES (?, ?, ?, ?)
        ''', (command, keyword, page, content))

        conn.commit()
        conn.close()
        logger.info(f"[缓存] 已保存: {command} {keyword} 第{page}页")

    def clean_expired(self):
        """清理过期缓存（超过30天）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM cache WHERE timestamp < datetime('now', '-30 days')")
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if deleted > 0:
            logger.info(f"[缓存] 清理了 {deleted} 条过期记录")

# ===== Pyrogram镜像客户端 =====
class PyrogramMirror:
    """Pyrogram客户端 - 镜像@openaiw_bot"""

    def __init__(self):
        self.client = Client(
            "user_session",
            api_id=API_ID,
            api_hash=API_HASH,
            proxy=PROXY
        )
        self.search_bot = SEARCH_BOT_USERNAME
        logger.info("✅ Pyrogram镜像客户端初始化")

    async def start(self):
        """启动Pyrogram客户端"""
        await self.client.start()
        logger.info("✅ Pyrogram客户端已启动")

    async def stop(self):
        """停止Pyrogram客户端"""
        await self.client.stop()

    async def send_command(self, command: str, keyword: str = "", page: int = 1) -> str:
        """
        发送搜索命令到@openaiw_bot并获取结果

        Args:
            command: 命令类型 (search/text/human/topchat)
            keyword: 搜索关键词
            page: 页码

        Returns:
            搜索结果文本
        """
        try:
            # 构建命令
            if command == "topchat":
                cmd_text = f"/{command}"
            else:
                cmd_text = f"/{command} {keyword}" if page == 1 else f"next"

            logger.info(f"[Pyrogram] 发送命令: {cmd_text}")

            # 发送消息
            message = await self.client.send_message(self.search_bot, cmd_text)

            # 等待回复
            await asyncio.sleep(3)

            # 获取最新消息
            async for msg in self.client.get_chat_history(self.search_bot, limit=1):
                if msg.text:
                    logger.info(f"[Pyrogram] 收到回复 ({len(msg.text)} 字)")
                    return msg.text

            return "未收到回复"

        except FloodWait as e:
            logger.warning(f"[Pyrogram] 触发限流，等待 {e.value} 秒")
            await asyncio.sleep(e.value)
            return await self.send_command(command, keyword, page)

        except Exception as e:
            logger.error(f"[Pyrogram] 错误: {e}")
            return f"搜索失败: {str(e)}"

# ===== 自动翻页管理器 =====
class AutoPaginationManager:
    """后台自动翻页 - 用户无感知抓取2-10页"""

    def __init__(self, pyrogram_client: PyrogramMirror, database: Database):
        self.pyrogram = pyrogram_client
        self.db = database
        self.active_tasks: Dict[int, asyncio.Task] = {}
        logger.info("✅ 自动翻页管理器已初始化")

    async def start_pagination(self, user_id: int, command: str, keyword: str, first_result: str):
        """启动后台翻页任务"""
        if user_id in self.active_tasks:
            logger.info(f"[翻页] 用户 {user_id} 已有翻页任务运行中")
            return

        task = asyncio.create_task(
            self._paginate(user_id, command, keyword, first_result)
        )
        self.active_tasks[user_id] = task
        logger.info(f"[翻页] 用户 {user_id} 后台任务已启动")

    async def _paginate(self, user_id: int, command: str, keyword: str, first_result: str):
        """后台翻页逻辑"""
        try:
            # 保存第1页
            self.db.save_cache(command, keyword, 1, first_result)

            # 抓取2-10页
            for page in range(2, 11):
                # 检查缓存
                cached = self.db.get_cache(command, keyword, page)
                if cached:
                    logger.info(f"[翻页] 第{page}页已缓存，跳过")
                    continue

                # 发送 next 命令
                logger.info(f"[翻页] 抓取第{page}页...")
                result = await self.pyrogram.send_command("next", "", page)

                # 保存结果
                self.db.save_cache(command, keyword, page, result)

                # 等待避免限流
                await asyncio.sleep(2)

            logger.info(f"[翻页] 用户 {user_id} 完成抓取 (1-10页)")

        except Exception as e:
            logger.error(f"[翻页] 错误: {e}")

        finally:
            if user_id in self.active_tasks:
                del self.active_tasks[user_id]

# ===== 统一Bot类 =====
class UnifiedTelegramBot:
    """统一Telegram Bot - 整合所有功能"""

    def __init__(self):
        self.db = Database()
        self.pyrogram = PyrogramMirror()
        self.pagination_manager = None  # 启动后初始化
        self.app = None

        # Claude客户端
        self.claude_client = anthropic.Anthropic(
            auth_token=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
            base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
        )

        # 对话历史
        self.conversation_history: Dict[int, List[Dict]] = {}

        logger.info("✅ 统一Bot初始化完成")

    def get_history(self, user_id: int, limit: int = 2) -> List[Dict]:
        """获取用户对话历史（最近N轮）"""
        if user_id not in self.conversation_history:
            return []
        messages = self.conversation_history[user_id][-limit*2:]
        return [{"role": msg["role"], "content": msg["content"]} for msg in messages]

    def add_to_history(self, user_id: int, role: str, content: str):
        """添加到对话历史"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        self.conversation_history[user_id].append({"role": role, "content": content})
        # 保持最多10轮
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][-20:]

    async def call_claude(self, user_id: int, message: str) -> Dict:
        """
        调用Claude API

        Args:
            user_id: 用户ID
            message: 用户消息

        Returns:
            {
                "response": "AI回复",
                "buttons": [...]
            }
        """
        try:
            logger.info(f"[Claude] 用户 {user_id} 调用Claude API: {message}")

            # 获取历史
            history = self.get_history(user_id)
            history.append({"role": "user", "content": message})

            # 调用Claude
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=history
            )

            # 提取回复
            reply_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    reply_text += block.text

            # 保存历史
            self.add_to_history(user_id, "user", message)
            self.add_to_history(user_id, "assistant", reply_text)

            # 提取按钮
            buttons = self._extract_buttons(reply_text)

            logger.info(f"[Claude] ✅ 回复成功 ({len(reply_text)} 字)")

            return {
                "response": reply_text,
                "buttons": buttons
            }

        except Exception as e:
            logger.error(f"[Claude] ❌ 错误: {e}")
            return {
                "response": f"AI服务出错: {str(e)}",
                "buttons": []
            }

    def _extract_buttons(self, text: str) -> List[Dict[str, str]]:
        """从AI回复中提取可点击按钮"""
        buttons = []
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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user_id = update.effective_user.id
        logger.info(f"[命令] 用户 {user_id} 启动Bot")

        # 使用之前的欢迎方式
        await update.message.reply_text("👋 我来帮你搜索！\n\n直接告诉我你想找什么，或者使用以下命令：\n\n/search <关键词> - 搜索群组名称\n/text <关键词> - 搜索讨论内容\n/human <关键词> - 搜索用户\n/topchat - 查看热门分类")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息 - 调用Claude"""
        user_id = update.effective_user.id
        user_message = update.message.text

        logger.info(f"[消息] 用户 {user_id}: {user_message}")

        # 调用Claude
        claude_result = await self.call_claude(user_id, user_message)

        response_text = claude_result["response"]
        buttons = claude_result["buttons"]

        # 发送回复（带按钮）
        if buttons:
            keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])]
                       for btn in buttons]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response_text, reply_markup=reply_markup)
            logger.info(f"[回复] 已发送（带 {len(buttons)} 个按钮）")
        else:
            await update.message.reply_text(response_text)
            logger.info(f"[回复] 已发送")

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮点击"""
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        user_id = query.from_user.id
        logger.info(f"[按钮] 用户 {user_id} 点击: {callback_data}")

        # 解析按钮命令
        if callback_data.startswith("cmd_"):
            parts = callback_data[4:].split("_")
            command = parts[0]
            keyword = "_".join(parts[1:]) if len(parts) > 1 else ""

            # 执行搜索
            await self.execute_search(query.message, user_id, command, keyword)

    async def execute_search(self, message, user_id: int, command: str, keyword: str):
        """执行搜索并返回结果"""
        logger.info(f"[搜索] 用户 {user_id}: /{command} {keyword}")

        # 检查缓存
        cached = self.db.get_cache(command, keyword, 1)
        if cached:
            await message.reply_text(cached)
            logger.info(f"[搜索] 返回缓存结果")
            return

        # 通过Pyrogram搜索
        result = await self.pyrogram.send_command(command, keyword, 1)

        # 发送结果
        await message.reply_text(result)

        # 启动后台翻页
        await self.pagination_manager.start_pagination(user_id, command, keyword, result)

    async def post_init(self, app: Application):
        """启动后初始化"""
        # 启动Pyrogram
        await self.pyrogram.start()

        # 初始化翻页管理器
        self.pagination_manager = AutoPaginationManager(self.pyrogram, self.db)

        logger.info("✅ 所有组件已初始化")

    async def post_shutdown(self, app: Application):
        """关闭时清理"""
        await self.pyrogram.stop()
        logger.info("👋 Bot已停止")

    def run(self):
        """启动Bot"""
        logger.info("=" * 60)
        logger.info("🚀 统一Telegram Bot启动中...")
        logger.info(f"📅 时间: {datetime.now()}")
        logger.info(f"🤖 Claude: 直接调用Anthropic API")
        logger.info("=" * 60)

        # 创建Application
        self.app = Application.builder().token(TELEGRAM_TOKEN).post_init(self.post_init).post_shutdown(self.post_shutdown).build()

        # 注册处理器
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.handle_button))

        # 启动轮询
        logger.info("✅ Bot已启动，等待消息...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

# ===== 主入口 =====
if __name__ == "__main__":
    bot = UnifiedTelegramBot()
    bot.run()
