from pyrogram import Client

API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"

# 添加代理配置
proxy = {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080
}

app = Client(
    "user_session",
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=proxy  # 使用代理
)

print("使用代理连接: SOCKS5 127.0.0.1:1080")
print("开始创建session...")
app.start()
me = app.get_me()
print(f"✅ Session创建成功！用户: {me.first_name}")
app.stop()
