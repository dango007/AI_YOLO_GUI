import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
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

if __name__ == "__main__":
    controller = ApplicationController()
    controller.run()