# exam_system_backend/yolo_inference.py
import os
import cv2
import json
from ultralytics import YOLO

# 获取当前文件的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 模型路径（相对路径）
MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"模型文件不存在: {MODEL_PATH}")
# 加载模型
model = YOLO(MODEL_PATH)


def run_yolo_inference(input_path: str, output_dir: str):
    # 确保总输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 推理
    results = model.predict(source=input_path)

    # 存储所有试卷的结果，最终返回最后一个试卷的目录
    last_paper_dir = None

    # 遍历每张图片结果
    for r in results:
        img = r.orig_img  # 原始图片
        filename = os.path.splitext(os.path.basename(r.path))[0]  # 试卷文件名（不带扩展名）

        # 每份试卷一个目录
        paper_dir = os.path.join(output_dir, filename)
        os.makedirs(paper_dir, exist_ok=True)

        # 创建json目录
        json_dir = os.path.join(paper_dir, "json")
        os.makedirs(json_dir, exist_ok=True)

        # 存储当前试卷的所有目标位置信息
        positions_info = {
            "filename": filename,
            "objects": []
        }

        for i, box in enumerate(r.boxes):
            cls_id = int(box.cls[0])  # 类别ID
            cls_name = model.names[cls_id]  # 类别名

            # 在试卷目录下创建类别子目录
            cls_dir = os.path.join(paper_dir, cls_name)
            os.makedirs(cls_dir, exist_ok=True)

            # 裁剪目标
            xyxy = box.xyxy[0].cpu().numpy().astype(int)
            crop = img[xyxy[1]:xyxy[3], xyxy[0]:xyxy[2]]

            # 保存文件
            save_path = os.path.join(cls_dir, f"{filename}_{cls_name}_{i}.jpg")
            cv2.imwrite(save_path, crop)

            # 记录位置信息
            positions_info["objects"].append({
                "id": i,
                "class": cls_name,
                "position": {
                    "x1": int(xyxy[0]),
                    "y1": int(xyxy[1]),
                    "x2": int(xyxy[2]),
                    "y2": int(xyxy[3])
                },
                "image_path": os.path.relpath(save_path, paper_dir)
            })

        # 保存位置信息到JSON文件
        json_path = os.path.join(json_dir, f"{filename}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(positions_info, f, ensure_ascii=False, indent=2)

        last_paper_dir = paper_dir

    # 返回最后处理的试卷的分割目录
    return last_paper_dir

