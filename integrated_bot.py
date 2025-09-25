#!/usr/bin/env python3
"""
整合版客服机器人 - 包含镜像搜索功能
修复了事件循环冲突问题
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from datetime import datetime

# Pyrogram imports
from pyrogram import Client as PyrogramClient, filters
from pyrogram.types import Message as PyrogramMessage
from pyrogram.raw.functions.messages import GetBotCallbackAnswer

# Telegram Bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters as tg_filters
from telegram.ext import ContextTypes

# 项目imports
from src.config.settings import Settings
from src.core.bot import CustomerServiceBot

# ================== 配置 ==================
API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
SESSION_NAME = "mirror_session"
BOT_TOKEN = "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4"
TARGET_BOT = "@openaiw_bot"
ADMIN_ID = 7363537082

# 搜索命令列表
SEARCH_COMMANDS = ['/topchat', '/search', '/text', '/human']

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedBot:
    """整合的客服机器人 - 包含镜像搜索功能"""

    def __init__(self):
        # 加载配置
        self.config = Settings.from_env()

        # Bot应用
        self.app = None

        # Pyrogram客户端（用于镜像）
        self.pyrogram_client: Optional[PyrogramClient] = None
        self.target_bot_id: Optional[int] = None

        # 消息映射
        self.pyrogram_to_telegram = {}  # pyrogram_msg_id -> telegram_msg_id
        self.telegram_to_pyrogram = {}  # telegram_msg_id -> pyrogram_msg_id
        self.callback_data_map = {}     # telegram_callback_id -> (pyrogram_msg_id, original_callback_data)
        self.user_search_sessions = {}  # user_id -> search_session_info

    async def setup_pyrogram(self):
        """设置Pyrogram客户端用于镜像"""
        try:
            self.pyrogram_client = PyrogramClient(
                SESSION_NAME,
                api_id=API_ID,
                api_hash=API_HASH
            )

            await self.pyrogram_client.start()
            logger.info("✅ Pyrogram客户端已启动")

            # 获取目标机器人信息
            target = await self.pyrogram_client.get_users(TARGET_BOT)
            self.target_bot_id = target.id
            logger.info(f"✅ 已连接到搜索机器人: {target.username} (ID: {target.id})")

            # 设置消息监听器
            @self.pyrogram_client.on_message(filters.user(self.target_bot_id))
            async def on_bot_response(_, message: PyrogramMessage):
                await self.handle_search_response(message)

            @self.pyrogram_client.on_edited_message(filters.user(self.target_bot_id))
            async def on_message_edited(_, message: PyrogramMessage):
                await self.handle_search_response(message, is_edit=True)

            logger.info("✅ 搜索监听器已设置")
            return True

        except Exception as e:
            logger.error(f"Pyrogram设置失败: {e}")
            return False

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令"""
        user = update.effective_user
        welcome_text = (
            f"👋 您好 {user.first_name}！\n\n"
            "暂时支持的搜索指令：\n\n"
            "- 群组目录 /topchat\n"
            "- 群组搜索 /search\n"
            "- 按消息文本搜索 /text\n"
            "- 按名称搜索 /human\n\n"
            "您可以使用以上指令进行搜索，或直接发送消息联系客服。"
        )
        await update.message.reply_text(welcome_text)

        # 通知管理员有新用户访问
        admin_notification = (
            f"🆕 新用户访问:\n"
            f"👤 姓名: {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"👤 用户名: @{user.username or '无'}\n"
            f"📱 命令: /start\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification
        )

        logger.info(f"新用户访问 /start: {user.id} ({user.first_name})")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理所有消息"""
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        text = update.message.text
        is_admin = user.id == ADMIN_ID

        # 管理员回复逻辑
        if is_admin and update.message.reply_to_message:
            await self.handle_admin_reply(update, context)
            return

        # 搜索命令处理
        if self.is_search_command(text):
            await self.handle_search_command(update, context)
            return

        # 普通客服消息转发
        await self.forward_to_admin(update, context)

    def is_search_command(self, text: str) -> bool:
        """检查是否是搜索命令"""
        if not text:
            return False
        command = text.split()[0]
        return command in SEARCH_COMMANDS

    async def handle_search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理搜索命令 - 通过Pyrogram转发"""
        user = update.effective_user
        user_id = user.id
        command = update.message.text

        try:
            # 通知管理员有用户执行搜索
            admin_notification = (
                f"🔍 用户执行搜索:\n"
                f"👤 姓名: {user.first_name} {user.last_name or ''}\n"
                f"🆔 ID: {user_id}\n"
                f"👤 用户名: @{user.username or '无'}\n"
                f"📝 搜索内容: {command}\n"
                f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_notification
            )

            # 发送等待消息
            wait_msg = await update.message.reply_text("🔍 正在搜索，请稍候...")

            # 记录搜索会话
            self.user_search_sessions[user_id] = {
                'chat_id': update.effective_chat.id,
                'wait_msg_id': wait_msg.message_id,
                'command': command,
                'timestamp': datetime.now()
            }

            # 通过Pyrogram发送到搜索机器人
            await self.pyrogram_client.send_message(self.target_bot_id, command)
            logger.info(f"用户 {user.first_name}({user_id}) 执行搜索: {command}")

        except Exception as e:
            logger.error(f"搜索命令处理失败: {e}")
            await update.message.reply_text("❌ 搜索失败，请稍后重试")

    async def handle_search_response(self, message: PyrogramMessage, is_edit: bool = False):
        """处理搜索机器人的响应"""
        try:
            # 查找最近的搜索请求
            if not self.user_search_sessions:
                return

            # 获取最近的请求用户
            user_id = max(
                self.user_search_sessions.keys(),
                key=lambda k: self.user_search_sessions[k]['timestamp']
            )

            session = self.user_search_sessions[user_id]

            # 提取消息内容
            text = message.text or message.caption or "无结果"

            # 处理HTML格式
            try:
                if message.text and hasattr(message.text, 'html'):
                    text = message.text.html
            except:
                pass

            # 转换键盘
            keyboard = self.convert_keyboard(message)

            # 更新或发送消息
            if is_edit and message.id in self.pyrogram_to_telegram:
                # 编辑现有消息
                telegram_msg_id = self.pyrogram_to_telegram[message.id]
                await self.app.bot.edit_message_text(
                    chat_id=session['chat_id'],
                    message_id=telegram_msg_id,
                    text=text[:4000],
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                # 删除等待消息，发送新消息
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

                # 记录映射
                self.pyrogram_to_telegram[message.id] = sent.message_id
                self.telegram_to_pyrogram[sent.message_id] = message.id

        except Exception as e:
            logger.error(f"处理搜索响应失败: {e}")

    def convert_keyboard(self, message: PyrogramMessage) -> Optional[InlineKeyboardMarkup]:
        """转换Pyrogram键盘为Telegram键盘"""
        if not message.reply_markup or not message.reply_markup.inline_keyboard:
            return None

        try:
            buttons = []
            for row in message.reply_markup.inline_keyboard:
                button_row = []
                for btn in row:
                    if btn.url:
                        button_row.append(InlineKeyboardButton(
                            text=btn.text,
                            url=btn.url
                        ))
                    elif btn.callback_data:
                        # 创建callback ID
                        callback_id = f"cb_{time.time():.0f}_{len(self.callback_data_map)}"
                        self.callback_data_map[callback_id] = (
                            message.id,
                            btn.callback_data
                        )

                        button_row.append(InlineKeyboardButton(
                            text=btn.text,
                            callback_data=callback_id[:64]
                        ))

                if button_row:
                    buttons.append(button_row)

            return InlineKeyboardMarkup(buttons) if buttons else None

        except Exception as e:
            logger.error(f"键盘转换失败: {e}")
            return None

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询（翻页等）"""
        query = update.callback_query
        callback_id = query.data

        await query.answer("正在加载...")

        if callback_id not in self.callback_data_map:
            await query.answer("按钮已过期", show_alert=True)
            return

        pyrogram_msg_id, original_callback = self.callback_data_map[callback_id]

        try:
            # 准备callback数据
            if not isinstance(original_callback, bytes):
                original_callback = original_callback.encode() if original_callback else b''

            # 调用原始callback
            result = await self.pyrogram_client.invoke(
                GetBotCallbackAnswer(
                    peer=await self.pyrogram_client.resolve_peer(self.target_bot_id),
                    msg_id=pyrogram_msg_id,
                    data=original_callback
                )
            )

            # 等待Bot编辑消息
            await asyncio.sleep(1)

            logger.info("✅ Callback已处理")

        except Exception as e:
            logger.error(f"Callback处理失败: {e}")
            await query.answer("操作失败", show_alert=True)

    async def forward_to_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """转发客户消息给管理员"""
        user = update.effective_user
        message = update.effective_message

        # 构建转发消息
        forward_text = (
            f"📬 新消息来自客户:\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"👤 用户名: @{user.username or '无'}\n"
            f"💬 消息: {message.text}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # 发送给管理员
        sent = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=forward_text
        )

        logger.info(f"已转发消息给管理员: 来自 {user.id}")

    async def handle_admin_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理管理员回复"""
        reply_to = update.message.reply_to_message

        if not reply_to or not reply_to.text:
            return

        # 从回复的消息中提取用户ID
        lines = reply_to.text.split('\n')
        user_id = None
        for line in lines:
            if 'ID:' in line or '🆔' in line:
                try:
                    # 尝试多种格式提取ID
                    if '🆔 ID:' in line:
                        user_id = int(line.split('🆔 ID:')[1].strip())
                    elif 'ID:' in line:
                        id_part = line.split('ID:')[1].strip()
                        # 提取数字部分
                        import re
                        numbers = re.findall(r'\d+', id_part)
                        if numbers:
                            user_id = int(numbers[0])
                    break
                except Exception as e:
                    logger.debug(f"提取ID失败: {e}, line: {line}")

        if not user_id:
            logger.warning(f"无法识别用户ID，消息内容：{reply_to.text}")
            await update.message.reply_text("❌ 无法识别用户ID")
            return

        # 发送回复给用户
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=update.message.text
            )

            # 给管理员确认
            await update.message.reply_text(f"✅ 已回复给用户 {user_id}")
            logger.info(f"管理员回复了用户 {user_id}: {update.message.text}")

        except Exception as e:
            logger.error(f"回复失败: {e}")
            await update.message.reply_text(f"❌ 回复失败: {str(e)}")

    async def initialize(self):
        """初始化机器人"""
        try:
            logger.info("正在初始化整合机器人...")

            # 初始化Pyrogram客户端
            if not await self.setup_pyrogram():
                logger.error("Pyrogram初始化失败")
                return False

            # 创建Bot应用
            self.app = Application.builder().token(BOT_TOKEN).build()

            # 注册处理器
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
            # 启动Bot
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)

            logger.info("="*50)
            logger.info("✅ 整合机器人已启动")
            logger.info(f"客服功能: 消息转发给管理员 {ADMIN_ID}")
            logger.info(f"搜索功能: 镜像 {TARGET_BOT}")
            logger.info("="*50)

            # 保持运行
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
    bot = IntegratedBot()

    if await bot.initialize():
        await bot.run()
    else:
        logger.error("初始化失败，退出")


if __name__ == "__main__":
    asyncio.run(main())