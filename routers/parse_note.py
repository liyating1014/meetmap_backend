import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Note, User
from services.ai_parser import parse_travel_note

router = APIRouter()


async def handle_parse_note(request: Request, db: Session) -> JSONResponse:
    """
    核心解析逻辑：
    - 兼容多种字段名（original_text / text / content / url）
    - 始终返回 200，彻底消灭 500
    - 解析成功后自动存库
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    print(f"【parse-note 收到载荷】: {str(data)[:200]}")

    # 兼容多种字段名
    text = (
        data.get("original_text")
        or data.get("text")
        or data.get("content")
        or data.get("url")
        or ""
    )
    user_id = data.get("user_id") or data.get("userId") or 1

    if not text or not text.strip():
        return JSONResponse(status_code=200, content={
            "status": "error",
            "message": "请提供旅游攻略文本或链接（字段名：original_text / text / content / url）"
        })

    try:
        result = parse_travel_note(text.strip())
    except Exception as e:
        print(f"【⚠️ AI 解析异常】: {str(e)}")
        return JSONResponse(status_code=200, content={
            "status": "fail",
            "message": f"AI 解析失败：{str(e)}"
        })

    # 存库：确保用户存在
    try:
        user_id = int(user_id)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, username=f"user_{user_id}")
            db.add(user)
            db.commit()
            db.refresh(user)

        note = Note(
            user_id=user_id,
            original_text=text.strip(),
            generated_json=json.dumps(result, ensure_ascii=False)
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        note_id = note.id
    except Exception as e:
        print(f"【⚠️ 存库失败，但不影响返回】: {str(e)}")
        db.rollback()
        note_id = None

    return JSONResponse(status_code=200, content={
        "status": "success",
        **result,
        "_meta": {
            "note_id": note_id,
            "char_count": len(text)
        }
    })


# 双路由绑定：下划线（原有）+ 连字符（新增）
@router.post("/parse_note", tags=["parse"])
@router.post("/parse-note", tags=["parse"])
async def parse_note_endpoint(request: Request, db: Session = Depends(get_db)):
    return await handle_parse_note(request, db)
