from .base import BasePlatform
import json
from typing import Dict, List
import time
from utils.analyzer import JobAnalyzer
import os
from datetime import datetime, timedelta

class ZhilianBot(BasePlatform):
    def __init__(self, config):
        super().__init__(config)
        self.analyzer = JobAnalyzer()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.zhaopin.com',
            'Referer': 'https://www.zhaopin.com/'
        }
        
    def login(self) -> bool:
        """使用Cookie登录"""
        try:
            cookies_file = self.config['platforms']['zhilian']['cookies_file']
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
                'https://i.zhaopin.com/api/user/getUserInfo',
                headers=self.headers
            )
            return response.status_code == 200 and response.json().get('code') == 200
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {str(e)}")
            return False
            
    def search_jobs(self):
        """搜索职位"""
        total_delivered = 0
        max_jobs = self.config['platforms']['zhilian'].get('max_jobs', 100)
        
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
        url = 'https://fe-api.zhaopin.com/c/i/sou'
        params = {
            'pageSize': 30,
            'cityId': city,
            'kw': keyword,
            'page': page
        }
        
        try:
            response = self.session.get(url, params=params, headers=self.headers)
            data = response.json()
            if data['code'] == 200:
                return self._parse_jobs(data['data']['results'])
        except Exception as e:
            self.logger.error(f"获取职位列表失败: {str(e)}")
            
        return []
        
    def _parse_jobs(self, jobs_data: List[Dict]) -> List[Dict]:
        """解析职位数据"""
        jobs = []
        for item in jobs_data:
            try:
                job = {
                    'job_id': item['number'],
                    'job_name': item['jobName'],
                    'company_name': item['company']['name'],
                    'salary': item['salary'],
                    'city': item['city']['display'],
                    'recruiter': item.get('recruiterName', ''),
                    'company_size': item['company'].get('size', {}).get('name', ''),
                    'work_year': item.get('workingExp', {}).get('name', ''),
                    'education': item.get('eduLevel', {}).get('name', ''),
                    'job_tags': [tag['name'] for tag in item.get('welfare', [])],
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
        
    def _deliver_job(self, job: Dict) -> bool:
        """投递职位"""
        if not self._check_delivery_limit():
            return False
            
        url = "https://fe-api.zhaopin.com/c/i/resume/deliver"
        data = {
            "jobNumber": job['job_id'],
            "resumeNumber": self.config['platforms']['zhilian']['resumeId']
        }
        
        try:
            response = self.session.post(url, json=data, headers=self.headers)
            result = response.json()
            
            if result['code'] == 200:
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
                    
                daily_limit = self.config['platforms']['zhilian']['delivery_limit']['daily']
                if len(records) >= daily_limit:
                    self.logger.warning(f"已达到每日投递限制: {daily_limit}")
                    return False
                    
                hourly_limit = self.config['platforms']['zhilian']['delivery_limit']['hourly']
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