"""解析器工厂:自动识别并解析账单文件"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .base import BaseParser, Transaction
from .wechat import WeChatParser
from .alipay import AlipayParser
from .bank import BankParser
from .image_ocr import ImageOCRParser


ALL_PARSERS: list[BaseParser] = [
    WeChatParser(),
    AlipayParser(),
    BankParser(),
    ImageOCRParser(),
]


def parse_file(file_path: str) -> tuple[str, list[Transaction]]:
    """解析单个账单文件。返回 (源平台名, 交易列表)。
    若无人能解析,抛出 ValueError。"""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    for parser in ALL_PARSERS:
        if parser.can_parse(str(p)):
            txs = parser.parse(str(p))
            return parser.name, txs

    raise ValueError(
        f"无法识别 {p.name} 的格式。请确认:\n"
        f"  1. 文件为 CSV/Excel/图片\n"
        f"  2. 表头完整(微信/支付宝导出的标准格式)\n"
        f"  3. 图片 OCR 需要先安装 Tesseract"
    )


def auto_parse(file_paths: Iterable[str]) -> list[Transaction]:
    """批量解析多个账单文件,合并返回统一交易列表"""
    all_txs: list[Transaction] = []
    for fp in file_paths:
        try:
            source, txs = parse_file(fp)
            print(f"  [OK] {fp} -> {source}, 解析 {len(txs)} 条")
            all_txs.extend(txs)
        except Exception as e:
            print(f"  [FAIL] {fp} -> {e}")
    return all_txs