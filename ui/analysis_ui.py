import csv
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDateEdit,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QSplitter, QGroupBox, QFormLayout,
                             QComboBox, QMessageBox, QFileDialog, QLabel)
from PyQt5.QtChart import QChart, QChartView, QPieSeries
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import QDate, Qt, pyqtSlot

from backend.database import DatabaseManager
from utils.signals import event_bus

class ResultAnalysisDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self._setup_ui()
        self._bind_signals()
        
        # 初始化时触发一次默认查询
        self._execute_query()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # ==================== 1. 左侧：高级过滤与操作面板 ====================
        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        filter_layout = QVBoxLayout(left_panel)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        group_filter = QGroupBox("多维数据检索 (Data Filter)")
        form_layout = QFormLayout(group_filter)
        
        # 时间边界控制
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        
        # 模式枚举过滤
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
        
        form_layout.addRow("起始日期:", self.date_start)
        form_layout.addRow("截止日期:", self.date_end)
        form_layout.addRow("缺陷模式:", self.combo_defect_type)
        
        # 操作按钮
        self.btn_query = QPushButton("执行聚合查询 (Query)")
        self.btn_query.setStyleSheet("background-color: #1976d2; color: white; font-weight: bold; padding: 6px;")
        
        self.btn_export = QPushButton("导出流水至 CSV (Export)")
        self.btn_export.setStyleSheet("padding: 6px;")
        
        filter_layout.addWidget(group_filter)
        filter_layout.addWidget(self.btn_query)
        filter_layout.addWidget(self.btn_export)
        filter_layout.addStretch()
        
        # ==================== 2. 右侧：洞察视图区 (Splitter) ====================
        right_splitter = QSplitter(Qt.Vertical)
        
        # 2.1 顶部：可视化图表
        chart_container = QWidget()
        chart_layout = QHBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pie_chart_view = QChartView()
        self.pie_chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.pie_chart_view)
        
        # 2.2 底部：全量流水台账
        group_table = QGroupBox("历史检测台账 (Task Pipeline)")
        table_layout = QVBoxLayout(group_table)
        
        self.table_history = QTableWidget(0, 10) # 改为 10 列
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
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_splitter)

    def _bind_signals(self):
        self.btn_query.clicked.connect(self._execute_query)
        self.btn_export.clicked.connect(self._export_to_csv)
        # ========== 新增：监听全局推理完成信号，实现自动刷新 ==========
        event_bus.inference_finished.connect(self._execute_query)

    def _execute_query(self):
        """
        触发真实数据查询。收集参数并调用底层仓储接口。
        """
        start_date = self.date_start.date().toString(Qt.ISODate)
        end_date = self.date_end.date().toString(Qt.ISODate)
        type_filter = self.combo_defect_type.currentText()
        
        try:
            # 强依赖调用：请求后端数据库进行实时计算与提取
            real_data = self.db.get_analysis_data(start_date, end_date, type_filter)
            self.update_dashboard(real_data)
        except Exception as e:
            event_bus.db_error.emit(f"聚合查询执行失败: {str(e)}")

    @pyqtSlot(dict)
    def update_dashboard(self, data_payload):
        if not data_payload:
            return

        # 1. 重绘饼图
        distribution = data_payload.get("distribution", {})
        self._render_pie_chart(distribution)
        
        # 2. 填充数据表
        rows = data_payload.get("history_rows", [])
        self.table_history.setSortingEnabled(False)
        self.table_history.setRowCount(0)
        
        for r_idx, row_data in enumerate(rows):
            self.table_history.insertRow(r_idx)
            for c_idx, cell_value in enumerate(row_data):
                item = QTableWidgetItem(str(cell_value))
                item.setTextAlignment(Qt.AlignCenter)
                # 对危险缺陷(裂纹)大于0的任务行进行颜色警示
                if c_idx == 5 and str(cell_value).isdigit() and int(cell_value) > 0:
                    item.setForeground(QColor(211, 47, 47))
                    item.setFont(QFont("Arial", 10, QFont.Bold))
                self.table_history.setItem(r_idx, c_idx, item)
                
        self.table_history.setSortingEnabled(True)

    def _render_pie_chart(self, defect_data):
        series = QPieSeries()
        
        has_data = False
        for label, count in defect_data.items():
            if count <= 0: continue
            has_data = True
            slice_ = series.append(f"{label} ({count})", count)
            if "裂纹" in label:
                slice_.setExploded(True)
                slice_.setExplodeDistanceFactor(0.1)
                slice_.setLabelVisible(True)
                slice_.setColor(QColor(211, 47, 47))
        
        chart = QChart()
        if has_data:
            chart.addSeries(series)
        chart.setTitle("缺陷模式全局分布拓扑")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setAlignment(Qt.AlignRight)
        
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