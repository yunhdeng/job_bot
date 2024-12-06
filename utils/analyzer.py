from typing import Dict, List
import json
from datetime import datetime
import os
import logging

class JobAnalyzer:
    def __init__(self):
        self.jobs = []
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def add_job(self, job: Dict):
        """添加职位记录"""
        job['timestamp'] = datetime.now().isoformat()
        self.jobs.append(job)
        
    def save_records(self):
        """保存投递记录"""
        try:
            # 创建数据目录
            data_dir = 'data'
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
                
            # 按日期保存记录
            date_str = datetime.now().strftime('%Y%m%d')
            file_path = os.path.join(data_dir, f'job_records_{date_str}.json')
            
            # 读取已有记录
            existing_records = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_records = json.load(f)
                    
            # 合并记录
            all_records = existing_records + self.jobs
            
            # 去重（根据job_id）
            seen = set()
            unique_records = []
            for record in all_records:
                job_id = record['job_id']
                if job_id not in seen:
                    seen.add(job_id)
                    unique_records.append(record)
                    
            # 保存记录
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(unique_records, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"投递记录已保存到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存投递记录失败: {str(e)}")
            
    def get_statistics(self) -> Dict:
        """获取简单统计"""
        total = len(self.jobs)
        if not total:
            return {"total": 0}
            
        companies = set(job['company_name'] for job in self.jobs)
        cities = set(job['city'] for job in self.jobs)
        
        salary_sum = sum(
            (job['salary_min'] + job['salary_max'])/2 
            for job in self.jobs
        )
        
        return {
            "total": total,
            "unique_companies": len(companies),
            "cities": list(cities),
            "avg_salary": round(salary_sum / total, 2)
        } 

    def generate_report(self) -> str:
        """生成简单的统计报告"""
        stats = self.get_statistics()
        
        report = [
            "=== 投递统计报告 ===",
            f"总投递数量: {stats['total']}",
            f"目标公司数: {stats['unique_companies']}",
            f"目标城市: {', '.join(stats['cities'])}",
            f"平均薪资: {stats['avg_salary']}k",
            "\n详细记录已保存到: data/job_records_*.json"
        ]
        
        return "\n".join(report)