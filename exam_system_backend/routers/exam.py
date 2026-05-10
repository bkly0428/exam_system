import json
import cv2
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
import shutil
import os
from datetime import datetime
from fenge import run_yolo_inference
from score import AnswerSheetGrader  # 选择题评分模块
from database import get_db
from models import ExamPaper, ExamResult
from schemas import (
    ExamPaperResponse,
    ExamResultResponse,
)
from ronghe import fuse_after_grading
router = APIRouter()

# 基础路径定义
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam_system_backend目录
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_papers")
SEGMENT_DIR = os.path.join(BASE_DIR, "cropped_questions")
FINAL_EXAM_DIR = os.path.join(BASE_DIR, "final_exams")  # 完整试卷保存目录

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SEGMENT_DIR, exist_ok=True)
os.makedirs(FINAL_EXAM_DIR, exist_ok=True)  # 补充创建最终试卷目录

# 选择题答案文件路径及评分器初始化
ANSWER_KEY_PATH = os.path.join(BASE_DIR, "answers.json")
# 检查答案文件是否存在
if not os.path.exists(ANSWER_KEY_PATH):
    raise RuntimeError(f"选择题答案文件不存在，请检查路径: {ANSWER_KEY_PATH}")

# 初始化评分器
grader = AnswerSheetGrader(
    model_path=os.path.join(BASE_DIR, "models", "best12.pt"),
    answer_file=ANSWER_KEY_PATH
)


# 上传试卷并分割、自动评分
@router.post("/upload/", response_model=ExamPaperResponse)
def upload_exam_paper(
        exam_name: str = Form(...),
        subject: str = Form(...),
        student_name: str = Form(...),
        student_id: str = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    try:
        # 1. 保存原始试卷
        folder_name = f"{exam_name}_{subject}"
        folder_path = os.path.join(UPLOAD_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # 生成唯一文件名（精确到微秒避免重复）
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        ext = os.path.splitext(file.filename)[1].lower()  # 统一扩展名格式
        filename = f"{student_id}_{student_name}_{timestamp}{ext}"
        file_path = os.path.join(folder_path, filename)

        # 安全保存文件（确保资源释放）
        with open(file_path, "wb") as f_dst, file.file as f_src:
            shutil.copyfileobj(f_src, f_dst)

        # 2. YOLO分割试卷
        segmented_dir = os.path.join(SEGMENT_DIR, folder_name)
        os.makedirs(segmented_dir, exist_ok=True)
        segmented_path = run_yolo_inference(file_path, segmented_dir)

        # 验证分割结果
        if not os.path.isdir(segmented_path):
            raise ValueError(f"试卷分割失败，未生成有效目录: {segmented_path}")

        # 3. 选择题自动评分
        choice_dir = os.path.join(segmented_path, "xuanzeti")
        if not os.path.exists(choice_dir):
            raise ValueError(f"未找到选择题区域，路径不存在: {choice_dir}")

        # 处理评分结果
        results_dir = os.path.join(segmented_path, "results")
        os.makedirs(results_dir, exist_ok=True)
        choice_results = grader.batch_process(choice_dir, results_dir)
        total_choice_score = sum(r.get("score", 0) for r in choice_results)  # 兼容可能的键缺失

        # 4. 大题目录（人工评分用）
        subjective_dir = os.path.join(segmented_path, "dati")
        subjective_images = []
        if os.path.exists(subjective_dir):
            subjective_images = [
                os.path.join(subjective_dir, f)
                for f in os.listdir(subjective_dir)
                if f.lower().endswith((".jpg", ".png", ".jpeg"))
            ]
        # 在评分之后、数据库提交之前添加以下代码

        # 6. 执行图片融合
        # 构建分割信息JSON路径（根据fenge.py的输出结构）
        json_filename = f"{os.path.splitext(filename)[0]}.json"
        json_path = os.path.join(segmented_path, "json", json_filename)

        if not os.path.exists(json_path):
            raise ValueError(f"未找到分割信息JSON文件: {json_path}")

        # 构建融合后图片的保存路径
        fused_folder = os.path.join(FINAL_EXAM_DIR, folder_name)
        os.makedirs(fused_folder, exist_ok=True)
        fused_filename = f"{os.path.splitext(filename)[0]}_fused.jpg"
        fused_filepath = os.path.join(fused_folder, fused_filename)

        # 执行融合操作
        try:
            fused_filepath = fuse_after_grading(
                original_image_path=file_path,
                json_path=json_path,
                output_path=fused_filepath
            )
        except Exception as e:
            raise ValueError(f"图片融合失败: {str(e)}")

        # 5. 保存到数据库
        # 保存试卷记录
        # 7. 保存到数据库（更新部分）
        db_paper = ExamPaper(
            exam_name=exam_name,
            subject=subject,
            student_name=student_name,
            student_id=student_id,
            filename=filename,
            filepath=file_path,
            fused_filepath=fused_filepath,  # 保存融合路径
            upload_time=datetime.now(),
        )
        db.add(db_paper)
        db.commit()
        db.refresh(db_paper)

        # 保存成绩记录
        db_result = ExamResult(
            student_name=student_name,
            exam_name=exam_name,
            subject=subject,
            score=total_choice_score, #初始只有选择题分
            comments=f"选择题分数: {total_choice_score}, 大题分数: 0"
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)

        return {
            "id": db_paper.id,
            "exam_name": exam_name,
            "subject": subject,
            "student_name": student_name,
            "student_id": student_id,
            "filename": filename,
            "filepath": file_path,
            "fused_filepath": fused_filepath,  # 返回融合路径
            "upload_time": db_paper.upload_time,
            "segmented_path": segmented_path,
            "choice_score": total_choice_score,
            "subjective_score": 0,
            "total_score": total_choice_score,
            "choice_visualization_path": results_dir,  # 可视化目录路径
            "subjective_images": subjective_images  # 返回大题图片列表
        }

    except Exception as e:
        db.rollback()  # 出错时回滚数据库事务
        raise HTTPException(status_code=500, detail=f"上传或评分失败: {str(e)}")

# 获取试卷列表（支持筛选和分页）
@router.get("/papers/", response_model=list[ExamPaperResponse])
def list_exam_papers(
        exam_name: str | None = None,
        student_name: str | None = None,
        student_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """获取试卷列表，可按考试名称、学生姓名或学号筛选，并支持分页"""
    query = db.query(ExamPaper)

    if exam_name:
        query = query.filter(ExamPaper.exam_name == exam_name)
    if student_name:
        query = query.filter(ExamPaper.student_name == student_name)
    if student_id:
        query = query.filter(ExamPaper.student_id == student_id)

    return query.offset(skip).limit(limit).all()


# 保存成绩（支持手动录入）
@router.post("/results/", response_model=ExamResultResponse)
def create_exam_result(
        student_name: str = Form(...),
        exam_name: str = Form(...),
        subject: str = Form(...),
        score: int = Form(...),
        comments: str | None = Form(None),
        db: Session = Depends(get_db)
):
    """保存成绩到数据库，支持手动录入成绩（如大题评分）"""
    # 验证分数有效性
    if score < 0 or score > 100:
        raise HTTPException(status_code=400, detail="分数必须在0-100之间")

    db_result = ExamResult(
        student_name=student_name,
        exam_name=exam_name,
        subject=subject,
        score=score,
        comments=comments
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


# 获取成绩列表（支持筛选）
@router.get("/results/", response_model=list[ExamResultResponse])
def get_results(
        exam_name: str | None = None,
        student_name: str | None = None,
        db: Session = Depends(get_db)
):
    """获取成绩列表，支持按考试名称和学生姓名筛选"""
    query = db.query(ExamResult)

    if exam_name:
        query = query.filter(ExamResult.exam_name == exam_name)
    if student_name:
        query = query.filter(ExamResult.student_name == student_name)

    return query.all()
