from typing import Dict, List

class ResumeAnalyzer:
    def __init__(self, config):
        self.config = config
        self.ai_service = AIService(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def analyze_online_resume(self, resume_url: str) -> Dict:
        """分析在线简历"""
        try:
            # 1. 获取简历内容
            resume_content = await self._fetch_resume_content(resume_url)
            
            # 2. AI分析简历
            analysis = await self._analyze_resume(resume_content)
            
            # 3. 生成推荐配置
            config = self._generate_config(analysis)
            
            return {
                "analysis": analysis,
                "recommended_config": config
            }
            
        except Exception as e:
            self.logger.error(f"简历分析失败: {str(e)}")
            return None
            
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _fetch_resume_content(self, url: str) -> Dict:
        """带重试机制的简历获取"""
        try:
            if "zhipin.com" in url:
                return await self._fetch_boss_resume(url)
            raise ValueError("暂不支持该平台")
        except Exception as e:
            self.logger.error(f"获取简历失败: {str(e)}")
            raise
        
    async def _fetch_boss_resume(self, url: str) -> Dict:
        """获取BOSS直聘简历内容"""
        try:
            # 1. 获取用户的Cookie
            cookies_file = self.config['platforms']['boss']['cookies_file']
            if not os.path.exists(cookies_file):
                raise ValueError(f"Cookie文件不存在: {cookies_file}")
            
            with open(cookies_file, 'r') as f:
                cookies_str = f.read().strip()
                if not cookies_str:
                    raise ValueError("Cookie文件为空")
                
            # 2. 解析Cookie
            cookies = {}
            for item in cookies_str.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value

            # 3. 构建API请求
            api_url = "https://www.zhipin.com/wapi/zpgeek/resume/attachment/preview.json"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.zhipin.com/web/geek/resume'
            }
            
            # 4. 发送请求获取简历数据
            async with aiohttp.ClientSession(cookies=cookies) as session:
                # 先访问简历页面获取必要的token等信息
                await session.get('https://www.zhipin.com/web/geek/resume', headers=headers)
                
                # 然后请求简历数据
                async with session.get(api_url, headers=headers) as response:
                    data = await response.json()
                    if data['code'] != 0:
                        raise ValueError(f"获取简历失败: {data.get('message')}")
                        
                    resume_data = data['zpData']['resume']
                    return self._parse_resume_data(resume_data)
                    
        except Exception as e:
            self.logger.error(f"获取BOSS直聘简历失败: {str(e)}")
            raise
        
    def _parse_resume_data(self, resume_data: Dict) -> Dict:
        """解析简历数据"""
        return {
            "basic_info": {
                "name": resume_data['name'],
                "gender": resume_data['gender'],
                "age": resume_data['age'],
                "education": resume_data['education'],
                "work_years": resume_data['workYears']
            },
            "work_experience": [
                {
                    "company": exp['company'],
                    "position": exp['position'],
                    "duration": exp['duration'],
                    "description": exp['description']
                }
                for exp in resume_data.get('workExperience', [])
            ],
            "project_experience": [
                {
                    "name": proj['name'],
                    "role": proj['role'],
                    "description": proj['description'],
                    "technologies": proj['technologies']
                }
                for proj in resume_data.get('projectExperience', [])
            ],
            "skills": resume_data.get('skills', []),
            "education_experience": [
                {
                    "school": edu['school'],
                    "major": edu['major'],
                    "degree": edu['degree'],
                    "duration": edu['duration']
                }
                for edu in resume_data.get('educationExperience', [])
            ]
        }
        
    async def _analyze_resume(self, resume: Dict) -> Dict:
        """AI分析简历"""
        prompt = f"""
作为一位资深HR和职业顾问，请分析这份简历并提供以下信息：

简历内容：
{json.dumps(resume, ensure_ascii=False, indent=2)}

请提供：
1. 技能评估
   - 核心技能
   - 技能熟练度
   - 技术栈匹配建议

2. 经验分析
   - 工作年限
   - 项目经验
   - 行业背景

3. 求职偏好推断
   - 适合的职位类型
   - 建议的工作市
   - 合理的薪资范围
   - 匹配的行业方向

4. 简历优化建议
   - 内容完整性
   - 亮点提升
   - 不足改进

请以结构化JSON格式返回。
"""
        response = await self.ai_service.chat_completion(prompt)
        return json.loads(response)
        
    def _generate_config(self, analysis: Dict) -> Dict:
        """根据分析结果生成推荐配置"""
        return {
            "job_preferences": {
                "keywords": analysis["suitable_positions"],
                "cities": analysis["recommended_cities"],
                "expected_salary": analysis["salary_range"],
                "education": analysis["education_level"],
                "max_work_year": analysis["work_years"] + 2,  # 高于当前经验
                "excluded_industries": [],  # 用户可以手动设置
                "blacklist": {
                    "companies": [],
                    "recruiters": ["猎头"],  # 默认过滤猎头
                    "keywords": ["外包", "外派"]  # 默认过滤外包
                }
            },
            "ai": {
                "introduce": self._generate_introduction(analysis),
                "settings": {
                    "min_match_score": 60,
                    "model": "gpt-3.5-turbo"
                },
                "weights": {
                    "skill_match": 0.4,
                    "experience_match": 0.3,
                    "industry_match": 0.2,
                    "career_growth": 0.1
                }
            }
        }
        
    def _generate_introduction(self, analysis: Dict) -> str:
        """生成个人介绍"""
        return f"""我是一名{analysis['work_years']}年经验的{analysis['position_type']}开发工程师，
熟练使用{', '.join(analysis['core_skills'])}等技术栈，
擅长{', '.join(analysis['expertise'])}，
具备{analysis['industry_background']}行业经验。
{analysis['highlight']}""" 
        
    def _extract_resume_id(self, url: str) -> str:
        """从URL中提取简历ID"""
        try:
            # 处理不同格式的URL
            if '/resume/detail' in url:
                return url.split('/')[-1].split('.')[0]
            elif 'resumeId=' in url:
                return url.split('resumeId=')[1].split('&')[0]
            else:
                raise ValueError("无效的简历URL格式")
        except Exception as e:
            raise ValueError(f"解析简历URL失败: {str(e)}") 