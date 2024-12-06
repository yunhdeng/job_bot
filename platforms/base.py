from abc import ABC, abstractmethod
import json
import time
import random
import requests
import logging
from typing import Dict, List

class BasePlatform(ABC):
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.blacklist = self._load_blacklist()
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _load_blacklist(self):
        try:
            with open('blacklist.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "blackCompanies": [],
                "blackRecruiters": ["猎头"],
                "blackJobs": ["外包", "外派"]
            }
            
    @abstractmethod
    def login(self) -> bool:
        """平台登录"""
        pass
    
    @abstractmethod
    def search_jobs(self):
        """搜索职位"""
        pass
    
    def _should_skip_job(self, job: Dict) -> bool:
        """检查是否应该跳过该职位"""
        if job['company_name'] in self.blacklist['blackCompanies']:
            return True
            
        for keyword in self.blacklist['blackJobs']:
            if keyword in job['job_name']:
                return True
                
        min_salary, max_salary = self._parse_salary(job['salary'])
        if not (self.config['job_preferences']['expected_salary'][0] <= max_salary and 
                min_salary <= self.config['job_preferences']['expected_salary'][1]):
            return True
            
        return False
    
    def random_sleep(self, min_sec=2, max_sec=5):
        """随机延迟"""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def _parse_salary(self, salary_text: str) -> tuple[int, int]:
        """解析薪资范围
        Args:
            salary_text: 如 "15k-20k" 或 "15-20k" 或 "15K-20K"
        Returns:
            (min_salary, max_salary): 如 (15, 20)
        """
        try:
            # 统一格式
            salary = salary_text.lower().replace('k', '').replace('K', '')
            min_s, max_s = salary.split('-')
            return int(min_s), int(max_s)
        except Exception as e:
            self.logger.error(f"薪资解析失败 {salary_text}: {str(e)}")
            return 0, 0