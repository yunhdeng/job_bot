import json
import logging
import os
import argparse
import asyncio
from platforms.boss import BossBot
from utils.logger import setup_logger
from utils.resume_analyzer import ResumeAnalyzer
from utils.login import BossLogin

# 默认配置
default_config = {
    "global": {
        "use_proxy": True,
        "max_retries": 3,
        "retry_delay": 5,
        "log_level": "INFO"
    },
    "ai": {
        "settings": {
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 1000
        }
    }
}

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_environment():
    """检查运行环境"""
    required_dirs = ['logs', 'data', 'cookies']
    for d in required_dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            
    required_files = [
        'config/config.json',
        'config/proxy_pool.json',
        'blacklist.json'
    ]
    for f in required_files:
        if not os.path.exists(f):
            logger.error(f"缺少必要的配置文件: {f}")
            return False
            
    return True

def parse_args():
    parser = argparse.ArgumentParser(description='JobBot - 自动投递简历工具')
    parser.add_argument('--config', default='config/config.json', help='配置文件路径')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--no-proxy', action='store_true', help='禁用代理')
    return parser.parse_args()

async def init_from_resume():
    """从简历初始化配置"""
    # 1. 先检查Cookie
    cookies_file = 'cookies/boss_cookies.txt'
    if not os.path.exists(cookies_file):
        print("请先登录BOSS直聘并保存Cookie到:", cookies_file)
        return None
        
    # 2. 初始化BOSS直聘平台
    platform = BossBot(default_config)
    if not platform.login():
        print("登录失败,请检查Cookie是否有效")
        return None
        
    # 3. 分析简历
    analyzer = ResumeAnalyzer(default_config)
    result = await analyzer.analyze_online_resume(
        "https://www.zhipin.com/web/geek/resume"
    )
    
    if not result:
        print("简历分析失败，请使用手动配置模式")
        return None
        
    # 4. 保存推荐配置
    config_path = 'config/config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(result['recommended_config'], f, ensure_ascii=False, indent=2)
        
    print("\n=== 简历分析完成 ===")
    print("已生成推荐配置，您可以查看并修改：config/config.json")
    print("\n=== 分析结果 ===")
    print(json.dumps(result['analysis'], ensure_ascii=False, indent=2))
    
    return result['recommended_config']

async def init_from_manual_input():
    """手动输入简历信息"""
    print("请输入您的简历信息:")
    
    resume = {
        "basic_info": {
            "name": input("姓名: ").strip(),
            "education": input("最高学历: ").strip(),
            "work_years": int(input("工作年限: ").strip())
        },
        "skills": input("技能(用逗号分隔): ").strip().split(','),
        "work_experience": []
    }
    
    # 工作经历
    while True:
        print("\n添加工作经历(直接回车结束):")
        company = input("公司名称: ").strip()
        if not company:
            break
            
        resume["work_experience"].append({
            "company": company,
            "position": input("职位: ").strip(),
            "duration": input("工作时间: ").strip(),
            "description": input("工作描述: ").strip()
        })
        
    # 分析简历
    analyzer = ResumeAnalyzer(default_config)
    result = await analyzer.analyze_resume(resume)
    
    return result

async def check_login():
    """检查登录状态"""
    cookies_file = 'cookies/boss_cookies.txt'
    
    # 如果Cookie文件不存在或已过期，则自动登录
    if not os.path.exists(cookies_file) or is_cookie_expired(cookies_file):
        login_handler = BossLogin()
        cookies = await login_handler.login()
        if not cookies:
            print("自动登录失败，请检查账号密码或手动处理验证码")
            return False
    return True

def is_cookie_expired(cookies_file: str) -> bool:
    """检查Cookie是否过期"""
    try:
        platform = BossBot(default_config)
        return not platform.login()
    except:
        return True

def main():
    # 检查登录状态
    if not asyncio.run(check_login()):
        return
        
    print("请选择初始化模式：")
    print("1. 从BOSS直聘在线简历导入")
    print("2. 手动输入简历信息")
    print("3. 使用配置文件(config.json)")
    
    choice = input().strip()
    config = None
    
    if choice == "1":
        config = asyncio.run(init_from_resume())
    elif choice == "2":
        config = asyncio.run(init_from_manual_input())
    else:
        config = load_config()
    
    args = parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.no_proxy:
        config['global']['use_proxy'] = False
        
    # 环境检
    if not check_environment():
        return
        
    # 设置日志
    logger = setup_logger(config['global']['log_level'])
    
    # 初始化平台
    platform = BossBot(config)
    
    # 执行任务
    try:
        if platform.login():
            platform.search_jobs()
            # 输出统计信息
            stats = platform.analyzer.get_statistics()
            logger.info(f"\n投递统计:\n{json.dumps(stats, ensure_ascii=False, indent=2)}")
        else:
            logger.error("登录失败")
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")

if __name__ == "__main__":
    main() 