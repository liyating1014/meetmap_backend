from dotenv import load_dotenv
import os
import json
from services.ai_parser import parse_travel_note

# 加载环境变量
load_dotenv()

# 测试文本
test_text = """
北京三日游攻略

第一天：早上到达北京首都机场，打车去天安门广场（116.397428, 39.90923），参观故宫博物院，下午去王府井步行街购物。

第二天：上午去八达岭长城（116.5654, 40.3594），下午返回市区，晚上去后海酒吧街。

第三天：早上参观天坛公园（116.4074, 39.8837），下午去颐和园（116.2730, 39.9998），晚上从北京大兴机场返程。
"""

print("开始测试 AI 解析...")
print(f"测试文本：\n{test_text}\n")
print("=" * 50)

try:
    result = parse_travel_note(test_text)
    print("解析成功！")
    print("=" * 50)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 50)
    print(f"标题: {result.get('title')}")
    print(f"地点数量: {len(result.get('locations', []))}")
except Exception as e:
    print(f"解析失败: {e}")
