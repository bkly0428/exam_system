from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserLogin, UserResponse
from auth import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 创建新用户（密码哈希后存储）
    new_user = User(
        username=user.username,
        password=hash_password(user.password)  # 存储哈希后的密码
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=UserResponse)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录（简单密码对比）"""
    # 查询用户
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 验证密码
    if not verify_password(login_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 登录成功，返回用户信息
    return user