from fastapi import FastAPI
from routers import exam, auth  # 导入auth路由
from database import Base, engine

# 初始化数据库（会创建新的users表）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="自动阅卷系统 API")

# 注册路由
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(auth.router)  # 添加认证路由

@app.get("/")
def root():
    return {"message": "欢迎使用 自动阅卷系统 API 🎯"}