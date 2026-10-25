"""商户名归一化

跨平台合并时,同一家店在不同账单里的写法往往不一致:
    "美团外卖" / "美团-某某店" / "美团(国贸店)"
不归一化会让 TOP 商户统计分裂、订阅识别失效。

本模块只做**保守**归一(剥门店/公司后缀 + 品牌别名),不过度合并 ——
明细表仍然显示原始商户名,归一化结果只用于统计与识别。
"""
from __future__ import annotations

import re

# 品牌别名: 商户名中命中 key 时,统一替换为 value
MERCHANT_ALIASES: dict[str, str] = {
    "美团外卖": "美团",
    "瑞幸咖啡": "瑞幸",
    "luckin coffee": "瑞幸",
    "luckincoffee": "瑞幸",
    "京东商城": "京东",
    "滴滴出行": "滴滴",
    "顺丰快递": "顺丰",
    "星巴克咖啡": "星巴克",
    "starbucks": "星巴克",
    "肯德基": "肯德基",
    "kfc": "肯德基",
    "麦当劳": "麦当劳",
    "mcdonald": "麦当劳",
}

# 需要剥离的尾部公司字样(循环剥离,可命中多个)
_TAIL_NOISE = (
    "有限责任公司",
    "有限公司",
    "股份有限公司",
    "分公司",
    "连锁",
    "门店",
)

# 括号/方括号包裹的内容(通常是门店名或备注)
_BRACKET_RE = re.compile(r"[（(【\[][^）)】\]]{0,24}[）)】\]]")

# "-某某店" / "—某某分公司" 这类连字符后缀
_DASH_SUFFIX_RE = re.compile(r"\s*[-—–]\s*\S{1,16}$")

_WS_RE = re.compile(r"\s+")


def _halfwidth(s: str) -> str:
    """全角括号/连字符转半角,统一后续处理"""
    return (
        s.replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("—", "-")
        .replace("–", "-")
    )


def normalize_merchant(name: str) -> str:
    """把商户名归一化到品牌级。

    处理顺序: 压缩空白 → 剥 "-某某店" → 剥括号内容 → 剥公司后缀 → 别名替换。
    剥后缀时保留至少 2 个字符,避免把 "7-11" 削成 "7"。
    """
    if not name:
        return ""

    s = _halfwidth(str(name)).strip()
    s = _WS_RE.sub(" ", s)
    if not s:
        return ""

    # 连字符后缀: 剩余部分太短就不剥
    m = _DASH_SUFFIX_RE.search(s)
    if m and len(s[: m.start()].strip()) >= 2:
        s = s[: m.start()].strip()

    # 括号内容(可能有多个)
    s = _BRACKET_RE.sub("", s).strip()

    # 公司后缀,循环剥
    changed = True
    while changed:
        changed = False
        for tail in _TAIL_NOISE:
            if s.endswith(tail) and len(s) > len(tail) + 1:
                s = s[: -len(tail)].strip()
                changed = True

    # 别名替换: key 长的优先,保证"美团外卖"先于"美团"匹配
    low = s.lower()
    for key in sorted(MERCHANT_ALIASES, key=len, reverse=True):
        if key.lower() in low:
            return MERCHANT_ALIASES[key]

    return s


def normalize_dataframe(df):
    """给 DataFrame 增加 merchant_norm 列(归一化商户名)。

    原始 merchant 列保持不变,明细表仍显示用户熟悉的写法。
    """
    if df.empty:
        df["merchant_norm"] = []
        return df

    df["merchant_norm"] = df["merchant"].astype(str).map(normalize_merchant)
    # 归一化后为空的(如商户名只有括号)退回原始值
    blank = df["merchant_norm"].str.len() == 0
    if blank.any():
        df.loc[blank, "merchant_norm"] = df.loc[blank, "merchant"].astype(str)
    return df
