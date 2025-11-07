# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import threading
import sys
import time
import urllib.request
import socket
import base64
import io

import customtkinter
import pystray
from pynput import keyboard
from PIL import Image, ImageDraw, ImageFont

from icon_data import get_icon_base64
from core.constants import V2RAY_CORE_PATH, HTTP_INBOUND_PORT, DEFAULT_CONFIG_PATH
from core.settings import load_app_settings, save_app_settings, get_persistent_data_path
from core.utils import resource_path
from core.startup import set_startup
from core.v2ray_manager import V2rayManager
from core.proxy_manager import ProxyManager

from ui.config_generator import ConfigGeneratorWindow
from ui.hotkey_settings import HotkeySettingsWindow

class V2rayClientApp(customtkinter.CTk):
    """
    主应用窗口类。
    继承自customtkinter.CTk，是整个应用的UI入口。
    """
    def __init__(self, master=None):
        super().__init__()
        self.current_config_path = ""
        self.generator_window = None # 用于持有配置生成器窗口的引用
        self.hotkey_window = None # 用于持有快捷键设置窗口的引用

        self.title("V2fly 客户端")
        self.geometry("800x600")

        # 设置UI主题
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")
        
        # 初始化V2Ray管理器
        self.v2ray_manager = V2rayManager(self.log_message_from_thread)

        # 初始化代理管理器
        self.proxy_manager = ProxyManager(self.log_message_from_thread)

        # 加载应用设置
        self.settings = load_app_settings()

        self.create_widgets() # 创建UI组件
        self._setup_tray_icon() # 设置系统托盘图标

        if self.settings.get("run_on_startup"):
            self.run_on_startup_check.select()
        if self.settings.get("auto_start_v2ray"):
            self.auto_start_v2ray_check.select()

        # 加载上次使用的配置文件
        last_path = self.load_last_config_path()
        if last_path:
            self.current_config_path = last_path
            self.config_path_label.configure(text=self.current_config_path)
            self.log_message(f"已加载上次使用的配置文件: {self.current_config_path}")
            self.load_config_to_editor(self.current_config_path)
            self.start_button.configure(state="normal")
            self.test_latency_button.configure(state="normal")
        else:
            self.load_default_config() # 如果没有上次的配置，就加载默认配置

        if not self.current_config_path:
            self.start_button.configure(state="disabled")
            self.test_latency_button.configure(state="disabled")

        # 检查是否需要自动启动V2Ray
        if self.settings.get("auto_start_v2ray") and self.current_config_path:
            self.start_v2ray()

        # 在一个单独的线程中运行托盘图标，防止UI阻塞
        if self.icon:
            threading.Thread(target=self.icon.run, daemon=True).start()

        # 设置全局快捷键
        self.hotkey_listener = None
        self.setup_hotkeys()

    def create_widgets(self):
        """创建主窗口的所有UI组件"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_top_frame()
        self._create_log_and_editor_frames()

    def _create_top_frame(self):
        """创建包含所有控制和设置的顶部框架"""
        top_frame = customtkinter.CTkFrame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(0, weight=1)

        # --- Row 0: Config Path ---
        config_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
        config_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        config_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(config_frame, text="配置文件:").grid(row=0, column=0, sticky="w")
        self.config_path_label = customtkinter.CTkLabel(config_frame, text="未选择", anchor="w")
        self.config_path_label.grid(row=0, column=1, sticky="ew", padx=10)
        
        self.select_config_button = customtkinter.CTkButton(config_frame, text="选择配置", command=self.select_config_file, width=100)
        self.select_config_button.grid(row=0, column=2, padx=(0, 5))

        self.generate_config_button = customtkinter.CTkButton(config_frame, text="生成配置", command=self.open_generator_window, width=100)
        self.generate_config_button.grid(row=0, column=3)

        # --- Row 1: Main Actions ---
        main_actions_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
        main_actions_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        self.start_button = customtkinter.CTkButton(main_actions_frame, text="启动 V2ray", command=self.start_v2ray, fg_color="green", hover_color="#008000")
        self.start_button.grid(row=0, column=0, padx=(0, 5))

        self.stop_button = customtkinter.CTkButton(main_actions_frame, text="停止 V2ray", command=self.stop_v2ray, fg_color="red", hover_color="#800000", state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5)

        self.test_latency_button = customtkinter.CTkButton(main_actions_frame, text="测试延迟", command=self.test_latency, state="disabled")
        self.test_latency_button.grid(row=0, column=2, padx=5)

        self.test_speed_button = customtkinter.CTkButton(main_actions_frame, text="测试速度", command=self.test_speed, state="disabled")
        self.test_speed_button.grid(row=0, column=3, padx=5)

        main_actions_frame.grid_columnconfigure(4, weight=1)
        self.minimize_button = customtkinter.CTkButton(main_actions_frame, text="最小化到托盘", command=self._hide_window)
        self.minimize_button.grid(row=0, column=5, sticky="e")

        # --- Row 2: Settings ---
        settings_container = customtkinter.CTkFrame(top_frame)
        settings_container.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 10))
        settings_container.grid_columnconfigure(1, weight=1)

        # App Settings
        app_settings_frame = customtkinter.CTkFrame(settings_container, fg_color="transparent")
        app_settings_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=5)
        
        customtkinter.CTkLabel(app_settings_frame, text="应用设置", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=(0,5))
        self.run_on_startup_check = customtkinter.CTkCheckBox(app_settings_frame, text="开机自启动", command=self.toggle_run_on_startup)
        self.run_on_startup_check.grid(row=1, column=0, sticky="w")
        self.auto_start_v2ray_check = customtkinter.CTkCheckBox(app_settings_frame, text="自动启动v2ray", command=self.toggle_auto_start_v2ray)
        self.auto_start_v2ray_check.grid(row=2, column=0, sticky="w", pady=(5,0))

        # Proxy Settings
        proxy_frame = customtkinter.CTkFrame(settings_container, fg_color="transparent")
        proxy_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=5)
        proxy_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(proxy_frame, text="系统代理设置", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))
        self.proxy_enable_check = customtkinter.CTkCheckBox(proxy_frame, text="启用系统代理", command=self.toggle_proxy_fields)
        self.proxy_enable_check.grid(row=1, column=0, columnspan=2, sticky="w")

        proxy_address_frame = customtkinter.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_address_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        proxy_address_frame.grid_columnconfigure(1, weight=1)
        customtkinter.CTkLabel(proxy_address_frame, text="代理地址:").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.proxy_address_entry = customtkinter.CTkEntry(proxy_address_frame)
        self.proxy_address_entry.grid(row=0, column=1, sticky="ew")
        self.proxy_address_entry.insert(0, f"127.0.0.1:{HTTP_INBOUND_PORT}")

        proxy_buttons_frame = customtkinter.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_buttons_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.apply_proxy_button = customtkinter.CTkButton(proxy_buttons_frame, text="应用", command=self.apply_system_proxy, width=60)
        self.apply_proxy_button.grid(row=0, column=0)
        self.clear_proxy_button = customtkinter.CTkButton(proxy_buttons_frame, text="清除", command=self.clear_system_proxy, width=60)
        self.clear_proxy_button.grid(row=0, column=1, padx=5)
        proxy_buttons_frame.grid_columnconfigure(2, weight=1)
        self.hotkey_settings_button = customtkinter.CTkButton(proxy_buttons_frame, text="快捷键...", command=self.open_hotkey_window)
        self.hotkey_settings_button.grid(row=0, column=3, sticky="e")

        self.toggle_proxy_fields()

    def _create_log_and_editor_frames(self):
        """创建可调整大小的日志和编辑器区域"""
        paned_window = tk.PanedWindow(self, orient=tk.VERTICAL, sashrelief=tk.RAISED, bg="gray")
        paned_window.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Log frame
        log_frame = customtkinter.CTkFrame(paned_window, corner_radius=0)
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        customtkinter.CTkLabel(log_frame, text="日志输出:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        self.log_text = customtkinter.CTkTextbox(log_frame, wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.log_text.configure(state="disabled")
        paned_window.add(log_frame, height=150) # Initial height

        # Editor frame
        editor_frame = customtkinter.CTkFrame(paned_window, corner_radius=0)
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(1, weight=1)
        
        editor_label_frame = customtkinter.CTkFrame(editor_frame, fg_color="transparent")
        editor_label_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        editor_label_frame.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(editor_label_frame, text="配置文件内容 (可编辑):").grid(row=0, column=0, sticky="w")
        self.save_config_button = customtkinter.CTkButton(editor_label_frame, text="保存更改", command=self.save_config_file)
        self.save_config_button.grid(row=0, column=1)

        self.config_editor = customtkinter.CTkTextbox(editor_frame, wrap="word")
        self.config_editor.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.config_editor.configure(state="normal")
        paned_window.add(editor_frame)

    def log_message(self, message):
        """在UI的日志区域显示一条消息"""
        self.log_text.configure(state="normal") # 临时设为可编辑以插入文本
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end") # 滚动到末尾
        self.log_text.configure(state="disabled") # 恢复为不可编辑

    def select_config_file(self):
        """弹出文件选择对话框，让用户选择一个配置文件"""
        file_path = filedialog.askopenfilename(title="选择 v2ray 配置文件", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            self.current_config_path = file_path
            self.config_path_label.configure(text=self.current_config_path)
            self.log_message(f"已选择配置文件: {self.current_config_path}")
            self.load_config_to_editor(self.current_config_path)
            self.save_last_config_path(self.current_config_path)
            self.start_button.configure(state="normal")
            self.test_latency_button.configure(state="normal")
        else:
            self.log_message("未选择配置文件。 ")
            self.start_button.configure(state="disabled")
            self.test_latency_button.configure(state="disabled")

    def open_generator_window(self):
        """打开配置生成器窗口"""
        if self.generator_window is None or not self.generator_window.winfo_exists():
            self.generator_window = ConfigGeneratorWindow(self, on_generate_success=self.handle_config_generated)
        else:
            self.generator_window.focus() # 如果已存在，则将其带到前台

    def open_hotkey_window(self):
        """打开快捷键设置窗口"""
        if self.hotkey_window is None or not self.hotkey_window.winfo_exists():
            self.hotkey_window = HotkeySettingsWindow(self)
        else:
            self.hotkey_window.focus()

    def save_config_file(self):
        """保存对配置文件的修改"""
        if not self.current_config_path:
            messagebox.showwarning("警告", "没有加载任何配置文件，无法保存。" )
            return

        content = self.config_editor.get("1.0", "end-1c") # 获取编辑器中的所有文本
        try:
            json.loads(content) # 校验是否为有效的JSON
            with open(self.current_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.log_message(f"配置文件已成功保存到: {self.current_config_path}")
            messagebox.showinfo("成功", "配置文件已保存。" )
        except json.JSONDecodeError:
            self.log_message("保存失败: 配置文件内容不是有效的JSON格式。" )
            messagebox.showerror("错误", "保存失败: 配置文件内容不是有效的JSON格式。" )
        except Exception as e:
            self.log_message(f"保存配置文件失败: {e}")
            messagebox.showerror("错误", f"保存配置文件失败: {e}")

    def load_config_to_editor(self, path):
        """从文件加载配置内容到编辑器中"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # 先用json.load解析，再用json.dumps格式化，确保显示美观
                config_content = json.dumps(json.load(f), indent=2, ensure_ascii=False)
            self.config_editor.configure(state="normal")
            self.config_editor.delete("1.0", "end")
            self.config_editor.insert("end", config_content)
        except Exception as e:
            self.log_message(f"加载配置文件失败: {e}")
            self.config_editor.configure(state="normal")
            self.config_editor.delete("1.0", "end")
            self.config_editor.insert("end", f"无法加载配置文件: {e}")

    def load_default_config(self):
        """加载默认的配置文件"""
        default_config_path = resource_path(DEFAULT_CONFIG_PATH)
        if os.path.exists(default_config_path):
            self.current_config_path = default_config_path
            self.config_path_label.configure(text=self.current_config_path)
            self.log_message(f"已加载默认配置文件: {self.current_config_path}")
            self.load_config_to_editor(self.current_config_path)
            self.start_button.configure(state="normal")
            self.test_latency_button.configure(state="normal")
        else:
            self.log_message("未找到默认配置文件 (configs/default.json)。")
            self.start_button.configure(state="disabled")
            self.test_latency_button.configure(state="disabled")

    def handle_config_generated(self, new_filepath):
        """Callback function for when a new config is generated."""
        self.log_message(f"成功生成配置文件: {new_filepath}")
        self.current_config_path = new_filepath
        self.config_path_label.configure(text=self.current_config_path)
        self.load_config_to_editor(self.current_config_path)
        self.save_last_config_path(self.current_config_path)
        self.start_button.configure(state="normal")
        self.test_latency_button.configure(state="normal")

    def log_message_from_thread(self, message):
        """从后台线程安全地记录消息到UI"""
        self.after(0, self.log_message, message)

    def start_v2ray(self):
        """启动v2ray核心进程"""
        if not self.current_config_path:
            messagebox.showwarning("警告", "请先选择 v2ray 配置文件！")
            return
        if self.v2ray_manager.is_running():
            messagebox.showinfo("信息", "V2ray 已经在运行中")
            return

        # 将UI更新回调传递给管理器
        on_exit_callback = lambda: self.after(0, self._on_v2ray_stopped)
        
        if self.v2ray_manager.start(self.current_config_path, on_exit_callback):
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.test_latency_button.configure(state="disabled") # 启动时禁用延迟测试
            self.test_speed_button.configure(state="normal")
        else:
            # 如果启动失败，确保UI状态正确
            self._on_v2ray_stopped()

    def stop_v2ray(self):
        """停止v2ray核心进程"""
        if not self.v2ray_manager.is_running():
            self.log_message("V2ray 未运行")
            self._on_v2ray_stopped() # 确保UI状态一致
            return
        
        self.v2ray_manager.stop()
        # on_exit_callback 将在进程真正退出后更新UI

    def _on_v2ray_stopped(self):
        """当v2ray停止后，更新UI按钮的状态"""
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.test_speed_button.configure(state="disabled")
        if self.current_config_path:
            self.test_latency_button.configure(state="normal")
        else:
            self.test_latency_button.configure(state="disabled")

    def test_latency(self):
        """启动延迟测试线程"""
        if not self.current_config_path:
            self.log_message("错误: 未选择配置文件，无法测试延迟。" )
            return
        
        self.log_message("正在测试延迟...")
        self.test_latency_button.configure(state="disabled")
        
        # 从主线程获取配置内容
        config_content = self.config_editor.get("1.0", "end-1c")
        
        # 将配置内容传递给后台线程
        threading.Thread(target=self._run_latency_test_in_thread, args=(config_content,), daemon=True).start()

    def _run_latency_test_in_thread(self, config_content):
        """在后台线程中通过TCP ping测试延迟"""
        address, port, _ = self._get_config_details(config_content)

        if not address or not port:
            self.after(0, self.log_message, "延迟测试失败: 在配置中找不到服务器地址或端口。" )
            self.after(0, lambda: self.test_latency_button.configure(state="normal") )
            return

        try:
            # 2. 使用socket进行TCP连接测试
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10) # 10秒超时
            
            start_time = time.time()
            sock.connect((address, port))
            end_time = time.time()
            sock.close()

            latency_ms = (end_time - start_time) * 1000
            self.after(0, self.log_message, f"TCP Ping 测试成功: 延迟 {latency_ms:.2f} ms")

        except socket.timeout:
            self.after(0, self.log_message, f"延迟测试失败: 连接服务器 {address}:{port} 超时。" )
        except ConnectionRefusedError:
            self.after(0, self.log_message, f"延迟测试失败: 连接服务器 {address}:{port} 被拒绝。" )
        except socket.gaierror:
            self.after(0, self.log_message, f"延迟测试失败: 无法解析服务器地址 {address}。" )
        except Exception as e:
            self.after(0, self.log_message, f"延迟测试出错: {e}")
        finally:
            # 无论成功与否，测试结束后都重新启用按钮
            if not self.v2ray_manager.is_running():
                 self.after(0, lambda: self.test_latency_button.configure(state="normal") )

    def _get_config_details(self, config_content):
        """从配置内容中解析服务器地址、端口和HTTP端口"""
        address, port, http_port = None, None, None
        try:
            config = json.loads(config_content)
            # 解析出站服务器信息
            for outbound in config.get("outbounds", []):
                if outbound.get("protocol") in ["vmess", "vless"]:
                    vnext = outbound.get("settings", {}).get("vnext", [])
                    if vnext:
                        address = vnext[0].get("address")
                        port = vnext[0].get("port")
                        break  # 找到第一个就停止
            # 解析入站HTTP端口
            for inbound in config.get("inbounds", []):
                if inbound.get("protocol") == "http":
                    http_port = inbound.get("port")
                    break
        except json.JSONDecodeError:
            self.after(0, self.log_message, "解析配置文件失败。" )
        return address, port, http_port

    def test_speed(self):
        """启动速度测试线程"""
        if not self.v2ray_manager.is_running():
            self.log_message("错误: V2ray 未运行，无法测试速度。" )
            return
            
        self.log_message("正在测试下载速度... (可能需要一些时间)")
        self.test_speed_button.configure(state="disabled")
        
        # 从主线程获取配置内容
        config_content = self.config_editor.get("1.0", "end-1c")
        
        # 将配置内容传递给后台线程
        threading.Thread(target=self._run_speed_test_in_thread, args=(config_content,), daemon=True).start()

    def _run_speed_test_in_thread(self, config_content):
        """在后台线程中运行下载速度测试"""
        _, _, http_port = self._get_config_details(config_content)

        if not http_port:
            self.after(0, self.log_message, "速度测试失败: 在配置中找不到 HTTP 入站端口。" )
            self.after(0, lambda: self.test_speed_button.configure(state="normal") )
            return

        try:
            proxy_address = f'127.0.0.1:{http_port}'
            proxy_handler = urllib.request.ProxyHandler({'http': proxy_address, 'https': proxy_address})
            opener = urllib.request.build_opener(proxy_handler)
            
            test_url = 'http://cachefly.cachefly.net/10mb.test'
            self.after(0, self.log_message, f"将从 {test_url} 下载文件进行测试...")

            start_time = time.time()
            
            with opener.open(test_url, timeout=60) as response:
                downloaded_bytes = 0
                chunk_size = 8192
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    downloaded_bytes += len(chunk)

            end_time = time.time()
            duration = end_time - start_time

            if duration > 0:
                speed_bps = (downloaded_bytes * 8) / duration
                speed_mbps = speed_bps / (1024 * 1024)
                self.after(0, self.log_message, f"测试完成: 下载速度约为 {speed_mbps:.2f} Mbps")
            else:
                self.after(0, self.log_message, "速度测试失败: 下载时间过短无法计算。" )

        except urllib.error.URLError as e:
            self.after(0, self.log_message, f"速度测试失败: 网络错误 - {e}")
        except Exception as e:
            self.after(0, self.log_message, f"速度测试出错: {e}")
        finally:
            if self.v2ray_manager.is_running():
                self.after(0, lambda: self.test_speed_button.configure(state="normal") )

    def setup_hotkeys(self):
        """设置并启动全局快捷键监听器"""
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception as e:
                self.log_message(f"停止旧的快捷键监听器时出错: {e}")

        enable_hotkey = self.settings.get("enable_proxy_hotkey", "<ctrl>+<alt>+e")
        disable_hotkey = self.settings.get("disable_proxy_hotkey", "<ctrl>+<alt>+d")

        def on_activate_enable():
            self.log_message("检测到启用代理快捷键。" )
            self.after(0, self.apply_system_proxy_hotkey)

        def on_activate_disable():
            self.log_message("检测到清除代理快捷键。" )
            self.after(0, self.clear_system_proxy)

        try:
            # 验证快捷键组合
            keyboard.HotKey.parse(enable_hotkey)
            keyboard.HotKey.parse(disable_hotkey)
            
            hotkeys = {
                enable_hotkey: on_activate_enable,
                disable_hotkey: on_activate_disable
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.start()
            self.log_message(f"已设置快捷键: 启用代理({enable_hotkey}), 清除代理({disable_hotkey})")
        except Exception as e:
            self.log_message(f"设置快捷键失败: {e}")
            messagebox.showerror("快捷键错误", f"无法解析快捷键，请检查格式（例如 '<ctrl>+<alt>+e'）。\n错误: {e}")

    def apply_system_proxy_hotkey(self):
        """通过快捷键应用系统代理"""
        self.proxy_enable_check.select()
        self.toggle_proxy_fields()
        self.apply_system_proxy()

    def on_closing(self):
        """处理点击窗口关闭按钮的事件"""
        if messagebox.askokcancel("退出", "确定要退出客户端吗？V2ray 进程将会被停止。" ):
            if self.hotkey_listener:
                self.hotkey_listener.stop()
            self.stop_v2ray()
            self.destroy() # 销毁窗口并退出程序
        else:
            self._hide_window() # 如果选择“取消”，则最小化到托盘

    def toggle_run_on_startup(self):
        """切换开机自启动设置。"""
        is_enabled = self.run_on_startup_check.get()
        self.settings["run_on_startup"] = is_enabled
        save_app_settings(self.settings)
        set_startup(is_enabled)
        self.log_message(f"开机自启动已 {'启用' if is_enabled else '禁用'}。" )

    def toggle_auto_start_v2ray(self):
        """切换自动启动V2Ray的设置。"""
        is_enabled = self.auto_start_v2ray_check.get()
        self.settings["auto_start_v2ray"] = is_enabled
        save_app_settings(self.settings)
        self.log_message(f"自动启动 V2Ray 已 {'启用' if is_enabled else '禁用'}。" )

    def toggle_proxy_fields(self):
        """根据“启用系统代理”复选框的状态，启用或禁用下方的输入框和按钮"""
        enabled = self.proxy_enable_check.get()
        self.proxy_address_entry.configure(state="normal" if enabled else "disabled")
        self.apply_proxy_button.configure(state="normal" if enabled else "disabled")

    def apply_system_proxy(self):
        """应用系统代理设置"""
        proxy_address = self.proxy_address_entry.get().strip()
        if not proxy_address:
            messagebox.showwarning("警告", "代理地址不能为空！")
            return
        if self.proxy_enable_check.get():
            self.proxy_manager.set_proxy(proxy_address)
        else:
            self.proxy_manager.clear_proxy()

    def clear_system_proxy(self):
        """清除系统代理设置"""
        self.proxy_enable_check.deselect()
        self.toggle_proxy_fields()
        self.proxy_manager.clear_proxy()

    def save_last_config_path(self, path):
        """将最后一次使用的配置文件路径保存到文件中"""
        try:
            config_file_path = get_persistent_data_path("last_config.txt")
            with open(config_file_path, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception as e:
            self.log_message(f"保存上次配置文件路径失败: {e}")

    def load_last_config_path(self):
        """从文件中加载最后一次使用的配置文件路径"""
        try:
            config_file_path = get_persistent_data_path("last_config.txt")
            if os.path.exists(config_file_path):
                with open(config_file_path, "r", encoding="utf-8") as f:
                    path = f.read().strip()
                if os.path.exists(path):
                    return path
        except Exception as e:
            self.log_message(f"加载上次配置文件路径失败: {e}")
        return None

    def _setup_tray_icon(self):
        """设置系统托盘图标和右键菜单"""
        try:
            # 调用函数，动态加载base64字符串
            icon_base64_string = get_icon_base64()
            icon_data = base64.b64decode(icon_base64_string)
            image = Image.open(io.BytesIO(icon_data))
        except Exception as e:
            # 如果加载图标失败，创建一个简单的备用图标
            self.log_message(f"加载托盘图标失败: {e}。将使用备用图标。" )
            image = Image.new('RGB', (64, 64), color = 'black')
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("msyh.ttc", 20)
            except IOError:
                font = ImageFont.load_default()
            draw.text((10, 20), "V2", font=font, fill='white')

        # 定义托盘图标的右键菜单
        menu = (
            pystray.MenuItem('显示窗口', self._show_window, default=True),
            pystray.MenuItem('隐藏窗口', self._hide_window),
            pystray.MenuItem('启动 V2ray', self._start_v2ray_from_tray),
            pystray.MenuItem('停止 V2ray', self._stop_v2ray_from_tray),
            pystray.MenuItem('退出', self._on_tray_exit)
        )
        # 创建托盘图标对象
        self.icon = pystray.Icon('v2fly_client', image, 'V2fly 客户端', menu)

    def _show_window(self, icon, item):
        """显示主窗口"""
        self.deiconify() # 从最小化或隐藏状态恢复窗口
        self.lift()      # 将窗口带到最顶层
        self.focus_force() # 强制窗口获取焦点

    def _hide_window(self):
        """隐藏主窗口到托盘"""
        self.withdraw()

    def _on_tray_exit(self, icon, item):
        """处理从托盘菜单退出的事件"""
        if self.icon:
            self.icon.stop() # 停止托盘图标
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        self.stop_v2ray() # 停止v2ray
        self.quit()       # 退出Tkinter主循环

    def _start_v2ray_from_tray(self, icon, item):
        """从托盘菜单启动v2ray"""
        self.after(0, self.start_v2ray)

    def _stop_v2ray_from_tray(self, icon, item):
        """从托盘菜单停止v2ray"""
        self.after(0, self.stop_v2ray)