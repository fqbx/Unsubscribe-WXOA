"""CustomTkinter GUI for WeChat official account batch unsubscribe."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk

from src.core.adb_manager import ADBManager, DeviceInfo
from src.core.controller import (
    AutomationController,
    BatchProgress,
    ControllerCallbacks,
    ControllerState,
    load_config,
)
from src.utils.logger import setup_logger, get_logger

logger = get_logger()

STATE_LABELS = {
    ControllerState.IDLE: "空闲",
    ControllerState.CONNECTING: "连接中",
    ControllerState.NAVIGATING: "导航中",
    ControllerState.RUNNING: "运行中",
    ControllerState.PAUSED: "已暂停",
    ControllerState.STOPPED: "已停止",
    ControllerState.COMPLETED: "已完成",
    ControllerState.ERROR: "错误",
}


class UnsubscribeApp(ctk.CTk):
    """Main application window."""

    def __init__(self, config_path: str = "config/default.yaml") -> None:
        super().__init__()

        self.config_path = config_path
        self.controller_config = load_config(config_path)
        self._ui_queue: queue.Queue = queue.Queue()
        self._devices: List[DeviceInfo] = []
        self._device_map: dict[str, str] = {}

        self.title("微信公众号批量取关")
        self.geometry("720x640")
        self.minsize(600, 500)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._build_ui()
        self._setup_controller()
        self._bind_hotkeys()
        self._poll_ui_queue()
        self._refresh_devices()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # --- Device row ---
        device_frame = ctk.CTkFrame(self)
        device_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        device_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(device_frame, text="设备:").grid(row=0, column=0, padx=(8, 4), pady=8)
        self.device_var = ctk.StringVar(value="")
        self.device_menu = ctk.CTkOptionMenu(
            device_frame,
            variable=self.device_var,
            values=["无设备"],
            width=280,
        )
        self.device_menu.grid(row=0, column=1, sticky="ew", padx=4, pady=8)

        self.refresh_btn = ctk.CTkButton(
            device_frame, text="刷新", width=70, command=self._refresh_devices
        )
        self.refresh_btn.grid(row=0, column=2, padx=4, pady=8)

        self.connect_btn = ctk.CTkButton(
            device_frame, text="连接", width=70, command=self._connect_device
        )
        self.connect_btn.grid(row=0, column=3, padx=(4, 8), pady=8)

        self.conn_status = ctk.CTkLabel(device_frame, text="未连接", text_color="gray")
        self.conn_status.grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        # --- Params row ---
        params_frame = ctk.CTkFrame(self)
        params_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        params_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(params_frame, text="操作间隔(秒):").grid(
            row=0, column=0, padx=(8, 4), pady=8
        )
        self.delay_var = ctk.StringVar(
            value=str(
                (self.controller_config.delay_min + self.controller_config.delay_max) / 2
            )
        )
        self.delay_entry = ctk.CTkEntry(params_frame, textvariable=self.delay_var, width=80)
        self.delay_entry.grid(row=0, column=1, padx=4, pady=8)

        ctk.CTkLabel(params_frame, text="每批上限:").grid(row=0, column=2, padx=(16, 4), pady=8)
        self.max_count_var = ctk.StringVar(value=str(self.controller_config.max_count))
        self.max_count_entry = ctk.CTkEntry(
            params_frame, textvariable=self.max_count_var, width=80
        )
        self.max_count_entry.grid(row=0, column=3, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(
            params_frame,
            text="(实际间隔含 1.5–3s 随机抖动)",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, columnspan=4, padx=8, pady=(0, 8), sticky="w")

        # --- Progress row ---
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(progress_frame, text="进度: 0/0")
        self.progress_label.grid(row=1, column=0, padx=8, pady=2, sticky="w")

        self.status_label = ctk.CTkLabel(progress_frame, text="状态: 空闲")
        self.status_label.grid(row=2, column=0, padx=8, pady=(2, 8), sticky="w")

        self.stats_label = ctk.CTkLabel(
            progress_frame, text="成功: 0  失败: 0", text_color="gray"
        )
        self.stats_label.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="w")

        # --- Control buttons ---
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=6)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="开始", width=100, command=self._on_start
        )
        self.start_btn.pack(side="left", padx=8, pady=8)

        self.pause_btn = ctk.CTkButton(
            btn_frame, text="暂停", width=100, command=self._on_pause, state="disabled"
        )
        self.pause_btn.pack(side="left", padx=4, pady=8)

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="停止",
            width=100,
            fg_color="#c0392b",
            hover_color="#a93226",
            command=self._on_stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=4, pady=8)

        ctk.CTkLabel(
            btn_frame,
            text="紧急停止: F11",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(side="right", padx=8, pady=8)

        # --- Log area ---
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(6, 12))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_frame, text="日志:").grid(row=0, column=0, padx=8, pady=(8, 4), sticky="w")

        self.log_text = ctk.CTkTextbox(log_frame, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    def _setup_controller(self) -> None:
        callbacks = ControllerCallbacks(
            on_state_change=self._on_state_change_threadsafe,
            on_progress=self._on_progress_threadsafe,
            on_log=None,
        )
        self.controller = AutomationController(
            config=self.controller_config,
            callbacks=callbacks,
        )

    def _bind_hotkeys(self) -> None:
        self.bind("<F11>", lambda _e: self._on_emergency_stop())

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                callback(*args)
        except queue.Empty:
            pass
        self.after(100, self._poll_ui_queue)

    def _enqueue(self, callback, *args) -> None:
        self._ui_queue.put((callback, args))

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_state_change_threadsafe(self, state: ControllerState, message: str) -> None:
        self._enqueue(self._handle_state_change, state, message)

    def _on_progress_threadsafe(self, progress: BatchProgress) -> None:
        self._enqueue(self._handle_progress, progress)

    def _handle_state_change(self, state: ControllerState, message: str) -> None:
        label = STATE_LABELS.get(state, state.value)
        self.status_label.configure(text=f"状态: {label} — {message}")

        running_states = {
            ControllerState.CONNECTING,
            ControllerState.NAVIGATING,
            ControllerState.RUNNING,
            ControllerState.PAUSED,
        }

        if state in running_states:
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal")
            self.stop_btn.configure(state="normal")
        else:
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")

        if state == ControllerState.PAUSED:
            self.pause_btn.configure(text="继续")
        else:
            self.pause_btn.configure(text="暂停")

        if state == ControllerState.ERROR:
            self.conn_status.configure(text=f"错误: {message}", text_color="#e74c3c")
        elif state == ControllerState.COMPLETED:
            self.conn_status.configure(text=message, text_color="#27ae60")

        self._append_log(f"[{label}] {message}")

    def _handle_progress(self, progress: BatchProgress) -> None:
        total = max(progress.total, 1)
        fraction = min(progress.current / total, 1.0)
        self.progress_bar.set(fraction)
        self.progress_label.configure(
            text=f"进度: {progress.current}/{progress.total}"
        )
        self.stats_label.configure(
            text=f"成功: {progress.success}  失败: {progress.failed}"
        )
        if progress.message:
            self.status_label.configure(
                text=f"状态: {STATE_LABELS.get(self.controller.state, '')} — {progress.message}"
            )

    def _refresh_devices(self) -> None:
        self._devices = self.controller.list_devices()
        self._device_map = {d.display_name: d.serial for d in self._devices}

        if self._devices:
            names = [d.display_name for d in self._devices]
            self.device_menu.configure(values=names)
            self.device_var.set(names[0])
            self.conn_status.configure(
                text=f"发现 {len(names)} 台设备", text_color="gray"
            )
        else:
            self.device_menu.configure(values=["无设备"])
            self.device_var.set("无设备")
            self.conn_status.configure(
                text="未发现 ADB 设备 — 请检查 USB 调试", text_color="#e67e22"
            )

    def _get_selected_serial(self) -> Optional[str]:
        name = self.device_var.get()
        return self._device_map.get(name)

    def _connect_device(self) -> None:
        serial = self._get_selected_serial()
        if not serial:
            self._append_log("请先连接 Android 设备")
            return

        def _connect():
            ok = self.controller.connect_device(serial)
            self._enqueue(
                self._handle_connect_result,
                ok,
                self.controller.adb.health_check().get("message", ""),
            )

        threading.Thread(target=_connect, daemon=True).start()

    def _handle_connect_result(self, ok: bool, message: str) -> None:
        if ok:
            self.conn_status.configure(text=f"已连接 — {message}", text_color="#27ae60")
            self._append_log(f"设备连接成功: {message}")
        else:
            self.conn_status.configure(text="连接失败", text_color="#e74c3c")
            self._append_log(f"连接失败: {message}")

    def _parse_params(self) -> tuple[float, float, int]:
        try:
            delay = float(self.delay_var.get())
            d_min = max(0.5, delay - 0.5)
            d_max = delay + 0.5
        except ValueError:
            d_min = self.controller_config.delay_min
            d_max = self.controller_config.delay_max

        try:
            max_count = int(self.max_count_var.get())
            max_count = max(1, min(max_count, 200))
        except ValueError:
            max_count = self.controller_config.max_count

        return d_min, d_max, max_count

    def _on_start(self) -> None:
        serial = self._get_selected_serial()
        if not serial:
            self._append_log("错误: 未选择设备")
            return

        d_min, d_max, max_count = self._parse_params()
        self.progress_bar.set(0)
        self._append_log(
            f"开始批处理: 上限 {max_count}, 间隔 {d_min:.1f}–{d_max:.1f}s"
        )
        self.controller.start_batch(
            serial=serial,
            max_count=max_count,
            delay_min=d_min,
            delay_max=d_max,
        )

    def _on_pause(self) -> None:
        if self.controller.state == ControllerState.PAUSED:
            self.controller.resume()
            self._append_log("已继续")
        else:
            self.controller.pause()
            self._append_log("已暂停")

    def _on_stop(self) -> None:
        self.controller.stop()
        self._append_log("正在停止...")

    def _on_emergency_stop(self) -> None:
        self.controller.emergency_stop()
        self._append_log("!!! 紧急停止 (F11) !!!")


def run_app(config_path: str = "config/default.yaml") -> None:
    """Entry point for the GUI application."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_queue: queue.Queue = queue.Queue()

    def log_callback(message: str) -> None:
        log_queue.put(message)

    setup_logger(log_dir=log_dir, level="INFO", log_callback=log_callback)
    app = UnsubscribeApp(config_path=config_path)

    def drain_log_queue() -> None:
        try:
            while True:
                msg = log_queue.get_nowait()
                app._append_log(msg)
        except queue.Empty:
            pass
        app.after(200, drain_log_queue)

    drain_log_queue()
    app.mainloop()
