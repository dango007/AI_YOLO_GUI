import sys
import traceback
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QSettings

from ui.login_ui import LoginWindow
from ui.main_ui import MainWindow
from utils.signals import event_bus


# ==================== 全局异常处理 ====================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常捕获钩子，拦截所有未处理异常"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"CRITICAL SYSTEM CRASH:\n{error_msg}", file=sys.stderr)

    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("致命错误")
    msg_box.setText("系统发生未捕获的严重异常，即将退出。")
    msg_box.setDetailedText(error_msg)
    msg_box.exec_()
    sys.exit(1)


# ==================== 主题管理器 ====================
class ThemeManager:
    """负责加载全局 QSS 样式表，与 .qss 文件解耦"""
    @staticmethod
    def load_theme(app: QApplication, qss_path: str):
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"[WARNING] QSS file not found: {qss_path}", file=sys.stderr)
            app.setStyleSheet("")  # 回退到原生样式

    @staticmethod
    def clear_theme(app: QApplication):
        app.setStyleSheet("")


# ==================== 应用程序控制器 ====================
class ApplicationController:
    """应用程序生命周期与路由控制器"""
    def __init__(self):
        self.app = QApplication(sys.argv)
        sys.excepthook = global_exception_handler

        # 计算 QSS 文件所在目录 (基于当前文件位置)
        self.base_dir = Path(__file__).resolve().parent  # main.py 所在目录
        self.themes_dir = self.base_dir / "utils" / "themes"

        # 1. 启动时读取持久化配置并应用一次全局主题
        settings = QSettings("IndustrialAI", "DefectEngine")
        initial_theme = settings.value("ui/theme", "Dark")  # 默认深色
        self._apply_theme(initial_theme)

        # 2. 挂载全局事件总线，监听运行时的主题热更新信号
        event_bus.theme_changed.connect(self._apply_theme)

        self.login_window = LoginWindow()
        self.main_window = None

        # 路由绑定
        event_bus.auth_success.connect(self._route_to_main_dashboard)

    def run(self):
        self.login_window.show()
        sys.exit(self.app.exec_())

    def _route_to_main_dashboard(self, user_context):
        self.login_window.close()
        self.login_window.deleteLater()
        self.main_window = MainWindow(user_context)
        self.main_window.show()

    # ==================== 主题渲染核心逻辑 ====================
    def _apply_theme(self, theme_name: str):
        """
        根据传入的主题标识，向 QApplication 注入全局 QSS 样式表。
        支持的值: "Dark", "Light", "System" 或带模式名的变体。
        """
        # 规范化主题名称
        theme_lower = theme_name.lower()
        if "dark" in theme_lower:
            qss_file = self.themes_dir / "dark_theme.qss"
            ThemeManager.load_theme(self.app, str(qss_file))
        elif "light" in theme_lower:
            qss_file = self.themes_dir / "light_theme.qss"
            ThemeManager.load_theme(self.app, str(qss_file))
        elif "system" in theme_lower:
            ThemeManager.clear_theme(self.app)
        else:
            # 默认回退到深色主题
            qss_file = self.themes_dir / "dark_theme.qss"
            ThemeManager.load_theme(self.app, str(qss_file))


if __name__ == "__main__":
    controller = ApplicationController()
    controller.run()