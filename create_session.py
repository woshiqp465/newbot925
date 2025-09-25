#!/usr/bin/env python3
"""
创建 Pyrogram session 文件
运行此脚本来进行Telegram账号认证
"""

import asyncio
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

# 配置
API_ID = 24660516
API_HASH = "eae564578880a59c9963916ff1bbbd3a"
SESSION_NAME = "mirror_session"


async def main():
    print("=" * 50)
    print("Pyrogram Session 创建工具")
    print("=" * 50)
    print("\n此工具将创建一个session文件，用于连接Telegram")
    print("您需要输入您的手机号码和验证码")
    print("\n注意：这将使用您的Telegram账号来监听搜索机器人的响应")
    print("=" * 50)

    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH
    )

    try:
        # 启动客户端
        await app.start()

        # 获取当前用户信息
        me = await app.get_me()

        print("\n✅ Session创建成功！")
        print(f"Session文件已保存为: {SESSION_NAME}.session")
        print(f"\n登录账号信息：")
        print(f"  姓名: {me.first_name} {me.last_name or ''}")
        print(f"  用户名: @{me.username or 'N/A'}")
        print(f"  ID: {me.id}")
        print(f"  手机: {me.phone_number if hasattr(me, 'phone_number') else 'N/A'}")

        # 测试连接到目标机器人
        print("\n正在测试连接到搜索机器人...")
        try:
            target_bot = await app.get_users("@openaiw_bot")
            print(f"✅ 成功连接到搜索机器人: {target_bot.first_name} (@{target_bot.username})")
        except Exception as e:
            print(f"⚠️ 连接搜索机器人失败: {e}")

        # 停止客户端
        await app.stop()

        print("\n✅ 完成！Session文件创建成功。")
        print("您现在可以运行主程序了。")
        return True

    except SessionPasswordNeeded:
        print("\n检测到两步验证，请输入您的两步验证密码：")
        # 两步验证会在 app.start() 中自动处理

    except Exception as e:
        print(f"\n❌ Session创建失败: {e}")
        print("\n可能的原因：")
        print("1. 手机号码格式错误（需要包含国家代码，如 +86xxx）")
        print("2. 验证码输入错误或超时")
        print("3. 网络连接问题")
        print("\n请重新运行脚本再试一次。")
        return False

    finally:
        try:
            await app.stop()
        except:
            pass


if __name__ == "__main__":
    print("\n启动中...")

    # 运行异步主函数
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n\n已取消操作")
    finally:
        loop.close()