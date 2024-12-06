import asyncio
import json
import os
from utils.ai_service import AIService
import logging

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 测试用配置
test_config = {
    "ai": {
        "api": {
            "provider": "siliconflow",
            "api_base": "https://api.flow.siliconflow.com/v1",
            "model": "Qwen2.5-72B"
        },
        "settings": {
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "introduce": """我是一名4年经验的Python开发工程师..."""
    },
    "platforms": {
        "boss": {
            "default_greeting": "您好，看到贵公司的招聘信息很感兴趣，想了解一下职位详情。"
        }
    }
}

# 测试用职位数据
test_job = {
    "job_name": "Python开发工程师",
    "company_name": "测试科技有限公司",
    "company_size": "500-1000人",
    "company_stage": "C轮",
    "city": "北京",
    "salary": "25-35K",
    "work_year": "3-5年",
    "education": "本科",
    "job_tags": ["Python", "Django", "Redis", "MySQL"],
    "job_desc": """岗位职责：
1. 负责公司核心业务系统的开发和维护
2. 参与系统架构设计和技术方案制定
3. 解决系统性能瓶颈，优化系统架构
4. 编写技术文档，参与code review

任职要求：
1. 本科及以上学历，计算机相关专业
2. 3年以上Python开发经验
3. 熟练掌握Python、Django、Redis、MySQL
4. 有大型项目开发经验优先
5. 良好的团队协作能力和沟通能力"""
}

async def test_chat_completion():
    """测试基础对话功能"""
    print("\n=== 测试基础对话功能 ===")
    try:
        ai_service = AIService(test_config)
        prompt = "你是一个专业的HR助手，请简单介绍一下你自己"
        response = await ai_service.chat_completion(prompt)
        print(f"\nAI响应:\n{response}")
        assert isinstance(response, str) and len(response) > 0
        print("基础对话测试通过")
    except Exception as e:
        print(f"基础对话测试失败: {str(e)}")

async def test_job_analysis():
    """测试职位分析功能"""
    print("\n=== 测试职位分析功能 ===")
    try:
        ai_service = AIService(test_config)
        result = await ai_service.analyze_job_match(test_job, {})
        print("\n职位分析结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        assert isinstance(result, dict)
        assert "match_score" in result
        print("职位分析测试通过")
    except Exception as e:
        print(f"职位分析测试失败: {str(e)}")

async def test_greeting():
    """测试打招呼���生成"""
    print("\n=== 测试打招呼语生成 ===")
    try:
        ai_service = AIService(test_config)
        greeting = await ai_service.generate_greeting(test_job)
        print(f"\n生成的打招呼语:\n{greeting}")
        assert isinstance(greeting, str) and len(greeting) > 0
        print("打招呼语生成测试通过")
    except Exception as e:
        print(f"打招呼语生成测试失败: {str(e)}")

async def test_keyword_extraction():
    """测试关键词提取"""
    print("\n=== 测试关键词提取 ===")
    try:
        ai_service = AIService(test_config)
        keywords = await ai_service.extract_job_keywords(test_job["job_desc"])
        print("\n提取的关键词:")
        print(json.dumps(keywords, indent=2, ensure_ascii=False))
        assert isinstance(keywords, dict)
        print("关键词提取测试通过")
    except Exception as e:
        print(f"关键词提取测试失败: {str(e)}")

async def main():
    """运行所有测试"""
    print("开始AI功能测试...")
    
    # 打印配置信息
    print("\n=== 当前配置 ===")
    print(f"API Base: {test_config['ai']['api']['api_base']}")
    print(f"Model: {test_config['ai']['api']['model']}")
    
    # 测试API连接
    print("\n=== 测试API连接 ===")
    try:
        ai_service = AIService(test_config)
        print("API配置成功")
    except Exception as e:
        print(f"API配置失败: {str(e)}")
        return
    
    # 运行测试
    await test_chat_completion()
    await test_job_analysis()
    await test_greeting()
    await test_keyword_extraction()

if __name__ == "__main__":
    asyncio.run(main())
