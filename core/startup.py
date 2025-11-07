# -*- coding: utf-8 -*-

import sys
import winreg
from .constants import APP_NAME

def set_startup(enable):
    """启用或禁用应用程序在系统启动时运行。"""
    app_path = sys.executable
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{app_path}"')
                print(f"设置启动项: {app_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("已删除启动项。")
                except FileNotFoundError:
                    pass  # 如果我们正在禁用它，则找不到键是正常的。
    except Exception as e:
        print(f"修改启动注册表失败: {e}")
