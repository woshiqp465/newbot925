#!/usr/bin/env python3
"""
手动创建Session - 避开验证码限制
"""
from pyrogram import Client
import asyncio

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"

# 不使用代理，避免IP被限制
app = Client(
    "user_session_new",  # 使用新的session名称
    api_id=API_ID,
    api_hash=API_HASH,
    # 不使用代理，直接连接
)

print("=" * 50)
print("创建新的Session文件")
print("=" * 50)
print("\n重要提示：")
print("1. 使用新的session名称: user_session_new")
print("2. 直接连接Telegram（不通过代理）")
print("3. 如果还是被限制，请等待几小时后再试")
print("=" * 50)

try:
    app.start()
    me = app.get_me()
    print(f"\n✅ Session创建成功！")
    print(f"账号: {me.first_name}")
    print(f"ID: {me.id}")
    print(f"Session文件: user_session_new.session")
    app.stop()
except Exception as e:
    print(f"\n❌ 错误: {e}")
    if "FLOOD_WAIT" in str(e):
        print("还在限制期内，请稍后再试")
