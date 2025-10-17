# -*- coding: utf-8 -*-

import os
import sys

def resource_path(relative_path):
    """
    获取资源的绝对路径。
    这个函数非常重要，用于处理开发环境和打包后（PyInstaller）环境下资源文件的路径问题。
    """
    if getattr(sys, 'frozen', False):
        # 如果程序被打包成.exe文件，'frozen'属性会被PyInstaller设置成True
        # 此时，基准路径就是.exe文件所在的目录
        base_path = os.path.dirname(sys.executable)
    else:
        # 如果是作为.py脚本直接运行，基准路径就是当前脚本所在的目录
        base_path = os.path.abspath(".")
    # 返回拼接后的绝对路径
    return os.path.join(base_path, relative_path)
