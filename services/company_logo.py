"""
公司Logo生成器
- 有真实Logo图片（static/company_logos/{key}.png/jpg/svg）→ 显示图片
- 没有真实Logo → 自动生成SVG品牌色圆标
"""
import os
import re

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
LOGO_DIR = os.path.join(STATIC_DIR, "company_logos")

# 品牌色映射（与schema.py保持一致）
BRAND_COLORS = {
    "比亚迪": "#4CAF50", "海天": "#E53935", "双汇": "#1565C0",
    "百威": "#FDD835", "伊利": "#1B5E20", "红牛": "#E65100",
    "李宁": "#D32F2F", "益华": "#9C27B0", "景鸿源": "#00BCD4",
    "嘉能可": "#FF5722", "荣辉": "#607D8B", "宝瑞坦": "#795548",
    "博格": "#FF9800", "壮方": "#3F51B5", "贝联": "#009688",
}

# 非品牌公司的默认色池（30种高区分度颜色）
DEFAULT_COLORS = [
    "#E85D04", "#D32F2F", "#1565C0", "#2B9348", "#6C5CE7",
    "#00BCD4", "#FF5722", "#9C27B0", "#FDD835", "#E65100",
    "#4CAF50", "#795548", "#607D8B", "#FF9800", "#3F51B5",
    "#C62828", "#283593", "#00695C", "#F9A825", "#AD1457",
    "#00838F", "#D84315", "#4527A0", "#2E7D32", "#EF6C00",
    "#5C6BC0", "#78909C", "#8D6E63", "#26A69A", "#EC407A",
]


def _get_company_char(company: str) -> str:
    """取公司名的第一个中文字符"""
    for ch in company.strip():
        if '\u4e00' <= ch <= '\u9fff':
            return ch
    return company[0] if company else "?"


def _get_company_color(company: str) -> str:
    """获取公司品牌色，无匹配则用名字hash取色"""
    for keyword, color in BRAND_COLORS.items():
        if keyword in company:
            return color
    # hash取色
    idx = hash(company) % len(DEFAULT_COLORS)
    return DEFAULT_COLORS[idx]


def get_logo_path(company_key: str) -> str | None:
    """检查是否有真实Logo文件"""
    for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp"]:
        path = os.path.join(LOGO_DIR, f"{company_key}{ext}")
        if os.path.isfile(path):
            return f"/static/company_logos/{company_key}{ext}"
    return None


def generate_logo(company_key: str, char: str = None, color: str = None) -> str:
    """
    生成品牌色SVG圆标HTML（带渐变背景，更精致）
    返回可直接插入页面的SVG标签字符串
    """
    char = char or _get_company_char(company_key)
    color = color or _get_company_color(company_key)
    # 将hex转为rgb
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    
    return f"""<svg width="36" height="36" viewBox="0 0 36 36" style="border-radius:8px;flex-shrink:0;">
    <defs>
        <linearGradient id="grad_{hash(company_key) % 10000}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:rgba({r},{g},{b},1)"/>
            <stop offset="100%" style="stop-color:rgba({max(0,r-40)},{max(0,g-40)},{max(0,b-40)},1)"/>
        </linearGradient>
    </defs>
    <rect width="36" height="36" rx="8" fill="url(%23grad_{hash(company_key) % 10000})"/>
    <text x="18" y="23" text-anchor="middle" font-size="16" font-weight="700" fill="#fff" font-family="sans-serif">{char}</text>
</svg>"""


def company_logo_html(company_key: str, size: int = 36) -> str:
    """
    统一的公司Logo HTML（优先真实图片，否则SVG渐变圆标）
    """
    real = get_logo_path(company_key)
    if real:
        return f'<img src="{real}" alt="{company_key}" style="width:{size}px;height:{size}px;border-radius:8px;object-fit:cover;flex-shrink:0;">'
    char = _get_company_char(company_key)
    color = _get_company_color(company_key)
    # 将hex转为rgb用于渐变
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    font_size = size // 2 - 1
    y_pos = size // 2 + font_size // 3
    grad_id = f"g{hash(company_key) % 10000}"
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="border-radius:{size//5}px;flex-shrink:0;">
    <defs>
        <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:rgb({r},{g},{b})"/>
            <stop offset="100%" style="stop-color:rgb({max(0,r-40)},{max(0,g-40)},{max(0,b-40)})"/>
        </linearGradient>
    </defs>
    <rect width="{size}" height="{size}" rx="{size//5}" fill="url(%23{grad_id})"/>
    <text x="{size//2}" y="{y_pos}" text-anchor="middle" font-size="{font_size}" font-weight="700" fill="#fff" font-family="sans-serif">{char}</text>
</svg>"""
