import openai
import json
from typing import Dict, List, Optional
import os
from datetime import datetime
import logging
from enum import Enum
import httpx

class ModelProvider(Enum):
    """AI模型提供商"""
    OPENAI = "openai"
    SILICONFLOW = "siliconflow"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"

class AIService:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 从配置中获取API设置
        self.api_settings = self.config['ai'].get('api', {})
        self.provider = ModelProvider(self.api_settings.get('provider', 'siliconflow'))
        
        # 设置API配置
        self._setup_api()
        
    def _setup_api(self):
        """设置API配置"""
        try:
            # 获取API密钥
            if self.provider == ModelProvider.SILICONFLOW:
                self.api_key = os.getenv('SILICON_API_KEY') or self.api_settings.get('api_key')
                self.api_base = self.api_settings.get('api_base', "https://api.siliconflow.com/v1")
                # 根据文档支持的模型列表
                self.model = self.api_settings.get('model', 'Qwen/Qwen2.5-72B-Instruct')
            elif self.provider == ModelProvider.OPENAI:
                self.api_key = os.getenv('OPENAI_API_KEY') or self.api_settings.get('api_key')
                self.api_base = self.api_settings.get('api_base', "https://api.openai.com/v1")
                self.model = self.api_settings.get('model', 'gpt-3.5-turbo')
            elif self.provider == ModelProvider.ANTHROPIC:
                self.api_key = os.getenv('ANTHROPIC_API_KEY') or self.api_settings.get('api_key')
                self.api_base = self.api_settings.get('api_base', "https://api.anthropic.com/v1")
                self.model = self.api_settings.get('model', 'claude-2')
            elif self.provider == ModelProvider.CUSTOM:
                self.api_key = os.getenv('CUSTOM_API_KEY') or self.api_settings.get('api_key')
                self.api_base = self.api_settings.get('api_base')
                self.model = self.api_settings.get('model')
                
            if not self.api_key:
                raise ValueError(f"未设置 {self.provider.value} 的API密钥")
            if not self.api_base:
                raise ValueError(f"未设置 {self.provider.value} 的API地址")
            if not self.model:
                raise ValueError(f"未设置 {self.provider.value} 的模型名称")
                
            # 配置API客户端
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                http_client=httpx.AsyncClient(
                    verify=False,  # 禁用SSL验证
                    timeout=30.0   # 设置超时时间
                )
            )
            
            self.logger.info(f"已配置 {self.provider.value} API")
            
        except Exception as e:
            self.logger.error(f"API配置失败: {str(e)}")
            raise
            
    async def chat_completion(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """通用的AI对话接口"""
        try:
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # 打印请求信息
            self.logger.debug(f"API请求信息:")
            self.logger.debug(f"URL: {self.api_base}")
            self.logger.debug(f"Model: {self.model}")
            self.logger.debug(f"Messages: {messages}")
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.config['ai']['settings'].get('temperature', 0.7),
                    max_tokens=self.config['ai']['settings'].get('max_tokens', 1000),
                    top_p=self.config['ai']['settings'].get('top_p', 0.7),
                    frequency_penalty=self.config['ai']['settings'].get('frequency_penalty', 0.5)
                )
                return response.choices[0].message.content
                
            except openai.APIConnectionError as e:
                self.logger.error(f"API连接错误: {str(e)}")
                raise
            except openai.APIError as e:
                self.logger.error(f"API错误: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"未知错误: {str(e)}")
                raise
                
        except Exception as e:
            self.logger.error(f"API请求失败: {str(e)}")
            raise
            
    async def analyze_job_match(self, job: Dict, resume: Dict) -> Dict:
        """分析职位与简历的匹配度"""
        prompt = f"""
作为一位资深HR和职业顾问，请详细分析这个职位与求职者的匹配程度：

职位详细信息：
1. 职位名称：{job['job_name']}
2. 公司信息：{job['company_name']}（规模：{job.get('company_size', '未知')}）
3. 地点要求：{job['city']}
4. 薪资范围：{job['salary']}
5. 工作年：{job.get('work_year', '不限')}
6. 学历要求：{job.get('education', '不限')}
7. 技能要求：{', '.join(job.get('job_tags', []))}
8. 职位描述：{job.get('job_desc', '')}

求职者背景：
{self.config['ai']['introduce']}

请从以下维度进行分析：
1. 技能匹配度(0-100)：技术栈、工具、平台的匹配程度
2. 经验匹配度(0-100)：工作年限、项目经验的匹配程度
3. 行业匹配度(0-100)：行业背景、业务领域的匹配程度
4. 职业发展(0-100)：职位对职业成长的帮助程度
5. 综合评分(0-100)：总体匹配程度

并提供：
1. 最突出的3个优势
2. 最主要的3个不足
3. 3-5条具体的改进建议
4. 是否建议投递的结论和理由

请以JSON格式返回结果。
"""
        try:
            response = await self.chat_completion(prompt, "你是一位专业的HR顾问。")
            return json.loads(response)
        except Exception as e:
            self.logger.error(f"职位分析失败: {str(e)}")
            return {
                "match_score": 0,
                "advantages": [],
                "disadvantages": [],
                "suggestions": []
            }
            
    async def generate_greeting(self, job: Dict) -> str:
        """生成个性化打招呼语"""
        prompt = f"""
请基于以下信息，生成一个个性化的专业打招呼语：

职位信息：
- 职位名称：{job['job_name']}
- 公司名称：{job['company_name']}
- 公司规模：{job.get('company_size', '未知')}
- 融资阶段：{job.get('company_stage', '未知')}
- 工作城市：{job['city']}
- 技术要求：{', '.join(job.get('job_tags', []))}

我的背景：
{self.config['ai']['introduce']}

要求：
1. 个性化定制，避免模板化
2. 突出与职位的匹配点
3. 展现对公司的了解
4. 表达真诚的求职意愿
5. 字数控制在50-100字
6. 语气专业且友好
7. 可以适当展示自己的优势，但不要过度自夸
"""
        try:
            response = await self.chat_completion(
                prompt,
                "你是一位专业的求职顾问，帮助生成合适的打招呼语。"
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"生成打招呼语失败: {str(e)}")
            return self.config['platforms']['boss']['default_greeting']
            
    async def extract_job_keywords(self, job_desc: str) -> Dict:
        """提取职位关键词并分析"""
        prompt = f"""
请分析这个职位描述，提取并分类关键信息：

职位描述：
{job_desc}

请提取以下类别的键词：
1. 技术栈：编程语言、框架、工具等
2. 软技能：沟通能力、团队协作等
3. 业务领域：所属行业、业务方向等
4. 加分项：优先考虑��经验或技能
5. 职责重点：工作中最重要的部分

请以JSON格式返回结果。
"""
        try:
            response = await self.chat_completion(
                prompt,
                "你是一位专业的HR顾问，帮助提取职位关键词。"
            )
            return json.loads(response)
        except Exception as e:
            self.logger.error(f"提取关键词失败: {str(e)}")
            return {}