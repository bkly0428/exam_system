from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from database import Base

# models.py (修改ExamPaper模型)
class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, index=True)
    exam_name = Column(String, nullable=False)   # 考试名称
    subject = Column(String, nullable=False)     # 科目
    student_name = Column(String, index=True)  # 学生姓名
    student_id = Column(String, index=True)    # 学号
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    fused_filepath = Column(String, nullable=True)  # 新增：融合后图片路径
    upload_time = Column(DateTime, default=datetime.now)


class ExamResult(Base):
    __tablename__ = "exam_results"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, nullable=False)
    exam_name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    comments = Column(String, nullable=True)
# 新增用户模型
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)  # 唯一用户名
    password = Column(String, nullable=False)  # 存储哈希后的密码
    created_at = Column(DateTime, default=datetime.now)

class QuestionScore(Base):
    __tablename__ = "question_scores"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, nullable=False)
    exam_name = Column(String, nullable=False)
    question_id = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    full_score = Column(Integer, nullable=False)
