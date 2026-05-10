from passlib.context import CryptContext

# 密码加密上下文（使用bcrypt算法）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """对密码进行哈希处理"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)