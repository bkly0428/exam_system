from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# 试卷信息
# schemas.py (修改ExamPaperResponse)
class ExamPaperResponse(BaseModel):
    id: int
    exam_name: str
    subject: str
    student_name: str
    student_id: str
    filename: str
    filepath: str
    fused_filepath: Optional[str] = None  # 新增融合路径字段
    upload_time: datetime

    class Config:
        from_attributes = True


# 成绩提交/查询
class ExamResultResponse(BaseModel):
    id: int
    student_name: str
    exam_name: str
    subject: str
    score: int
    comments: Optional[str] = None

    class Config:
        from_attributes = True

# 评分请求模型
class GradeRequest(BaseModel):
    paper_id: int
    model_path: str
    answer_file: str

# 题目详情
class QuestionDetail(BaseModel):
    recognized: str
    correct: str
    is_correct: bool
    status: str

# 评分结果
class GradeResult(BaseModel):
    filename: str
    score: int
    total: int
    question_details: Optional[dict[int, QuestionDetail]] = None
    status: str
# 新增用户模型
class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=6)  # 密码至少6位

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True