from dotenv import load_dotenv
import os
import json
from services.ai_parser import parse_travel_note

# 加载环境变量
load_dotenv()

# 测试文本 - 包含人均消费和推荐菜
test_text = """
北京三日游美食攻略

第一天：早上到达北京，先去全聚德烤鸭店（116.397428, 39.90923）品尝正宗烤鸭，人均消费200元，营业时间是11:00-21:00，推荐菜有北京烤鸭、芥末鸭掌，记得提前预约。下午去故宫博物院（116.4039, 39.9242）参观，门票60元，营业时间08:30-17:00，推荐看点有太和殿、乾清宫，建议穿舒适的鞋子。

第二天：上午去东来顺火锅（116.4179, 39.9131），人均消费150元，营业时间10:00-22:00，推荐菜有涮羊肉、芝麻烧饼，冬天去特别暖和。下午去颐和园（116.2730, 39.9998）游玩，门票30元，营业时间06:30-18:00，推荐景点有昆明湖、万寿山，建议带相机拍照。

第三天：早上去庆丰包子铺（116.4074, 39.8837），人均消费30元，营业时间06:00-21:00，推荐菜有猪肉大葱包子、豆汁，老北京人的早餐首选。下午去八达岭长城（116.5654, 40.3594），门票40元，营业时间07:00-18:00，推荐看点有北八楼、好汉坡，建议穿运动鞋。
"""

print("开始测试 AI 解析...")
print(f"测试文本：\n{test_text}\n")
print("=" * 80)

try:
    result = parse_travel_note(test_text)
    print("解析成功！")
    print("=" * 80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 80)
    
    # 验证字段完整性
    print("\n字段验证：")
    for i, location in enumerate(result.get('locations', [])):
        print(f"\n地点 {i+1}: {location.get('name')}")
        print(f"  - avg_cost: {location.get('avg_cost')} (类型: {type(location.get('avg_cost')).__name__})")
        print(f"  - opening_hours: {location.get('opening_hours')} (类型: {type(location.get('opening_hours')).__name__})")
        print(f"  - recommendations: {location.get('recommendations')} (类型: {type(location.get('recommendations')).__name__})")
        print(f"  - tips: {location.get('tips')} (类型: {type(location.get('tips')).__name__})")
        
        # 验证数据类型
        if location.get('avg_cost') is not None and not isinstance(location.get('avg_cost'), (int, float)):
            print(f"  ❌ 错误: avg_cost 应该是数字类型")
        if location.get('recommendations') is not None and not isinstance(location.get('recommendations'), list):
            print(f"  ❌ 错误: recommendations 应该是数组类型")
            
except Exception as e:
    print(f"解析失败: {e}")
    import traceback
    traceback.print_exc()
