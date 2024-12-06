import logging
from typing import Dict
import os
import aiohttp

class JobNotifier:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.hook_url = os.getenv('HOOK_URL')
        
    async def notify_delivery(self, job: Dict, success: bool):
        """投递结果通知"""
        if not self.config.get('bot', {}).get('is_send', False):
            return
            
        message = (
            f"{'✅' if success else '❌'} "
            f"{job['job_name']} - {job['company_name']}\n"
            f"薪资: {job['salary']}\n"
            f"城市: {job['city']}\n"
        )
        
        if job.get('ai_analysis'):
            message += (
                f"匹配度: {job['ai_analysis']['match_score']}分\n"
                f"优势: {', '.join(job['ai_analysis']['advantages'][:2])}\n"
                f"建议: {', '.join(job['ai_analysis']['suggestions'][:2])}"
            )
            
        await self._send_to_wechat(message)
        
    async def _send_to_wechat(self, message: str):
        """发送企业微信通知"""
        if not self.hook_url:
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.hook_url,
                    json={"msgtype": "text", "text": {"content": message}}
                )
        except Exception as e:
            self.logger.error(f"发送企业微信通知失败: {str(e)}") 