from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QMessageBox
from backend.database import DatabaseManager
from utils.signals import event_bus

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("AI 缺陷引擎 - 认证网关")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        self.title_label = QLabel("工业视觉质检系统")
        # 此处省略样式设置代码...
        
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("系统账号")
        
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("认证凭证")
        self.input_password.setEchoMode(QLineEdit.Password) # 屏蔽明文
        
        self.btn_login = QPushButton("授权登录")
        self.btn_login.clicked.connect(self._attempt_login)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.input_username)
        layout.addWidget(self.input_password)
        layout.addWidget(self.btn_login)
        self.setLayout(layout)

    def _attempt_login(self):
        username = self.input_username.text().strip()
        password = self.input_password.text().strip()
        
        # 前端非空拦截
        if not username or not password:
            QMessageBox.warning(self, "校验失败", "账号或密码流不可为空。")
            return
            
        self.btn_login.setEnabled(False)
        
        # 移交后端核验
        user_context = self.db.authenticate(username, password)
        
        if user_context:
            # 认证通过，全局广播上下文
            event_bus.auth_success.emit(user_context)
        else:
            QMessageBox.critical(self, "拒绝访问", "凭证无效或账号不存在。")
            self.input_password.clear()
            self.btn_login.setEnabled(True)