import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMessageBox, QStatusBar, QListWidget, QStackedWidget)
from PyQt5.QtCore import Qt

# 核心总线与必须的子组件
from utils.signals import event_bus
from ui.inference_ui import InferenceDashboard

# 采用防御性导入模式
try:
    from ui.analysis_ui import ResultAnalysisDashboard
except ImportError:
    ResultAnalysisDashboard = None

try:
    from ui.user_mgmt_ui import UserManagementDashboard
except ImportError:
    UserManagementDashboard = None

try:
    from ui.settings_ui import SettingsDashboard
except ImportError:
    SettingsDashboard = None


class MainWindow(QMainWindow):
    def __init__(self, user_context):
        super().__init__()
        self.user_context = user_context
        self._setup_ui()
        self._bind_global_signals()

    def _setup_ui(self):
        # 窗口基础属性
        self.setWindowTitle(f"工业 AI 缺陷检测系统 - 当前用户: [{self.user_context.get('username', 'Unknown')}]")
        self.resize(1440, 900)  
        self.setMinimumSize(1024, 768)

        # ==================== 核心重构：使用现代侧边栏架构 ====================
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) # 消除边缘空隙
        main_layout.setSpacing(0)

        # 1. 侧边导航栏 (替代原 QTabBar)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("mainSidebar")
        self.sidebar.setFixedWidth(140)
        self.sidebar.setFocusPolicy(Qt.NoFocus) # 消除点击时产生的虚线框
        
        # 2. 右侧多视图堆叠容器 (替代原 QTabWidget 内容区)
        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.stack)

        # 路由绑定：点击侧边栏自动切换右侧页面
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        # ======================================================================

        # 挂载各业务模块
        self.inference_tab = InferenceDashboard()
        self._add_module("推理引擎", self.inference_tab)

        if ResultAnalysisDashboard:
            self.analysis_tab = ResultAnalysisDashboard()
            self._add_module("数据洞察", self.analysis_tab)
        else:
            self._mount_placeholder_tab("数据洞察")

        if self.user_context.get('role') == 'admin':
            if UserManagementDashboard:
                current_id = self.user_context.get('id') 
                self.user_mgmt_tab = UserManagementDashboard(current_id)
                self._add_module("系统治理", self.user_mgmt_tab)

        if SettingsDashboard:
            self.settings_tab = SettingsDashboard()
            self._add_module("系统设置", self.settings_tab)
        else:
            self._mount_placeholder_tab("系统设置")

        # 默认选中第一个模块
        if self.sidebar.count() > 0:
            self.sidebar.setCurrentRow(0)

        # 挂载底部状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"系统总线就绪。当前权限级别: {self.user_context.get('role', 'user').upper()}")

    def _add_module(self, title, widget):
        """内部辅助方法：注册新模块到侧边栏与视图栈"""
        self.sidebar.addItem(title)
        self.stack.addWidget(widget)

    def _mount_placeholder_tab(self, title):
        """占位符渲染器"""
        tab = QWidget()
        layout = QVBoxLayout()
        label = QLabel(f"[{title}] 模块尚未加载或不存在对应的 Python 视图实现...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #7f8c8d; font-size: 16px; font-weight: bold;")
        layout.addWidget(label)
        tab.setLayout(layout)
        self._add_module(title, tab)

    def _bind_global_signals(self):
        event_bus.db_error.connect(self._handle_global_error)

    def _handle_global_error(self, err_msg):
        self.statusBar.showMessage("检测到全局致命异常！", 5000)
        QMessageBox.critical(self, "系统底层错误", err_msg)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, '系统退出确认',
            '确定要关闭工作台吗？进行中的 AI 推理作业将被强制切断。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if hasattr(self, 'inference_tab') and self.inference_tab.worker:
                if self.inference_tab.worker.isRunning():
                    self.statusBar.showMessage("正在销毁推理计算线程，请稍候...")
                    self.inference_tab.worker.stop()
                    self.inference_tab.worker.wait(2000) 
            event.accept()
        else:
            event.ignore()