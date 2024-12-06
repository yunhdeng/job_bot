from .base import BasePlatform
import json
from typing import Dict, List
import time
from utils.analyzer import JobAnalyzer
import os
from datetime import datetime, timedelta

class LiepinBot(BasePlatform):
    def __init__(self, config):
        super().__init__(config)
        self.analyzer = JobAnalyzer()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.liepin.com',
            'Referer': 'https://www.liepin.com/'
        }
        
    def login(self) -> bool:
        """使用Cookie登录"""
        try:
            cookies_file = self.config['platforms']['liepin']['cookies_file']
            if not os.path.exists(cookies_file):
                self.logger.error(f"Cookie文件不存在: {cookies_file}")
                return False
                
            with open(cookies_file, 'r') as f:
                cookies_str = f.read().strip()
                if not cookies_str:
                    self.logger.error("Cookie文件为空")
                    return False
                    
                cookies = {}
                for item in cookies_str.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookies[key] = value
                        
                self.session.cookies.update(cookies)
                
                if self._check_login():
                    self.logger.info("登录成功")
                    return True
                else:
                    self.logger.error("Cookie已失效，请更新")
                    return False
                    
        except Exception as e:
            self.logger.error(f"登录失败: {str(e)}")
            return False
            
    def _check_login(self) -> bool:
        """检查登录状态"""
        try:
            response = self.session.get(
                'https://www.liepin.com/api/com.liepin.usercenter.user.getUserInfo',
                headers=self.headers
            )
            return response.status_code == 200 and response.json().get('code') == 0
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {str(e)}")
            return False
            
    def search_jobs(self):
        """搜索职位"""
        total_delivered = 0
        max_jobs = self.config['platforms']['liepin'].get('max_jobs', 100)
        
        for keyword in self.config['job_preferences']['keywords']:
            for city in self.config['job_preferences']['cities']:
                page = 1
                retry_count = 0
                max_retries = self.config['global']['max_retries']
                
                while total_delivered < max_jobs:
                    try:
                        self.logger.info(f"搜索 {city} 的 {keyword} 职位，第 {page} 页")
                        jobs = self._fetch_jobs(keyword, city, page)
                        
                        if not jobs:
                            break
                            
                        for job in jobs:
                            if self._should_skip_job(job):
                                continue
                                
                            if self._deliver_job(job):
                                total_delivered += 1
                                self.analyzer.add_job(job)
                                
                            if total_delivered >= max_jobs:
                                break
                                
                            self.random_sleep(5, 8)
                            
                        page += 1
                        self.random_sleep(3, 5)
                        
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            break
                        self.random_sleep(10, 15)
                        
        self.analyzer.save_records()
        self.logger.info(f"总计投递: {total_delivered} 个职位")
        
    def _fetch_jobs(self, keyword: str, city: str, page: int) -> List[Dict]:
        """获取职位列表"""
        url = 'https://www.liepin.com/api/com.liepin.searchfront.search-for-pc'
        data = {
            "data": {
                "mainSearchPcConditionForm": {
                    "city": city,
                    "dq": city,
                    "key": keyword,
                    "currentPage": page,
                    "pageSize": 40
                }
            }
        }
        
        try:
            response = self.session.post(url, json=data, headers=self.headers)
            result = response.json()
            if result['code'] == 0:
                return self._parse_jobs(result['data']['data']['jobCardList'])
        except Exception as e:
            self.logger.error(f"获取职位列表失败: {str(e)}")
            
        return []
        
    def _parse_jobs(self, jobs_data: List[Dict]) -> List[Dict]:
        """解析职位数据"""
        jobs = []
        for item in jobs_data:
            try:
                if item.get('advertiseFlag'):  # 跳过广告职位
                    continue
                    
                job = {
                    'job_id': item['jobId'],
                    'job_name': item['jobName'],
                    'company_name': item['companyName'],
                    'salary': self._format_salary(item['salary']),
                    'city': item['cityName'],
                    'recruiter': item.get('recruiterName', ''),
                    'company_size': item.get('companySize', ''),
                    'work_year': item.get('requireWorkYears', ''),
                    'education': item.get('requireEduLevel', ''),
                    'job_tags': item.get('labels', []),
                    'timestamp': datetime.now().isoformat()
                }
                
                min_salary, max_salary = self._parse_salary(job['salary'])
                job['salary_min'] = min_salary
                job['salary_max'] = max_salary
                
                if self._check_job_requirements(job):
                    jobs.append(job)
                    
            except Exception as e:
                self.logger.error(f"解析职位数据失败: {str(e)}")
                
        return jobs
        
    def _format_salary(self, salary_info: Dict) -> str:
        """统一薪资格式为 'XXk-YYk'"""
        if isinstance(salary_info, dict):
            min_salary = salary_info.get('minSalary', 0)
            max_salary = salary_info.get('maxSalary', 0)
            return f"{min_salary}k-{max_salary}k"
        return salary_info
        
    def _deliver_job(self, job: Dict) -> bool:
        """投递职位"""
        if not self._check_delivery_limit():
            return False
            
        url = "https://www.liepin.com/api/com.liepin.delivery.client.delivery.submitDelivery"
        data = {
            "data": {
                "jobId": job['job_id'],
                "resumeId": self.config['platforms']['liepin']['resumeId'],
                "greetingContent": self._generate_greeting(job)
            }
        }
        
        try:
            response = self.session.post(url, json=data, headers=self.headers)
            result = response.json()
            
            if result['code'] == 0:
                self.logger.info(f"投递成功: {job['job_name']} - {job['company_name']}")
                return True
            else:
                self.logger.warning(f"投递失败: {result.get('message', '未知错误')}")
                return False
                
        except Exception as e:
            self.logger.error(f"投递请求失败: {str(e)}")
            return False
            
    def _check_delivery_limit(self) -> bool:
        """检查是否达到投递限制"""
        today = datetime.now().strftime('%Y%m%d')
        records_file = f'data/job_records_{today}.json'
        
        try:
            if os.path.exists(records_file):
                with open(records_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    
                daily_limit = self.config['platforms']['liepin']['delivery_limit']['daily']
                if len(records) >= daily_limit:
                    self.logger.warning(f"已达到每日投递限制: {daily_limit}")
                    return False
                    
                hourly_limit = self.config['platforms']['liepin']['delivery_limit']['hourly']
                now = datetime.now()
                hour_ago = now - timedelta(hours=1)
                
                hour_count = sum(
                    1 for r in records 
                    if datetime.fromisoformat(r['timestamp']) > hour_ago
                )
                
                if hour_count >= hourly_limit:
                    self.logger.warning(f"已达到每小时投递限制: {hourly_limit}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"检查投递限制失败: {str(e)}")
            return False