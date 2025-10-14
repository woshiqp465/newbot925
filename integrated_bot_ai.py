#!/usr/bin/env python3
"""
整合版客服机器人 - AI增强版
包含：
1. AI对话引导
2. 镜像搜索功能
3. 自动翻页缓存
4. 智能去重
"""

import asyncio
import logging
from enhanced_logger import EnhancedLogger
import time
import os
import httpx
import re
import anthropic
import json
import sys
from typing import Dict, Optional
from datetime import datetime

# 添加路径
sys.path.insert(0, "/home/atai/bot_data")

# Pyrogram imports
from pyrogram import Client as PyrogramClient, filters
from pyrogram.types import Message as PyrogramMessage
from pyrogram.raw.functions.messages import GetBotCallbackAnswer

# Telegram Bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters as tg_filters
from telegram.ext import ContextTypes

# 导入数据库
try:
    from database import CacheDatabase
except ImportError:
    CacheDatabase = None
    logging.warning("database.py未找到，缓存功能将禁用")

# ================== 配置 ==================
API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
SESSION_NAME = "user_session"
BOT_TOKEN = "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4"
TARGET_BOT = "@openaiw_bot"
ADMIN_ID = 7363537082

# AI服务配置
MAC_API_URL = "http://192.168.9.10:8000"

# 搜索命令列表
SEARCH_COMMANDS = ['/topchat', '/search', '/text', '/human']

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# 使用增强型日志系统
enhanced_log = EnhancedLogger("integrated_bot", log_dir="./logs")
logger = enhanced_log.get_logger()
logger.info("🚀 增强型日志系统已启动 - 所有日志将被完整保留")

# 初始化Claude客户端
try:
    claude_client = anthropic.Anthropic(
        api_key=os.environ.get('ANTHROPIC_AUTH_TOKEN'),
        base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    )
    logger.info("✅ Claude API客户端已初始化")
except Exception as e:
    logger.error(f"❌ Claude API初始化失败: {e}")
    claude_client = None


def serialize_callback_data(value):
    """将按钮callback_data序列化为可JSON存储的结构"""
    if value is None:
        return None
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    return None


def deserialize_callback_data(data):
    """从缓存中恢复原始callback_data"""
    if not data:
        return None
    if isinstance(data, dict):
        data_type = data.get("type")
        value = data.get("value")
        if data_type == "bytes" and isinstance(value, str):
            try:
                return bytes.fromhex(value)
            except ValueError:
                return None
        if data_type == "str":
            return value
    if isinstance(data, str):
        if data.startswith('hex:'):
            try:
                return bytes.fromhex(data[4:])
            except ValueError:
                return None
        return data
    return None





# ================== 对话管理 ==================
class ConversationManager:
    """管理用户对话上下文"""
    
    def __init__(self, max_history=5):
        self.conversations = {}
        self.max_history = max_history
    
    def add_message(self, user_id: int, role: str, content: str):
        """添加消息到历史"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        self.conversations[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # 保持最近的N条消息
        if len(self.conversations[user_id]) > self.max_history * 2:
            self.conversations[user_id] = self.conversations[user_id][-self.max_history * 2:]
    
    def get_history(self, user_id: int, limit: int = 2) -> list:
        """获取用户对话历史"""
        if user_id not in self.conversations:
            return []
        
        history = self.conversations[user_id][-limit * 2:]
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]
    
    def clear_history(self, user_id: int):
        """清空用户历史"""
        if user_id in self.conversations:
            del self.conversations[user_id]


# ================== 自动翻页管理器 ==================
class AutoPaginationManager:
    """后台自动翻页 - 用户无感知"""
    
    def __init__(self, pyrogram_client, cache_db, target_bot_id, logger):
        self.pyrogram_client = pyrogram_client
        self.cache_db = cache_db
        self.target_bot_id = target_bot_id
        self.logger = logger
        self.active_tasks = {}
        
    async def start_pagination(self, user_id, command, keyword, first_message):
        """启动后台翻页任务"""
        if user_id in self.active_tasks:
            return
        
        task = asyncio.create_task(self._paginate(user_id, command, keyword, first_message))
        self.active_tasks[user_id] = task
        self.logger.info(f"[翻页] 后台任务启动: {command} {keyword}")
    
    async def _paginate(self, user_id, command, keyword, message):
        """执行翻页"""
        try:
            page = 1
            self._save_to_cache(command, keyword, page, message)
            
            if not self._has_next(message):
                self.logger.info(f"[翻页] 只有1页")
                return
            
            current = message
            for page in range(2, 11):  # 最多10页
                await asyncio.sleep(2)
                
                next_msg = await self._click_next(current)
                if not next_msg:
                    break
                
                self._save_to_cache(command, keyword, page, next_msg)
                self.logger.info(f"[翻页] 第{page}页已保存")
                
                if not self._has_next(next_msg):
                    self.logger.info(f"[翻页] 完成，共{page}页")
                    break
                
                current = next_msg
                
        except Exception as e:
            self.logger.error(f"[翻页] 错误: {e}")
        finally:
            if user_id in self.active_tasks:
                del self.active_tasks[user_id]
    
    def _has_next(self, msg):
        """检查是否有下一页"""
        if not msg.reply_markup:
            return False
        for row in msg.reply_markup.inline_keyboard:
            for btn in row:
                if btn.text and any(x in btn.text for x in ['下一页', 'Next', '▶']):
                    return True
        return False
    
    async def _click_next(self, msg):
        """点击下一页"""
        try:
            from pyrogram.raw.functions.messages import GetBotCallbackAnswer
            
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.text and any(x in btn.text for x in ['下一页', 'Next', '▶']):
                        await self.pyrogram_client.invoke(
                            GetBotCallbackAnswer(
                                peer=await self.pyrogram_client.resolve_peer(self.target_bot_id),
                                msg_id=msg.id,
                                data=btn.callback_data
                            )
                        )
                        await asyncio.sleep(1.5)
                        return await self.pyrogram_client.get_messages(self.target_bot_id, msg.id)
        except Exception as e:
            self.logger.error(f"[翻页] 点击失败: {e}")
        return None
    
    def _save_to_cache(self, cmd, keyword, page, msg):
        """保存到缓存"""
        if not self.cache_db:
            return
        try:
            text = msg.text or msg.caption or ""
            buttons = []
            if getattr(msg, 'reply_markup', None) and getattr(msg.reply_markup, 'inline_keyboard', None):
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        btn_data = {'text': btn.text}
                        if btn.url:
                            btn_data['url'] = btn.url
                        if btn.callback_data is not None:
                            serialized = serialize_callback_data(btn.callback_data)
                            if serialized:
                                btn_data['callback_data'] = serialized
                        buttons.append(btn_data)
            self.cache_db.save_cache(cmd, keyword, page, text, buttons)
        except Exception as e:
            self.logger.error(f"[翻页] 保存失败: {e}")

class IntegratedBotAI:
    """整合的客服机器人 - AI增强版"""

    def __init__(self):
        # Bot应用
        self.app = None

        # Pyrogram客户端（用于镜像）
        self.pyrogram_client: Optional[PyrogramClient] = None
        self.target_bot_id: Optional[int] = None

        # 消息映射
        self.pyrogram_to_telegram = {}
        self.telegram_to_pyrogram = {}
        self.callback_data_map = {}
        self.user_search_sessions = {}

        # AI会话状态
        self.user_ai_sessions = {}

        # 缓存数据库
        self.cache_db = CacheDatabase() if CacheDatabase else None

        # 对话管理器
        self.conversation_manager = ConversationManager()
        self.pagination_manager = None

    async def setup_pyrogram(self):
        """设置Pyrogram客户端"""
        try:
            proxy_config = None
            if os.environ.get('ALL_PROXY'):
                proxy_url = os.environ.get('ALL_PROXY', '').replace('socks5://', '')
                if proxy_url:
                    host, port = proxy_url.split(':')
                    proxy_config = {"scheme": "socks5", "hostname": host, "port": int(port)}

            self.pyrogram_client = PyrogramClient(
                SESSION_NAME, api_id=API_ID, api_hash=API_HASH,
                proxy=proxy_config if proxy_config else None
            )

            await self.pyrogram_client.start()
            logger.info("✅ Pyrogram客户端已启动")

            # 初始化自动翻页管理器
            self.pagination_manager = AutoPaginationManager(
                self.pyrogram_client, self.cache_db, self.target_bot_id, logger
            )
            logger.info("✅ 自动翻页管理器已初始化")

            target = await self.pyrogram_client.get_users(TARGET_BOT)
            self.target_bot_id = target.id
            logger.info(f"✅ 已连接到搜索机器人: {target.username}")

            @self.pyrogram_client.on_message(filters.user(self.target_bot_id))
            async def on_bot_response(_, message: PyrogramMessage):
                await self.handle_search_response(message)

            @self.pyrogram_client.on_edited_message(filters.user(self.target_bot_id))
            async def on_message_edited(_, message: PyrogramMessage):
                await self.handle_search_response(message, is_edit=True)

            return True
        except Exception as e:
            logger.error(f"Pyrogram设置失败: {e}")
            return False

    async def call_ai_service(self, user_id: int, message: str, context: dict = None) -> dict:
        """优化的Claude API调用 - 带上下文记忆和改进提示词"""
        
        if not claude_client:
            logger.error("Claude客户端未初始化")
            return {
                "type": "auto",
                "response": "👋 我来帮你搜索！\n\n直接发关键词，或试试：\n• /search 群组名\n• /text 讨论内容\n• /topchat 热门分类",
                "confidence": 0.3
            }
        
        try:
            logger.info(f"[用户 {user_id}] 调用Claude API: {message}")
            
            username = context.get('username', f'user_{user_id}') if context else f'user_{user_id}'
            first_name = context.get('first_name', '') if context else ''
            
            # 构建对话历史
            messages = []
            
            # 添加历史对话（最近2轮）
            history = self.conversation_manager.get_history(user_id, limit=2)
            messages.extend(history)
            
            # 添加当前消息（优化的提示词）
            current_prompt = f"""你是@ktfund_bot的AI助手，专业的Telegram群组搜索助手。

【重要】你的回复中可以包含可执行的命令，我会为它们生成按钮。
命令格式：/search 关键词 或 /text 关键词

用户信息：@{username} ({first_name})
用户说："{message}"

【可用工具】
• /search [关键词] - 搜索群组名称
• /text [关键词] - 搜索讨论内容
• /human [关键词] - 搜索用户
• /topchat - 热门分类

【回复要求】
1. 简短友好（2-4行）
2. 给1-2个具体命令建议
3. 口语化，像朋友聊天
4. 命令要在独立的一行

【示例】
用户："找AI群"
回复：
找AI群的话，试试：
/search AI
/text ChatGPT

直接回复："""

            messages.append({
                "role": "user",
                "content": current_prompt
            })
            
            # 调用Claude API
            response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                temperature=0.7,
                messages=messages
            )
            
            claude_response = response.content[0].text.strip()
            
            # 保存对话历史
            self.conversation_manager.add_message(user_id, "user", message)
            self.conversation_manager.add_message(user_id, "assistant", claude_response)
            
            logger.info(f"[用户 {user_id}] ✅ Claude回复成功 ({len(claude_response)}字)")
            
            # 智能提取命令建议
            suggested_commands = self._extract_commands(claude_response)
            
            return {
                "type": "ai",
                "response": claude_response,
                "confidence": 1.0,
                "suggested_commands": suggested_commands
            }
            
        except Exception as e:
            logger.error(f"[用户 {user_id}] ❌ Claude API失败: {e}")
            return {
                "type": "auto",
                "response": "👋 我来帮你搜索！\n\n直接发关键词，或试试：\n• /search 群组名\n• /text 讨论内容\n• /topchat 热门分类",
                "confidence": 0.3
            }
    
    def _extract_commands(self, response_text: str) -> list:
        """从回复中提取建议的命令"""
        import re
        commands = []
        
        # 匹配 /command pattern
        patterns = [
            r'/search\s+[\w\s]+',
            r'/text\s+[\w\s]+',
            r'/human\s+[\w\s]+',
            r'/topchat'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response_text)
            commands.extend([m.strip() for m in matches[:1]])
        
        return commands[:2]



    def _extract_command_buttons(self, text: str) -> list:
        """从AI回复中提取命令按钮"""
        import re
        buttons = []
        
        # 匹配：/command keyword
        pattern = r'/(search|text|human|topchat)\s*([^\n]*)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for cmd, keywords in matches[:3]:
            cmd = cmd.lower()
            keywords = keywords.strip()[:30]  # 限制长度
            
            if keywords:
                display = f"/{cmd} {keywords}"
                callback = f"cmd_{cmd}_{keywords.replace(' ', '_')}"[:64]
            else:
                display = f"/{cmd}"
                callback = f"cmd_{cmd}"
            
            buttons.append((display, callback))
        
        return buttons

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令 - AI引导模式"""
        user = update.effective_user
        user_id = user.id

        self.user_ai_sessions[user_id] = {"started_at": datetime.now(), "conversation": []}

        welcome_text = (
            f"👋 您好 {user.first_name}！\n\n"
            "我是智能搜索助手，可以帮您找到Telegram上的群组和频道。\n\n"
            "🔍 我能做什么：\n"
            "• 搜索群组/频道\n"
            "• 搜索特定话题的讨论\n"
            "• 查找用户\n"
            "• 浏览热门分类\n\n"
            "💬 直接告诉我您想找什么，我会帮您选择最合适的搜索方式！"
        )

        keyboard = [
            [InlineKeyboardButton("🔍 搜索群组", callback_data="quick_search"),
             InlineKeyboardButton("📚 使用指南", callback_data="quick_help")],
            [InlineKeyboardButton("🔥 热门分类", callback_data="quick_topchat")]
        ]

        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

        # 通知管理员
        admin_notification = (
            f"🆕 新用户访问 (AI模式):\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 {user.id}\n"
            f"👤 @{user.username or '无'}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理所有消息 - AI智能路由"""
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        user_id = user.id
        text = update.message.text
        is_admin = user_id == ADMIN_ID

        if is_admin and update.message.reply_to_message:
            await self.handle_admin_reply(update, context)
            return

        if self.is_search_command(text):
            await self.handle_search_command(update, context)
            return

        await self.handle_ai_conversation(update, context)

    def _prepare_keyword_for_buttons(self, keyword: str) -> Optional[tuple[str, str]]:
        """根据用户输入生成展示关键词和callback参数"""
        if not keyword:
            return None
        cleaned = re.sub(r'\s+', ' ', keyword.strip())
        if not cleaned:
            return None
        display = cleaned[:30]
        callback_arg = display.replace(' ', '_')
        return display, callback_arg


    def is_search_command(self, text: str) -> bool:
        """检查是否是搜索命令"""
        return text and text.split()[0] in SEARCH_COMMANDS

    async def handle_ai_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI对话处理 - 带智能按钮"""
        user = update.effective_user
        user_id = user.id
        message = update.message.text
        
        # 显示"正在输入"
        await update.message.chat.send_action("typing")
        
        # 构建上下文
        user_context = {
            "username": user.username or f"user{user_id}",
            "first_name": user.first_name or "朋友",
            "last_name": user.last_name
        }
        
        # 调用AI
        ai_response = await self.call_ai_service(user_id, message, user_context)
        response_text = ai_response.get("response", "")
        
        # 提取命令按钮
        buttons = self._extract_command_buttons(response_text)
        button_callbacks = {cb for _, cb in buttons}

        # 默认提供基于原始输入的命令按钮，确保用户可一键选择
        prepared = self._prepare_keyword_for_buttons(message)
        if prepared:
            display_kw, callback_kw = prepared
            base_commands = [
                (f"/search {display_kw}", f"cmd_search_{callback_kw}"[:64]),
                (f"/text {display_kw}", f"cmd_text_{callback_kw}"[:64]),
                (f"/human {display_kw}", f"cmd_human_{callback_kw}"[:64])
            ]
            default_buttons = []
            for display, callback in base_commands:
                if callback not in button_callbacks:
                    default_buttons.append((display, callback))
                    button_callbacks.add(callback)
            if default_buttons:
                buttons = default_buttons + buttons
        
        try:
            if buttons:
                # 构建按钮键盘
                keyboard = []
                for display, callback in buttons:
                    keyboard.append([InlineKeyboardButton(
                        f"🔍 {display}",
                        callback_data=callback
                    )])
                
                # 添加常用按钮
                keyboard.append([
                    InlineKeyboardButton("🔥 热门目录", callback_data="cmd_topchat"),
                    InlineKeyboardButton("📖 帮助", callback_data="cmd_help")
                ])
                
                await update.message.reply_text(
                    response_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info(f"[AI对话] 已回复用户 {user_id} (带{len(buttons)}个按钮)")
            else:
                # 无按钮版本
                await update.message.reply_text(response_text)
                logger.info(f"[AI对话] 已回复用户 {user_id}")
                
        except Exception as e:
            logger.error(f"[AI对话] 发送失败: {e}, 降级为纯文本")
            try:
                await update.message.reply_text(response_text)
            except:
                await update.message.reply_text("抱歉，回复失败。请直接发送命令，如：/search AI")



    async def handle_search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理搜索命令 - 带缓存"""
        user = update.effective_user
        user_id = user.id
        command = update.message.text

        # 提取命令和关键词
        parts = command.split(maxsplit=1)
        cmd = parts[0]
        keyword = parts[1] if len(parts) > 1 else ""

        # 检查缓存
        if self.cache_db and keyword:
            cached = self.cache_db.get_cache(cmd, keyword, 1)
            if cached:
                logger.info(f"[缓存命中] {cmd} {keyword} page1")

                # 恢复按钮
                keyboard = None
                if cached.get('buttons'):
                    buttons = []
                    for btn_data in cached['buttons']:
                        if btn_data.get('url'):
                            buttons.append([InlineKeyboardButton(text=btn_data['text'], url=btn_data['url'])])
                        elif btn_data.get('callback_data'):
                            original_callback = deserialize_callback_data(btn_data.get('callback_data'))
                            if original_callback is not None:
                                callback_id = f"cb_{time.time():.0f}_{len(self.callback_data_map)}"
                                # 需要存储原始message_id，这里用0作为占位符，实际翻页时从缓存获取
                                self.callback_data_map[callback_id] = (0, original_callback)
                                buttons.append([InlineKeyboardButton(text=btn_data['text'], callback_data=callback_id[:64])])

                    if buttons:
                        keyboard = InlineKeyboardMarkup(buttons)

                # 发送缓存结果（带按钮）
                sent = await update.message.reply_text(
                    cached['text'][:4000],
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )

                # 记录会话，以便翻页时使用
                self.user_search_sessions[user_id] = {
                    'chat_id': update.effective_chat.id,
                    'wait_msg_id': sent.message_id,
                    'command': cmd,
                    'keyword': keyword,
                    'timestamp': datetime.now()
                }

                return

        # 通知管理员
        admin_notification = (
            f"🔍 用户执行搜索:\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 {user_id}\n"
            f"📝 {command}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification)

        wait_msg = await update.message.reply_text("🔍 正在搜索，请稍候...")

        self.user_search_sessions[user_id] = {
            'chat_id': update.effective_chat.id,
            'wait_msg_id': wait_msg.message_id,
            'command': cmd,
            'keyword': keyword,
            'timestamp': datetime.now()
        }

        await self.pyrogram_client.send_message(self.target_bot_id, command)
        logger.info(f"搜索: {command}")

    async def handle_search_response(self, message: PyrogramMessage, is_edit: bool = False):
        """处理搜索机器人的响应 - 保存到缓存"""
        try:
            if not self.user_search_sessions:
                return

            user_id = max(self.user_search_sessions.keys(), key=lambda k: self.user_search_sessions[k]['timestamp'])
            session = self.user_search_sessions[user_id]

            text = message.text or message.caption or "无结果"

            try:
                if message.text and hasattr(message.text, 'html'):
                    text = message.text.html
            except:
                pass

            keyboard = self.convert_keyboard(message)

            if is_edit and message.id in self.pyrogram_to_telegram:
                telegram_msg_id = self.pyrogram_to_telegram[message.id]
                await self.app.bot.edit_message_text(
                    chat_id=session['chat_id'],
                    message_id=telegram_msg_id,
                    text=text[:4000],
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                try:
                    await self.app.bot.delete_message(
                        chat_id=session['chat_id'],
                        message_id=session['wait_msg_id']
                    )
                except:
                    pass

                sent = await self.app.bot.send_message(
                    chat_id=session['chat_id'],
                    text=text[:4000],
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )

                self.pyrogram_to_telegram[message.id] = sent.message_id
                self.telegram_to_pyrogram[sent.message_id] = message.id

                # 保存到缓存
                if self.cache_db and session.get('keyword'):
                    buttons = self.extract_buttons(message)
                    self.cache_db.save_cache(
                        session['command'],
                        session['keyword'],
                        1,  # 第一页
                        text,
                        buttons
                    )
                    
                    # 后台自动翻页（用户无感知）
                    if self.pagination_manager:
                        asyncio.create_task(
                            self.pagination_manager.start_pagination(
                                user_id, session['command'], session['keyword'], message
                            )
                        )

        except Exception as e:
            logger.error(f"处理搜索响应失败: {e}")

    def convert_keyboard(self, message: PyrogramMessage) -> Optional[InlineKeyboardMarkup]:
        """转换键盘"""
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
                        callback_id = f"cb_{time.time():.0f}_{len(self.callback_data_map)}"
                        self.callback_data_map[callback_id] = (message.id, btn.callback_data)
                        button_row.append(InlineKeyboardButton(text=btn.text, callback_data=callback_id[:64]))

                if button_row:
                    buttons.append(button_row)

            return InlineKeyboardMarkup(buttons) if buttons else None
        except Exception as e:
            logger.error(f"键盘转换失败: {e}")
            return None

    def extract_buttons(self, message: PyrogramMessage) -> list:
        """提取按钮数据（包含callback_data用于缓存）"""
        if not message.reply_markup or not message.reply_markup.inline_keyboard:
            return []

        buttons = []
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                btn_data = {"text": btn.text}
                if btn.url:
                    btn_data["url"] = btn.url
                if btn.callback_data is not None:
                    serialized = serialize_callback_data(btn.callback_data)
                    if serialized:
                        btn_data["callback_data"] = serialized
                buttons.append(btn_data)
        return buttons

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮点击 - 执行搜索命令或翻页"""
        query = update.callback_query
        data = query.data
        user = query.from_user

        logger.info(f"[回调] 收到callback: user={user.id}, data={data}")

        await query.answer()

        if data.startswith("cb_"):
            # 处理翻页按钮
            if data in self.callback_data_map:
                orig_msg_id, orig_callback = self.callback_data_map[data]
                logger.info(f"[翻页] 用户 {user.id} 点击: {orig_callback}")

                if isinstance(orig_callback, bytes):
                    orig_callback_bytes = orig_callback
                    try:
                        orig_callback_text = orig_callback.decode()
                    except UnicodeDecodeError:
                        orig_callback_text = None
                else:
                    orig_callback_text = str(orig_callback) if orig_callback is not None else None
                    orig_callback_bytes = orig_callback_text.encode() if orig_callback_text is not None else None

                session = self.user_search_sessions.get(user.id)

                # 解析callback_data获取页码（格式如：page_2）
                try:
                    if orig_callback_text and orig_callback_text.startswith("page_"):
                        page = int(orig_callback_text.split("_")[1])

                        # 从会话获取搜索信息
                        if session and 'command' in session and 'keyword' in session:
                            cmd = session['command']
                            keyword = session['keyword']

                            # 先检查缓存
                            cached = self.cache_db.get_cache(cmd, keyword, page) if self.cache_db else None
                            if cached:
                                logger.info(f"[翻页缓存] 命中: {cmd} {keyword} page{page}")

                                # 从缓存恢复按钮
                                keyboard = None
                                if cached.get('buttons'):
                                    buttons = []
                                    for btn_data in cached['buttons']:
                                        if btn_data.get('url'):
                                            buttons.append([InlineKeyboardButton(text=btn_data['text'], url=btn_data['url'])])
                                        elif btn_data.get('callback_data'):
                                            restored = deserialize_callback_data(btn_data.get('callback_data'))
                                            if restored is not None:
                                                # 重新生成callback_id
                                                callback_id = f"cb_{time.time():.0f}_{len(self.callback_data_map)}"
                                                self.callback_data_map[callback_id] = (orig_msg_id, restored)
                                                buttons.append([InlineKeyboardButton(text=btn_data['text'], callback_data=callback_id[:64])])

                                    if buttons:
                                        keyboard = InlineKeyboardMarkup(buttons)

                                # 发送缓存结果
                                await query.message.edit_text(
                                    text=cached['text'],
                                    reply_markup=keyboard,
                                    parse_mode='HTML'
                                )
                                return

                            else:
                                logger.info(f"[翻页] 缓存未命中，转发到搜索bot")

                    # 如果缓存未命中或不是page_格式，转发到搜索bot
                    if orig_callback_bytes is None:
                        raise ValueError("callback_data 无法编码")

                    await self.pyrogram_client.request_callback_answer(
                        chat_id=self.target_bot_id,
                        message_id=orig_msg_id,
                        callback_data=orig_callback_bytes
                    )

                    # 记录等待响应
                    self.user_search_sessions[user.id] = {
                        'chat_id': query.message.chat_id,
                        'wait_msg_id': query.message.message_id,
                        'command': session.get('command') if session else None,
                        'keyword': session.get('keyword') if session else None,
                        'timestamp': datetime.now()
                    }

                    logger.info(f"[翻页] 已转发callback到搜索bot")

                except Exception as e:
                    logger.error(f"[翻页] 处理失败: {e}")
                    await query.message.reply_text("❌ 翻页失败，请稍后重试")
            else:
                logger.warning(f"[翻页] callback_id不存在: {data}")
                await query.message.reply_text("❌ 按钮已过期，请重新搜索")

        elif data.startswith("cmd_"):
            # 解析命令
            parts = data.replace("cmd_", "").split("_", 1)
            cmd = parts[0]
            keywords = parts[1].replace("_", " ") if len(parts) > 1 else ""

            # 构造完整命令
            command = f"/{cmd} {keywords}" if keywords else f"/{cmd}"

            logger.info(f"[用户 {user.id}] 点击按钮: {command}")

            # 显示执行提示
            await query.message.reply_text(f"🔍 正在执行：{command}\n请稍候...")

            # 转发到搜索bot
            try:
                await self.pyrogram_client.send_message(self.target_bot_id, command)

                # 记录搜索会话
                self.user_search_sessions[user.id] = {
                    'chat_id': query.message.chat_id,
                    'wait_msg_id': query.message.message_id + 1,
                    'command': f"/{cmd}",
                    'keyword': keywords,
                    'timestamp': datetime.now()
                }

                logger.info(f"[镜像] 已转发: {command}")

            except Exception as e:
                logger.error(f"[镜像] 转发失败: {e}")
                await query.message.reply_text("❌ 搜索失败，请稍后重试或直接发送命令")

        elif data == "quick_search":
            # 搜索群组引导
            keyboard = [
                [InlineKeyboardButton("🔍 搜索群组", callback_data="cmd_search")],
                [InlineKeyboardButton("💬 搜索消息内容", callback_data="cmd_text")],
                [InlineKeyboardButton("👤 搜索用户", callback_data="cmd_human")]
            ]
            await query.message.edit_text(
                "请选择搜索类型，或直接发送关键词：",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "quick_help":
            await query.message.edit_text(
                "📖 使用指南：\n\n"
                "🔍 搜索方式：\n"
                "• /search [关键词] - 按群组名称搜索\n"
                "• /text [关键词] - 按消息内容搜索\n"
                "• /human [关键词] - 按用户名搜索\n"
                "• /topchat - 浏览热门群组目录\n\n"
                "💡 快捷使用：\n"
                "直接发送关键词，我会智能分析并选择最合适的搜索方式！\n\n"
                "📋 示例：\n"
                "• 发送 '区块链' → 自动搜索相关群组\n"
                "• 发送 'NFT交易' → 智能搜索讨论内容\n\n"
                "❓ 有任何问题都可以直接问我！"
            )
        
        elif data == "quick_topchat":
            # 直接触发topchat命令
            logger.info(f"[用户 {user.id}] 点击热门分类按钮")
            await query.message.edit_text("🔥 正在加载热门分类...\n请稍候...")
            
            try:
                await self.pyrogram_client.send_message(self.target_bot_id, "/topchat")
                self.user_search_sessions[user.id] = {
                    'chat_id': query.message.chat_id,
                    'wait_msg_id': query.message.message_id,
                    'command': '/topchat',
                    'keyword': '',
                    'timestamp': datetime.now()
                }
                logger.info(f"[镜像] 已转发: /topchat")
            except Exception as e:
                logger.error(f"[镜像] 转发失败: {e}")
                await query.message.edit_text("❌ 加载失败，请稍后重试")

        elif data == "cmd_help":
            await query.message.reply_text(
                "📖 使用指南：\n\n"
                "• /search [关键词] - 按群组名称搜索\n"
                "• /text [关键词] - 按消息内容搜索\n"
                "• /human [关键词] - 按用户名搜索\n"
                "• /topchat - 热门群组目录\n\n"
                "💡 或者直接告诉我你想找什么！"
            )

        else:
            logger.warning(f"未知callback: {data}")

    
    async def handle_admin_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理管理员回复"""
        reply_to = update.message.reply_to_message
        if not reply_to or not reply_to.text:
            return

        import re
        user_id = None
        for line in reply_to.text.split('\n'):
            if '🆔' in line or 'ID:' in line:
                numbers = re.findall(r'\d+', line)
                if numbers:
                    user_id = int(numbers[0])
                    break

        if not user_id:
            await update.message.reply_text("❌ 无法识别用户ID")
            return

        try:
            await context.bot.send_message(chat_id=user_id, text=update.message.text)
            await update.message.reply_text(f"✅ 已回复给用户 {user_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ 回复失败: {str(e)}")

    async def initialize(self):
        """初始化机器人"""
        try:
            logger.info("正在初始化整合机器人...")

            if not await self.setup_pyrogram():
                logger.error("Pyrogram初始化失败")
                return False

            builder = Application.builder().token(BOT_TOKEN)

            if os.environ.get('HTTP_PROXY'):
                proxy_url = os.environ.get('HTTP_PROXY')
                logger.info(f"配置Telegram Bot代理: {proxy_url}")
                request = httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=30.0)
                builder = builder.request(request)

            self.app = builder.build()

            self.app.add_handler(CommandHandler("start", self.handle_start))
            self.app.add_handler(CallbackQueryHandler(self.handle_callback))
            self.app.add_handler(MessageHandler(tg_filters.ALL, self.handle_message))

            logger.info("✅ 整合机器人初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def run(self):
        """运行机器人"""
        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)

            logger.info("="*50)
            logger.info("✅ AI增强版Bot已启动")
            logger.info(f"AI服务: {MAC_API_URL}")
            logger.info(f"缓存功能: {'启用' if self.cache_db else '禁用'}")
            logger.info("="*50)

            await asyncio.Event().wait()

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
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
    bot = IntegratedBotAI()

    if await bot.initialize():
        await bot.run()
    else:
        logger.error("初始化失败，退出")


if __name__ == "__main__":
    asyncio.run(main())
