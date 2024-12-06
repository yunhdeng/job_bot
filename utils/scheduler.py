import schedule
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os

class JobScheduler:
    def __init__(self, config_path: str = 'config/config.json'):
        self.config = self._load_config(config_path)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.running = False
        self.last_run = {}  # 记录每个平台上次运行时间
        
    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def start(self):
        """启动调度器"""
        self.running = True
        self.logger.info("启动定时任务调度器")
        
        # 设置定时任务
        schedule.every().day.at("09:00").do(self.run_all_platforms)  # 早上9点
        schedule.every().day.at("14:00").do(self.run_all_platforms)  # 下午2点
        
        # 运行调度循环
        while self.running:
            schedule.run_pending()
            time.sleep(60)
            
    def stop(self):
        """停止调度器"""
        self.running = False
        self.logger.info("停止定时任务调度器")
        
    async def run_platform(self, platform_name: str, platform_class):
        """运行单个平台的任务"""
        try:
            # 检查运行间隔
            if not self._check_run_interval(platform_name):
                return
                
            # 初始化平台
            platform = platform_class(self.config)
            
            # 运行任务
            if await platform.login():
                await platform.search_jobs()
                self.last_run[platform_name] = datetime.now()
                
                # 生成报告
                if hasattr(platform, 'analyzer'):
                    report = platform.analyzer.generate_report()
                    self.logger.info(f"\n{platform_name} 投递报告:\n{report}")
            else:
                self.logger.error(f"{platform_name} 登录失败")
                
        except Exception as e:
            self.logger.error(f"{platform_name} 任务执行失败: {str(e)}")
            
    def _check_run_interval(self, platform_name: str) -> bool:
        """检查是否满足运行间隔要求"""
        if platform_name not in self.last_run:
            return True
            
        last_time = self.last_run[platform_name]
        interval = timedelta(hours=self.config['scheduler']['min_interval_hours'])
        
        if datetime.now() - last_time < interval:
            self.logger.info(f"{platform_name} 运行间隔不足 {interval.total_seconds()/3600} 小时")
            return False
            
        return True
        
    async def run_all_platforms(self):
        """运行所有平台的任务"""
        self.logger.info("开始运行所有平台任务")
        
        # 导入平台类
        from platforms.boss import BossBot
        from platforms.liepin import LiepinBot
        from platforms.zhilian import ZhilianBot
        
        # 创建任务列表
        tasks = []
        platform_map = {
            'boss': BossBot,
            'liepin': LiepinBot,
            'zhilian': ZhilianBot
        }
        
        # 添加启用的平台任务
        for name, cls in platform_map.items():
            if self.config['platforms'][name]['enabled']:
                tasks.append(self.run_platform(name, cls))
                
        # 并行运行所有任务
        await asyncio.gather(*tasks)
        
        self.logger.info("所有平台任务完成")
        
    def run_forever(self):
        """在主线程中运行调度器"""
        try:
            self.start()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            self.logger.error(f"调度器运行异常: {str(e)}")
            self.stop() 