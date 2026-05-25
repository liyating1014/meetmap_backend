import os
import requests as http_requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.ai_parser import suggest_meeting_points

router = APIRouter()

# 广州市中心兜底坐标（方案 B）
FALLBACK_START = {"lng": 113.264434, "lat": 23.129162, "name": "广州市中心（兜底默认起点）"}
FALLBACK_END   = {"lng": 113.361990, "lat": 23.130610, "name": "广州天河（兜底默认终点）"}


def _geocode_by_amap(place_name: str) -> dict:
    """方案 A：调用高德地理编码 API，将地名转为经纬度字典"""
    amap_key = os.getenv("AMAP_KEY", "")
    if not amap_key:
        return None
    try:
        resp = http_requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"address": place_name, "key": amap_key, "output": "JSON"},
            timeout=5
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") == "1" and body.get("geocodes"):
            location = body["geocodes"][0]["location"]  # "lng,lat"
            lng, lat = location.split(",")
            formatted = body["geocodes"][0].get("formatted_address", place_name)
            print(f"【高德地理编码成功】{place_name} → {location}")
            return {"lng": float(lng), "lat": float(lat), "name": formatted}
    except Exception as e:
        print(f"【高德地理编码失败】{place_name}: {e}")
    return None


def _extract_location(val) -> dict:
    """将各种格式的起止点统一成 {'lng':..., 'lat':..., 'name':...} 字典"""
    if not val:
        return None
    if isinstance(val, dict):
        lng = val.get('lng') or val.get('longitude') or val.get('lon')
        lat = val.get('lat') or val.get('latitude')
        name = val.get('name') or val.get('address') or val.get('label') or ""
        if lng and lat:
            return {"lng": float(lng), "lat": float(lat), "name": name}
        if name:
            return {"name": name}  # 有地名但无坐标，后续走地理编码
    if isinstance(val, str) and val.strip():
        return {"name": val.strip()}
    return None


def _location_to_str(loc: dict) -> str:
    """把坐标字典转成 AI 可读的描述字符串"""
    name = loc.get("name", "")
    lng  = loc.get("lng")
    lat  = loc.get("lat")
    if name and lng and lat:
        return f"{name}（经度{lng}，纬度{lat}）"
    if lng and lat:
        return f"经度{lng}，纬度{lat}"
    return name


def _resolve_location(raw, fallback: dict, label: str) -> dict:
    """
    三级兜底策略：
    1. 原始坐标有效 → 直接用
    2. 只有地名 → 高德地理编码（方案 A）
    3. 啥都没有 → 广州默认坐标（方案 B）
    """
    loc = _extract_location(raw)

    # 已有完整坐标，直接返回
    if loc and loc.get("lng") and loc.get("lat"):
        return loc

    # 尝试用地名做地理编码（方案 A）
    if loc and loc.get("name"):
        geocoded = _geocode_by_amap(loc["name"])
        if geocoded:
            return geocoded
        # 地理编码失败，但至少有地名，直接把地名给 AI
        print(f"【{label}】地理编码失败，将地名直接传给 AI：{loc['name']}")
        return {"lng": None, "lat": None, "name": loc["name"]}

    # 方案 B：静态默认坐标
    print(f"【🚨 {label}】前端未传有效数据，启用广州默认坐标兜底")
    return fallback


async def handle_route_planning(request: Request) -> JSONResponse:
    """核心处理：三级兜底 + 全包容容错，始终返回 200"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    print(f"【后端收到原始载荷】: {data}")

    # 兼容多种键名
    start_raw   = data.get('start_point') or data.get('startPoint') or data.get('start')
    end_raw     = data.get('end_point')   or data.get('endPoint')   or data.get('end')
    # 也接收纯文本地名字段
    start_name  = data.get('start_name')  or data.get('startName')
    end_name    = data.get('end_name')    or data.get('endName')
    commute_raw = data.get('commute_time') or data.get('commuteTime') or 30
    start_bounds = data.get('startBounds', None)

    # 如果坐标为空但有纯文本地名，构造成可用的 raw
    if not start_raw and start_name:
        start_raw = start_name
    if not end_raw and end_name:
        end_raw = end_name

    # 检测高德崩溃信号（Bounds 为 0 视为无效）
    amap_crashed = (start_bounds == 0) or (not start_raw and not end_raw)
    if amap_crashed:
        print("【🚨 后端检测到前端高德故障】触发纯后端地理坐标同步兜底...")

    # 三级兜底解析
    start_loc = _resolve_location(start_raw, FALLBACK_START, "起点")
    end_loc   = _resolve_location(end_raw,   FALLBACK_END,   "终点")

    start_str = _location_to_str(start_loc)
    end_str   = _location_to_str(end_loc)

    try:
        commute_time = int(commute_raw)
    except (TypeError, ValueError):
        commute_time = 30

    print(f"【最终传入 AI】起点={start_str}，终点={end_str}，通勤={commute_time}分钟")

    try:
        result = suggest_meeting_points(start_str, end_str, commute_time)
        # 始终返回 200，让旧版前端能正常解析
        return JSONResponse(status_code=200, content={
            "status": "success",
            **result,
            "_debug": {
                "start_resolved": start_str,
                "end_resolved": end_str,
                "fallback_used": amap_crashed
            }
        })
    except Exception as e:
        print(f"【⚠️ 后端捕获严重异常】: {str(e)}")
        # 依然返回 200，让前端能拿到内容而不是网络错误
        return JSONResponse(status_code=200, content={
            "status": "fail",
            "message": f"后端捕获未预期错误: {str(e)}，请检查参数匹配。"
        })


# 三路由绑定（/api 前缀由 main.py 的 include_router 添加）
@router.post("/suggest-meeting-points", tags=["route-planning"])
@router.post("/route-planning", tags=["route-planning"])
async def route_planning_endpoint(request: Request):
    return await handle_route_planning(request)
