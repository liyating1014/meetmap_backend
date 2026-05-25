from openai import OpenAI
import os
import json
import re
import requests
from dotenv import load_dotenv
from pathlib import Path

# Explicitly load .env from the current directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("API_KEY")
base_url = os.getenv("BASE_URL")

if not api_key:
    raise ValueError("API_KEY environment variable is not set. Please check your .env file.")
if not base_url:
    raise ValueError("BASE_URL environment variable is not set. Please check your .env file.")

# 自动补全协议前缀，防止遗漏 https:// 导致 Connection error
if base_url and not base_url.startswith(("http://", "https://")):
    base_url = "https://" + base_url

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

SYSTEM_PROMPT = """你是一个专业的旅游攻略解析助手。你的任务是将用户输入的旅游攻略文本解析为结构化的 JSON 数据。

请严格按照以下 JSON 格式返回，不要包含任何其他文字说明：

{
  "title": "游记标题",
  "locations": [
    {
      "name": "地点名称",
      "longitude": 经度数字（例如：116.397428）,
      "latitude": 纬度数字（例如：39.90923）,
      "description": "该地点的简短游玩说明（50字以内）",
      "day": 第几天（数字，从1开始）,
      "avg_cost": 人均消费（纯数字，例如：150）,
      "opening_hours": "营业时间（字符串，例如：09:00-22:00）",
      "recommendations": ["推荐菜/必看点1", "推荐菜/必看点2"],
      "tips": "注意事项（字符串，例如：需要提前预约）"
    }
  ]
}

注意事项：
1. 只返回纯 JSON 格式，不要有任何 markdown 标记（如 ```json）或额外文字
2. locations 数组按旅游时间顺序排列
3. 经纬度必须是数字格式，不要使用字符串
4. day 字段表示第几天的行程，从1开始递增
5. description 字段要简洁明了，控制在50字以内
6. avg_cost 必须是纯数字，不要包含货币符号或单位
7. opening_hours 如果文本中未提及，设为 null
8. recommendations 必须是数组格式，如果文本中未提及，设为空数组 []
9. tips 如果文本中未提及，设为 null
10. 如果文本中明确提到了经纬度，请使用文本中的经纬度；如果未提及，请根据地点名称推测合理的经纬度
11. 确保所有地点都有有效的经纬度坐标
"""

def extract_url(text: str) -> str:
    """使用正则表达式提取文本中的 URL"""
    url_pattern = r'https?://[^\s]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

def fetch_content_from_url(url: str) -> str:
    """使用 Jina Reader API 获取网页内容"""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(jina_url, timeout=10)
        response.raise_for_status()
        content = response.text
        # 截取前 2000 个字符
        return content[:2000]
    except Exception as e:
        print(f"警告: Jina Reader API 请求失败: {str(e)}，将使用原始文本")
        return None

def preprocess_text(original_text: str) -> str:
    """预处理文本：提取 URL 并获取网页内容"""
    url = extract_url(original_text)
    if url:
        print(f"检测到 URL: {url}，正在获取网页内容...")
        fetched_content = fetch_content_from_url(url)
        if fetched_content:
            # 将获取的内容与原始文本拼接
            return f"{fetched_content}\n\n{original_text}"
    return original_text

def parse_travel_note(original_text: str) -> dict:
    """调用 AI 解析旅游攻略文本"""
    try:
        # 预处理文本（URL 提取和内容获取）
        processed_text = preprocess_text(original_text)
        
        response = client.chat.completions.create(
            model="doubao-1-5-pro-32k-250115",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": processed_text}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        raise Exception(f"AI 解析失败: {str(e)}")

ROUTE_PLANNING_PROMPT = """你是一个专业的路线规划助手。你的任务是根据两个起点和通勤时间，提供智能的见面地点建议。

请严格按照以下 JSON 格式返回，不要包含任何其他文字说明：

{
  "suggestions": [
    {
      "name": "推荐地点名称",
      "type": "地点类型（如：咖啡馆、餐厅、图书馆、联合办公空间）",
      "scene": "场景分类（校园/生活/生产）",
      "reason": "推荐理由（30字以内）",
      "estimated_time_a": "A点预计到达时间（如：15分钟）",
      "estimated_time_b": "B点预计到达时间（如：18分钟）"
    }
  ],
  "route_summary": "路线总结（50字以内）"
}

注意事项：
1. 只返回纯 JSON 格式，不要有任何 markdown 标记（如 ```json）或额外文字
2. suggestions 数组包含 3-5 个推荐地点
3. 推荐地点应考虑双方通勤时间的平衡性
4. scene 字段只能是：校园、生活、生产 之一
5. estimated_time_a 和 estimated_time_b 应基于给定的通勤时间阈值
"""

def suggest_meeting_points(start_point: str, end_point: str, commute_time: int) -> dict:
    """调用 AI 生成见面地点建议"""
    try:
        prompt = f"""
起点 A: {start_point}
起点 B: {end_point}
通勤时间阈值: {commute_time} 分钟

请根据以上信息，推荐 3-5 个适合双方见面的地点，考虑通勤时间平衡和场景需求。
"""
        
        response = client.chat.completions.create(
            model="doubao-1-5-pro-32k-250115",
            messages=[
                {"role": "system", "content": ROUTE_PLANNING_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        raise Exception(f"AI 路线规划失败: {str(e)}")
