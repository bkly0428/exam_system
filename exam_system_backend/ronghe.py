import os
import cv2
import json
from typing import Optional


class ImageFusion:
    def __init__(self):
        """初始化图片融合工具，用于将裁剪后的图片融合回原始图片"""
        pass

    def fuse_images(self, original_image_path: str, json_path: str, output_path: Optional[str] = None) -> str:
        """
        核心融合方法：读取JSON中的裁剪信息，将对应裁剪图放回原图指定位置

        Args:
            original_image_path: 原始图片完整路径
            json_path: 包含裁剪位置和图片路径的JSON文件路径
            output_path: 融合后图片的保存路径，为空则自动生成

        Returns:
            融合后图片的保存路径
        """
        # 验证输入文件存在性
        if not os.path.isfile(original_image_path):
            raise FileNotFoundError(f"原始图片不存在: {original_image_path}")
        if not os.path.isfile(json_path):
            raise FileNotFoundError(f"裁剪信息JSON不存在: {json_path}")

        # 读取原始图片
        original_img = cv2.imread(original_image_path)
        if original_img is None:
            raise ValueError(f"无法加载原始图片，可能格式不支持: {original_image_path}")

        # 读取JSON裁剪信息
        with open(json_path, 'r', encoding='utf-8') as f:
            crop_data = json.load(f)

        # 解析路径关系（修改：将选择题图片来源指向 试卷根目录/results 子目录）
        json_dir = os.path.dirname(json_path)
        paper_dir = os.path.dirname(json_dir)  # 试卷根目录（JSON目录的父目录）
        # 新增：定义选择题图片所在的子目录（试卷根目录下的results）
        choice_images_dir = os.path.join(paper_dir, "results")

        # 遍历所有裁剪区域进行融合
        for obj in crop_data.get('objects', []):
            # 构建裁剪图片的绝对路径（修改：基于results子目录拼接）
            crop_rel_path = obj['image_path'].replace('\\', os.sep)  # 处理跨平台路径分隔符
            # 关键修改：从 试卷根目录/results 子目录中读取图片
            crop_abs_path = os.path.join(choice_images_dir, crop_rel_path)

            # 跳过不存在的裁剪图
            if not os.path.isfile(crop_abs_path):
                print(f"警告：裁剪图片不存在，已跳过 -> {crop_abs_path}")
                continue

            # 读取裁剪图片
            crop_img = cv2.imread(crop_abs_path)
            if crop_img is None:
                print(f"警告：无法加载裁剪图片，已跳过 -> {crop_abs_path}")
                continue

            # 获取原始位置坐标
            pos = obj['position']
            x1, y1 = int(pos['x1']), int(pos['y1'])
            x2, y2 = int(pos['x2']), int(pos['y2'])

            # 确保坐标在有效范围内
            img_h, img_w = original_img.shape[:2]
            x1 = max(0, min(x1, img_w))
            y1 = max(0, min(y1, img_h))
            x2 = max(x1, min(x2, img_w))
            y2 = max(y1, min(y2, img_h))

            # 调整裁剪图尺寸以匹配原始区域
            target_size = (x2 - x1, y2 - y1)
            resized_crop = cv2.resize(crop_img, target_size, interpolation=cv2.INTER_AREA)

            # 融合到原始图片
            original_img[y1:y2, x1:x2] = resized_crop

        # 处理输出路径
        if not output_path:
            # 自动生成输出路径（在原图目录下添加"_fused"后缀）
            orig_dir = os.path.dirname(original_image_path)
            orig_name = os.path.splitext(os.path.basename(original_image_path))[0]
            output_path = os.path.join(orig_dir, f"{orig_name}_fused.jpg")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # 保存融合结果
        if not cv2.imwrite(output_path, original_img):
            raise IOError(f"无法保存融合图片到: {output_path}")

        return output_path


def fuse_after_grading(original_image_path: str, json_path: str, output_path: Optional[str] = None) -> str:
    """评分后调用的融合接口，简化调用流程"""
    fusion = ImageFusion()
    return fusion.fuse_images(original_image_path, json_path, output_path)


# 命令行运行支持
if __name__ == "__main__":
    import sys

    if len(sys.argv) not in [3, 4]:
        print("用法: python ronghe.py <原始图片路径> <裁剪信息JSON路径> [可选输出路径]")
        sys.exit(1)

    try:
        result_path = fuse_after_grading(
            original_image_path=sys.argv[1],
            json_path=sys.argv[2],
            output_path=sys.argv[3] if len(sys.argv) == 4 else None
        )
        print(f"图片融合成功，保存路径: {result_path}")
    except Exception as e:
        print(f"融合失败: {str(e)}", file=sys.stderr)
        sys.exit(1)
