#!/usr/bin/env python3
"""
客服机器人 - 简化版（无镜像功能）
只包含消息转发和管理员回复功能
"""
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 配置
BOT_TOKEN = "8426529617:AAHAxzohSMFBAxInzbAVJsZfkB5bHnOyFC4"
ADMIN_ID = 7363537082
ADMIN_USERNAME = "xiaobai_80"

# 日志配置
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

class CustomerServiceBot:
    def __init__(self):
        self.app = None
        self.user_sessions = {}  # 存储用户会话

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令"""
        user = update.effective_user
        welcome_text = (
            f"👋 您好 {user.first_name}！\n\n"
            "我是您的智能客服助手\n\n"
            "直接发送消息即可联系人工客服\n"
            f"技术支持：@{ADMIN_USERNAME}\n\n"
            "⚠️ 搜索功能暂时维护中..."
        )
        await update.message.reply_text(welcome_text)

        # 通知管理员
        if user.id != ADMIN_ID:
            admin_msg = (
                f"🆕 新用户访问:\n"
                f"用户: {user.first_name} (@{user.username or '无'})\n"
                f"ID: {user.id}"
            )
            try:
                await context.bot.send_message(ADMIN_ID, admin_msg)
            except:
                pass

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户消息"""
        user = update.effective_user
        
        # 如果是管理员回复用户
        if user.id == ADMIN_ID:
            # 检查是否是回复命令
            text = update.message.text
            if text.startswith("/reply "):
                await self.handle_reply_command(update, context)
                return
            elif text == "/list":
                await self.handle_list_command(update, context)
                return
        
        # 普通用户消息，转发给管理员
        if user.id != ADMIN_ID:
            await self.forward_to_admin(update, context)

    async def forward_to_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """转发消息给管理员"""
        user = update.effective_user
        msg = update.message.text
        
        # 保存用户信息
        self.user_sessions[user.id] = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "last_message": datetime.now()
        }
        
        forward_msg = (
            f"📨 用户消息\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 {user.first_name} {user.last_name or ''}\n"
            f"🆔 ID: {user.id}\n"
            f"👤 用户名: @{user.username or '无'}\n"
            f"💬 内容:\n{msg}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"回复: /reply {user.id} 您的消息"
        )
        
        try:
            await context.bot.send_message(ADMIN_ID, forward_msg)
            await update.message.reply_text("✅ 消息已发送给客服，请稍候...")
            logger.info(f"转发消息 - 用户 {user.id}: {msg[:50]}")
        except Exception as e:
            logger.error(f"转发失败: {e}")
            await update.message.reply_text("❌ 发送失败，请稍后重试")

    async def handle_reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理管理员回复"""
        parts = update.message.text.split(maxsplit=2)
        if len(parts) < 3:
            await update.message.reply_text("格式: /reply 用户ID 消息")
            return

        try:
            user_id = int(parts[1])
            reply_msg = parts[2]
            
            await context.bot.send_message(
                user_id,
                f"💬 客服回复:\n{reply_msg}"
            )
            await update.message.reply_text(f"✅ 已回复用户 {user_id}")
            logger.info(f"回复用户 {user_id}: {reply_msg[:50]}")
        except Exception as e:
            await update.message.reply_text(f"❌ 发送失败: {e}")

    async def handle_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """列出最近的用户"""
        if not self.user_sessions:
            await update.message.reply_text("暂无用户会话")
            return
        
        msg = "📋 最近的用户:\n\n"
        for user_id, info in self.user_sessions.items():
            msg += f"ID: {user_id}\n"
            msg += f"姓名: {info['first_name']} {info.get('last_name', '')}\\n"
            msg += f"用户名: @{info.get('username', '无')}\\n"
            msg += f"最后消息: {info['last_message'].strftime('%Y-%m-%d %H:%M:%S')}\\n"
            msg += "━━━━━━━━━━\n"
        
        await update.message.reply_text(msg)

    async def run(self):
        """运行机器人"""
        try:
            logger.info("启动客服机器人...")
            
            self.app = Application.builder().token(BOT_TOKEN).build()

            # 注册处理器
            self.app.add_handler(CommandHandler("start", self.handle_start))
            self.app.add_handler(CommandHandler("help", self.handle_start))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            logger.info("✅ 机器人已启动!")
            logger.info(f"管理员: @{ADMIN_USERNAME} (ID: {ADMIN_ID})")
            
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            while True:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"运行错误: {e}")
        finally:
            if self.app:
                await self.app.stop()

if __name__ == "__main__":
    bot = CustomerServiceBot()
    asyncio.run(bot.run())
