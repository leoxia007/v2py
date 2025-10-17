# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox
import customtkinter
from pynput import keyboard

from core.settings import save_app_settings

class HotkeySettingsWindow(customtkinter.CTkToplevel):
    """
    快捷键设置窗口
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.title("快捷键设置")
        self.geometry("400x200")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(self, text="全局快捷键设置").grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        customtkinter.CTkLabel(self, text="启用系统代理:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.enable_hotkey_entry = customtkinter.CTkEntry(self, width=150)
        self.enable_hotkey_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        self.enable_hotkey_entry.insert(0, self.master.settings.get("enable_proxy_hotkey", "<ctrl>+<alt>+e"))

        customtkinter.CTkLabel(self, text="清除系统代理:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.disable_hotkey_entry = customtkinter.CTkEntry(self, width=150)
        self.disable_hotkey_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        self.disable_hotkey_entry.insert(0, self.master.settings.get("disable_proxy_hotkey", "<ctrl>+<alt>+d"))

        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        self.save_button = customtkinter.CTkButton(button_frame, text="保存", command=self.save_hotkeys)
        self.save_button.pack(side=tk.LEFT, padx=10)
        self.cancel_button = customtkinter.CTkButton(button_frame, text="取消", command=self.destroy)
        self.cancel_button.pack(side=tk.LEFT, padx=10)

    def save_hotkeys(self):
        """保存快捷键设置"""
        enable_hotkey = self.enable_hotkey_entry.get().strip()
        disable_hotkey = self.disable_hotkey_entry.get().strip()

        if not enable_hotkey or not disable_hotkey:
            messagebox.showwarning("警告", "快捷键不能为空。", parent=self)
            return
        
        try:
            # 在保存前验证快捷键
            keyboard.HotKey.parse(enable_hotkey)
            keyboard.HotKey.parse(disable_hotkey)
        except Exception as e:
            messagebox.showerror("快捷键错误", f"无法解析快捷键，请检查格式（例如 '<ctrl>+<alt>+e'）。\n错误: {e}", parent=self)
            return

        self.master.settings["enable_proxy_hotkey"] = enable_hotkey
        self.master.settings["disable_proxy_hotkey"] = disable_hotkey
        save_app_settings(self.master.settings)
        self.master.log_message("快捷键已保存。正在重新加载快捷键...")
        
        # 重新设置快捷键
        self.master.setup_hotkeys()
        
        messagebox.showinfo("成功", "快捷键已更新。", parent=self)
        self.destroy()
