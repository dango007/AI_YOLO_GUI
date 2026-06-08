from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLineEdit, QMessageBox, 
                             QHeaderView, QDialog, QFormLayout, QComboBox, QDialogButtonBox)
from PyQt5.QtCore import Qt
from backend.database import DatabaseManager
from utils.signals import event_bus

class UserFormDialog(QDialog):
    """独立的模态对话框，用于安全地收集新增用户信息"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增系统账号")
        self.setMinimumWidth(360)
        self._setup_ui()

    def _setup_ui(self):
        # 增加内边距，提升表单呼吸感
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("输入唯一登录名...")
        
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("输入初始密码...")
        self.input_password.setEchoMode(QLineEdit.Password) 
        
        self.combo_role = QComboBox()
        self.combo_role.addItems(["user", "admin"])

        form_layout.addRow("系统账号:", self.input_username)
        form_layout.addRow("初始密码:", self.input_password)
        form_layout.addRow("分配角色:", self.combo_role)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # 拦截原生对话框按钮并注入我们的语义化 QSS 属性
        btn_ok = self.button_box.button(QDialogButtonBox.Ok)
        btn_ok.setText("确认分配")
        btn_ok.setProperty("type", "primary")
        btn_ok.setCursor(Qt.PointingHandCursor)
        
        btn_cancel = self.button_box.button(QDialogButtonBox.Cancel)
        btn_cancel.setText("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)

        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    def get_form_data(self):
        return {
            "username": self.input_username.text().strip(),
            "password": self.input_password.text().strip(),
            "role": self.combo_role.currentText()
        }


class UserManagementDashboard(QWidget):
    def __init__(self, current_user_id):
        super().__init__()
        self.db = DatabaseManager()
        self.current_user_id = current_user_id  
        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)
        
        # 1. 顶部控制台 (过滤与操作)
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput") # 挂载专属 ID 以便 QSS 定制
        self.search_input.setPlaceholderText("🔍 模糊搜索: 账号或角色...")
        self.search_input.setMinimumWidth(280)
        self.search_input.textChanged.connect(self._filter_users)
        
        self.btn_add = QPushButton("新增分配")
        self.btn_add.setProperty("type", "primary") # 剥离硬编码，交由 QSS 接管
        self.btn_add.setCursor(Qt.PointingHandCursor)
        
        self.btn_delete = QPushButton("安全回收 (删除)")
        self.btn_delete.setProperty("type", "danger") # 剥离硬编码，交由 QSS 接管
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        
        top_layout.addWidget(self.search_input)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_add)
        top_layout.addWidget(self.btn_delete)
        
        # 2. 数据台账视图
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "系统账号", "RBAC 角色", "创建时间", "最后登录"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers) 
        self.table.setSortingEnabled(True)
        self.table.setCornerButtonEnabled(False)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._add_user)
        self.btn_delete.clicked.connect(self._safe_delete_user)

    def _load_users(self):
        try:
            user_list = self.db.get_all_users()
            self.table.setSortingEnabled(False) 
            self.table.setRowCount(0)
            
            for row, user in enumerate(user_list):
                self.table.insertRow(row)
                
                last_login = user.get('last_login')
                last_login_str = str(last_login) if last_login else "从未登录"
                created_at = user.get('created_at')
                created_at_str = str(created_at) if created_at else "N/A"

                items = [
                    QTableWidgetItem(str(user['id'])),
                    QTableWidgetItem(str(user['username'])),
                    QTableWidgetItem(str(user['role']).upper()),
                    QTableWidgetItem(created_at_str),
                    QTableWidgetItem(last_login_str)
                ]
                
                for col_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col_idx, item)
                    
            self.table.setSortingEnabled(True)
        except Exception as e:
            event_bus.db_error.emit(f"读取用户台账失败: {str(e)}")

    def _filter_users(self, keyword):
        keyword = keyword.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and keyword in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def _add_user(self):
        dialog = UserFormDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_form_data()
            
            if not data['username'] or not data['password']:
                QMessageBox.warning(self, "输入无效", "账号与密码不能为空。")
                return
                
            try:
                success = self.db.add_user(data['username'], data['password'], data['role'])
                if success:
                    self._load_users() 
                    QMessageBox.information(self, "操作成功", f"用户 [{data['username']}] 已创建。")
                else:
                    QMessageBox.warning(self, "操作失败", "可能账号已存在，请检查输入。")
            except Exception as e:
                event_bus.db_error.emit(f"写入新用户失败: {str(e)}")

    def _safe_delete_user(self):
        selected = self.table.selectedItems()
        if not selected:
            return
            
        target_id = int(self.table.item(selected[0].row(), 0).text())
        target_name = self.table.item(selected[0].row(), 1).text()
        
        if target_id == self.current_user_id:
            QMessageBox.critical(self, "越权拦截", "系统拒绝执行：禁止在此会话中注销/删除当前高权账号自身。")
            return
            
        reply = QMessageBox.warning(self, '高危操作确认', 
                                     f"即将永久清除资产账户 [{target_name}] 的所有授权，此操作不可逆。是否继续？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_user(target_id)
                self._load_users() 
            except Exception as e:
                event_bus.db_error.emit(f"删除账户失败: {str(e)}")