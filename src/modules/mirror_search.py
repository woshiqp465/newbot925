"""
搜索镜像模块 - 自动转发搜索指令到目标机器人并返回结果
基于 jingxiang 项目的镜像机制
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from pyrogram import Client, filters
from pyrogram.types import Message as PyrogramMessage
from pyrogram.raw.functions.messages import GetBotCallbackAnswer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class MirrorSearchHandler:
    """处理搜索指令的镜像转发"""

    def __init__(self, config):
        self.config = config
        self.enabled = False

        # Pyrogram配置（需要在.env中配置）
        self.api_id = None
        self.api_hash = None
        self.session_name = "search_mirror_session"
        self.target_bot = "@openaiw_bot"  # 目标搜索机器人

        # Pyrogram客户端
        self.pyrogram_client: Optional[Client] = None
        self.target_bot_id: Optional[int] = None

        # 消息映射
        self.user_search_requests: Dict[int, Dict[str, Any]] = {}  # user_id -> search_info
        self.pyrogram_to_user: Dict[int, int] = {}  # pyrogram_msg_id -> user_id
        self.user_to_telegram: Dict[int, int] = {}  # user_id -> telegram_msg_id

        # 支持的搜索命令
        self.search_commands = ['/topchat', '/search', '/text', '/human']

    async def initialize(self, api_id: int, api_hash: str):
        """初始化Pyrogram客户端"""
        try:
            self.api_id = api_id
            self.api_hash = api_hash

            self.pyrogram_client = Client(
                self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash
            )

            await self.pyrogram_client.start()
            logger.info("✅ 搜索镜像客户端已启动")

            # 获取目标机器人信息
            target = await self.pyrogram_client.get_users(self.target_bot)
            self.target_bot_id = target.id
            logger.info(f"✅ 连接到搜索机器人: {target.username} (ID: {target.id})")

            # 设置消息监听器
            await self._setup_listeners()

            self.enabled = True
            return True

        except Exception as e:
            logger.error(f"镜像搜索初始化失败: {e}")
            self.enabled = False
            return False

    async def _setup_listeners(self):
        """设置Pyrogram消息监听器"""
        if not self.pyrogram_client:
            return

        @self.pyrogram_client.on_message(filters.user(self.target_bot_id))
        async def on_bot_response(_, message: PyrogramMessage):
            """当收到搜索机器人的响应时"""
            await self._handle_bot_response(message)

        @self.pyrogram_client.on_edited_message(filters.user(self.target_bot_id))
        async def on_message_edited(_, message: PyrogramMessage):
            """当搜索机器人编辑消息时（翻页）"""
            await self._handle_bot_response(message, is_edit=True)

        logger.info("✅ 消息监听器已设置")

    def is_search_command(self, text: str) -> bool:
        """检查是否是搜索命令"""
        if not text:
            return False
        command = text.split()[0]
        return command in self.search_commands

    async def process_search_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int,
        command: str
    ) -> bool:
        """处理用户的搜索命令"""

        if not self.enabled or not self.pyrogram_client:
            logger.warning("搜索镜像未启用")
            return False

        try:
            # 记录用户搜索请求
            self.user_search_requests[user_id] = {
                'command': command,
                'chat_id': update.effective_chat.id,
                'update': update,
                'context': context,
                'timestamp': asyncio.get_event_loop().time()
            }

            # 通过Pyrogram发送命令给目标机器人
            sent_message = await self.pyrogram_client.send_message(
                self.target_bot,
                command
            )

            # 记录映射关系
            if sent_message:
                logger.info(f"已发送搜索命令给 {self.target_bot}: {command}")
                # 等待响应会通过监听器处理

                # 发送等待提示给用户
                waiting_msg = await update.message.reply_text(
                    "🔍 正在搜索，请稍候..."
                )
                self.user_to_telegram[user_id] = waiting_msg.message_id

                return True

        except Exception as e:
            logger.error(f"发送搜索命令失败: {e}")
            await update.message.reply_text(
                "❌ 搜索请求失败，请稍后重试或联系管理员"
            )
            return False

    async def _handle_bot_response(self, message: PyrogramMessage, is_edit: bool = False):
        """处理搜索机器人的响应"""
        try:
            # 查找对应的用户
            # 这里需要根据时间戳或其他方式匹配用户请求
            user_id = self._find_user_for_response(message)

            if not user_id or user_id not in self.user_search_requests:
                logger.debug(f"未找到对应的用户请求")
                return

            user_request = self.user_search_requests[user_id]

            # 转换消息格式并发送给用户
            await self._forward_to_user(message, user_request, is_edit)

        except Exception as e:
            logger.error(f"处理机器人响应失败: {e}")

    def _find_user_for_response(self, message: PyrogramMessage) -> Optional[int]:
        """查找响应对应的用户"""
        # 简单的实现：返回最近的请求用户
        # 实际应用中可能需要更复杂的匹配逻辑
        if self.user_search_requests:
            # 获取最近的请求
            recent_user = max(
                self.user_search_requests.keys(),
                key=lambda k: self.user_search_requests[k].get('timestamp', 0)
            )
            return recent_user
        return None

    async def _forward_to_user(
        self,
        pyrogram_msg: PyrogramMessage,
        user_request: Dict[str, Any],
        is_edit: bool = False
    ):
        """转发搜索结果给用户"""
        try:
            update = user_request['update']
            context = user_request['context']

            # 提取消息内容
            text = self._extract_text(pyrogram_msg)
            keyboard = self._convert_keyboard(pyrogram_msg)

            if is_edit and user_request['user_id'] in self.user_to_telegram:
                # 编辑现有消息
                telegram_msg_id = self.user_to_telegram[user_request['user_id']]
                await context.bot.edit_message_text(
                    chat_id=user_request['chat_id'],
                    message_id=telegram_msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            else:
                # 发送新消息
                sent = await context.bot.send_message(
                    chat_id=user_request['chat_id'],
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_to_telegram[user_request['user_id']] = sent.message_id

        except Exception as e:
            logger.error(f"转发消息给用户失败: {e}")

    def _extract_text(self, message: PyrogramMessage) -> str:
        """提取消息文本"""
        if message.text:
            return message.text
        elif message.caption:
            return message.caption
        return "（无文本内容）"

    def _convert_keyboard(self, message: PyrogramMessage) -> Optional[InlineKeyboardMarkup]:
        """转换Pyrogram键盘为Telegram键盘"""
        if not message.reply_markup:
            return None

        try:
            buttons = []
            for row in message.reply_markup.inline_keyboard:
                button_row = []
                for button in row:
                    if button.text:
                        # 创建回调按钮
                        callback_data = button.callback_data or f"mirror_{button.text}"
                        if len(callback_data.encode()) > 64:
                            # Telegram限制callback_data最大64字节
                            callback_data = callback_data[:60] + "..."

                        button_row.append(
                            InlineKeyboardButton(
                                text=button.text,
                                callback_data=callback_data
                            )
                        )
                if button_row:
                    buttons.append(button_row)

            return InlineKeyboardMarkup(buttons) if buttons else None

        except Exception as e:
            logger.error(f"转换键盘失败: {e}")
            return None

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询（翻页等）"""
        query = update.callback_query

        if not query.data.startswith("mirror_"):
            return False

        try:
            # 这里需要实现回调处理逻辑
            # 将回调转发给Pyrogram客户端
            await query.answer("处理中...")
            return True

        except Exception as e:
            logger.error(f"处理回调失败: {e}")
            await query.answer("操作失败", show_alert=True)
            return False

    async def cleanup(self):
        """清理资源"""
        if self.pyrogram_client:
            await self.pyrogram_client.stop()
            logger.info("搜索镜像客户端已停止")