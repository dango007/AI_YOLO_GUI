class ThemeEngine:
    """主题构建与样式分发引擎"""
    
    # 深色工业视觉主题
    DARK_THEME = """
    /* 基础通用容器 */
    QWidget {
        background-color: #1E1E1E;
        color: #D4D4D4;
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        font-size: 13px;
    }
    
    /* 交互式输入域 */
    QLineEdit, QComboBox, QDateEdit {
        background-color: #2D2D2D;
        border: 1px solid #3F3F46;
        border-radius: 4px;
        padding: 5px;
        selection-background-color: #062F4A;
    }
    QLineEdit:focus {
        border: 1px solid #007ACC;
    }
    
    /* 动作触发器 */
    QPushButton {
        background-color: #0E639C;
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #1177BB;
    }
    QPushButton:pressed {
        background-color: #094771;
    }
    QPushButton:disabled {
        background-color: #3C3C3C;
        color: #808080;
    }
    
    /* 结构化数据视图 (表格) */
    QTableWidget {
        background-color: #252526;
        gridline-color: #3F3F46;
        border: 1px solid #3F3F46;
    }
    QHeaderView::section {
        background-color: #333333;
        color: #CCCCCC;
        padding: 4px;
        border: 1px solid #3F3F46;
        font-weight: bold;
    }
    
    /* 分组控制台 */
    QGroupBox {
        border: 1px solid #3F3F46;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px 0 3px;
        color: #007ACC;
    }
    """

    @staticmethod
    def apply_theme(app_instance, theme_mode="dark"):
        """将样式表注入 QApplication 生命周期"""
        if theme_mode == "dark":
            app_instance.setStyleSheet(ThemeEngine.DARK_THEME)
        # 预留 light/auto 主题扩展口
        else:
            app_instance.setStyleSheet("")