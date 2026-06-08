import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QFormLayout, QComboBox, QLineEdit, QPushButton, 
                             QFileDialog, QMessageBox)
from PyQt5.QtCore import QSettings, Qt

class SettingsDashboard(QWidget):
    def __init__(self):
        super().__init__()
        # 初始化 QSettings，参数为 (组织名称, 应用名称)
        self.settings = QSettings("IndustrialAI", "DefectEngine")
        self._setup_ui()
        self._load_config()
        self._bind_events()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        # 增加外围留白与区块间距，提升呼吸感
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)

        # 1. UI 与外观设置组
        group_ui = QGroupBox("个性化与外观 (Appearance)")
        form_ui = QFormLayout(group_ui)
        form_ui.setSpacing(16)
        
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Dark", "Light", "System"])
        
        form_ui.addRow("系统主题:", self.combo_theme)

        # 2. 默认工程参数组
        group_project = QGroupBox("工程缺省参数 (Project Defaults)")
        form_project = QFormLayout(group_project)
        form_project.setSpacing(16)
        
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("指定检测结果与日志的默认落盘目录...")
        
        self.btn_browse_dir = QPushButton("浏览...")
        self.btn_browse_dir.setProperty("type", "secondary") # 赋予次级按钮样式
        self.btn_browse_dir.setCursor(Qt.PointingHandCursor)
        
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)
        dir_layout.addWidget(self.output_dir)
        dir_layout.addWidget(self.btn_browse_dir)
        
        self.combo_backend = QComboBox()
        self.combo_backend.addItems(["CUDA (Nvidia GPU)", "TensorRT (高吞吐)", "CPU (回退模式)"])
        
        form_project.addRow("默认输出目录:", dir_layout)
        form_project.addRow("首选算力后端:", self.combo_backend)

        # 3. 可观测性设置组
        group_obs = QGroupBox("可观测性与日志 (Observability)")
        form_obs = QFormLayout(group_obs)
        form_obs.setSpacing(16)
        
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG (详尽调试)", "INFO (标准信息)", "WARNING (仅警告)", "ERROR (仅错误)"])
        
        form_obs.addRow("全局日志级别:", self.combo_log_level)

        # 4. 底部操作栏
        action_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("保存并应用 (Save & Apply)")
        self.btn_save.setProperty("type", "primary") # 剥离硬编码，交由 QSS 的 primary 接管
        self.btn_save.setCursor(Qt.PointingHandCursor)
        
        self.btn_reset = QPushButton("恢复出厂设置 (Reset)")
        self.btn_reset.setProperty("type", "danger") # 剥离硬编码，交由 QSS 的 danger 接管
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        
        action_layout.addStretch()
        action_layout.addWidget(self.btn_reset)
        action_layout.addWidget(self.btn_save)

        # 组装至主视图
        main_layout.addWidget(group_ui)
        main_layout.addWidget(group_project)
        main_layout.addWidget(group_obs)
        main_layout.addStretch()
        main_layout.addLayout(action_layout)

    def _bind_events(self):
        self.btn_browse_dir.clicked.connect(self._browse_output_dir)
        self.btn_save.clicked.connect(self._save_config)
        self.btn_reset.clicked.connect(self._reset_config)

    def _browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择默认输出目录")
        if path:
            self.output_dir.setText(path)

    def _load_config(self):
        """将 QSettings 中的持久化数据反推回 UI 控件"""
        self.combo_theme.setCurrentText(self.settings.value("ui/theme", "Dark"))
        
        default_dir = os.path.join(os.path.expanduser("~"), "DefectEngine_Output")
        self.output_dir.setText(self.settings.value("project/output_dir", default_dir))
        self.combo_backend.setCurrentText(self.settings.value("project/backend", "CUDA (Nvidia GPU)"))
        
        self.combo_log_level.setCurrentText(self.settings.value("obs/log_level", "INFO (标准信息)"))

    def _save_config(self):
        """序列化 UI 状态并固化至本地"""
        selected_theme = self.combo_theme.currentText()
        self.settings.setValue("ui/theme", selected_theme)
        self.settings.setValue("project/output_dir", self.output_dir.text())
        self.settings.setValue("project/backend", self.combo_backend.currentText())
        self.settings.setValue("obs/log_level", self.combo_log_level.currentText())
        
        # 强制将内存中的配置写入磁盘
        self.settings.sync() 
        
        # 引入事件总线并触发动态换肤
        from utils.signals import event_bus
        event_bus.theme_changed.emit(selected_theme)
        
        QMessageBox.information(self, "设置已保存", "全局配置已更新，主题已动态应用。")

    def _reset_config(self):
        """高危操作防御：二次确认并清空 QSettings"""
        reply = QMessageBox.warning(
            self, '警告', '确定要清除所有自定义配置并恢复出厂默认值吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings.clear()
            self._load_config() # 重新加载缺省值覆盖 UI
            QMessageBox.information(self, "已重置", "配置已恢复为出厂状态。")