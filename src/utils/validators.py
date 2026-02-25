# -*- coding: utf-8 -*-
"""
验证工具
"""
import re
from urllib.parse import urlparse


def validate_email(email: str) -> bool:
    """
    验证邮箱格式

    Args:
        email: 邮箱地址

    Returns:
        是否有效
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """
    验证URL格式

    Args:
        url: URL地址

    Returns:
        是否有效
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except (TypeError, ValueError):
        return False


def validate_cron_expression(expr: str) -> bool:
    """
    验证Cron表达式格式

    Args:
        expr: Cron表达式 (分 时 日 月 周)

    Returns:
        是否有效
    """
    parts = expr.split()
    if len(parts) != 5:
        return False

    # 简单的格式检查
    for part in parts:
        if part == '*':
            continue
        # 检查数字范围
        if re.match(r'^\d+$', part):
            continue
        # 检查范围表达式
        if re.match(r'^\d+-\d+$', part):
            continue
        # 检查步长表达式
        if re.match(r'^\*/\d+$', part):
            continue
        # 检查列表表达式 (如 1,3,5)
        if re.match(r'^(\d+)(,\d+)*$', part):
            continue

        # 不匹配任何有效模式
        return False

    return True


def validate_phone_number(phone: str, region: str = 'CN') -> bool:
    """
    验证手机号格式

    Args:
        phone: 手机号
        region: 地区代码

    Returns:
        是否有效
    """
    if region == 'CN':
        # 中国大陆手机号
        pattern = r'^1[3-9]\d{9}$'
    else:
        # 通用格式
        pattern = r'^\+?[\d\s-]{8,}$'

    return bool(re.match(pattern, phone))
