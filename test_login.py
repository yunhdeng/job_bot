import asyncio
from utils.login import BossLogin

async def test_login():
    login = BossLogin()
    print("开始登录测试...")
    cookies = await login.login()
    if cookies:
        print("登录成功！Cookie已保存")
    else:
        print("登录失败")

if __name__ == "__main__":
    asyncio.run(test_login()) 