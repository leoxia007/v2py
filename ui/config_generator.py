# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox
import customtkinter
import os
import sys
import json
import uuid

from core.constants import SOCKS_INBOUND_PORT, HTTP_INBOUND_PORT
from core.utils import resource_path

class ConfigGeneratorWindow(customtkinter.CTkToplevel):
    """
    配置生成器窗口。
    这是一个customtkinter的顶层窗口（CTkToplevel），用于创建新的v2ray配置文件。
    """
    def __init__(self, master, on_generate_success):
        super().__init__(master)
        self.master = master # master是主窗口的引用
        self.on_generate_success = on_generate_success

        self.title("配置生成器")
        self.geometry("480x480")
        self.transient(master) # 设置为master窗口的瞬态窗口，会显示在master窗口之上
        self.grab_set() # 独占输入焦点，在关闭此窗口前无法操作主窗口

        self.grid_columnconfigure(1, weight=1) # 配置网格布局，让第二列（输入框）可以随窗口拉伸

        # --- 基础设置 ---
        customtkinter.CTkLabel(self, text="文件名:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.filename_entry = customtkinter.CTkEntry(self)
        self.filename_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # --- 入站设置 ---
        customtkinter.CTkLabel(self, text="本地入站:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        customtkinter.CTkLabel(self, text="SOCKS (10808), HTTP (10809)").grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # --- 出站设置 ---
        customtkinter.CTkLabel(self, text="服务器地址:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.address_entry = customtkinter.CTkEntry(self)
        self.address_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        customtkinter.CTkLabel(self, text="端口:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.port_entry = customtkinter.CTkEntry(self)
        self.port_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        customtkinter.CTkLabel(self, text="UUID:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.uuid_entry = customtkinter.CTkEntry(self)
        self.uuid_entry.grid(row=4, column=1, padx=10, pady=5, sticky="ew")
        self.uuid_entry.insert(0, str(uuid.uuid4())) # 自动生成一个UUID并插入

        customtkinter.CTkLabel(self, text="传输协议:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.network_var = tk.StringVar(value="tcp")
        self.network_button = customtkinter.CTkSegmentedButton(self, values=["tcp", "ws"], variable=self.network_var, command=self._update_ws_path_visibility)
        self.network_button.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

        # --- WebSocket 路径 (条件显示) ---
        self.ws_path_label = customtkinter.CTkLabel(self, text="WebSocket 路径:")
        self.ws_path_entry = customtkinter.CTkEntry(self)
        self.ws_path_entry.insert(0, "/")

        # --- TLS 设置 ---
        customtkinter.CTkLabel(self, text="TLS:").grid(row=7, column=0, padx=10, pady=5, sticky="w")
        self.tls_var = tk.BooleanVar()
        self.tls_checkbox = customtkinter.CTkCheckBox(self, text="启用", variable=self.tls_var)
        self.tls_checkbox.grid(row=7, column=1, padx=10, pady=5, sticky="w")

        # --- 按钮 ---
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        self.generate_button = customtkinter.CTkButton(button_frame, text="生成", command=self.generate)
        self.generate_button.pack(side=tk.LEFT, padx=10)
        self.cancel_button = customtkinter.CTkButton(button_frame, text="取消", command=self.destroy)
        self.cancel_button.pack(side=tk.LEFT, padx=10)

        self._update_ws_path_visibility() # 初始化时检查一次是否需要显示ws路径输入框

    def _update_ws_path_visibility(self, value=None):
        """根据选择的传输协议，动态显示或隐藏WebSocket路径输入框"""
        if self.network_var.get() == "ws":
            self.ws_path_label.grid(row=6, column=0, padx=10, pady=5, sticky="w")
            self.ws_path_entry.grid(row=6, column=1, padx=10, pady=5, sticky="ew")
        else:
            self.ws_path_label.grid_forget()
            self.ws_path_entry.grid_forget()

    def generate(self):
        """根据用户输入生成v2ray配置文件"""
        # 获取用户输入并去除首尾空格
        filename = self.filename_entry.get().strip()
        address = self.address_entry.get().strip()
        port_str = self.port_entry.get().strip()
        user_uuid = self.uuid_entry.get().strip()

        # 校验输入
        if not all([filename, address, port_str, user_uuid]):
            messagebox.showwarning("警告", "文件名、地址、端口和UUID均为必填项。", parent=self)
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showwarning("警告", "端口必须是数字。", parent=self)
            return

        if not filename.lower().endswith('.json'):
            filename += '.json'

        # 决定配置文件的保存路径
        configs_dir = resource_path('configs')
        if not os.path.exists(configs_dir):
            os.makedirs(configs_dir)
        
        new_filepath = os.path.join(configs_dir, filename)

        if os.path.exists(new_filepath):
            messagebox.showwarning("警告", f"文件 {filename} 已存在。", parent=self)
            return

        config = self._build_config(address, port, user_uuid)

        try:
            # 将配置写入json文件
            with open(new_filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 调用回调函数通知主窗口
            self.on_generate_success(new_filepath)
            self.destroy() # 关闭生成器窗口
        except Exception as e:
            self.master.log_message(f"生成配置文件失败: {e}")
            messagebox.showerror("错误", f"生成配置文件失败: {e}", parent=self)

    def _build_config(self, address, port, user_uuid):
        """构建v2ray配置字典"""
        config = {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {"port": SOCKS_INBOUND_PORT, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True}},
                {"port": HTTP_INBOUND_PORT, "listen": "127.0.0.1", "protocol": "http", "settings": {"auth": "noauth"}}
            ],
            "outbounds": [
                {
                    "protocol": "vmess",
                    "settings": {
                        "vnext": [
                            {"address": address, "port": port, "users": [{"id": user_uuid, "alterId": 0}]}
                        ]
                    },
                    "streamSettings": {"network": self.network_var.get()}
                },
                {"protocol": "freedom", "tag": "direct"}
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [{"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"}]
            }
        }

        stream_settings = config["outbounds"][0]["streamSettings"]
        network = self.network_var.get()

        if network == "ws":
            stream_settings["wsSettings"] = {"path": self.ws_path_entry.get().strip()}

        if self.tls_var.get():
            stream_settings["security"] = "tls"
            stream_settings["tlsSettings"] = {"serverName": address}
        
        return config
