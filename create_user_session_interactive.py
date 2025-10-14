#!/usr/bin/env python3
"""
创建用户Session用于镜像功能
需要交互式输入手机号码和验证码
"""
from pyrogram import Client

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
SESSION_NAME = "user_session"

# 设置代理
proxy = {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080
}

print("=" * 50)
print("创建用户Session - 用于镜像搜索功能")
print("=" * 50)
print("\n重要提示：")
print("1. 需要使用真实的Telegram账号（非Bot）")
print("2. 输入手机号码格式：+国家代码手机号 (如 +86138xxxxxxxx)")
print("3. 您将收到验证码，请准备好输入")
print("=" * 50)

try:
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy
    )

    with app:
        me = app.get_me()
        print(f"\n✅ Session创建成功！")
        print(f"账号信息：")
        print(f"  姓名：{me.first_name} {me.last_name or ''}")
        print(f"  用户名：@{me.username if me.username else '未设置'}") 
        print(f"  ID：{me.id}")
        print(f"  是否Bot：{'是' if me.is_bot else '否'}") 
        print(f"\nSession已保存为：{SESSION_NAME}.session")
        print("\n现在可以使用此账号进行镜像搜索了！")

except Exception as e:
    print(f"\n❌ 创建失败：{e}")
    print("\n可能的原因：")
    print("1. 手机号码格式错误")
    print("2. 验证码输入错误")
    print("3. 网络连接问题")
    print("4. 代理设置问题")
