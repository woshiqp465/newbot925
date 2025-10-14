from pyrogram import Client

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
CODE = "77194"

proxy = {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080
}

print("创建session中...")

app = Client(
    "user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=proxy
)

app.start()
me = app.get_me()
print(f"✅ Session创建成功！")
print(f"账号: {me.first_name} {me.last_name or ''}")
print(f"用户名: @{me.username if me.username else '无'}")
print(f"ID: {me.id}")
print(f"是否为Bot: {me.is_bot}")
print(f"Session已保存: user_session.session")
app.stop()
