from playwright.async_api import async_playwright
import asyncio
import json
import os
import logging
from typing import Dict, Optional
import qrcode
import io
from aiohttp import web
import qrcode_terminal  # 添加导入

class BossLogin:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def login(self) -> Optional[Dict]:
        """登录BOSS直聘"""
        browser = None
        try:
            # 1. 尝试使用已保存的Cookie
            if os.path.exists('cookies/boss_cookies.txt'):
                if await self.validate_cookies():
                    return self.load_cookies()
            
            # 2. 选择登录方式
            print("\n请选择登录方式:")
            print("1. 扫码登录(终端显示二维码)")
            print("2. 粘贴已有Cookie")
            
            choice = input("请选择(1-2): ").strip()
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # 访问登录页
                await page.goto('https://www.zhipin.com/web/user/?ka=header-login')
                
                if choice == "1":
                    await self._handle_qr_login(page)
                else:
                    return await self._handle_cookie_input()
                
                # 等待登录成功
                try:
                    await page.wait_for_selector('.user-nav', timeout=120000)
                    self.logger.info("登录成功")
                    
                    # 获取并保存cookies
                    cookies = await context.cookies()
                    cookies_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
                    os.makedirs('cookies', exist_ok=True)
                    with open('cookies/boss_cookies.txt', 'w') as f:
                        f.write(cookies_str)
                    
                    self.logger.info("Cookie已保存")
                    return cookies
                    
                except KeyboardInterrupt:
                    print("\n已取消登录")
                    return None
                except Exception as e:
                    self.logger.error(f"登录超时或失败: {str(e)}")
                    return None
                
        except KeyboardInterrupt:
            print("\n已取消登录")
            return None
        except Exception as e:
            self.logger.error(f"登录过程出错: {str(e)}")
            return None
        finally:
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            
    async def _handle_qr_login(self, page):
        """处理二维码登录"""
        try:
            print("正在加载二维码...")
            
            # 等待页面加载完成
            await page.wait_for_load_state('networkidle')
            await page.wait_for_load_state('domcontentloaded')
            
            # 确保在扫码登录模式
            ewm_switch = await page.wait_for_selector('.ewm-switch', timeout=5000)
            if ewm_switch:
                await ewm_switch.click()
                await asyncio.sleep(1)
            
            # 等待扫码界面加载
            await page.wait_for_selector('.scan-app-wrapper', timeout=30000)
            
            # 获取二维码内容
            qr_content = await page.evaluate('''
                () => {
                    const qrElement = document.querySelector('.qr-img-box img');
                    if (!qrElement) return null;
                    
                    // 获取二维码图片的src
                    const imgSrc = qrElement.getAttribute('src');
                    if (!imgSrc) return null;
                    
                    // 从URL中提取content参数
                    const match = imgSrc.match(/content=([^&]+)/);
                    if (!match) return null;
                    
                    // 解码content参数
                    return decodeURIComponent(match[1]);
                }
            ''')
            
            if not qr_content:
                raise Exception("无法获取二维码内容")
            
            print("\n============= BOSS直聘扫码登录 =============")
            print("\n[方式1] 扫描终端二维码:\n")
            
            try:
                # 使用qrcode-terminal渲染
                qrcode_terminal.draw(qr_content)  # 移除 small=True 参数
            except Exception as e:
                # 使用备选渲染方案
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=1,
                    border=1,
                )
                qr.add_data(qr_content)
                qr.make(fit=True)
                
                # 使用原来的渲染方式
                matrix = qr.get_matrix()
                for row in matrix:
                    line = ""
                    for cell in row:
                        if cell:
                            line += "██"  # 使用两个实心方块表示黑色模块
                        else:
                            line += "  "  # 使用两个空格表示白色模块
                    print(line)
            
            print("\n============= 等待扫码登录 =============")
            
            # 等待登录成功
            try:
                await page.wait_for_selector('.user-nav', timeout=120000)
                print("扫码登录成功！")
            except KeyboardInterrupt:
                print("\n已取消登录")
                return
            except Exception as e:
                print(f"登录失败: {str(e)}")
                return
            
        except Exception as e:
            self.logger.error(f"二维码处理失败: {str(e)}")
            raise

    async def _handle_cookie_input(self) -> Optional[Dict]:
        """处理手动输入Cookie"""
        print("\n请粘贴完整的Cookie字符串:")
        cookies_str = input().strip()
        
        if not cookies_str:
            self.logger.error("Cookie不能为空")
            return None
            
        try:
            # 解析Cookie字符串
            cookies = {}
            for item in cookies_str.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value
                    
            # 保存Cookie
            os.makedirs('cookies', exist_ok=True)
            with open('cookies/boss_cookies.txt', 'w') as f:
                f.write(cookies_str)
                
            self.logger.info("Cookie已保存")
            return cookies
            
        except Exception as e:
            self.logger.error(f"Cookie解析失败: {str(e)}")
            return None
            
    async def validate_cookies(self) -> bool:
        """验证Cookie是否有效"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                # 加载Cookie
                with open('cookies/boss_cookies.txt', 'r') as f:
                    cookies_str = f.read().strip()
                    
                cookies = {}
                for item in cookies_str.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookies[key] = value
                        
                # 设置Cookie
                await context.add_cookies([{
                    'name': k,
                    'value': v,
                    'domain': '.zhipin.com',
                    'path': '/'
                } for k, v in cookies.items()])
                
                # 测试访问
                page = await context.new_page()
                await page.goto('https://www.zhipin.com/web/geek/recommend')
                
                # 检查是否需要登录
                login_button = await page.query_selector('text=登录')
                return login_button is None
                
        except Exception as e:
            self.logger.error(f"Cookie验证失败: {str(e)}")
            return False
            
    def load_cookies(self) -> Dict:
        """加载已保存的Cookie"""
        with open('cookies/boss_cookies.txt', 'r') as f:
            cookies_str = f.read().strip()
            
        cookies = {}
        for item in cookies_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
                
        return cookies 