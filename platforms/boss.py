from .base import BasePlatform
import json
from typing import Dict, List
import time
from utils.analyzer import JobAnalyzer
import os
from datetime import datetime, timedelta
import requests

class BossBot(BasePlatform):
    def __init__(self, config):
        super().__init__(config)
        self.analyzer = JobAnalyzer()
        self.ai_service = AIService(config)
        self.notifier = JobNotifier(config)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.zhipin.com/'
        }
        
    def login(self) -> bool:
        """使用Cookie登录"""
        try:
            cookies_file = self.config['platforms']['boss']['cookies_file']
            if not os.path.exists(cookies_file):
                self.logger.error(f"Cookie文件不存在: {cookies_file}")
                return False
            
            with open(cookies_file, 'r') as f:
                cookies_str = f.read().strip()
                if not cookies_str:
                    self.logger.error("Cookie文件为空")
                    return False
                    
                # 将cookies字符串转换为字典
                cookies = {}
                for item in cookies_str.split(';'):
                    if '=' in item:
                        key, value = item.strip().split('=', 1)
                        cookies[key] = value
                    
                self.session.cookies.update(cookies)
                
                # 验证登录状态
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
            # 先访问首页获取必要的cookies
            self.session.get('https://www.zhipin.com/', headers=self.headers)
            
            # 检查登录状态
            response = self.session.get(
                'https://www.zhipin.com/wapi/zpgeek/common/data/getGeekInfo',
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code != 200:
                self.logger.error(f"登录检查请求失败: HTTP {response.status_code}")
                return False
            
            data = response.json()
            if data.get('code') == 0 and data.get('zpData'):
                return True
            
            self.logger.error(f"登录检查失败: {data.get('message', '未知错误')}")
            return False
            
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {str(e)}")
            return False
            
    def search_jobs(self):
        """搜索职位"""
        total_delivered = 0
        max_jobs = self.config['platforms']['boss'].get('max_jobs', 100)  # 最大投递数量
        
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
                            self.logger.info(f"{city} 的 {keyword} 职位搜索完成")
                            break
                            
                        for job in jobs:
                            if self._should_skip_job(job):
                                self.logger.debug(f"跳过职位: {job['job_name']} - {job['company_name']}")
                                continue
                                
                            if self._deliver_job(job):
                                total_delivered += 1
                                self.analyzer.add_job(job)
                                
                            if total_delivered >= max_jobs:
                                self.logger.info(f"达到最大投递数量: {max_jobs}")
                                break
                                
                            # 投递间隔
                            self.random_sleep(5, 8)
                            
                        page += 1
                        retry_count = 0  # 重置重试计数
                        self.random_sleep(3, 5)  # 翻页间隔
                        
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            self.logger.error(f"搜索失败次数过多，跳过当前搜索: {str(e)}")
                            break
                        self.logger.warning(f"搜索失败，第 {retry_count} 次重试: {str(e)}")
                        self.random_sleep(10, 15)  # 失败后等待更长时间
                        
        # 保存投递记录
        self.analyzer.save_records()
        self.logger.info(f"总计投递: {total_delivered} 个职位")
        
    def _fetch_jobs(self, keyword: str, city: str, page: int) -> List[Dict]:
        """获取职位列表"""
        url = 'https://www.zhipin.com/wapi/zpgeek/search/joblist.json'
        params = {
            'query': keyword,
            'city': city,
            'page': page,
            'pageSize': 30
        }
        
        try:
            response = self.session.get(url, params=params, headers=self.headers)
            data = response.json()
            if data['code'] == 0 and 'zpData' in data:
                return self._parse_jobs(data['zpData']['jobList'])
        except Exception as e:
            self.logger.error(f"获取职位列表失败: {str(e)}")
            
        return []
        
    def _parse_jobs(self, jobs_data: List[Dict]) -> List[Dict]:
        """解析职位数据"""
        jobs = []
        for item in jobs_data:
            try:
                # 必需字段检查
                required_fields = ['encryptJobId', 'jobName', 'cityName', 'salaryDesc']
                if not all(field in item for field in required_fields):
                    self.logger.warning(f"职位数据缺失必要字段: {item}")
                    continue
                    
                job = {
                    'job_id': item['encryptJobId'],
                    'job_name': item['jobName'],
                    'company_name': item.get('brandName') or item.get('brandComName', '未知公司'),
                    'salary': item['salaryDesc'],
                    'city': item['cityName'],
                    'recruiter': item.get('bossName', ''),
                    'company_size': item.get('companySize', ''),
                    'company_stage': item.get('stageName', ''),
                    'work_year': item.get('jobExperience', ''),
                    'education': item.get('jobDegree', ''),
                    'job_tags': item.get('jobLabels', []),
                    'job_desc': item.get('jobDesc', ''),
                    'address': item.get('jobAddress', {}),
                    'update_time': item.get('updateTime', ''),
                    'salary_min': 0,
                    'salary_max': 0
                }
                
                # 解析薪资
                min_salary, max_salary = self._parse_salary(item['salaryDesc'])
                job['salary_min'] = min_salary
                job['salary_max'] = max_salary
                
                # 添加额外的过滤条件
                if self._check_job_requirements(job):
                    jobs.append(job)
                    
            except Exception as e:
                self.logger.error(f"解析职位数据失败: {str(e)}")
                
        return jobs
        
    async def _deliver_job(self, job: Dict) -> bool:
        """投递职位"""
        # 先进行AI匹配度分析
        if self.config.get('enable_ai', True):
            try:
                analysis = await self.ai_service.analyze_job_match(job, self.config['resume'])
                if analysis['match_score'] < self.config.get('min_match_score', 60):
                    self.logger.info(f"匹配度过低({analysis['match_score']}分)，跳过投递: {job['job_name']}")
                    return False
                    
                # 保存分析结果
                job['ai_analysis'] = analysis
                
            except Exception as e:
                self.logger.error(f"AI分析失败: {str(e)}")
        
        # 检查投递限制
        if not self._check_delivery_limit():
            return False
        
        # 使用 AI 生成打招呼语
        if self.config.get('enable_ai', False):
            try:
                greeting = await self.ai_service.generate_greeting(job)
            except Exception as e:
                self.logger.error(f"AI生成打招呼语失败: {str(e)}")
                greeting = self.config['platforms']['boss']['default_greeting']
        else:
            greeting = self.config['platforms']['boss']['default_greeting']
        
        # 格式化打招呼语
        greeting = greeting.format(
            company_name=job['company_name'],
            job_name=job['job_name']
        )
        
        # 构建完整的投递URL
        url = 'https://www.zhipin.com/wapi/zpgeek/job/start.json'
        
        # 准备投递数据
        data = {
            'jobId': job['job_id'],
            'greeting': greeting,
            'lid': job.get('lid', ''),  # 可选参数
            'source': 1,  # 来源：1-搜索，2-推等
        }
        
        # 添加必要的请求头
        deliver_headers = {
            **self.headers,
            'Origin': 'https://www.zhipin.com',
            'Content-Type': 'application/json;charset=UTF-8'
        }
        
        max_retries = self.config['global']['max_retries']
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = await self.session.post(
                    url,
                    json=data,
                    headers=deliver_headers,
                    timeout=10
                )
                
                result = response.json()
                
                if result['code'] == 0:
                    self.logger.info(f"投递成功: {job['job_name']} - {job['company_name']}")
                    return True
                elif result['code'] == 1:  # 已经投递过
                    self.logger.info(f"已经投递过: {job['job_name']} - {job['company_name']}")
                    return False
                else:
                    error_msg = result.get('message', '未知错误')
                    self.logger.warning(f"投递失败: {error_msg}")
                    
                    if '频繁' in error_msg:
                        self.random_sleep(60, 120)  # 频繁操作时等更长时间
                    elif 'cookie' in error_msg.lower():
                        self.logger.error("Cookie已失效")
                        return False
                        
                    retry_count += 1
                    self.random_sleep(5, 10)
                    
            except Exception as e:
                self.logger.error(f"投递请求失败: {str(e)}")
                retry_count += 1
                self.random_sleep(5, 10)
                
        return False

    def _check_job_requirements(self, job: Dict) -> bool:
        """检查职位是否满足要求"""
        # 检查工作年限
        if job['work_year'] and '应届' not in job['work_year']:
            try:
                min_year = int(job['work_year'].split('-')[0])
                if min_year > self.config['job_preferences']['max_work_year']:
                    return False
            except:
                pass
                
        # 检查学历要求
        if job['education']:
            education_level = {
                '博士': 5, '硕士': 4, '本科': 3, '大专': 2, '高中': 1
            }
            required_level = education_level.get(job['education'], 0)
            my_level = education_level.get(
                self.config['job_preferences']['education'],
                3
            )
            if required_level > my_level:
                return False
                
        return True

    def _check_delivery_limit(self) -> bool:
        """检查投递限制"""
        today = datetime.now().strftime('%Y%m%d')
        records_file = f'data/job_records_{today}.json'
        
        try:
            if os.path.exists(records_file):
                with open(records_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    
                # 检查每日限制
                if len(records) >= self.config['global']['max_jobs_per_day']:
                    self.logger.warning(f"已达到每日投递限制: {self.config['global']['max_jobs_per_day']}")
                    return False
                    
                # 检查每小时限制
                now = datetime.now()
                hour_ago = now - timedelta(hours=1)
                hour_count = sum(
                    1 for r in records 
                    if datetime.fromisoformat(r['timestamp']) > hour_ago
                )
                
                hourly_limit = 20  # 每小时限制
                if hour_count >= hourly_limit:
                    self.logger.warning(f"已达到每小时投递限制: {hourly_limit}")
                    return False
                    
            return True
        except Exception as e:
            self.logger.error(f"检查投递限制失败: {str(e)}")
            return False

    def _request_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """带重试的请求"""
        max_retries = self.config['global']['max_retries']
        retry_delay = self.config['global']['retry_delay']
        
        for i in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    raise CookieExpiredException("Cookie已失效")
            except Exception as e:
                if i == max_retries - 1:
                    raise
                self.logger.warning(f"请求失败，第{i+1}次重试: {str(e)}")
                time.sleep(retry_delay)

    def _should_skip_job(self, job: Dict) -> bool:
        """检查是否应该跳过该职位"""
        # 1. 黑名单过滤
        if job['company_name'] in self.blacklist['companies']:
            return True
        
        # 2. 关键词过滤
        for keyword in self.blacklist['keywords']:
            if (keyword in job['job_name'].lower() or 
                keyword in job.get('job_desc', '').lower()):
                return True
                
        # 3. 招聘者过滤
        if any(k in job.get('recruiter', '') for k in self.blacklist['recruiters']):
            return True
        
        # 4. 行业过滤
        if job.get('industry') in self.config['job_preferences'].get('excluded_industries', []):
            return True
        
        # 5. 薪资过滤
        min_salary, max_salary = self._parse_salary(job['salary'])
        expected_range = self.config['job_preferences']['expected_salary']
        if not (expected_range[0] <= max_salary and min_salary <= expected_range[1]):
            return True
        
        return False

    def _check_job_quality(self, job: Dict) -> bool:
        """检查职位质量"""
        # 1. 检查HR活跃度
        if self.config['boss'].get('filterDeadHR', True):
            if not self._check_hr_active(job.get('recruiter', '')):
                return False
            
        # 2. 检查公司规模
        if job.get('company_size') == '少于15人':
            return False
        
        # 3. 检查更新时间
        if job.get('update_time'):
            try:
                update_time = datetime.fromisoformat(job['update_time'])
                if (datetime.now() - update_time).days > 7:
                    return False
            except:
                pass
            
        return True

    def _check_hr_active(self, recruiter: str) -> bool:
        """检查HR是否活跃"""
        try:
            url = f"https://www.zhipin.com/wapi/zpgeek/boss/info/get.json"
            response = self.session.get(url, headers=self.headers)
            data = response.json()
            
            if data['code'] == 0:
                last_active = data['zpData'].get('activeTimeDesc', '')
                if '半年前' in last_active or '一年前' in last_active:
                    return False
        except Exception as e:
            self.logger.error(f"检查HR活跃度失败: {str(e)}")
            
        return True

    async def _handle_delivery_result(self, job: Dict, success: bool):
        """处理投递结果"""
        # 1. 保存记录
        self.analyzer.add_job(job)
        
        # 2. 发送通知
        await self.notifier.notify_delivery(job, success)
        
        # 3. 更新黑名单
        if not success and job.get('company_name'):
            self._update_blacklist(job['company_name'])