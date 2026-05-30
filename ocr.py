#!/usr/bin/env python3
"""
本地OCR识别 - 用tesseract识别图片中的文字
不调用任何外部API，完全本地运行
"""
import subprocess, sys, os, re, json

def ocr_image(image_path, lang="chi_sim+eng"):
    """本地OCR识别图片"""
    if not os.path.exists(image_path):
        return {"error": f"文件不存在: {image_path}"}
    
    output_base = "/tmp/hermes_ocr_" + os.path.basename(image_path)
    
    try:
        # 调用tesseract
        result = subprocess.run(
            ["tesseract", image_path, output_base, "-l", lang],
            capture_output=True, text=True, timeout=30
        )
        
        # 读取结果
        txt_path = output_base + ".txt"
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            # 清理临时文件
            os.remove(txt_path)
            return {"text": text, "length": len(text)}
        else:
            return {"error": f"OCR输出文件未生成: {result.stderr}"}
    
    except subprocess.TimeoutExpired:
        return {"error": "OCR超时"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 ocr.py <图片路径>")
        sys.exit(1)
    
    result = ocr_image(sys.argv[1])
    if "error" in result:
        print(f"错误: {result['error']}")
    else:
        print(result["text"])
