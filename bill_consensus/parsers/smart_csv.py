"""智能 CSV/Excel 读取器
解决三大痛点:
  1. 编码乱码: 微信/支付宝/银行账单编码各异(UTF-8/GBK/UTF-16...)
  2. 前置说明行: 支付宝/银行导出的 CSV 前面往往有 5~20 行免责声明
  3. 表头定位: 不同平台表头列名不同,自动找到真正的数据起始行

用法:
    from .smart_csv import smart_read_csv
    df = smart_read_csv("你的账单.csv")
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd


# 编码候选(按国内账单常见程度排序)
ENCODINGS = [
    "utf-8-sig",   # 带 BOM 的 UTF-8 (微信/支付宝网页导出)
    "utf-8",       # 标准 UTF-8
    "gb18030",     # GBK 超集,兼容 GBK/GB2312 (银行/支付宝客户端)
    "gbk",
    "big5",        # 繁体
    "utf-16",      # 少数银行
    "latin-1",     # 兜底(不报错,但中文可能乱码)
]


def detect_encoding(file_path: str | Path, probe_bytes: int = 8192) -> str:
    """探测文件编码。读前 N 字节,优先选能解出中文关键词的编码。"""
    path = Path(file_path)
    raw = path.open("rb").read(probe_bytes)

    # 1. BOM 快速判定
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"

    # 2. 逐个编码试解,优先含中文关键字的
    keywords = ["交易", "金额", "时间", "账单", "日期", "收", "支"]
    best_fallback = None
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if any(kw in text for kw in keywords):
            return enc
        if best_fallback is None:
            best_fallback = enc
    return best_fallback or "utf-8"


def find_header_row(file_path: str | Path, encoding: str) -> int:
    """定位真正的表头行(跳过前面的说明/免责声明)。

    判定标准: 某行同时含"时间/日期"类字段 AND "金额/收支"类字段,
    且该行用逗号分隔后至少 3 列。
    """
    path = Path(file_path)
    with path.open("r", encoding=encoding, errors="replace") as f:
        for line_idx, line in enumerate(f):
            if line_idx > 50:  # 超过 50 行还没找到,放弃
                break
            line = line.strip()
            if not line or len(line) < 10:
                continue
            cols = [c.strip().strip('"') for c in line.split(",")]
            if len(cols) < 3:
                continue
            has_time = any(("时间" in c) or ("日期" in c) or ("Date" in c) for c in cols)
            has_amount = any(
                ("金额" in c) or ("收支" in c) or ("收/支" in c) or ("Amount" in c)
                for c in cols
            )
            if has_time and has_amount:
                return line_idx
    return 0  # 找不到就从头读,让 pandas 报错


def smart_read_csv(file_path: str | Path, **pandas_kwargs) -> pd.DataFrame:
    """智能读取账单 CSV。

    自动: 编码检测 → 表头行定位 → pandas 读入。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    enc = detect_encoding(path)
    header_row = find_header_row(path, enc)

    # 尝试读入,失败则降级重试
    last_err = None
    # index_col=False: 防止数据行比表头多列(如支付宝行尾逗号)时,pandas 误把第一列当索引
    read_kwargs = {"index_col": False, **pandas_kwargs}
    for try_enc in [enc] + [e for e in ENCODINGS if e != enc]:
        for try_skip in [header_row] + ([0] if header_row != 0 else []):
            try:
                df = pd.read_csv(path, encoding=try_enc, skiprows=try_skip, **read_kwargs)
                # 基本有效性检查:至少 2 列
                if df.shape[1] >= 2 and not df.empty:
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
            except Exception as e:
                last_err = e
                continue

    raise ValueError(
        f"无法解析 {path.name}: 尝试了 {len(ENCODINGS)} 种编码都失败。\n"
        f"最后错误: {last_err}\n"
        f"建议: 用 Excel 打开该文件,另存为 'CSV UTF-8' 格式后重试。"
    )


def smart_read_excel(file_path: str | Path, **pandas_kwargs) -> pd.DataFrame:
    """智能读取 Excel 账单(自动跳过前置说明行)。"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    # 先读一次看看表头在哪
    probe = pd.read_excel(path, header=None, nrows=60, **pandas_kwargs)
    header_row = 0
    for idx, row in probe.iterrows():
        cells = [str(c).strip() for c in row.tolist()]
        has_time = any(("时间" in c) or ("日期" in c) for c in cells if c and c != "nan")
        has_amount = any(("金额" in c) or ("收支" in c) or ("收/支" in c) for c in cells if c and c != "nan")
        if has_time and has_amount:
            header_row = idx
            break

    df = pd.read_excel(path, skiprows=header_row if header_row else 0, **pandas_kwargs)
    df.columns = [str(c).strip() for c in df.columns]
    return df