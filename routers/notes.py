import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Note
from services.ai_parser import parse_travel_note

router = APIRouter()


@router.get("/notes")
async def get_notes(page: int = 1, size: int = 10, q: str = None, db: Session = Depends(get_db)):
    """获取历史笔记列表，支持分页（?page=1&size=10）和关键词搜索（?q=北京）"""
    size = min(max(size, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * size

    query = db.query(Note)
    if q and q.strip():
        keyword = f"%{q.strip()}%"
        query = query.filter(Note.generated_json.like(keyword))

    total = query.count()
    notes = query.order_by(Note.created_at.desc()).offset(offset).limit(size).all()

    items = []
    for note in notes:
        try:
            generated_data = json.loads(note.generated_json)
            items.append({
                "id": note.id,
                "title": generated_data.get("title", ""),
                "locations": generated_data.get("locations", []),
                "created_at": note.created_at.isoformat()
            })
        except Exception:
            pass

    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
        "items": items
    }


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, db: Session = Depends(get_db)):
    """删除指定 ID 的笔记"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": f"未找到 ID 为 {note_id} 的笔记"
        })
    try:
        db.delete(note)
        db.commit()
        return JSONResponse(status_code=200, content={
            "status": "success",
            "message": f"笔记 {note_id} 已删除"
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=200, content={
            "status": "fail",
            "message": f"删除失败：{str(e)}"
        })


@router.put("/notes/{note_id}")
async def update_note(note_id: int, request: Request, db: Session = Depends(get_db)):
    """更新笔记原文并重新触发 AI 解析，刷新结构化数据"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": f"未找到 ID 为 {note_id} 的笔记"
        })

    try:
        data = await request.json()
    except Exception:
        data = {}

    new_text = (
        data.get("original_text")
        or data.get("text")
        or data.get("content")
        or ""
    ).strip()

    if not new_text:
        return JSONResponse(status_code=200, content={
            "status": "error",
            "message": "请提供更新后的文本（字段名：original_text / text / content）"
        })

    try:
        result = parse_travel_note(new_text)
    except Exception as e:
        print(f"【⚠️ 重新解析失败】: {str(e)}")
        return JSONResponse(status_code=200, content={
            "status": "fail",
            "message": f"AI 重新解析失败：{str(e)}"
        })

    try:
        note.original_text = new_text
        note.generated_json = json.dumps(result, ensure_ascii=False)
        db.commit()
        db.refresh(note)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=200, content={
            "status": "fail",
            "message": f"更新存库失败：{str(e)}"
        })

    return JSONResponse(status_code=200, content={
        "status": "success",
        "id": note.id,
        "updated_at": note.created_at.isoformat(),
        **result
    })


@router.get("/notes/{note_id}")
async def get_note_by_id(note_id: int, db: Session = Depends(get_db)):
    """根据 ID 获取单条笔记的完整解析数据"""
    note = db.query(Note).filter(Note.id == note_id).first()

    if not note:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": f"未找到 ID 为 {note_id} 的笔记"
        })

    try:
        generated_data = json.loads(note.generated_json)
    except Exception:
        generated_data = {}

    return JSONResponse(status_code=200, content={
        "status": "success",
        "id": note.id,
        "user_id": note.user_id,
        "original_text": note.original_text,
        "created_at": note.created_at.isoformat(),
        **generated_data
    })
