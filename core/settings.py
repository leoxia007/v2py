# -*- coding: utf-8 -*-

import os
import json
from .constants import APP_NAME, SETTINGS_FILE

def get_persistent_data_path(filename):
    """
    获取用于存储持久化数据的文件路径（例如，上次使用的配置文件路径）。
    这样即使用户移动了程序位置，配置也能得到保留。
    """
    # 在Windows上，APPDATA环境变量指向用户的应用数据目录，是一个可靠的存储位置
    app_data_dir = os.getenv('APPDATA')
    if not app_data_dir:
        # 如果获取APPDATA失败，退而求其次，使用用户的主目录
        app_data_dir = os.path.expanduser('~')

    # 在APPDATA目录下为我们的应用创建一个专属的文件夹
    persistent_dir = os.path.join(app_data_dir, APP_NAME)
    if not os.path.exists(persistent_dir):
        os.makedirs(persistent_dir)

    # 返回在应用专属文件夹下的文件路径
    return os.path.join(persistent_dir, filename)

def get_app_settings_path():
    """获取应用程序设置文件的路径。"""
    return get_persistent_data_path(SETTINGS_FILE)

def load_app_settings():
    """从设置文件加载应用程序设置。"""
    settings_path = get_app_settings_path()
    default_settings = {
        "run_on_startup": False,
        "auto_start_v2ray": False,
        "enable_proxy_hotkey": "<alt>+z",
        "disable_proxy_hotkey": "<alt>+x"
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # 确保所有默认键都存在
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载设置时出错，使用默认设置: {e}")
            return default_settings
    else:
        return default_settings

def save_app_settings(settings):
    """将应用程序设置保存到设置文件。"""
    settings_path = get_app_settings_path()
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except IOError as e:
        print(f"保存设置时出错: {e}")
