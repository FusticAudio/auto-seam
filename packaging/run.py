# -*- coding: utf-8 -*-
"""桌面工具启动入口：自动选端口、开浏览器、运行 FastAPI 服务。

双击由 PyInstaller 打包出的「启动工具.exe」即从此入口开始。
"""
from __future__ import annotations

import socket
import threading
import time
import webbrowser
from typing import Optional

import uvicorn

from server import app

DEFAULT_PORT = 8010
HOST = "127.0.0.1"


def find_free_port(preferred: int = DEFAULT_PORT) -> int:
    """优先使用 preferred，被占用则探测系统空闲端口。"""
    for port in (preferred, 0):  # 0 = 让系统分配空闲端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
            except OSError:
                continue
            return s.getsockname()[1]


def open_browser(url: str) -> None:
    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    threading.Timer(1.5, _open).start()


def main() -> None:
    port = find_free_port()
    url = f"http://{HOST}:{port}/"
    print("=" * 60)
    print("  服装裁片自动缝合标注 · 桌面工具")
    print(f"  编辑器:      {url}seam-preview/")
    print(f"  DXF 转换:    {url}dxf-convert/")
    print(f"  端口:        {port}")
    print("  正在打开浏览器… 关闭本窗口即退出服务")
    print("=" * 60)
    open_browser(url)
    # log_level 用 warning 可略去请求日志，保持控制台简洁
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()