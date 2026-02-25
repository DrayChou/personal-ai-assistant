# -*- coding: utf-8 -*-
"""
通用辅助函数
"""
import hashlib
import uuid
from datetime import datetime


def generate_id(prefix: str = "") -> str:
    """
    生成唯一ID

    Args:
        prefix: ID前缀

    Returns:
        唯一标识符
    """
    unique = uuid.uuid4().hex[:16]
    if prefix:
        return f"{prefix}_{unique}"
    return unique


def format_timestamp(dt: datetime | None = None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """
    格式化时间戳

    Args:
        dt: 时间对象，默认为当前时间
        fmt: 格式字符串

    Returns:
        格式化后的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(fmt)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def compute_hash(text: str, algorithm: str = "md5") -> str:
    """
    计算文本哈希

    Args:
        text: 输入文本
        algorithm: 哈希算法 (md5, sha256)

    Returns:
        哈希值
    """
    encoded = text.encode('utf-8')
    if algorithm == "md5":
        return hashlib.md5(encoded).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(encoded).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")


def estimate_tokens(text: str) -> int:
    """
    估算文本的token数量

    简单估算：中文约1.5字符/token，英文约4字符/token

    Args:
        text: 输入文本

    Returns:
        估算的token数
    """
    if not text:
        return 0

    # 统计中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars

    # 中文字符按1.5字符/token，其他按4字符/token
    chinese_tokens = chinese_chars / 1.5
    other_tokens = other_chars / 4

    return int(chinese_tokens + other_tokens)


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename.strip()
