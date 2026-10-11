"""图片账单 OCR 解析器
支持从账单截图中提取交易信息。
依赖(可选): pytesseract + Pillow + Tesseract-OCR

如果没有安装这些依赖,程序会给出明确提示并跳过图片文件。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .base import BaseParser, Transaction


# 常见时间格式
DATE_PATTERNS = [
    r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?",     # 2024-01-15
    r"(\d{1,2})[-/月](\d{1,2})[日]?",                     # 1-15 / 1月15日
]

# 金额(找 ¥ / 元 / 数字.数字 格式,优先带符号)
AMOUNT_PATTERNS = [
    r"[¥￥]\s*(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
    r"(-?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*元",
]

# 收入/支出标记
INCOME_KEYWORDS = ["收入", "收到", "转入", "入账", "退款", "红包收入", "充值成功"]
EXPENSE_KEYWORDS = ["支出", "支付", "扣款", "消费", "付款", "转账给", "红包"]


def try_ocr_image(image_path: str) -> str:
    """尝试 OCR 识别图片,返回识别文本"""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        raise RuntimeError(
            "OCR 功能需要安装 pytesseract + Pillow + Tesseract-OCR。\n"
            "安装命令:\n"
            "  pip install pytesseract Pillow\n"
            "然后从 https://github.com/tesseract-ocr/tesseract/releases 下载 Tesseract 并安装。"
        )
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    return text


class ImageOCRParser(BaseParser):
    """图片账单 OCR 解析器"""
    name = "image"
    supported_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.supported_extensions

    def parse(self, file_path: str) -> list[Transaction]:
        try:
            text = try_ocr_image(file_path)
        except RuntimeError:
            return []

        return self._parse_text(text, source_file=file_path)

    def _parse_text(self, text: str, source_file: str = "") -> list[Transaction]:
        """从 OCR 文本中提取交易"""
        transactions: list[Transaction] = []
        # 按行扫描
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            t = self._parse_line(line)
            if t:
                if source_file:
                    t.raw_text = f"[{Path(source_file).name}] {line}"
                transactions.append(t)
        return transactions

    def _parse_line(self, line: str) -> Transaction | None:
        # 提取日期
        date = None
        for pat in DATE_PATTERNS:
            m = re.search(pat, line)
            if m:
                try:
                    if len(m.groups()) == 3:
                        y, mo, d = m.groups()
                        date = datetime(int(y), int(mo), int(d))
                    else:
                        # 短日期,补全年份
                        mo, d = m.groups()
                        date = datetime(datetime.now().year, int(mo), int(d))
                    break
                except ValueError:
                    continue
        if not date:
            return None

        # 提取金额
        amount = None
        for pat in AMOUNT_PATTERNS:
            m = re.search(pat, line)
            if m:
                val = m.group(1).replace(",", "")
                try:
                    amount = float(val)
                    break
                except ValueError:
                    continue
        if amount is None or amount == 0:
            return None

        # 提取方向
        line_lower = line
        is_income = any(kw in line for kw in INCOME_KEYWORDS)
        is_expense = any(kw in line for kw in EXPENSE_KEYWORDS)

        if is_income and not is_expense:
            t_type = "income"
            signed = abs(amount)
        elif is_expense and not is_income:
            t_type = "expense"
            signed = -abs(amount)
        else:
            # 默认:有正负号则按符号,否则按绝对支出
            if amount < 0:
                t_type = "expense"
                signed = amount
            else:
                t_type = "expense"  # 大多数截图是支出
                signed = -amount

        # 商户/描述
        merchant = ""
        # 去掉日期和金额剩下的内容当作描述
        cleaned = re.sub(r"[¥￥]\s*-?\d+(?:[,.]\d+)*", "", line)
        cleaned = re.sub(r"\d{1,4}[-/年]\d{1,2}[-/月]?\d{0,2}[日]?", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            merchant = cleaned[:30]

        return Transaction(
            date=date,
            source="image",
            amount=signed,
            type=t_type,
            merchant=merchant,
            description=line,
        )