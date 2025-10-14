#\!/usr/bin/env python3
from pyrogram import Client

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"

proxy = {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080
}

app = Client(
    "user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=proxy
)

app.start()
me = app.get_me()
print(f"✅ Session创建成功！")
print(f"账号: {me.first_name}")
print(f"ID: {me.id}")
app.stop()
