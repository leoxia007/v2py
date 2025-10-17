# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
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
from core.proxy import set_startup

from ui.config_generator import ConfigGeneratorWindow
from ui.hotkey_settings import HotkeySettingsWindow

class V2rayClientApp(customtkinter.CTk):
    """
    主应用窗口类。
    继承自customtkinter.CTk，是整个应用的UI入口。
    """
    def __init__(self, master=None):
        super().__init__()
        self.v2ray_process = None
        self.current_config_path = ""
        self.generator_window = None # 用于持有配置生成器窗口的引用
        self.hotkey_window = None # 用于持有快捷键设置窗口的引用

        self.title("V2fly 客户端")
        self.geometry("800x600")

        # 设置UI主题
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        # 加载应用设置
        self.settings = load_app_settings()

        self.create_widgets() # 创建UI组件
        self._setup_tray_icon() # 设置系统托盘图标

        if self.settings.get("run_on_startup"):
            self.run_on_startup_check.select()
        if self.settings.get("auto_start_v2ray"):
            self.auto_start_v2ray_check.select()

        # 获取v2ray核心程序路径
        self.v2ray_executable = resource_path(V2RAY_CORE_PATH)
        if not os.path.exists(self.v2ray_executable):
            self.log_message(f"错误: 找不到 v2ray.exe，请确保它在 {self.v2ray_executable} 路径下。")

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
        self._create_control_frame()
        self._create_button_frame()
        self._create_app_settings_frame()
        self._create_proxy_frame()
        self._create_log_frame()
        self._create_editor_frame()

    def _create_control_frame(self):
        """创建顶部控制栏"""
        control_frame = customtkinter.CTkFrame(self, corner_radius=0)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        customtkinter.CTkLabel(control_frame, text="配置文件:").pack(side=tk.LEFT, padx=(0, 5))
        self.config_path_label = customtkinter.CTkLabel(control_frame, text="未选择", width=250, anchor="w")
        self.config_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.select_config_button = customtkinter.CTkButton(control_frame, text="选择配置文件", command=self.select_config_file)
        self.select_config_button.pack(side=tk.LEFT, padx=(0, 5))

        self.generate_config_button = customtkinter.CTkButton(control_frame, text="生成配置", command=self.open_generator_window)
        self.generate_config_button.pack(side=tk.LEFT)

    def _create_button_frame(self):
        """创建启动/停止按钮栏"""
        button_frame = customtkinter.CTkFrame(self, corner_radius=0)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_button = customtkinter.CTkButton(button_frame, text="启动 V2ray", command=self.start_v2ray, fg_color="green", hover_color="#008000")
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_button = customtkinter.CTkButton(button_frame, text="停止 V2ray", command=self.stop_v2ray, fg_color="red", hover_color="#800000", state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))

        self.test_latency_button = customtkinter.CTkButton(button_frame, text="测试延迟", command=self.test_latency, state="disabled")
        self.test_latency_button.pack(side=tk.LEFT, padx=(0, 5))

        self.test_speed_button = customtkinter.CTkButton(button_frame, text="测试速度", command=self.test_speed, state="disabled")
        self.test_speed_button.pack(side=tk.LEFT, padx=(0, 10))

        self.minimize_button = customtkinter.CTkButton(button_frame, text="最小化到托盘", command=self._hide_window)
        self.minimize_button.pack(side=tk.RIGHT, padx=(10, 0))

    def _create_app_settings_frame(self):
        """创建应用设置栏"""
        app_settings_frame = customtkinter.CTkFrame(self, corner_radius=0)
        app_settings_frame.pack(fill=tk.X, padx=10, pady=5)

        self.run_on_startup_check = customtkinter.CTkCheckBox(app_settings_frame, text="开机自启动", command=self.toggle_run_on_startup)
        self.run_on_startup_check.pack(side=tk.LEFT, anchor="w", padx=5)

        self.auto_start_v2ray_check = customtkinter.CTkCheckBox(app_settings_frame, text="自动启动v2ray", command=self.toggle_auto_start_v2ray)
        self.auto_start_v2ray_check.pack(side=tk.LEFT, anchor="w", padx=5)

    def _create_proxy_frame(self):
        """创建系统代理设置栏"""
        proxy_frame = customtkinter.CTkFrame(self, corner_radius=0)
        proxy_frame.pack(fill=tk.X, padx=10, pady=5)

        customtkinter.CTkLabel(proxy_frame, text="系统代理设置").pack(anchor="w", padx=5, pady=5)

        self.proxy_enable_check = customtkinter.CTkCheckBox(proxy_frame, text="启用系统代理", command=self.toggle_proxy_fields)
        self.proxy_enable_check.pack(anchor="w", padx=5)

        proxy_address_frame = customtkinter.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_address_frame.pack(fill=tk.X, pady=5)
        customtkinter.CTkLabel(proxy_address_frame, text="代理地址 (例如: 127.0.0.1:10809): ").pack(side=tk.LEFT)
        self.proxy_address_entry = customtkinter.CTkEntry(proxy_address_frame, width=200)
        self.proxy_address_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.proxy_address_entry.insert(0, f"127.0.0.1:{HTTP_INBOUND_PORT}")

        proxy_buttons_frame = customtkinter.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_buttons_frame.pack(fill=tk.X, pady=5)
        self.apply_proxy_button = customtkinter.CTkButton(proxy_buttons_frame, text="应用代理", command=self.apply_system_proxy)
        self.apply_proxy_button.pack(side=tk.LEFT, padx=(0, 10))
        self.clear_proxy_button = customtkinter.CTkButton(proxy_buttons_frame, text="清除代理", command=self.clear_system_proxy)
        self.clear_proxy_button.pack(side=tk.LEFT, padx=(0, 10))

        self.hotkey_settings_button = customtkinter.CTkButton(proxy_buttons_frame, text="快捷键设置...", command=self.open_hotkey_window)
        self.hotkey_settings_button.pack(side=tk.LEFT)

        self.toggle_proxy_fields() # 初始化代理设置区域的UI状态

    def _create_log_frame(self):
        """创建日志输出区域"""
        customtkinter.CTkLabel(self, text="日志输出:").pack(anchor="w", padx=10, pady=(10, 0))
        self.log_text = customtkinter.CTkTextbox(self, wrap="word", height=15)
        self.log_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.log_text.configure(state="disabled") # 默认设为不可编辑

    def _create_editor_frame(self):
        """创建配置文件编辑器"""
        editor_frame = customtkinter.CTkFrame(self, corner_radius=0)
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        editor_label_frame = customtkinter.CTkFrame(editor_frame, fg_color="transparent")
        editor_label_frame.pack(fill=tk.X)

        customtkinter.CTkLabel(editor_label_frame, text="配置文件内容 (可编辑):").pack(side=tk.LEFT, anchor="w", pady=(10, 0))
        self.save_config_button = customtkinter.CTkButton(editor_label_frame, text="保存更改", command=self.save_config_file)
        self.save_config_button.pack(side=tk.RIGHT, padx=(0, 5))

        self.config_editor = customtkinter.CTkTextbox(editor_frame, wrap="word", height=10)
        self.config_editor.pack(fill=tk.BOTH, expand=True, pady=5)
        self.config_editor.configure(state="normal")

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
            self.generator_window = ConfigGeneratorWindow(self)
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

    def start_v2ray(self):
        """启动v2ray核心进程"""
        if not self.current_config_path:
            messagebox.showwarning("警告", "请先选择 v2ray 配置文件！")
            return
        if self.v2ray_process and self.v2ray_process.poll() is None:
            messagebox.showinfo("信息", "V2ray 已经在运行中")
            return
        self.log_message("正在启动 V2ray...")
        try:
            # 在新线程中启动v2ray，避免UI阻塞
            threading.Thread(target=self._run_v2ray_in_thread, daemon=True).start()
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.test_latency_button.configure(state="disabled")
            self.test_speed_button.configure(state="normal")
        except Exception as e:
            self.log_message(f"启动 V2ray 失败: {e}")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def _run_v2ray_in_thread(self):
        """在后台线程中运行v2ray进程并监控其输出"""
        try:
            # 在Windows上使用CREATE_NO_WINDOW标志来隐藏v2ray的命令行窗口
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.v2ray_process = subprocess.Popen(
                [self.v2ray_executable, "run", "-c", self.current_config_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=creationflags
            )
            self.log_message("V2ray 已启动")
            # 创建线程分别读取标准输出和标准错误
            stdout_thread = threading.Thread(target=self._read_stream, args=(self.v2ray_process.stdout, "V2ray STDOUT"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream, args=(self.v2ray_process.stderr, "V2ray STDERR"), daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            self.v2ray_process.wait() # 等待v2ray进程结束
            self.log_message(f"V2ray 进程已退出，退出码: {self.v2ray_process.returncode}")
            self.after(0, self._on_v2ray_stopped) # 在主线程中更新UI
        except FileNotFoundError:
            self.log_message(f"错误: 找不到 v2ray.exe，请检查路径: {self.v2ray_executable}")
            self.after(0, self._on_v2ray_stopped)
        except Exception as e:
            self.log_message(f"V2ray 运行出错: {e}")
            self.after(0, self._on_v2ray_stopped)

    def _read_stream(self, stream, name):
        """读取v2ray进程的输出流并显示在日志区域"""
        for line in stream:
            # self.after(0, ...)确保UI更新在主线程中执行
            self.after(0, self.log_message, f"[{name}] {line.strip()}")

    def stop_v2ray(self):
        """停止v2ray核心进程"""
        if self.v2ray_process and self.v2ray_process.poll() is None:
            self.log_message("正在停止 V2ray...")
            try:
                self.v2ray_process.terminate() # 尝试正常终止
                self.v2ray_process.wait(timeout=5) # 等待5秒
                self.log_message("V2ray 已停止")
            except subprocess.TimeoutExpired:
                self.v2ray_process.kill() # 如果超时，则强制终止
                self.log_message("V2ray 强制停止")
            except Exception as e:
                self.log_message(f"停止 V2ray 失败: {e}")
            finally:
                self.v2ray_process = None
                self._on_v2ray_stopped()
        else:
            self.log_message("V2ray 未运行")
            self._on_v2ray_stopped()

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
            self.log_message("错误: 未选择配置文件，无法测试延迟。")
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
            if self.v2ray_process is None or self.v2ray_process.poll() is not None:
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
        if self.v2ray_process is None or self.v2ray_process.poll() is not None:
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
            if self.v2ray_process and self.v2ray_process.poll() is None:
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
            self._set_system_proxy(proxy_address)
        else:
            self._clear_system_proxy_settings()

    def clear_system_proxy(self):
        """清除系统代理设置"""
        self.proxy_enable_check.deselect()
        self.toggle_proxy_fields()
        self._clear_system_proxy_settings()

    def _set_system_proxy(self, proxy_address):
        """通过修改Windows注册表来设置系统代理"""
        try:
            import winreg
            # 打开注册表项
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            # 设置代理启用状态、代理服务器地址和本地地址不走代理
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_address)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
            winreg.CloseKey(key)
            self.log_message(f"系统代理已设置为: {proxy_address}")
            self._refresh_internet_settings()
        except Exception as e:
            self.log_message(f"设置系统代理失败: {e}")
            messagebox.showerror("错误", f"设置系统代理失败: {e}")

    def _clear_system_proxy_settings(self):
        """通过修改Windows注册表来清除系统代理"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            # 尝试删除代理服务器地址和覆盖设置，忽略可能的文件未找到错误
            try:
                winreg.DeleteValue(key, "ProxyServer")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteValue(key, "ProxyOverride")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            self.log_message("系统代理已清除。" )
            self._refresh_internet_settings()
        except Exception as e:
            self.log_message(f"清除系统代理失败: {e}")
            messagebox.showerror("错误", f"清除系统代理失败: {e}")

    def _refresh_internet_settings(self):
        """提醒用户代理设置可能需要重启浏览器或相关应用才能生效"""
        self.log_message("请注意：系统代理设置可能需要重启浏览器或相关应用才能生效。" )

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

