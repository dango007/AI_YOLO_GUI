from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QMessageBox, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt
from backend.database import DatabaseManager
from utils.signals import event_bus

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("AI 缺陷引擎 - 认证网关")
        self.setFixedSize(420, 360)
        
        # 外层容器：设置呼吸感间距
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)
        
        # 顶部标题区
        self.title_label = QLabel("工业视觉质检系统")
        self.title_label.setObjectName("loginTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        # 登录区容器
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("系统账号 (Username)")
        self.input_username.setObjectName("loginInput")
        
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("认证凭证 (Password)")
        self.input_password.setObjectName("loginInput")
        self.input_password.setEchoMode(QLineEdit.Password)
        
        self.btn_login = QPushButton("授权登录 (Login)")
        self.btn_login.setProperty("type", "primary") # 挂载语义化样式
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self._attempt_login)
        
        form_layout.addWidget(self.input_username)
        form_layout.addWidget(self.input_password)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.btn_login)
        
        main_layout.addStretch()
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(form_layout)
        main_layout.addStretch()

    def _attempt_login(self):
        username = self.input_username.text().strip()
        password = self.input_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "校验失败", "账号或密码不可为空。")
            return
            
        self.btn_login.setEnabled(False)
        user_context = self.db.authenticate(username, password)
        
        if user_context:
            event_bus.auth_success.emit(user_context)
        else:
            QMessageBox.critical(self, "拒绝访问", "凭证无效或账号不存在。")
            self.input_password.clear()
            self.btn_login.setEnabled(True)