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
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("输入唯一登录名...")
        
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("输入初始密码...")
        self.input_password.setEchoMode(QLineEdit.Password) # 开启密码遮罩
        
        self.combo_role = QComboBox()
        self.combo_role.addItems(["user", "admin"])

        form_layout.addRow("系统账号:", self.input_username)
        form_layout.addRow("初始密码:", self.input_password)
        form_layout.addRow("分配角色:", self.combo_role)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

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
        self.current_user_id = current_user_id  # 注入当前上下文 ID，用于防自杀拦截
        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # 1. 顶部控制台 (过滤与操作)
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("模糊搜索: 账号或角色...")
        self.search_input.textChanged.connect(self._filter_users)
        
        self.btn_add = QPushButton("新增分配")
        self.btn_add.setStyleSheet("background-color: #2e7d32; color: white;")
        self.btn_delete = QPushButton("安全回收 (删除)")
        self.btn_delete.setStyleSheet("background-color: #c62828; color: white;") 
        
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
        self.table.setEditTriggers(QTableWidget.NoEditTriggers) # 台账禁直接编辑
        self.table.setSortingEnabled(True)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        # 信号绑定
        self.btn_add.clicked.connect(self._add_user)
        self.btn_delete.clicked.connect(self._safe_delete_user)

    def _load_users(self):
        """全量加载并渲染用户台账，处理空值回退"""
        try:
            # 依赖后端 database.py 实现的 get_all_users() 方法
            user_list = self.db.get_all_users()
            
            self.table.setSortingEnabled(False) # 填充时关闭排序优化性能
            self.table.setRowCount(0)
            
            for row, user in enumerate(user_list):
                self.table.insertRow(row)
                
                # 适配字段可能为空的情况
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
        """本地内存级模糊搜索，零延迟过滤"""
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
        """弹出表单收集数据并执行写库操作"""
        dialog = UserFormDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_form_data()
            
            # 前端数据基础校验
            if not data['username'] or not data['password']:
                QMessageBox.warning(self, "输入无效", "账号与密码不能为空。")
                return
                
            try:
                # 依赖后端 database.py 实现的 add_user() 方法
                success = self.db.add_user(data['username'], data['password'], data['role'])
                if success:
                    self._load_users() # 同步刷新视图
                    QMessageBox.information(self, "操作成功", f"用户 [{data['username']}] 已创建。")
                else:
                    QMessageBox.warning(self, "操作失败", "可能账号已存在，请检查输入。")
            except Exception as e:
                event_bus.db_error.emit(f"写入新用户失败: {str(e)}")

    def _safe_delete_user(self):
        """包含防呆验证与自杀拦截的删除事务"""
        selected = self.table.selectedItems()
        if not selected:
            return
            
        target_id = int(self.table.item(selected[0].row(), 0).text())
        target_name = self.table.item(selected[0].row(), 1).text()
        
        # 致命逻辑拦截：禁止删除当前活跃账号
        if target_id == self.current_user_id:
            QMessageBox.critical(self, "越权拦截", "系统拒绝执行：禁止在此会话中注销/删除当前高权账号自身。")
            return
            
        # 二次防呆确认
        reply = QMessageBox.warning(self, '高危操作确认', 
                                     f"即将永久清除资产账户 [{target_name}] 的所有授权，此操作不可逆。是否继续？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                     
        if reply == QMessageBox.Yes:
            try:
                # 依赖后端 database.py 实现的 delete_user() 方法
                self.db.delete_user(target_id)
                self._load_users() # 同步刷新视图
            except Exception as e:
                event_bus.db_error.emit(f"删除账户失败: {str(e)}")