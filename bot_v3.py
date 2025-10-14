#!/usr/bin/env python3
"""
Telegram Bot V3 - 完整重构版
特性：
1. 智能AI引导 - 用户说需求，AI分析给出按钮选项
2. 完整的bytes处理 - 所有callback_data统一用hex存储
3. 返回重选功能 - 搜索结果可返回重新选择
4. 缓存与按需翻页 - 兼顾用户体验
5. 增强日志系统 - 不删档完整记录
"""

import asyncio
import logging
import time
import os
import httpx
import anthropic
import json
import re
from typing import Dict, Optional, List
from datetime import datetime, timedelta

# Pyrogram
from pyrogram import Client as PyrogramClient, filters
from pyrogram.types import Message as PyrogramMessage
from pyrogram.raw.functions.messages import GetBotCallbackAnswer

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters as tg_filters, ContextTypes
from telegram.request import HTTPXRequest

# 数据库
import sys
sys.path.insert(0, "/home/atai/bot_data")
from database import CacheDatabase

# 增强日志
from enhanced_logger import EnhancedLogger

# ==================== 配置 ====================
API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
SESSION_NAME = "user_session"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4")
TARGET_BOT = "@openaiw_bot"
ADMIN_ID = 7363537082

# 初始化日志
enhanced_log = EnhancedLogger("bot_v3", log_dir="./logs")
logger = enhanced_log.get_logger()
logger.info("🚀 Bot V3 启动中...")

# 初始化Claude
try:
    claude_client = anthropic.Anthropic(
        api_key=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
        base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    )
    logger.info("✅ Claude API已初始化")
except Exception as e:
    logger.error(f"❌ Claude API初始化失败: {e}")
    claude_client = None


# ==================== 工具函数 ====================

def bytes_to_hex(data) -> Optional[str]:
    """bytes转hex字符串 - 用于JSON存储"""
    if data is None:
        return None
    if isinstance(data, bytes):
        return data.hex()
    return str(data)

def hex_to_bytes(hex_str):
    """hex字符串转bytes - 用于恢复callback"""
    if hex_str is None:
        return None
    if isinstance(hex_str, bytes):
        return hex_str
    try:
        return bytes.fromhex(hex_str)
    except (ValueError, AttributeError):
        return hex_str.encode('utf-8') if isinstance(hex_str, str) else hex_str


# ==================== 会话管理器 ====================

class SessionManager:
    """用户会话管理"""
    def __init__(self):
        self.sessions: Dict[int, dict] = {}
        self.timeout = timedelta(minutes=30)

    def create(self, user_id: int, query: str) -> dict:
        """创建会话"""
        session = {
            "user_id": user_id,
            "stage": "initial",
            "query": query,
            "analysis": None,
            "selected": None,
            "can_back": False,
            "created_at": datetime.now()
        }
        self.sessions[user_id] = session
        logger.info(f"[会话] 创建: user={user_id}")
        return session

    def get(self, user_id: int) -> Optional[dict]:
        """获取会话"""
        session = self.sessions.get(user_id)
        if session and datetime.now() - session['created_at'] > self.timeout:
            del self.sessions[user_id]
            return None
        return session

    def update(self, user_id: int, **kwargs):
        """更新会话"""
        session = self.get(user_id)
        if session:
            session.update(kwargs)

    def clear(self, user_id: int):
        """清除会话"""
        if user_id in self.sessions:
            del self.sessions[user_id]


# ==================== AI分析器 ====================

class AIAnalyzer:
    """AI意图分析"""
    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-20250514"

    async def analyze(self, user_input: str) -> dict:
        """分析用户意图 - 生成30个相关关键词"""
        if not self.client:
            return self._fallback(user_input)

        prompt = f"""分析Telegram搜索需求，生成30个相关的关键词。

用户输入: "{user_input}"

要求:
1. 生成30个与用户输入相关的关键词
2. 关键词要具体、可搜索
3. 涵盖不同角度和相关话题
4. 按相关性排序(最相关的在前)

返回JSON格式:
{{
  "explanation": "1句话说明用户想要什么",
  "keywords": [
    "关键词1",
    "关键词2",
    ...共30个
  ]
}}

示例:
用户: "德州"
返回: {{"explanation": "德州扑克相关", "keywords": ["德州扑克", "德州扑克俱乐部", "德州扑克教学", ...]}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text.strip()

            # 提取JSON
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)

            # 尝试找到{}
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                text = match.group(0)

            result = json.loads(text)

            # 验证
            if 'keywords' in result and isinstance(result['keywords'], list):
                logger.info(f"[AI] 分析成功: {len(result['keywords'])}个关键词")
                return result
            else:
                raise ValueError("格式错误")

        except Exception as e:
            logger.error(f"[AI] 分析失败: {e}")
            return self._fallback(user_input)


def _fallback(self, user_input: str) -> dict:
    """Fallback - AI失败时生成基础关键词"""
    suffixes = [
        "",
        "群",
        "群聊",
        "交流群",
        "交流群组",
        "俱乐部",
        "社群",
        "社区",
        "论坛",
        "讨论组",
        "频道",
        "频道推荐",
        "资源",
        "资源分享",
        "教程",
        "教程分享",
        "学习",
        "学习群",
        "干货",
        "工具",
        "工具包",
        "软件",
        "APP",
        "推荐",
        "最新",
        "官方",
        "中文",
        "免费",
        "精品",
        "入门"
    ]
    keywords = []
    seen = set()
    for suffix in suffixes:
        keyword = f"{user_input}{suffix}".strip()
        lower = keyword.lower()
        if keyword and lower not in seen:
            keywords.append(keyword)
            seen.add(lower)
        if len(keywords) >= 30:
            break
    return {
        "explanation": f"为「{user_input}」生成的关键词",
        "keywords": keywords[:30]
    }



class TelegramBotV3:
    """主Bot类"""

    def __init__(self):
        self.sessions = SessionManager()
        self.ai = AIAnalyzer(claude_client)
        self.cache_db = None
        self.pyrogram_client = None
        self.app = None
        self.target_bot_id = None

        # Callback映射
        self.callback_map = {}

        # Pyrogram消息映射
        self.pyro_to_tg = {}
        self.tg_to_pyro = {}

        # 搜索会话
        self.search_sessions = {}

    async def setup_pyrogram(self) -> bool:
        """设置Pyrogram客户端"""
        try:
            proxy = {"scheme": "socks5", "hostname": "127.0.0.1", "port": 1080}

            self.pyrogram_client = PyrogramClient(
                SESSION_NAME,
                API_ID,
                API_HASH,
                workdir="/home/atai/telegram-bot",
                proxy=proxy
            )

            await self.pyrogram_client.start()

            # 获取目标bot
            target = await self.pyrogram_client.get_users(TARGET_BOT)
            self.target_bot_id = target.id

            # 设置消息处理
            @self.pyrogram_client.on_message(filters.user(self.target_bot_id))
            async def handle_bot_message(client, message):
                await self.handle_search_response(message)

            logger.info(f"✅ Pyrogram已启动: {TARGET_BOT}")
            return True

        except Exception as e:
            logger.error(f"❌ Pyrogram失败: {e}")
            return False

    async def initialize(self) -> bool:
        """初始化"""
        try:
            logger.info("正在初始化...")

            # 初始化Pyrogram
            if not await self.setup_pyrogram():
                return False

            # 初始化缓存
            try:
                self.cache_db = CacheDatabase("/home/atai/bot_data/cache.db")
                logger.info("✅ 缓存已加载")
            except Exception as e:
                logger.warning(f"缓存加载失败: {e}")


            # 初始化Telegram Bot
            builder = Application.builder().token(BOT_TOKEN)

            if os.environ.get('ALL_PROXY'):
                proxy_url = os.environ.get('ALL_PROXY')
                request = HTTPXRequest(
                    proxy=proxy_url,
                    connect_timeout=30.0,
                    read_timeout=30.0
                )
                builder = builder.request(request)

            self.app = builder.build()

            # 注册处理器
            self.app.add_handler(CommandHandler("start", self.handle_start))
            self.app.add_handler(MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, self.handle_message))
            self.app.add_handler(CallbackQueryHandler(self.handle_callback))

            logger.info("✅ 初始化完成")
            return True

        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start"""
        user = update.effective_user

        welcome = (
            f"👋 您好 {user.first_name}！\n\n"
            "我是智能搜索助手，可以帮您找到Telegram群组和频道。\n\n"
            "💬 直接告诉我您想找什么，我会为您准备搜索方案！\n\n"
            "例如：\n"
            "• 我想找德州扑克群\n"
            "• 寻找AI工具讨论\n"
            "• 科技资讯频道"
        )

        keyboard = [
            [InlineKeyboardButton("🔥 浏览热门分类", callback_data="cmd_topchat")],
            [InlineKeyboardButton("📖 使用帮助", callback_data="show_help")]
        ]

        await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

        # 通知管理员
        if user.id != ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🆕 新用户: {user.first_name} (@{user.username or '无'}) - {user.id}"
                )
            except:
                pass
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息 - 不再提供关键词推荐"""
        user = update.effective_user
        raw_text = update.message.text or ""
        text = raw_text.strip()

        if not text:
            await update.message.reply_text("请发送要搜索的内容，例如“德州扑克群”。")
            return

        logger.info(f"[用户 {user.id}] 输入: {text}")

        self.sessions.create(user.id, text)
        self.sessions.update(
            user.id,
            selected_keyword=text,
            stage="commands",
            can_back=False,
            analysis=None
        )

        buttons = [
            [InlineKeyboardButton("🔍 按名称搜索 (/search)", callback_data=f"cmd_{user.id}_search")],
            [InlineKeyboardButton("💬 按内容搜索 (/text)", callback_data=f"cmd_{user.id}_text")],
            [InlineKeyboardButton("👤 按用户搜索 (/human)", callback_data=f"cmd_{user.id}_human")],
            [InlineKeyboardButton("📊 查看信息 (/info)", callback_data=f"cmd_{user.id}_info")],
        ]

        reply_text = f"收到「{text}」\n\n请选择需要使用的搜索方式，或直接输入具体命令。"

        await update.message.reply_text(
            reply_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮点击"""
        query = update.callback_query
        data = query.data
        user = query.from_user

        logger.info(f"[回调] user={user.id}, data={data}")

        await query.answer()

        # 【第二级】处理指令选择 - 执行搜索
        if data.startswith("cmd_"):
            await self.handle_command_click(query)
            return

        # 返回搜索方式
        if data == "back_to_keywords":
            await self.handle_back_to_keywords(query)
            return

        # 手动输入
        if data == "manual_input":
            await query.message.edit_text(
                "✍️ 请直接发送命令：\n\n"
                "• /search 关键词\n"
                "• /text 关键词\n"
                "• /human 关键词\n"
                "• /topchat"
            )
            return

        # 快捷搜索
        if data.startswith("quick_"):
            parts = data.split("_", 2)
            if len(parts) == 3:
                cmd_type = parts[1]
                keyword = parts[2]

                await query.message.edit_text(f"🔍 搜索中: {keyword}\n请稍候...")

                try:
                    await self.pyrogram_client.send_message(
                        self.target_bot_id,
                        f"/{cmd_type} {keyword}"
                    )

                    self.search_sessions[user.id] = {
                        'chat_id': query.message.chat_id,
                        'wait_msg_id': query.message.message_id,
                        'command': f"/{cmd_type}",
                        'keyword': keyword,
                        'can_back': False
                    }
                except Exception as e:
                    logger.error(f"[搜索] 失败: {e}")
                    await query.message.edit_text("❌ 搜索失败")
            return

        # 翻页callback
        if data.startswith("cb_"):
            await self.handle_pagination(query, data)
            return

        logger.warning(f"[回调] 未知: {data}")

    async def handle_back_to_keywords(self, query):
        """返回搜索选项"""
        user = query.from_user
        session = self.sessions.get(user.id)

        if not session:
            await query.message.edit_text("❌ 会话已过期，请重新输入")
            return

        keyword = session.get('selected_keyword') or session.get('query') or ""

        buttons = [
            [InlineKeyboardButton("🔍 按名称搜索 (/search)", callback_data=f"cmd_{user.id}_search")],
            [InlineKeyboardButton("💬 按内容搜索 (/text)", callback_data=f"cmd_{user.id}_text")],
            [InlineKeyboardButton("👤 按用户搜索 (/human)", callback_data=f"cmd_{user.id}_human")],
            [InlineKeyboardButton("📊 查看信息 (/info)", callback_data=f"cmd_{user.id}_info")],
        ]

        reply_text = f"当前搜索词：{keyword or '（未指定）'}\n\n请选择需要使用的搜索方式，或直接输入具体命令。"

        await query.message.edit_text(
            reply_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        session['stage'] = 'commands'
        session['can_back'] = False
        self.sessions.update(user.id, stage='commands', can_back=False)

        logger.info(f"[用户 {user.id}] 返回搜索方式")

    async def handle_command_click(self, query):
        """【第二级】指令点击 - 执行搜索"""
        user = query.from_user
        data = query.data

        # 解析: cmd_userid_command
        parts = data.split("_")
        if len(parts) < 3:
            return

        command = parts[2]  # search/text/human/info

        # 获取会话
        session = self.sessions.get(user.id)
        if not session or not session.get('selected_keyword'):
            await query.message.edit_text("❌ 会话已过期，请重新输入")
            return

        keyword = session['selected_keyword']

        # 构建完整命令
        full_cmd = f"/{command} {keyword}"

        logger.info(f"[用户 {user.id}] 执行: {full_cmd}")

        # 先检查缓存

        # 缓存未命中,显示搜索中
        await query.message.edit_text(
            f"✅ 执行指令: <code>{full_cmd}</code>\n\n🔍 正在搜索，请稍候...",
            parse_mode='HTML'
        )

        # 执行搜索
        try:
            await self.pyrogram_client.send_message(self.target_bot_id, full_cmd)

            self.search_sessions[user.id] = {
                'chat_id': query.message.chat_id,
                'wait_msg_id': query.message.message_id,
                'command': f"/{command}",
                'keyword': keyword,
                'can_back': True,
                'last_page': 1,
                'source_msg_id': None,
                'timestamp': datetime.now()
            }

            logger.info(f"[搜索] 已转发: {full_cmd}")

        except Exception as e:
            logger.error(f"[搜索] 失败: {e}")
            await query.message.edit_text("❌ 搜索失败，请重试")



    async def handle_search_response(self, message: PyrogramMessage):
        """处理服务商返回的搜索结果"""
        try:
            for user_id, session in list(self.search_sessions.items()):
                if datetime.now() - session.get('timestamp', datetime.now()) > timedelta(seconds=10):
                    continue

                try:
                    text = message.text.html
                except Exception:
                    text = message.text or message.caption or ""

                keyboard = self.convert_keyboard(message)

                if session.get('can_back') and keyboard:
                    buttons = list(keyboard.inline_keyboard)
                    buttons.append([InlineKeyboardButton("🔙 返回搜索方式", callback_data="back_to_keywords")])
                    keyboard = InlineKeyboardMarkup(buttons)

                updated_message = None
                try:
                    updated_message = await self.app.bot.edit_message_text(
                        chat_id=session['chat_id'],
                        message_id=session['wait_msg_id'],
                        text=text[:4000],
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except Exception as edit_error:
                    logger.warning(f"[搜索响应] 编辑消息失败: {edit_error}")
                    try:
                        updated_message = await self.app.bot.send_message(
                            chat_id=session['chat_id'],
                            text=text[:4000],
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except Exception as send_error:
                        logger.error(f"[搜索响应] 发送消息失败: {send_error}")
                        continue

                session['message_id'] = updated_message.message_id
                session['chat_id'] = updated_message.chat_id
                session['wait_msg_id'] = updated_message.message_id
                session['source_msg_id'] = message.id
                session['last_page'] = 1
                session['can_back'] = True

                self.pyro_to_tg[message.id] = updated_message.message_id
                self.tg_to_pyro[updated_message.message_id] = message.id

                if self.cache_db and session.get('keyword'):
                    buttons_data = self.extract_buttons(message)
                    self.cache_db.save_cache(
                        session['command'],
                        session['keyword'],
                        1,
                        text,
                        buttons_data
                    )

                session['timestamp'] = datetime.now()
                self.search_sessions[user_id] = session
                break

        except Exception as e:
            logger.error(f"[搜索响应] 失败: {e}")


    async def fetch_updated_message(self, message_id: int, attempts: int = 6, delay: float = 0.7):
        for _ in range(attempts):
            try:
                msg = await self.pyrogram_client.get_messages(self.target_bot_id, message_id)
            except Exception as exc:
                logger.error(f"[翻页] 获取消息失败: {exc}")
                msg = None
            if msg and (msg.reply_markup or msg.text or msg.caption):
                return msg
            await asyncio.sleep(delay)
        return None


    async def handle_pagination(self, query, data):
        """处理翻页按钮"""
        user = query.from_user

        if data not in self.callback_map:
            await query.answer('按钮已过期', show_alert=False)
            return

        orig_msg_id, orig_callback = self.callback_map[data]
        session = self.search_sessions.get(user.id)
        if not session:
            await query.answer('会话已过期', show_alert=True)
            return

        if isinstance(orig_callback, bytes):
            callback_bytes = orig_callback
            callback_str = orig_callback.decode('utf-8', 'ignore')
        else:
            callback_str = str(orig_callback)
            callback_bytes = hex_to_bytes(callback_str)

        if orig_msg_id == 0 and session.get('source_msg_id'):
            orig_msg_id = session['source_msg_id']

        page = None
        match = re.search(r"page_(\d+)", callback_str or "")
        if match:
            page = int(match.group(1))
        elif session.get('last_page'):
            page = session['last_page'] + 1

        cached = None
        if self.cache_db and session.get('keyword') and page:
            cached = self.cache_db.get_cache(session['command'], session['keyword'], page)

        await query.answer('正在加载...', show_alert=False)

        try:
            await self.pyrogram_client.invoke(
                GetBotCallbackAnswer(
                    peer=await self.pyrogram_client.resolve_peer(self.target_bot_id),
                    msg_id=orig_msg_id,
                    data=callback_bytes
                )
            )
        except Exception as e:
            logger.error(f"[翻页] 回调失败: {e}")
            if cached:
                await self._apply_cached_page(query, session, cached, page)
            else:
                await query.message.edit_text("❌ 翻页失败")
            return

        updated_msg = await self.fetch_updated_message(orig_msg_id)
        if not updated_msg:
            if cached:
                await self._apply_cached_page(query, session, cached, page)
                return
            await query.message.edit_text("❌ 未获取到新内容，请稍后重试")
            return

        try:
            text = updated_msg.text.html
        except Exception:
            text = updated_msg.text or updated_msg.caption or ""

        keyboard = self.convert_keyboard(updated_msg)
        if session.get('can_back') and keyboard:
            buttons = list(keyboard.inline_keyboard)
            buttons.append([InlineKeyboardButton("🔙 返回搜索方式", callback_data="back_to_keywords")])
            keyboard = InlineKeyboardMarkup(buttons)

        await query.message.edit_text(
            text[:4000],
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        if self.cache_db and session.get('keyword') and page:
            buttons_data = self.extract_buttons(updated_msg)
            self.cache_db.save_cache(
                session['command'],
                session['keyword'],
                page,
                text,
                buttons_data
            )

        if page:
            session['last_page'] = page
        session['source_msg_id'] = updated_msg.id
        session['timestamp'] = datetime.now()
        self.search_sessions[user.id] = session


    async def _apply_cached_page(self, query, session, cached, page):
        keyboard = self.rebuild_keyboard(cached.get('buttons', []), session.get('can_back', False))
        await query.message.edit_text(
            cached['text'][:4000],
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        if page:
            session['last_page'] = page
        session['timestamp'] = datetime.now()
        self.search_sessions[query.from_user.id] = session


    def convert_keyboard(self, message: PyrogramMessage):
        if not message.reply_markup or not message.reply_markup.inline_keyboard:
            return None
        try:
            buttons = []
            for row in message.reply_markup.inline_keyboard:
                button_row = []
                for btn in row:
                    if btn.url:
                        button_row.append(InlineKeyboardButton(text=btn.text, url=btn.url))
                    elif btn.callback_data:
                        callback_id = f"cb_{time.time():.0f}_{len(self.callback_map)}"
                        self.callback_map[callback_id] = (message.id, btn.callback_data)
                        button_row.append(InlineKeyboardButton(text=btn.text, callback_data=callback_id[:64]))
                    else:
                        button_row.append(InlineKeyboardButton(text=btn.text, callback_data="unknown"))
                if button_row:
                    buttons.append(button_row)
            return InlineKeyboardMarkup(buttons) if buttons else None
        except Exception as e:
            logger.error(f"[键盘转换] 失败: {e}")
            return None


    def extract_buttons(self, message: PyrogramMessage) -> list:
        if not message.reply_markup or not message.reply_markup.inline_keyboard:
            return []
        buttons = []
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                btn_data = {"text": btn.text, "msg_id": message.id}
                if btn.url:
                    btn_data["url"] = btn.url
                if btn.callback_data:
                    btn_data["callback_data"] = bytes_to_hex(btn.callback_data)
                buttons.append(btn_data)
        return buttons


    def rebuild_keyboard(self, buttons_data: list, can_back: bool = False):
        if not buttons_data:
            if can_back:
                return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回搜索方式", callback_data="back_to_keywords")]])
            return None

        session_msg_id = 0
        for btn_data in buttons_data:
            if btn_data.get('msg_id'):
                session_msg_id = btn_data['msg_id']
                break

        buttons = []
        current_row = []
        for btn_data in buttons_data:
            btn = None
            if btn_data.get('url'):
                btn = InlineKeyboardButton(text=btn_data['text'], url=btn_data['url'])
            elif btn_data.get('callback_data'):
                callback_id = f"cb_{time.time():.0f}_{len(self.callback_map)}"
                callback_bytes = hex_to_bytes(btn_data['callback_data'])
                source_msg_id = btn_data.get('msg_id') or session_msg_id
                self.callback_map[callback_id] = (source_msg_id, callback_bytes)
                btn = InlineKeyboardButton(text=btn_data['text'], callback_data=callback_id[:64])
            if not btn:
                continue
            current_row.append(btn)
            if len(current_row) >= 4:
                buttons.append(current_row)
                current_row = []
        if current_row:
            buttons.append(current_row)
        if can_back:
            buttons.append([InlineKeyboardButton("🔙 返回搜索方式", callback_data="back_to_keywords")])
        return InlineKeyboardMarkup(buttons) if buttons else None


    async def run(self):
        """运行"""
        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)

            logger.info("=" * 60)
            logger.info("✅ Bot V3 已启动")
            logger.info("=" * 60)

            await asyncio.Event().wait()

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            await self.cleanup()


    async def cleanup(self):
        """清理"""
        logger.info("正在清理...")

        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

        if self.pyrogram_client:
            await self.pyrogram_client.stop()

        logger.info("✅ 清理完成")


async def main():
    """主函数"""
    bot = TelegramBotV3()

    if await bot.initialize():
        await bot.run()
    else:
        logger.error("初始化失败，退出")


if __name__ == "__main__":
    asyncio.run(main())
