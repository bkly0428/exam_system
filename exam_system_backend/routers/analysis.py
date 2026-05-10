from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import ExamResult

router = APIRouter(
    prefix="/analysis",
    tags=["成绩分析"]
)

# 1️⃣ 概览
@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    avg = db.query(func.avg(ExamResult.score)).scalar()
    max_score = db.query(func.max(ExamResult.score)).scalar()
    min_score = db.query(func.min(ExamResult.score)).scalar()

    total = db.query(ExamResult).count()
    pass_count = db.query(ExamResult).filter(ExamResult.score >= 60).count()
    excellent_count = db.query(ExamResult).filter(ExamResult.score >= 90).count()

    return {
        "avg": avg,
        "max": max_score,
        "min": min_score,
        "pass_rate": pass_count / total if total else 0,
        "excellent_rate": excellent_count / total if total else 0
    }


# 2️⃣ 分数分布
@router.get("/distribution")
def distribution(db: Session = Depends(get_db)):
    ranges = [(0,60),(60,70),(70,80),(80,90),(90,100)]
    result = {}

    for low, high in ranges:
        count = db.query(ExamResult).filter(
            ExamResult.score >= low,
            ExamResult.score < high
        ).count()
        result[f"{low}-{high}"] = count

    return result


# 3️⃣ 排名
@router.get("/rank")
def rank(db: Session = Depends(get_db)):
    rows = db.query(ExamResult).order_by(ExamResult.score.desc()).all()

    return [
        {
            "student": r.student_name,
            "score": r.score
        }
        for r in rows
    ]