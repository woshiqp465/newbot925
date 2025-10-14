#!/usr/bin/env python3
from pyrogram import Client
import asyncio
import qrcode
import io

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"

proxy = {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080
}

async def qr_login():
    app = Client(
        "user_session",
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy
    )
    
    @app.on_login_token()
    async def on_token(client, token):
        # 生成二维码URL
        url = f"tg://login?token={token}"
        print(f"\n扫描二维码登录：")
        print(f"URL: {url}")
        
        # 生成二维码
        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.make()
        qr.print_ascii()
        
        print("\n请使用Telegram APP扫描上方二维码")
        return True
    
    await app.start()
    me = await app.get_me()
    print(f"\n✅ 登录成功！")
    print(f"账号：{me.first_name}")
    print(f"ID：{me.id}")
    await app.stop()

print("正在生成二维码...")
asyncio.run(qr_login())
