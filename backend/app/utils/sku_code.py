"""
SKU 编码处理工具

- 统一口径：去掉中英文括号及括号内内容，并清理多余空白
"""

from __future__ import annotations

import re


_PAREN_CONTENT_RE = re.compile(r"[（(][^）)]*[）)]")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_sku_code(raw: str | None) -> str:
    """
    将商家编码清洗为“净编码”

    规则：
    - 去掉中英文括号及括号内内容：(...) / （...）
    - 去掉制表符
    - 去掉前后空格，并把中间连续空白压缩成单空格
    """
    if raw is None:
        return ""

    s = str(raw).replace("\t", "").strip()
    if not s or s == "nan":
        return ""

    s = _PAREN_CONTENT_RE.sub("", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


