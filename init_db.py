from database import engine, Base
from models import User, Note

def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    print("数据库表创建成功")

if __name__ == "__main__":
    init_db()
