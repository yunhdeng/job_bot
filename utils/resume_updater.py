import openai
import json
import os
from datetime import datetime
import logging
from typing import Dict, List, Optional

class ResumeUpdater:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.openai_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_key:
            self.logger.error("未设置OPENAI_API_KEY环境变量")
        openai.api_key = self.openai_key
        
    async def update_resume(self, job_requirements: List[str]) -> Dict:
        """根据职位要求更新简历"""
        current_resume = self._load_resume()
        prompt = self._create_update_prompt(current_resume, job_requirements)
        
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一位专业的简历优化顾问。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            suggestions = response.choices[0].message.content
            updated_resume = await self._apply_suggestions(current_resume, suggestions)
            self._save_resume(updated_resume)
            
            return updated_resume
            
        except Exception as e:
            self.logger.error(f"更新简历失败: {str(e)}")
            return current_resume
            
    def _load_resume(self) -> Dict:
        """加载当前简历"""
        try:
            with open('data/resume.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.config['resume']
            
    def _save_resume(self, resume: Dict):
        """保存更新后的简历"""
        os.makedirs('data', exist_ok=True)
        
        # 保存当前版本
        with open('data/resume.json', 'w', encoding='utf-8') as f:
            json.dump(resume, f, ensure_ascii=False, indent=2)
            
        # 保存历史版本
        history_dir = 'data/resume_history'
        os.makedirs(history_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f'{history_dir}/resume_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(resume, f, ensure_ascii=False, indent=2)
            
    def _create_update_prompt(self, resume: Dict, requirements: List[str]) -> str:
        """创建简历更新提示词"""
        return f"""
请根据以下职位要求，优化简历内容：

当前简历：
{json.dumps(resume, ensure_ascii=False, indent=2)}

职位要求：
{json.dumps(requirements, ensure_ascii=False, indent=2)}

请提供具体的修改建议，包括：
1. 技能描述优化
2. 工作经验调整
3. 项目经验优化
4. 自我评价调整
5. 其他建议

回复格式：
技能优化:
- 原内容: xxx
- 新内容: xxx
- 原因: xxx

经验调整:
- 原内容: xxx
- 新内容: xxx
- 原因: xxx

项目优化:
- 原内容: xxx
- 新内容: xxx
- 原因: xxx

自我评价:
- 原内容: xxx
- 新内容: xxx
- 原因: xxx

其他建议:
- 建议1
- 建议2
"""

    async def _apply_suggestions(self, resume: Dict, suggestions: str) -> Dict:
        """应用AI建议更新简历"""
        try:
            # 解析AI建议
            updates = self._parse_suggestions(suggestions)
            
            # 创建新简历
            new_resume = resume.copy()
            
            # 更新技能描述
            if 'skills' in new_resume and updates.get('skills'):
                new_resume['skills'] = updates['skills']
                
            # 更新工作经验
            if 'experience' in new_resume and updates.get('experience'):
                for i, exp in enumerate(new_resume['experience']):
                    if i < len(updates['experience']):
                        exp.update(updates['experience'][i])
                        
            # 更新项目经验
            if 'projects' in new_resume and updates.get('projects'):
                for i, proj in enumerate(new_resume['projects']):
                    if i < len(updates['projects']):
                        proj.update(updates['projects'][i])
                        
            # 更新自我评价
            if updates.get('self_evaluation'):
                new_resume['self_evaluation'] = updates['self_evaluation']
                
            return new_resume
            
        except Exception as e:
            self.logger.error(f"应用简历更新建议失败: {str(e)}")
            return resume
            
    def _parse_suggestions(self, suggestions: str) -> Dict:
        """解析AI建议"""
        updates = {
            'skills': [],
            'experience': [],
            'projects': [],
            'self_evaluation': '',
            'other_suggestions': []
        }
        
        try:
            lines = suggestions.strip().split('\n')
            current_section = None
            current_item = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('技能优化:'):
                    current_section = 'skills'
                elif line.startswith('经验调整:'):
                    current_section = 'experience'
                elif line.startswith('项目优化:'):
                    current_section = 'projects'
                elif line.startswith('自我评价:'):
                    current_section = 'self_evaluation'
                elif line.startswith('其他建议:'):
                    current_section = 'other'
                elif line.startswith('- 新内容:') and current_section:
                    content = line.split(':', 1)[1].strip()
                    if current_section == 'self_evaluation':
                        updates['self_evaluation'] = content
                    elif current_section in ['skills', 'experience', 'projects']:
                        current_item['content'] = content
                elif line.startswith('- 原因:') and current_item:
                    current_item['reason'] = line.split(':', 1)[1].strip()
                    if current_section in ['skills', 'experience', 'projects']:
                        updates[current_section].append(current_item)
                        current_item = {}
                elif line.startswith('-') and current_section == 'other':
                    updates['other_suggestions'].append(line[1:].strip())
                    
            return updates
            
        except Exception as e:
            self.logger.error(f"解析更新建议失败: {str(e)}")
            return updates