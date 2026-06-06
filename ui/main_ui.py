import sys
from PyQt5.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QLabel, QMessageBox, QStatusBar)
from PyQt5.QtCore import Qt

# 核心总线与必须的子组件
from utils.signals import event_bus
from ui.inference_ui import InferenceDashboard

# 采用防御性导入模式，保障主程序在子模块缺失时依然能够存活并提供降级界面
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
        self.resize(1440, 900)  # 放大默认基准分辨率
        self.setMinimumSize(1024, 768)

        # 主导航容器
        self.tabs = QTabWidget()
        # 侧边栏布局：在工业控制软件中，侧边栏能够容纳更多模块且不侵占纵向视觉空间
        self.tabs.setTabPosition(QTabWidget.West) 
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # 1. 核心推理工作台 (高优先级强依赖，假设已存在)
        self.inference_tab = InferenceDashboard()
        self.tabs.addTab(self.inference_tab, "推理引擎")

        # 2. 数据洞察模块 (所有人可见)
        if ResultAnalysisDashboard:
            self.analysis_tab = ResultAnalysisDashboard()
            self.tabs.addTab(self.analysis_tab, "数据洞察")
        else:
            self._mount_placeholder_tab("数据洞察")

        # 3. 系统治理模块 (RBAC 防线: 仅 Admin 可见)
        if self.user_context.get('role') == 'admin':
            if UserManagementDashboard:
                # 注入当前登录用户的 ID
                current_id = self.user_context.get('id') 
                self.user_mgmt_tab = UserManagementDashboard(current_id)
                self.tabs.addTab(self.user_mgmt_tab, "系统治理")

        # 4. 全局配置模块
        if SettingsDashboard:
            self.settings_tab = SettingsDashboard()
            self.tabs.addTab(self.settings_tab, "系统设置")
        else:
            self._mount_placeholder_tab("系统设置")

        # 挂载底部状态栏，用于展示全局生命周期信息
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"系统总线就绪。当前权限级别: {self.user_context.get('role', 'user').upper()}")

    def _mount_placeholder_tab(self, title):
        """占位符渲染器：用于隔离未实现模块，保障主控面板不奔溃"""
        tab = QWidget()
        layout = QVBoxLayout()
        label = QLabel(f"[{title}] 模块尚未加载或不存在对应的 Python 视图实现...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #7f8c8d; font-size: 16px; font-weight: bold;")
        layout.addWidget(label)
        tab.setLayout(layout)
        self.tabs.addTab(tab, title)

    def _bind_global_signals(self):
        """挂载全局异常监听，统一在主窗体进行最高级别告警拦截"""
        event_bus.db_error.connect(self._handle_global_error)

    def _handle_global_error(self, err_msg):
        self.statusBar.showMessage("检测到全局致命异常！", 5000)
        QMessageBox.critical(self, "系统底层错误", err_msg)

    def closeEvent(self, event):
        """
        生命周期终结拦截。
        架构铁律：当退出 UI 进程时，必须同步销毁底层的 C++ 线程 (QThread)，
        否则会导致 Segmentation Fault 或显存泄漏。
        """
        reply = QMessageBox.question(
            self, '系统退出确认',
            '确定要关闭工作台吗？进行中的 AI 推理作业将被强制切断。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 暴力清场：查找 inference_tab 中的 worker 是否还在挂载中
            if hasattr(self, 'inference_tab') and self.inference_tab.worker:
                if self.inference_tab.worker.isRunning():
                    self.statusBar.showMessage("正在销毁推理计算线程，请稍候...")
                    self.inference_tab.worker.stop()
                    # 阻塞主线程至多 2000ms 等待 QThread 退出，确保 GPU 显存释放
                    self.inference_tab.worker.wait(2000) 
            event.accept()
        else:
            event.ignore()