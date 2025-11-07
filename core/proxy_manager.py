# -*- coding: utf-8 -*-

import sys
import subprocess

class ProxyManager:
    """
    Manages system proxy settings for different operating systems.
    """
    def __init__(self, log_callback):
        self.log_callback = log_callback

    def set_proxy(self, proxy_address):
        """Sets the system proxy."""
        if sys.platform == "win32":
            self._set_windows_proxy(proxy_address)
        elif sys.platform == "darwin":
            self._set_macos_proxy(proxy_address)
        else:
            self.log_callback("Proxy settings are not supported on this OS.")

    def clear_proxy(self):
        """Clears the system proxy."""
        if sys.platform == "win32":
            self._clear_windows_proxy()
        elif sys.platform == "darwin":
            self._clear_macos_proxy()

    def _set_windows_proxy(self, proxy_address):
        """Sets the system proxy on Windows."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_address)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
            winreg.CloseKey(key)
            self.log_callback(f"System proxy set to: {proxy_address}")
            self._refresh_windows_internet_settings()
        except Exception as e:
            self.log_callback(f"Failed to set system proxy: {e}")

    def _clear_windows_proxy(self):
        """Clears the system proxy on Windows."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            try:
                winreg.DeleteValue(key, "ProxyServer")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteValue(key, "ProxyOverride")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            self.log_callback("System proxy cleared.")
            self._refresh_windows_internet_settings()
        except Exception as e:
            self.log_callback(f"Failed to clear system proxy: {e}")

    def _refresh_windows_internet_settings(self):
        """Notifies Windows that internet settings have changed."""
        try:
            import win32gui
            import win32con
            win32gui.SendMessage(win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 'Internet Settings')
            self.log_callback("Broadcasted internet settings change to the system.")
        except ImportError:
            self.log_callback("pywin32 is not installed. Proxy changes may require a manual refresh (e.g., browser restart).")
        except Exception as e:
            self.log_callback(f"Failed to refresh internet settings: {e}")

    def _set_macos_proxy(self, proxy_address):
        """Sets the system proxy on macOS."""
        # macOS proxy settings require splitting host and port
        try:
            host, port = proxy_address.split(":")
            # For Wi-Fi
            subprocess.run(['networksetup', '-setwebproxy', 'Wi-Fi', host, port], check=True)
            subprocess.run(['networksetup', '-setsecurewebproxy', 'Wi-Fi', host, port], check=True)
            # For Ethernet
            subprocess.run(['networksetup', '-setwebproxy', 'Ethernet', host, port], check=True)
            subprocess.run(['networksetup', '-setsecurewebproxy', 'Ethernet', host, port], check=True)
            self.log_callback(f"System proxy set to: {proxy_address}")
        except Exception as e:
            self.log_callback(f"Failed to set macOS proxy: {e}. Make sure you are connected to Wi-Fi or Ethernet.")

    def _clear_macos_proxy(self):
        """Clears the system proxy on macOS."""
        try:
            # For Wi-Fi
            subprocess.run(['networksetup', '-setwebproxystate', 'Wi-Fi', 'off'], check=True)
            subprocess.run(['networksetup', '-setsecurewebproxystate', 'Wi-Fi', 'off'], check=True)
            # For Ethernet
            subprocess.run(['networksetup', '-setwebproxystate', 'Ethernet', 'off'], check=True)
            subprocess.run(['networksetup', '-setsecurewebproxystate', 'Ethernet', 'off'], check=True)
            self.log_callback("System proxy cleared.")
        except Exception as e:
            self.log_callback(f"Failed to clear macOS proxy: {e}")
