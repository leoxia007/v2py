# -*- coding: utf-8 -*-

import subprocess
import threading
import sys
import os
from core.utils import resource_path
from core.constants import V2RAY_CORE_PATH

class V2rayManager:
    """
    Manages the V2Ray subprocess, including starting, stopping, and monitoring.
    """
    def __init__(self, log_callback):
        """
        Initializes the V2rayManager.

        :param log_callback: A function to call with log messages.
        """
        self.v2ray_process = None
        self.log_callback = log_callback
        self.v2ray_executable = resource_path(V2RAY_CORE_PATH)
        if not os.path.exists(self.v2ray_executable):
            self.log_callback(f"Error: v2ray.exe not found at {self.v2ray_executable}")

    def is_running(self):
        """Check if the V2Ray process is currently running."""
        return self.v2ray_process and self.v2ray_process.poll() is None

    def start(self, config_path, on_exit_callback=None):
        """Starts the V2Ray process in a separate thread."""
        if not config_path:
            self.log_callback("Error: V2Ray config path is not provided.")
            return False
        if self.is_running():
            self.log_callback("V2Ray is already running.")
            return False
        if not os.path.exists(self.v2ray_executable):
            self.log_callback(f"Error: v2ray.exe not found at {self.v2ray_executable}")
            return False

        self.log_callback("Starting V2Ray...")
        try:
            thread = threading.Thread(target=self._run_process, args=(config_path, on_exit_callback), daemon=True)
            thread.start()
            return True
        except Exception as e:
            self.log_callback(f"Failed to start V2Ray: {e}")
            return False

    def _run_process(self, config_path, on_exit_callback):
        """The actual process running logic."""
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.v2ray_process = subprocess.Popen(
                [self.v2ray_executable, "run", "-c", config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=creationflags
            )
            self.log_callback("V2Ray started successfully.")

            stdout_thread = threading.Thread(target=self._read_stream, args=(self.v2ray_process.stdout, "V2ray STDOUT"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream, args=(self.v2ray_process.stderr, "V2ray STDERR"), daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            self.v2ray_process.wait()
            exit_code = self.v2ray_process.returncode
            self.log_callback(f"V2Ray process has exited with code: {exit_code}")

        except FileNotFoundError:
            self.log_callback(f"Error: v2ray.exe not found. Please check the path: {self.v2ray_executable}")
        except Exception as e:
            self.log_callback(f"V2Ray runtime error: {e}")
        finally:
            self.v2ray_process = None
            if on_exit_callback:
                on_exit_callback()

    def _read_stream(self, stream, name):
        """Reads the output stream of the V2Ray process."""
        for line in stream:
            self.log_callback(f"[{name}] {line.strip()}")

    def stop(self):
        """Stops the V2Ray process."""
        if not self.is_running():
            self.log_callback("V2Ray is not running.")
            return

        self.log_callback("Stopping V2Ray...")
        try:
            self.v2ray_process.terminate()
            try:
                self.v2ray_process.wait(timeout=5)
                self.log_callback("V2Ray stopped.")
            except subprocess.TimeoutExpired:
                self.log_callback("V2Ray did not respond to terminate, killing it.")
                self.v2ray_process.kill()
                self.log_callback("V2Ray killed.")
        except Exception as e:
            self.log_callback(f"Error stopping V2Ray: {e}")
        finally:
            self.v2ray_process = None
