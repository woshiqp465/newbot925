"""
Bytes处理工具 - 统一处理所有bytes和字符串转换
"""
from typing import Union, Optional


def bytes_to_hex(data: Optional[Union[bytes, str]]) -> Optional[str]:
    """bytes转hex字符串；字符串保持原样"""
    if data is None:
        return None
    if isinstance(data, bytes):
        return data.hex()
    return str(data)


def hex_to_bytes(hex_str: Optional[Union[str, bytes]]) -> Optional[bytes]:
    """hex字符串转bytes，不可解析时返回原始字节"""
    if hex_str is None:
        return None
    if isinstance(hex_str, bytes):
        return hex_str
    try:
        return bytes.fromhex(hex_str)
    except (ValueError, TypeError):
        if isinstance(hex_str, str):
            return hex_str.encode("utf-8")
        return bytes(hex_str)


def safe_callback_data(callback_data: Optional[Union[str, bytes]]) -> Optional[str]:
    """安全处理callback_data，统一转为hex便于存储"""
    return bytes_to_hex(callback_data)


def restore_callback_data(hex_str: Optional[Union[str, bytes]]) -> Optional[bytes]:
    """恢复callback_data为bytes"""
    return hex_to_bytes(hex_str)
