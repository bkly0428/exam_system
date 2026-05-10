from fastapi import FastAPI
from routers import exam, auth  # 导入auth路由
from database import Base, engine
from routers import analysis

# 初始化数据库（会创建新的users表）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="自动阅卷系统 API")

# 注册路由
app.include_router(exam.router, prefix="/exam", tags=["Exam"])
app.include_router(auth.router)  # 添加认证路由
app.include_router(analysis.router)

@app.get("/")
def root():
    return {"message": "欢迎使用 自动阅卷系统 API 🎯"}

# 在main.py中添加跨域配置
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源，生产环境需指定前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)