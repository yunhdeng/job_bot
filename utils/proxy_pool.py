import requests
import json
import time
import random
from typing import Dict, List, Optional
import threading
from queue import Queue
import logging

class ProxyPool:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger('ProxyPool')
        self.proxies = Queue()
        self.valid_proxies = []
        self.check_interval = config.get('proxy_check_interval', 300)  # 5分钟检查一次
        self._start_checker()
        
    def get_proxy(self) -> Optional[Dict]:
        """获取一个可用代理"""
        if self.proxies.empty():
            self._refresh_proxies()
            
        try:
            return self.proxies.get_nowait()
        except:
            return None
            
    def report_proxy_status(self, proxy: Dict, success: bool):
        """报告代理使用状态"""
        if not success and proxy in self.valid_proxies:
            self.valid_proxies.remove(proxy)
            self.logger.info(f"移除失效代理: {proxy['host']}:{proxy['port']}")
            
    def _refresh_proxies(self):
        """刷新代理池"""
        # 1. 从配置文件获取代理
        if self.config.get('proxy_list'):
            self._add_proxies(self.config['proxy_list'])
            
        # 2. 从代理API获取
        if self.config.get('proxy_api', {}).get('enabled'):
            self._fetch_from_api()
            
        # 3. 验证代理可用性
        self._verify_proxies()
        
    def _add_proxies(self, proxy_list: List[Dict]):
        """添加代理到队列"""
        for proxy in proxy_list:
            if self._verify_proxy(proxy):
                self.proxies.put(proxy)
                if proxy not in self.valid_proxies:
                    self.valid_proxies.append(proxy)
                    
    def _fetch_from_api(self):
        """从API获取代理"""
        api_config = self.config['proxy_api']
        try:
            response = requests.get(
                api_config['url'],
                headers={'Authorization': api_config['api_key']},
                timeout=10
            )
            if response.status_code == 200:
                proxies = response.json()
                self._add_proxies(proxies)
        except Exception as e:
            self.logger.error(f"从API获取代理失败: {str(e)}")
            
    def _verify_proxy(self, proxy: Dict) -> bool:
        """验证单个代理"""
        test_urls = [
            'https://www.baidu.com',
            'https://www.zhipin.com',
            'https://www.liepin.com'
        ]
        
        proxy_url = f"http://{proxy['host']}:{proxy['port']}"
        if proxy.get('username'):
            proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
            
        proxy_dict = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        for url in test_urls:
            try:
                response = requests.get(
                    url,
                    proxies=proxy_dict,
                    timeout=5,
                    verify=False
                )
                if response.status_code != 200:
                    return False
            except:
                return False
                
        return True
        
    def _verify_proxies(self):
        """验证所有代理"""
        valid_proxies = []
        while not self.proxies.empty():
            try:
                proxy = self.proxies.get_nowait()
                if self._verify_proxy(proxy):
                    valid_proxies.append(proxy)
            except:
                continue
                
        # 重新加入验证通过的代理
        for proxy in valid_proxies:
            self.proxies.put(proxy)
            
    def _start_checker(self):
        """启动代理检查线程"""
        def check_loop():
            while True:
                time.sleep(self.check_interval)
                self._refresh_proxies()
                
        thread = threading.Thread(target=check_loop, daemon=True)
        thread.start() 