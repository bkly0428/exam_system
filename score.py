import subprocess

import cv2
import os
import json
import glob
import numpy as np
from datetime import datetime
from ultralytics import YOLO


class AnswerSheetGrader:
    def __init__(self, model_path, answer_file=None, device='cpu'):
        self.model = YOLO(model_path)
        self.device = device
        self.correct_answers = {}
        self.exam_config = {}

        if answer_file:
            self.correct_answers, self.exam_config = self.load_correct_answers(answer_file)

        self.class_names = {0: 'xzt', 1: 'choice'}
        self.all_results = []

    def load_correct_answers(self, answer_file):
        if not os.path.exists(answer_file):
            raise FileNotFoundError(f"正确答案文件未找到: {answer_file}")

        with open(answer_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        exam_config = {}
        if 'config' in data and 'answers' in data:
            exam_config = data['config']
            answers_data = data['answers']
        else:
            answers_data = data

        converted = {}
        for key, value in answers_data.items():
            try:
                q_num = int(key)
                converted[q_num] = value
            except ValueError:
                converted[key] = value

        return converted, exam_config

    def preprocess_image(self, image_path, thresh_val=150):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片未找到: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"无法读取图片: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
        return img, binary

    def detect_boxes(self, image_path, conf_threshold=0.1):
        results = self.model.predict(
            source=image_path,
            conf=conf_threshold,
            imgsz=1024,
            device=self.device,
            verbose=False
        )

        if not results:
            raise ValueError("未检测到任何目标")

        result = results[0]
        img_height, img_width = result.orig_shape

        question_boxes = []
        option_boxes = []

        for box in result.boxes:
            cls = int(box.cls.item())
            conf = box.conf.item()
            x_center, y_center, w, h = box.xywhn[0].cpu().numpy()

            x_center *= img_width
            y_center *= img_height
            w *= img_width
            h *= img_height
            x = x_center - w / 2
            y = y_center - h / 2

            if cls == 0:
                question_boxes.append((x, y, w, h, conf))
            elif cls == 1:
                option_boxes.append((x, y, w, h, conf))

        question_boxes = self.sort_questions_row_priority(question_boxes, img_height)
        return question_boxes, option_boxes, img_width, img_height

    def sort_questions_row_priority(self, question_boxes, img_height):
        if not question_boxes:
            return []

        rows = []
        row_height_threshold = img_height * 0.02
        question_boxes.sort(key=lambda box: box[1])

        current_row = []
        for box in question_boxes:
            if not current_row:
                current_row.append(box)
            else:
                if abs(box[1] - current_row[0][1]) < row_height_threshold:
                    current_row.append(box)
                else:
                    current_row.sort(key=lambda box: box[0])
                    rows.append(current_row)
                    current_row = [box]

        if current_row:
            current_row.sort(key=lambda box: box[0])
            rows.append(current_row)

        sorted_boxes = []
        for row in rows:
            sorted_boxes.extend(row)
        return sorted_boxes

    def create_physical_to_logical_mapping(self, num_questions, rows_info):
        if not self.correct_answers:
            raise ValueError("未加载正确答案配置")

        logical_numbers = sorted(self.correct_answers.keys())

        if num_questions != len(logical_numbers):
            print(f"警告: 检测到 {num_questions} 个题目，但正确答案文件中有 {len(logical_numbers)} 个题目")

        order_type = self.exam_config.get('order', 'row_wise')
        custom_order = self.exam_config.get('custom_order', [])
        rows = self.exam_config.get('rows', len(rows_info))
        cols = self.exam_config.get('cols', max(rows_info) if rows_info else 0)

        if order_type == 'column_wise' and rows > 0 and cols > 0:
            mapping = self.create_column_wise_mapping(rows, cols, logical_numbers, num_questions)
        elif order_type == 'custom' and custom_order:
            mapping = self.create_custom_mapping(custom_order, logical_numbers, num_questions)
        else:
            mapping = self.create_row_wise_mapping(rows_info, logical_numbers, num_questions)

        return mapping

    def create_row_wise_mapping(self, rows_info, logical_numbers, num_questions):
        mapping = {}
        logical_idx = 0

        for row_idx, row_count in enumerate(rows_info):
            for col_idx in range(row_count):
                physical_idx = sum(rows_info[:row_idx]) + col_idx

                if physical_idx < num_questions and logical_idx < len(logical_numbers):
                    mapping[physical_idx] = logical_numbers[logical_idx]
                    logical_idx += 1

        return mapping

    def create_column_wise_mapping(self, rows, cols, logical_numbers, num_questions):
        mapping = {}
        logical_idx = 0

        physical_grid = []
        for i in range(rows):
            row = []
            for j in range(cols):
                if i * cols + j < num_questions:
                    row.append(i * cols + j)
            if row:
                physical_grid.append(row)

        for col in range(cols):
            for row in range(rows):
                if col < len(physical_grid[row]):
                    physical_idx = physical_grid[row][col]
                    if physical_idx < num_questions and logical_idx < len(logical_numbers):
                        mapping[physical_idx] = logical_numbers[logical_idx]
                        logical_idx += 1

        return mapping

    def create_custom_mapping(self, custom_order, logical_numbers, num_questions):
        mapping = {}
        valid_order = [q for q in custom_order if q in logical_numbers]

        if len(valid_order) < num_questions:
            remaining = [q for q in logical_numbers if q not in valid_order]
            valid_order.extend(remaining)

        for physical_idx, logical_num in enumerate(valid_order):
            if physical_idx < num_questions:
                mapping[physical_idx] = logical_num

        return mapping

    def get_rows_info(self, question_boxes, img_height):
        if not question_boxes:
            return []

        rows_info = []
        row_height_threshold = img_height * 0.02
        sorted_boxes = sorted(question_boxes, key=lambda box: box[1])

        current_row = []
        for box in sorted_boxes:
            if not current_row:
                current_row.append(box)
            else:
                if abs(box[1] - current_row[0][1]) < row_height_threshold:
                    current_row.append(box)
                else:
                    rows_info.append(len(current_row))
                    current_row = [box]

        if current_row:
            rows_info.append(len(current_row))

        return rows_info

    def recognize_answers(self, binary_img, question_boxes, option_boxes, threshold=0.3):
        answers = {}
        option_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

        for physical_idx, q_box in enumerate(question_boxes):
            q_x, q_y, q_w, q_h, _ = q_box
            current_options = []

            for o_box in option_boxes:
                o_x, o_y, o_w, o_h, _ = o_box
                o_center_x = o_x + o_w / 2
                o_center_y = o_y + o_h / 2

                if (q_x <= o_center_x <= q_x + q_w and
                        q_y <= o_center_y <= q_y + q_h):
                    current_options.append(o_box)

            current_options.sort(key=lambda box: box[0])
            selected = []

            for o_idx, (x, y, w, h, _) in enumerate(current_options):
                if o_idx >= len(option_letters):
                    continue

                roi = binary_img[int(y):int(y + h), int(x):int(x + w)]
                if roi.size == 0:
                    continue

                fill_ratio = cv2.countNonZero(roi) / (w * h)
                if fill_ratio > threshold:
                    selected.append(option_letters[o_idx])

            answers[physical_idx] = ''.join(sorted(selected)) if selected else '未作答'
        return answers

    def grade_answers(self, recognized_answers, num_questions, rows_info):
        if not self.correct_answers:
            raise ValueError("未加载正确答案配置")

        score = 0
        question_details = {}
        physical_to_logical = self.create_physical_to_logical_mapping(num_questions, rows_info)

        for physical_idx in range(num_questions):
            logical_num = physical_to_logical.get(physical_idx)
            if logical_num is None:
                continue

            ans = recognized_answers.get(physical_idx, '未作答')
            correct = self.correct_answers.get(logical_num)
            is_correct = False

            if correct is None:
                question_details[logical_num] = {
                    'recognized': ans,
                    'correct': '无答案',
                    'is_correct': False,
                    'status': '无答案配置'
                }
                continue

            if ans == '未作答':
                question_details[logical_num] = {
                    'recognized': ans,
                    'correct': correct,
                    'is_correct': False,
                    'status': '未作答'
                }
                continue

            if isinstance(correct, (list, tuple)):
                sorted_ans = ''.join(sorted(ans))
                sorted_correct = ''.join(sorted(correct))
                if sorted_ans == sorted_correct:
                    score += 1
                    is_correct = True
                    status = '正确'
                else:
                    status = '错误'
            elif isinstance(correct, str):
                if ans == correct:
                    score += 1
                    is_correct = True
                    status = '正确'
                else:
                    status = '错误'
            else:
                status = '格式错误'

            question_details[logical_num] = {
                'recognized': ans,
                'correct': correct,
                'is_correct': is_correct,
                'status': status
            }

        return score, question_details
    def visualize_results(self, img, question_boxes, option_boxes, recognized_answers, save_path, rows_info):

        # 创建物理到逻辑的映射
        num_questions = len(question_boxes)
        physical_to_logical = self.create_physical_to_logical_mapping(num_questions, rows_info)

        # 创建副本以避免修改原图
        result_img = img.copy()

        # 绘制题目区域（绿色矩形）
        for physical_idx, (x, y, w, h, conf) in enumerate(question_boxes):
            logical_num = physical_to_logical.get(physical_idx)
            if logical_num is None:
                logical_num = physical_idx + 1  # 如果没有映射，使用物理索引+1

            cv2.rectangle(result_img, (int(x), int(y)), (int(x + w), int(y + h)), (0, 255, 0), 2)
            cv2.putText(result_img, f"Q{logical_num}", (int(x), int(y) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 绘制选项区域（蓝色矩形）
        for (x, y, w, h, conf) in option_boxes:
            cv2.rectangle(result_img, (int(x), int(y)), (int(x + w), int(y + h)), (255, 0, 0), 1)

        # 显示识别结果（红色文字）
        for physical_idx, ans in recognized_answers.items():
            if physical_idx < len(question_boxes):
                logical_num = physical_to_logical.get(physical_idx)
                if logical_num is None:
                    logical_num = physical_idx + 1  # 如果没有映射，使用物理索引+1

                x, y, w, h, _ = question_boxes[physical_idx]
                display_text = f"{logical_num}:{ans}"
                cv2.putText(result_img, display_text,
                            (int(x) + 5, int(y) + 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # 保存结果图片
        cv2.imwrite(save_path, result_img)
        return result_img

    def process_single_paper(self, image_path, output_dir=None, threshold=0.3):
        start_time = datetime.now()

        try:
            color_img, binary_img = self.preprocess_image(image_path)  # color_img 是原始彩色图
            question_boxes, option_boxes, img_width, img_height = self.detect_boxes(image_path)

            if not question_boxes:
                raise ValueError("未检测到题目区域")
            if not option_boxes:
                raise ValueError("未检测到选项区域")

            rows_info = self.get_rows_info(question_boxes, img_height)
            recognized_answers = self.recognize_answers(binary_img, question_boxes, option_boxes, threshold)
            score, question_details = self.grade_answers(recognized_answers, len(question_boxes), rows_info)
            total_questions = len(self.correct_answers)

            # 新增：生成可视化结果
            if output_dir:
                # 构建可视化图片保存路径（例如：results/visualizations/xxx.jpg）
                visual_dir = os.path.join(output_dir, "xuanzeti")  # 将目录名改为xuanzeti
                os.makedirs(visual_dir, exist_ok=True)
                filename = os.path.basename(image_path)
                visual_save_path = os.path.join(visual_dir, f"{filename}")
                # 调用可视化函数
                self.visualize_results(
                    img=color_img,
                    question_boxes=question_boxes,
                    option_boxes=option_boxes,
                    recognized_answers=recognized_answers,
                    save_path=visual_save_path,
                    rows_info=rows_info
                )

            process_time = (datetime.now() - start_time).total_seconds()

            result = {
                "filename": os.path.basename(image_path),
                "score": score,
                "total": total_questions,
                "question_details": question_details,
                "process_time": f"{process_time:.2f}秒",
                "status": "成功",
                "visualization_path": visual_save_path if output_dir else None  # 新增：返回可视化图片路径
            }

            self.all_results.append(result)
            return result

        except Exception as e:
            error_result = {
                "filename": os.path.basename(image_path),
                "score": 0,
                "total": len(self.correct_answers),
                "question_details": {},
                "process_time": "0秒",
                "status": f"失败: {str(e)}"
            }
            self.all_results.append(error_result)
            return error_result

    def batch_process(self, image_dir, output_dir=None):
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp"]:
            image_files.extend(glob.glob(os.path.join(image_dir, ext)))

        for image_path in image_files:
            self.process_single_paper(image_path, output_dir)

        return self.all_results
