from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import parse_note, notes, route_planning
from routers.route_planning import handle_route_planning

app = FastAPI(title="AI Travel Note API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse_note.router, prefix="/api", tags=["parse"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(route_planning.router, prefix="/api", tags=["route-planning"])

# 兼容旧版前端路由（三轨合一）
# /st-meeting-points        — 旧版前端直接请求
# /api/suggest-meeting-points — 经由 router 注册
# /api/route-planning        — 经由 router 注册
@app.post("/st-meeting-points", tags=["compat"])
async def st_meeting_points(request: Request):
    """兼容旧版前端，与 /api/suggest-meeting-points 完全等价"""
    return await handle_route_planning(request)

@app.get("/api/health", tags=["health"])
async def health_check():
    """健康检查接口，供前端探测后端是否在线"""
    return {"status": "ok", "message": "后端服务运行正常"}

@app.get("/")
async def root():
    return {"message": "AI Travel Note API"}
