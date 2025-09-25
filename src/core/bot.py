"""客服机器人主类"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from telegram import Update, Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from ..config.settings import Settings
from ..utils.logger import get_logger, Logger
from ..utils.exceptions import BotException, ErrorHandler
from ..utils.decorators import log_action, measure_performance
from .router import MessageRouter, RouteBuilder, MessageContext
from .handlers import BaseHandler, HandlerContext


logger = get_logger(__name__)


class CustomerServiceBot:
    """客服机器人"""

    def __init__(self, config: Settings = None):
        """初始化机器人"""
        # 加载配置
        self.config = config or Settings.from_env()
        self.config.validate()

        # 初始化日志系统
        Logger(self.config)
        self.logger = get_logger(self.__class__.__name__, self.config)

        # 初始化组件
        self.application: Optional[Application] = None
        self.router = MessageRouter(self.config)
        self.route_builder = RouteBuilder(self.router)
        self.handlers: Dict[str, BaseHandler] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

        # 当前会话管理
        self.current_customer = None  # 当前正在对话的客户

        # 统计信息
        self.stats = {
            'messages_received': 0,
            'messages_forwarded': 0,
            'replies_sent': 0,
            'errors': 0,
            'start_time': datetime.now()
        }

        self.logger.info(f"Bot initialized with version {self.config.version}")

    async def initialize(self):
        """异步初始化"""
        try:
            # 创建应用
            self.application = Application.builder().token(
                self.config.telegram.bot_token
            ).build()

            # 设置命令
            await self.setup_commands()

            # 注册处理器
            self.register_handlers()

            # 初始化数据库（如果需要）
            if self.config.features.enable_customer_history:
                from ..modules.storage import DatabaseManager
                self.db_manager = DatabaseManager(self.config)
                await self.db_manager.initialize()


            self.logger.info("Bot initialization completed")

        except Exception as e:
            self.logger.error(f"Failed to initialize bot: {e}")
            raise

    async def setup_commands(self):
        """设置机器人命令"""
        commands = [
            BotCommand("start", "开始使用机器人"),
            BotCommand("help", "获取帮助信息"),
            BotCommand("status", "查看机器人状态"),
            BotCommand("contact", "联系人工客服"),
        ]

        # 管理员命令
        admin_commands = commands + [
            BotCommand("stats", "查看统计信息"),
            BotCommand("sessions", "查看活跃会话"),
            BotCommand("reply", "回复客户消息"),
            BotCommand("broadcast", "广播消息"),
            BotCommand("settings", "机器人设置"),
        ]

        # 设置命令
        await self.application.bot.set_my_commands(commands)

        # 为管理员设置特殊命令
        await self.application.bot.set_my_commands(
            admin_commands,
            scope={"type": "chat", "chat_id": self.config.telegram.admin_id}
        )

    def register_handlers(self):
        """注册消息处理器"""
        # 命令处理器
        self.application.add_handler(CommandHandler("start", self.handle_start))
        self.application.add_handler(CommandHandler("help", self.handle_help))
        self.application.add_handler(CommandHandler("status", self.handle_status))
        self.application.add_handler(CommandHandler("contact", self.handle_contact))

        # 管理员命令
        self.application.add_handler(CommandHandler("stats", self.handle_stats))
        self.application.add_handler(CommandHandler("sessions", self.handle_sessions))
        self.application.add_handler(CommandHandler("reply", self.handle_reply))
        self.application.add_handler(CommandHandler("broadcast", self.handle_broadcast))
        self.application.add_handler(CommandHandler("settings", self.handle_settings))

        # 消息处理器 - 处理所有消息（包括搜索指令）
        # 只排除机器人自己处理的命令，其他命令（如搜索指令）也会转发
        self.application.add_handler(MessageHandler(
            filters.ALL,
            self.handle_message
        ))

        # 回调查询处理器
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # 错误处理器
        self.application.add_error_handler(self.handle_error)

    @log_action("start_command")
    async def handle_start(self, update: Update, context):
        """处理 /start 命令"""
        user = update.effective_user
        is_admin = user.id == self.config.telegram.admin_id

        if is_admin:
            text = (
                f"👋 欢迎，管理员 {user.first_name}！\n\n"
                "🤖 客服机器人已就绪\n"
                "📊 使用 /stats 查看统计\n"
                "💬 使用 /sessions 查看会话\n"
                "⚙️ 使用 /settings 进行设置"
            )
        else:
            text = (
                f"👋 您好 {user.first_name}！\n\n"
                "暂时支持的搜索指令：\n\n"
                "- 群组目录 /topchat\n"
                "- 群组搜索 /search\n"
                "- 按消息文本搜索 /text\n"
                "- 按名称搜索 /human\n\n"
                "您可以使用以上指令进行搜索，或直接发送消息联系客服。"
            )

            # 通知管理员
            await self.notify_admin_new_customer(user)

        await update.message.reply_text(text)
        self.stats['messages_received'] += 1

    async def handle_help(self, update: Update, context):
        """处理 /help 命令"""
        user = update.effective_user
        is_admin = user.id == self.config.telegram.admin_id

        if is_admin:
            text = self._get_admin_help()
        else:
            text = self._get_user_help()

        await update.message.reply_text(text, parse_mode='Markdown')

    async def handle_status(self, update: Update, context):
        """处理 /status 命令"""
        uptime = datetime.now() - self.stats['start_time']
        hours = uptime.total_seconds() / 3600

        text = (
            "✅ 机器人运行正常\n\n"
            f"⏱ 运行时间：{hours:.1f} 小时\n"
            f"📊 处理消息：{self.stats['messages_received']} 条\n"
            f"👥 活跃会话：{len(self.active_sessions)} 个"
        )

        await update.message.reply_text(text)

    async def handle_contact(self, update: Update, context):
        """处理 /contact 命令"""
        await update.message.reply_text(
            "正在为您转接人工客服，请稍候...\n"
            "您可以直接发送消息，客服会尽快回复您。"
        )
        # 修复：传递正确的 context 参数
        await self.forward_customer_message(update, context)

    @measure_performance
    async def handle_message(self, update: Update, context):
        """处理普通消息"""
        try:
            user = update.effective_user
            message = update.effective_message
            is_admin = user.id == self.config.telegram.admin_id

            self.stats['messages_received'] += 1

            if is_admin:
                # 管理员消息 - 检查是否是回复
                if message.reply_to_message:
                    await self.handle_admin_reply(update, context)
                elif self.current_customer:
                    # 如果有当前客户，直接发送给当前客户
                    await self.reply_to_current_customer(update, context)
                else:
                    # 没有当前客户时，提示管理员
                    await message.reply_text(
                        "💡 提示：暂无活跃客户\n\n"
                        "等待客户发送消息，或使用：\n"
                        "• 直接回复转发的客户消息\n"
                        "• /sessions 查看所有会话\n"
                        "• /reply <用户ID> <消息> 回复指定用户"
                    )
            else:
                # 客户消息 - 转发给管理员（包括搜索指令）
                # 处理所有客户消息，包括 /topchat, /search, /text, /human 等指令
                await self.forward_customer_message(update, context)

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            await self.send_error_message(update, e)

    async def forward_customer_message(self, update: Update, context):
        """转发客户消息给管理员"""
        user = update.effective_user
        message = update.effective_message
        chat = update.effective_chat

        # 创建或更新会话
        session_id = f"{chat.id}_{user.id}"
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'chat_id': chat.id,
                'messages': [],
                'started_at': datetime.now()
            }

        # 记录消息
        self.active_sessions[session_id]['messages'].append({
            'message_id': message.message_id,
            'text': message.text or "[非文本消息]",
            'timestamp': datetime.now()
        })

        # 设置为当前客户
        self.current_customer = {
            'user_id': user.id,
            'chat_id': chat.id,
            'username': user.username,
            'first_name': user.first_name,
            'session_id': session_id
        }

        # 构建用户信息 - 转义特殊字符
        def escape_markdown(text):
            """转义 Markdown 特殊字符"""
            if text is None:
                return ''
            # 转义特殊字符
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = str(text).replace(char, f'\\{char}')
            return text

        first_name = escape_markdown(user.first_name)
        last_name = escape_markdown(user.last_name) if user.last_name else ''
        username = escape_markdown(user.username) if user.username else 'N/A'

        # 构建用户信息
        user_info = (
            f"📨 来自客户的消息\n"
            f"👤 姓名：{first_name} {last_name}\n"
            f"🆔 ID：`{user.id}`\n"
            f"📱 用户名：@{username}\n"
            f"💬 会话：`{session_id}`\n"
            f"━━━━━━━━━━━━━━━━"
        )

        # 发送用户信息
        await context.bot.send_message(
            chat_id=self.config.telegram.admin_id,
            text=user_info,
            parse_mode='MarkdownV2'
        )

        # 转发原始消息
        forwarded = await context.bot.forward_message(
            chat_id=self.config.telegram.admin_id,
            from_chat_id=chat.id,
            message_id=message.message_id
        )

        # 保存转发消息ID映射
        context.bot_data.setdefault('message_map', {})[forwarded.message_id] = {
            'original_chat': chat.id,
            'original_user': user.id,
            'session_id': session_id
        }

        # 提示管理员可以直接输入文字回复
        await context.bot.send_message(
            chat_id=self.config.telegram.admin_id,
            text="💬 现在可以直接输入文字回复此客户，或回复上方转发的消息"
        )

        # 自动回复（如果启用）
        if self.config.features.enable_auto_reply and not is_business_hours(self.config):
            await self.send_auto_reply(update, context)

        self.stats['messages_forwarded'] += 1

    async def handle_admin_reply(self, update: Update, context):
        """处理管理员回复"""
        replied_to = update.message.reply_to_message

        # 查找原始消息信息
        message_map = context.bot_data.get('message_map', {})
        if replied_to.message_id not in message_map:
            await update.message.reply_text("⚠️ 无法找到原始消息信息")
            return

        original_info = message_map[replied_to.message_id]
        original_chat = original_info['original_chat']
        session_id = original_info['session_id']

        # 发送回复给客户
        try:
            if update.message.text:
                await context.bot.send_message(
                    chat_id=original_chat,
                    text=update.message.text
                )
            elif update.message.photo:
                await context.bot.send_photo(
                    chat_id=original_chat,
                    photo=update.message.photo[-1].file_id,
                    caption=update.message.caption
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=original_chat,
                    document=update.message.document.file_id,
                    caption=update.message.caption
                )

            # 确认发送
            await update.message.reply_text("✅ 消息已发送给客户")

            # 更新会话
            if session_id in self.active_sessions:
                self.active_sessions[session_id]['last_reply'] = datetime.now()

            self.stats['replies_sent'] += 1

        except Exception as e:
            await update.message.reply_text(f"❌ 发送失败：{e}")
            self.logger.error(f"Failed to send reply: {e}")

    async def handle_stats(self, update: Update, context):
        """处理 /stats 命令（管理员）"""
        if update.effective_user.id != self.config.telegram.admin_id:
            return

        uptime = datetime.now() - self.stats['start_time']
        days = uptime.days
        hours = uptime.seconds // 3600

        text = (
            "📊 **统计信息**\n\n"
            f"⏱ 运行时间：{days} 天 {hours} 小时\n"
            f"📨 接收消息：{self.stats['messages_received']} 条\n"
            f"📤 转发消息：{self.stats['messages_forwarded']} 条\n"
            f"💬 回复消息：{self.stats['replies_sent']} 条\n"
            f"❌ 错误次数：{self.stats['errors']} 次\n"
            f"👥 活跃会话：{len(self.active_sessions)} 个\n"
            f"📅 启动时间：{self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await update.message.reply_text(text, parse_mode='Markdown')

    async def handle_sessions(self, update: Update, context):
        """处理 /sessions 命令（管理员）"""
        if update.effective_user.id != self.config.telegram.admin_id:
            return

        if not self.active_sessions:
            await update.message.reply_text("当前没有活跃会话")
            return

        text = "👥 **活跃会话**\n\n"
        for session_id, session in self.active_sessions.items():
            duration = datetime.now() - session['started_at']
            text += (
                f"会话 `{session_id}`\n"
                f"👤 {session['first_name']} (@{session['username'] or 'N/A'})\n"
                f"💬 消息数：{len(session['messages'])}\n"
                f"⏱ 时长：{duration.seconds // 60} 分钟\n"
                f"━━━━━━━━━━━━━━━━\n"
            )

        await update.message.reply_text(text, parse_mode='Markdown')

    async def handle_reply(self, update: Update, context):
        """处理 /reply 命令（管理员）"""
        if update.effective_user.id != self.config.telegram.admin_id:
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "用法：/reply <用户ID> <消息>\n"
                "示例：/reply 123456789 您好，有什么可以帮助您？"
            )
            return

        try:
            user_id = int(context.args[0])
            message = ' '.join(context.args[1:])

            await context.bot.send_message(chat_id=user_id, text=message)
            await update.message.reply_text(f"✅ 消息已发送给用户 {user_id}")
            self.stats['replies_sent'] += 1

        except Exception as e:
            await update.message.reply_text(f"❌ 发送失败：{e}")


    async def reply_to_current_customer(self, update: Update, context):
        """回复当前客户"""
        if not self.current_customer:
            await update.message.reply_text("❌ 没有选中的客户")
            return

        try:
            message = update.effective_message

            # 发送消息给当前客户
            if message.text:
                await context.bot.send_message(
                    chat_id=self.current_customer['chat_id'],
                    text=message.text
                )
            elif message.photo:
                await context.bot.send_photo(
                    chat_id=self.current_customer['chat_id'],
                    photo=message.photo[-1].file_id,
                    caption=message.caption
                )
            elif message.document:
                await context.bot.send_document(
                    chat_id=self.current_customer['chat_id'],
                    document=message.document.file_id,
                    caption=message.caption
                )

            # 简洁确认消息
            await update.message.reply_text(f"✅ → {self.current_customer['first_name']}")
            self.stats['replies_sent'] += 1

        except Exception as e:
            await update.message.reply_text(f"❌ 发送失败：{e}")
            self.logger.error(f"Failed to send reply: {e}")

    async def handle_broadcast(self, update: Update, context):
        """处理 /broadcast 命令（管理员）"""
        if update.effective_user.id != self.config.telegram.admin_id:
            return

        if not context.args:
            await update.message.reply_text(
                "用法：/broadcast <消息>\n"
                "示例：/broadcast 系统维护通知：今晚10点进行系统维护"
            )
            return

        message = ' '.join(context.args)
        sent = 0
        failed = 0

        for session_id, session in self.active_sessions.items():
            try:
                await context.bot.send_message(
                    chat_id=session['chat_id'],
                    text=message
                )
                sent += 1
            except Exception as e:
                failed += 1
                self.logger.error(f"Failed to broadcast to {session['chat_id']}: {e}")

        await update.message.reply_text(
            f"✅ 广播完成\n"
            f"成功：{sent} 个\n"
            f"失败：{failed} 个"
        )

    async def handle_settings(self, update: Update, context):
        """处理 /settings 命令（管理员）"""
        if update.effective_user.id != self.config.telegram.admin_id:
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if self.config.features.enable_auto_reply else '❌'} 自动回复",
                    callback_data="toggle_auto_reply"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if self.config.features.enable_statistics else '❌'} 统计功能",
                    callback_data="toggle_statistics"
                )
            ],
            [
                InlineKeyboardButton("📊 查看所有设置", callback_data="view_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚙️ **机器人设置**\n\n点击按钮切换功能：",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_callback(self, update: Update, context):
        """处理回调查询"""
        query = update.callback_query
        await query.answer()

        data = query.data
        if data.startswith("done_"):
            session_id = data.replace("done_", "")
            await query.edit_message_text(f"✅ 会话 {session_id} 已标记为完成")
        elif data.startswith("later_"):
            session_id = data.replace("later_", "")
            await query.edit_message_text(f"⏸ 会话 {session_id} 已标记为稍后处理")
        elif data == "toggle_auto_reply":
            self.config.features.enable_auto_reply = not self.config.features.enable_auto_reply
            await query.edit_message_text(
                f"自动回复已{'启用' if self.config.features.enable_auto_reply else '禁用'}"
            )

    async def handle_error(self, update: Update, context):
        """处理错误"""
        self.stats['errors'] += 1
        error_info = await ErrorHandler.handle_error(context.error)
        self.logger.error(f"Update {update} caused error {context.error}")

        if update and update.effective_message:
            user_message = ErrorHandler.create_user_message(context.error)
            await update.effective_message.reply_text(user_message)

    async def notify_admin_new_customer(self, user):
        """通知管理员有新客户"""
        def escape_markdown(text):
            """转义 Markdown 特殊字符"""
            if text is None:
                return ''
            # 转义特殊字符
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = str(text).replace(char, f'\\{char}')
            return text

        first_name = escape_markdown(user.first_name)
        last_name = escape_markdown(user.last_name) if user.last_name else ''
        username = escape_markdown(user.username) if user.username else 'N/A'

        text = (
            f"🆕 新客户加入\n"
            f"👤 姓名：{first_name} {last_name}\n"
            f"🆔 ID：`{user.id}`\n"
            f"📱 用户名：@{username}"
        )

        try:
            await self.application.bot.send_message(
                chat_id=self.config.telegram.admin_id,
                text=text,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            self.logger.error(f"Failed to notify admin: {e}")

    async def send_auto_reply(self, update: Update, context):
        """发送自动回复"""
        import pytz
        from datetime import time

        # 检查营业时间
        tz = pytz.timezone(self.config.business.timezone)
        now = datetime.now(tz).time()
        start_time = time.fromisoformat(self.config.business.business_hours_start)
        end_time = time.fromisoformat(self.config.business.business_hours_end)

        if not (start_time <= now <= end_time):
            message = self.config.business.offline_message.format(
                start=self.config.business.business_hours_start,
                end=self.config.business.business_hours_end
            )
            await update.message.reply_text(message)

    async def send_error_message(self, update: Update, error: Exception):
        """发送错误消息给用户"""
        user_message = ErrorHandler.create_user_message(error)
        await update.message.reply_text(user_message)

    def _get_admin_help(self) -> str:
        """获取管理员帮助信息"""
        return (
            "📚 **管理员帮助**\n\n"
            "**基础命令**\n"
            "/start - 启动机器人\n"
            "/help - 显示帮助\n"
            "/status - 查看状态\n\n"
            "**管理命令**\n"
            "/stats - 查看统计信息\n"
            "/sessions - 查看活跃会话\n"
            "/reply <用户ID> <消息> - 回复指定用户\n"
            "/broadcast <消息> - 广播消息给所有用户\n"
            "/settings - 机器人设置\n\n"
            "**快速回复客户**\n"
            "• 直接输入文字 - 自动发送给最近的客户\n"
            "• 回复转发消息 - 回复特定客户"
        )

    def _get_user_help(self) -> str:
        """获取用户帮助信息"""
        return (
            "📚 **帮助信息**\n\n"
            "**使用方法**\n"
            "• 直接发送消息，客服会尽快回复您\n"
            "• 支持发送文字、图片、文件等\n"
            "• /contact - 联系人工客服\n"
            "• /status - 查看服务状态\n\n"
            f"**工作时间**\n"
            f"{self.config.business.business_hours_start} - {self.config.business.business_hours_end}\n\n"
            "如有紧急情况，请留言，我们会尽快处理"
        )


    def run(self):
        """运行机器人"""
        try:
            # 同步初始化
            asyncio.get_event_loop().run_until_complete(self.initialize())

            self.logger.info("Starting bot...")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)

        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot crashed: {e}")
            raise
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        self.logger.info("Cleaning up resources...")
        # 保存统计信息、关闭数据库等
        pass


def is_business_hours(config: Settings) -> bool:
    """检查是否在营业时间"""
    import pytz
    from datetime import time

    tz = pytz.timezone(config.business.timezone)
    now = datetime.now(tz).time()
    start_time = time.fromisoformat(config.business.business_hours_start)
    end_time = time.fromisoformat(config.business.business_hours_end)

    return start_time <= now <= end_time