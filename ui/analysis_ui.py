import csv
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDateEdit,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSplitter, QGroupBox, QFormLayout,
                             QComboBox, QMessageBox, QFileDialog, QLabel)
from PyQt5.QtChart import QChart, QChartView, QPieSeries
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import QDate, Qt, pyqtSlot
from PyQt5.QtChart import QChart, QChartView, QPieSeries, QPieSlice # 确保导入了 QPieSlice

from backend.database import DatabaseManager
from utils.signals import event_bus

class ResultAnalysisDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self._setup_ui()
        self._bind_signals()
        self._execute_query()

    def _setup_ui(self):
        # 顶层使用 QSplitter 实现左右拖拽
        main_splitter = QSplitter(Qt.Horizontal, self)
        main_splitter.setHandleWidth(2)
        main_splitter.setChildrenCollapsible(False)

        # ==================== 左侧：高级过滤与操作面板 ====================
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        # 不再使用 setFixedWidth，改为由 splitter 设置初始尺寸
        left_panel.setMinimumWidth(220)
        filter_layout = QVBoxLayout(left_panel)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        group_filter = QGroupBox("多维数据检索 (Data Filter)")
        group_filter.setObjectName("filterGroup")
        form_layout = QFormLayout(group_filter)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # 时间边界
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        self.date_start.setObjectName("dateStart")

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setObjectName("dateEnd")

        # 缺陷模式
        self.combo_defect_type = QComboBox()
        self.combo_defect_type.addItems([
            "全部 (All)",
            "crazing (龟裂)",
            "inclusion (夹杂物)",
            "patches (斑块)",
            "pitted_surface (麻点)",
            "rolled-in_scale (氧化铁皮)",
            "scratches (划痕)"
        ])
        self.combo_defect_type.setObjectName("defectTypeCombo")

        form_layout.addRow("起始日期:", self.date_start)
        form_layout.addRow("截止日期:", self.date_end)
        form_layout.addRow("缺陷模式:", self.combo_defect_type)

        # 按钮
        self.btn_query = QPushButton("执行聚合查询 (Query)")
        self.btn_query.setProperty("type", "primary")
        self.btn_query.setCursor(Qt.PointingHandCursor)

        self.btn_export = QPushButton("导出流水至 CSV (Export)")
        self.btn_export.setProperty("type", "secondary")
        self.btn_export.setCursor(Qt.PointingHandCursor)

        filter_layout.addWidget(group_filter)
        filter_layout.addWidget(self.btn_query)
        filter_layout.addWidget(self.btn_export)
        filter_layout.addStretch()

        # ==================== 右侧：洞察视图区 ====================
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(2)
        right_splitter.setChildrenCollapsible(False)

        # 图表
        chart_container = QWidget()
        chart_layout = QHBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        self.pie_chart_view = QChartView()
        self.pie_chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.pie_chart_view)

        # 表格
        group_table = QGroupBox("历史检测台账 (Task Pipeline)")
        group_table.setObjectName("tableGroup")
        table_layout = QVBoxLayout(group_table)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_history = QTableWidget(0, 10)
        self.table_history.setObjectName("historyTable")
        self.table_history.setHorizontalHeaderLabels([
            "任务 ID", "执行时间", "吞吐量(张)",
            "crazing", "inclusion", "patches",
            "pitted_surface", "rolled-in_scale", "scratches", "状态"
        ])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_history.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_history.setSortingEnabled(True)
        table_layout.addWidget(self.table_history)

        right_splitter.addWidget(chart_container)
        right_splitter.addWidget(group_table)
        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 6)

        # 将左右面板加入顶层 splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_splitter)

        # 设置初始比例：左侧 280px，右侧占满剩余空间
        main_splitter.setSizes([280, 800])
        main_splitter.setStretchFactor(0, 0)  # 左侧不随窗口拉伸
        main_splitter.setStretchFactor(1, 1)  # 右侧完全拉伸

        # 主布局仅包含 splitter
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.addWidget(main_splitter)

    def _bind_signals(self):
        self.btn_query.clicked.connect(self._execute_query)
        self.btn_export.clicked.connect(self._export_to_csv)
        event_bus.inference_finished.connect(self._execute_query)

    def _execute_query(self):
        start_date = self.date_start.date().toString(Qt.ISODate)
        end_date = self.date_end.date().toString(Qt.ISODate)
        type_filter = self.combo_defect_type.currentText()

        try:
            real_data = self.db.get_analysis_data(start_date, end_date, type_filter)
            # ======= 核心修复 1：将当前的筛选状态注入数据包中传递给渲染层 =======
            real_data['current_filter'] = type_filter
            self.update_dashboard(real_data)
        except Exception as e:
            event_bus.db_error.emit(f"聚合查询执行失败: {str(e)}")

    @pyqtSlot(dict)
    def update_dashboard(self, data_payload):
        if not data_payload:
            return

        distribution = data_payload.get("distribution", {})
        self._render_pie_chart(distribution)

        rows = data_payload.get("history_rows", [])
        # 获取注入的过滤状态，默认为全部
        current_filter = data_payload.get("current_filter", "全部 (All)")

        # ======= 核心修复 2：建立动态高亮列的映射规则 =======
        highlight_cols = []
        if "全部" in current_filter or "All" in current_filter:
            # 如果是全部，高亮所有 6 种缺陷列 (索引 3 到 8)
            highlight_cols = [3, 4, 5, 6, 7, 8]
        else:
            # 如果是特定缺陷，精准定位对应列
            if "crazing" in current_filter: highlight_cols = [3]
            elif "inclusion" in current_filter: highlight_cols = [4]
            elif "patches" in current_filter: highlight_cols = [5]
            elif "pitted_surface" in current_filter: highlight_cols = [6]
            elif "rolled-in_scale" in current_filter: highlight_cols = [7]
            elif "scratches" in current_filter: highlight_cols = [8]
        # ====================================================

        self.table_history.setSortingEnabled(False)
        self.table_history.setRowCount(0)

        for r_idx, row_data in enumerate(rows):
            self.table_history.insertRow(r_idx)
            for c_idx, cell_value in enumerate(row_data):
                item = QTableWidgetItem(str(cell_value))
                item.setTextAlignment(Qt.AlignCenter)
                
                # ======= 核心修复 3：使用动态计算出的 highlight_cols 进行判定 =======
                if c_idx in highlight_cols and str(cell_value).isdigit() and int(cell_value) > 0:
                    item.setForeground(QColor(211, 47, 47)) # 警示红
                    item.setFont(QFont("Arial", 10, QFont.Bold))
                    
                self.table_history.setItem(r_idx, c_idx, item)

        self.table_history.setSortingEnabled(True)

    def _render_pie_chart(self, defect_data):
        series = QPieSeries()
        # 预定义缺陷颜色映射（按固定顺序，避免默认随机色）
        color_map = {
            "crazing": QColor("#F1C40F"),          # 金黄
            "inclusion": QColor("#E67E22"),        # 橙
            "patches": QColor("#3498DB"),          # 蓝
            "pitted_surface": QColor("#9B59B6"),   # 紫
            "rolled-in_scale": QColor("#1ABC9C"),  # 青绿
            "scratches": QColor("#E74C3C"),        # 红
        }

        has_data = False
        for label, count in defect_data.items():
            if count <= 0:
                continue
            has_data = True
            display_label = f"{label} ({count})"
            slice_ = series.append(display_label, count)

            # 设置颜色
            if label in color_map:
                slice_.setColor(color_map[label])
            else:
                slice_.setColor(QColor.fromHsl((hash(label) * 40) % 360, 180, 160))

            # ======= 修复点 1：让所有区块都显示引出线与标签 =======
            slice_.setLabelVisible(True)
            # 让标签在饼图外侧（引出线模式）
            slice_.setLabelPosition(QPieSlice.LabelOutside)
            
            # 特殊处理“裂纹”类：只进行分离突出，不再控制标签可见性
            if "裂纹" in label or "scratches" in label:
                slice_.setExploded(True)
                slice_.setExplodeDistanceFactor(0.05)

            slice_.setBorderColor(QColor(255, 255, 255, 80))
            slice_.setBorderWidth(1)

        chart = QChart()
        if has_data:
            chart.addSeries(series)
        chart.setTitle("缺陷模式全局分布拓扑")
        chart.setTitleFont(QFont("Segoe UI", 14, QFont.Bold))
        chart.setAnimationOptions(QChart.SeriesAnimations)

        # 图例美化
        legend = chart.legend()
        legend.setFont(QFont("Segoe UI", 12))
        legend.setAlignment(Qt.AlignRight)
        legend.setLabelColor(QColor("#2C3E50"))          # 浅色主题下文字颜色（深色下需动态调整）
        legend.setBackgroundVisible(True)
        legend.setColor(QColor(255, 255, 255, 150))      # 半透明白背景，避免遮盖图表

        # 如果使用深色主题，需在外部切换时重新设置图例颜色（此处暂用浅色）
        self.pie_chart_view.setChart(chart)

    def _export_to_csv(self):
        if self.table_history.rowCount() == 0:
            QMessageBox.information(self, "导出提示", "当前无数据可供导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据", "Defect_Analysis_Report.csv", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                headers = [self.table_history.horizontalHeaderItem(i).text() for i in range(self.table_history.columnCount())]
                writer.writerow(headers)
                for row in range(self.table_history.rowCount()):
                    row_data = []
                    for col in range(self.table_history.columnCount()):
                        item = self.table_history.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "导出成功", f"数据已成功导出至:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"文件 I/O 错误: {str(e)}")