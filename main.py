import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QSettings

from ui.login_ui import LoginWindow
from ui.main_ui import MainWindow
from utils.signals import event_bus

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常捕获钩子，拦截所有未处理异常"""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    # 在实际工程中，此处应将 error_msg 写入持久化日志文件
    print(f"CRITICAL SYSTEM CRASH:\n{error_msg}", file=sys.stderr)
    
    # 尝试弹窗警告，但此时 GUI 线程可能已损坏，需谨慎
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("致命错误")
    msg_box.setText("系统发生未捕获的严重异常，即将退出。")
    msg_box.setDetailedText(error_msg)
    msg_box.exec_()
    sys.exit(1)

class ApplicationController:
    """应用程序生命周期与路由控制器"""
    def __init__(self):
        self.app = QApplication(sys.argv)
        sys.excepthook = global_exception_handler
        
        # ==================== 新增：主题管理初始化 ====================
        # 1. 启动时读取持久化配置并应用一次全局主题
        settings = QSettings("IndustrialAI", "DefectEngine")
        initial_theme = settings.value("ui/theme", "Dark") # 默认给 Dark
        self._apply_theme(initial_theme)
        
        # 2. 挂载全局事件总线，监听运行时的主题热更新信号
        event_bus.theme_changed.connect(self._apply_theme)
        # ==========================================================
        
        self.login_window = LoginWindow()
        self.main_window = None
        
        # 路由绑定：监听登录成功信号以进行界面跳转
        event_bus.auth_success.connect(self._route_to_main_dashboard)

    def run(self):
        self.login_window.show()
        sys.exit(self.app.exec_())

    def _route_to_main_dashboard(self, user_context):
        """销毁登录窗体，注入用户上下文并拉起主框架"""
        self.login_window.close()
        self.login_window.deleteLater()
        
        # 将用户上下文（包含 role）注入主窗体
        self.main_window = MainWindow(user_context)
        self.main_window.show()

    # ==================== 新增：主题渲染核心逻辑 ====================
    def _apply_theme(self, theme_name):
        """
        根据传入的主题标识，向 QApplication 注入全局 QSS 样式表。
        """
        if theme_name == "Dark" or theme_name == "深色模式 (Dark)":
            # 工业级深色模式 QSS (类似 VSCode / IDE 的深色)
            dark_qss = """
                QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: "Microsoft YaHei", Arial; }
                QPushButton { background-color: #3a3a3a; border: 1px solid #555555; padding: 6px; border-radius: 4px; }
                QPushButton:hover { background-color: #4a4a4a; }
                QPushButton:pressed { background-color: #2a2a2a; }
                QLineEdit, QComboBox, QSpinBox, QDateEdit { background-color: #2d2d2d; border: 1px solid #444444; padding: 4px; border-radius: 3px; }
                QGroupBox { border: 1px solid #444444; border-radius: 5px; margin-top: 10px; font-weight: bold; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #569cd6; }
                QTableWidget { background-color: #1e1e1e; alternate-background-color: #252526; gridline-color: #333333; border: 1px solid #444; }
                QHeaderView::section { background-color: #2d2d2d; color: #d4d4d4; padding: 4px; border: 1px solid #444444; font-weight: bold; }
                QProgressBar { border: 1px solid #444; border-radius: 3px; text-align: center; color: white; }
                QProgressBar::chunk { background-color: #007acc; width: 10px; }
                QSplitter::handle { background-color: #333333; }
            """
            self.app.setStyleSheet(dark_qss)
            
        elif theme_name == "Light" or theme_name == "浅色模式 (Light)":
            # 清爽浅色模式 QSS
            light_qss = """
                QWidget { background-color: #f5f5f5; color: #202124; font-family: "Microsoft YaHei", Arial; }
                QPushButton { background-color: #e0e0e0; border: 1px solid #cccccc; padding: 6px; border-radius: 4px; color: #000; }
                QPushButton:hover { background-color: #d5d5d5; }
                QPushButton:pressed { background-color: #cccccc; }
                QLineEdit, QComboBox, QSpinBox, QDateEdit { background-color: #ffffff; border: 1px solid #c0c0c0; padding: 4px; border-radius: 3px; color: #000; }
                QGroupBox { border: 1px solid #c0c0c0; border-radius: 5px; margin-top: 10px; font-weight: bold; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #1976d2; }
                QTableWidget { background-color: #ffffff; alternate-background-color: #f9f9f9; gridline-color: #e0e0e0; border: 1px solid #c0c0c0; }
                QHeaderView::section { background-color: #e0e0e0; color: #333; padding: 4px; border: 1px solid #c0c0c0; font-weight: bold; }
                QProgressBar { border: 1px solid #c0c0c0; border-radius: 3px; text-align: center; color: black; }
                QProgressBar::chunk { background-color: #1976d2; width: 10px; }
                QSplitter::handle { background-color: #dcdcdc; }
            """
            self.app.setStyleSheet(light_qss)
            
        else:
            # System (跟随系统设置) -> 置空样式表，交还给操作系统进行默认原生绘制
            self.app.setStyleSheet("")

if __name__ == "__main__":
    controller = ApplicationController()
    controller.run()