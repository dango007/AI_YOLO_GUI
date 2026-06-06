import numpy as np
from PyQt5.QtWidgets import (QWidget, QMessageBox, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QLabel, QPushButton, QLineEdit,
                             QSlider, QComboBox, QRadioButton, QCheckBox,
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QFileDialog, QHeaderView, QSplitter, QFormLayout, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSlot, QSettings
import os
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont

from backend.inference_engine import InferenceWorker
from utils.signals import event_bus

class InferenceDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._setup_ui()
        self._bind_signals()

    def _setup_ui(self):
        """主布局构建：采用水平拆分器，确保多分辨率下左右区域的自适应伸缩"""
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        
        # ==================== 左侧：控制台面板 ====================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 模型配置组
        group_model = QGroupBox("模型配置 (Model Config)")
        form_model = QFormLayout(group_model)
        
        self.model_path = QLineEdit()
        self.model_path.setPlaceholderText("选择 .pt / .onnx 文件...")
        self.btn_load_model = QPushButton("浏览")
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_path)
        model_row.addWidget(self.btn_load_model)
        
        self.slider_conf = QSlider(Qt.Horizontal)
        self.slider_conf.setRange(1, 100)
        self.slider_conf.setValue(50)
        self.lbl_conf_val = QLabel("0.50")
        conf_row = QHBoxLayout()
        conf_row.addWidget(self.slider_conf)
        conf_row.addWidget(self.lbl_conf_val)
        
        self.slider_iou = QSlider(Qt.Horizontal)
        self.slider_iou.setRange(1, 100)
        self.slider_iou.setValue(45)
        self.lbl_iou_val = QLabel("0.45")
        iou_row = QHBoxLayout()
        iou_row.addWidget(self.slider_iou)
        iou_row.addWidget(self.lbl_iou_val)

        self.combo_backend = QComboBox()
        self.combo_backend.addItems(["CUDA", "TensorRT", "CPU"])

        self.combo_size = QComboBox()
        self.combo_size.addItems(["640x640", "1280x1280", "1920x1080", "Native"])

        form_model.addRow("模型权重:", model_row)
        form_model.addRow("计算引擎:", self.combo_backend)
        form_model.addRow("输入尺寸:", self.combo_size)
        form_model.addRow("置信度阈值 (Conf):", conf_row)
        form_model.addRow("交并比阈值 (IoU):", iou_row)
        left_layout.addWidget(group_model)

        # 2. 任务编排组
        group_task = QGroupBox("任务编排 (Task Orchestration)")
        v_task = QVBoxLayout(group_task)
        
        # 数据源单选
        source_row = QHBoxLayout()
        self.radio_img = QRadioButton("图像")
        self.radio_dir = QRadioButton("目录")
        self.radio_vid = QRadioButton("视频")
        self.radio_cam = QRadioButton("摄像头")
        self.radio_img.setChecked(True)
        self.source_group = QButtonGroup(self)
        for r in [self.radio_img, self.radio_dir, self.radio_vid, self.radio_cam]:
            self.source_group.addButton(r)
            source_row.addWidget(r)
        
        # 路径挂载
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("挂载输入数据路径...")
        self.btn_load_input = QPushButton("浏览")
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_path)
        input_row.addWidget(self.btn_load_input)

        self.chk_save_res = QCheckBox("持久化输出结果至本地目录")
        
        # 控制按钮
        btn_row = QHBoxLayout()
        self.btn_start_task = QPushButton("启动推理 (Start)")
        self.btn_stop_task = QPushButton("中断任务 (Stop)")
        self.btn_stop_task.setEnabled(False)
        self.btn_start_task.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_stop_task.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
        btn_row.addWidget(self.btn_start_task)
        btn_row.addWidget(self.btn_stop_task)

        v_task.addLayout(source_row)
        v_task.addLayout(input_row)
        v_task.addWidget(self.chk_save_res)
        v_task.addLayout(btn_row)
        left_layout.addWidget(group_task)

        # 3. 监控大屏组
        group_monitor = QGroupBox("系统状态与监控 (Monitoring)")
        v_monitor = QVBoxLayout(group_monitor)
        
        self.lbl_status = QLabel("状态: 就绪 (Ready)")
        self.lbl_status.setStyleSheet("color: #1565c0; font-weight: bold;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.lbl_throughput = QLabel("吞吐量: 0 FPS / 总计: 0 帧")
        
        v_monitor.addWidget(self.lbl_status)
        v_monitor.addWidget(self.progress_bar)
        v_monitor.addWidget(self.lbl_throughput)
        left_layout.addWidget(group_monitor)
        
        left_layout.addStretch() # 挤压空白区域

        # ==================== 右侧：可视化工作区 ====================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 渲染画布
        self.label_canvas = QLabel("等待数据接入...")
        self.label_canvas.setAlignment(Qt.AlignCenter)
        self.label_canvas.setStyleSheet("background-color: #1e1e1e; color: #757575; border: 1px solid #424242;")
        self.label_canvas.setMinimumSize(640, 480)
        
        # 结构化结果表格
        self.table_results = QTableWidget(0, 6)
        self.table_results.setHorizontalHeaderLabels(["序号", "时间戳", "帧ID", "缺陷分类", "置信度", "坐标 (x1,y1,x2,y2)"])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_results.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_results.setSelectionBehavior(QTableWidget.SelectRows)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.label_canvas)
        right_splitter.addWidget(self.table_results)
        right_splitter.setStretchFactor(0, 7) # 画布占 7
        right_splitter.setStretchFactor(1, 3) # 表格占 3
        right_layout.addWidget(right_splitter)

        # 组装至主拆分器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        main_layout.addWidget(splitter)

    def _bind_signals(self):
        # UI 交互事件
        self.slider_conf.valueChanged.connect(lambda v: self.lbl_conf_val.setText(f"{v/100.0:.2f}"))
        self.slider_iou.valueChanged.connect(lambda v: self.lbl_iou_val.setText(f"{v/100.0:.2f}"))
        self.btn_load_model.clicked.connect(self._browse_model)
        self.btn_load_input.clicked.connect(self._browse_input)
        self.btn_start_task.clicked.connect(self._start_inference)
        self.btn_stop_task.clicked.connect(self._stop_inference)
        
        # 全局总线事件解耦绑定
        event_bus.engine_ready.connect(self._on_engine_ready)
        event_bus.inference_result.connect(self._update_canvas_and_table)
        event_bus.inference_progress.connect(self._update_progress_bar)
        event_bus.inference_error.connect(self._handle_error)
        event_bus.inference_finished.connect(self._reset_ui_state)

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型权重", "", "Model Files (*.pt *.onnx)")
        if path: self.model_path.setText(path)

    def _browse_input(self):
        # 依据单选按钮状态切换挂载逻辑
        if self.radio_dir.isChecked():
            path = QFileDialog.getExistingDirectory(self, "选择输入目录")
        elif self.radio_vid.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "Video Files (*.mp4 *.avi *.mkv)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择图像", "", "Images (*.png *.jpg *.bmp)")
        if path: self.input_path.setText(path)

    def _start_inference(self):
        # 准入拦截校验
        if not self.model_path.text():
            QMessageBox.warning(self, "校验失败", "必须指定模型权重路径。")
            return
            
        # ---------------- 新增逻辑开始 ----------------
        # 实例化 QSettings 以读取全局配置
        settings = QSettings("IndustrialAI", "DefectEngine")
        # 生成与 settings_ui 一致的缺省兜底目录
        default_dir = os.path.join(os.path.expanduser("~"), "DefectEngine_Output")
        # 读取当前设定的输出目录
        target_output_dir = settings.value("project/output_dir", default_dir)
        # ---------------- 新增逻辑结束 ----------------

        config = {
            'source_path': self.input_path.text(),
            'model_path': self.model_path.text(),
            'conf': self.slider_conf.value() / 100.0,
            'iou': self.slider_iou.value() / 100.0,
            'hardware': self.combo_backend.currentText(),
            'save_result': self.chk_save_res.isChecked(),
            'output_dir': target_output_dir  # <--- 将提取到的路径传递给 Worker
        }

        # 防抖与状态扭转
        self.btn_start_task.setEnabled(False)
        self.btn_stop_task.setEnabled(True)
        self.lbl_status.setText("状态: 引擎初始化中...")
        self.lbl_status.setStyleSheet("color: #f57c00; font-weight: bold;")
        self.table_results.setRowCount(0)

        # 挂载工作线程 (严格禁止直接在主线程调用 predict)
        self.worker = InferenceWorker(config)
        self.worker.start()

    def _stop_inference(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.lbl_status.setText("状态: 正在终止线程...")

    @pyqtSlot(bool, str)
    def _on_engine_ready(self, status, msg):
        if status:
            self.lbl_status.setText("状态: 推理中 (Running)")
            self.lbl_status.setStyleSheet("color: #388e3c; font-weight: bold;")
        else:
            self._handle_error(msg)

    @pyqtSlot(dict)
    def _update_canvas_and_table(self, payload):
        """
        核心渲染与数据绑定槽函数。
        防腐层设计：假定传入的是安全的数据结构，直接进行内存拷贝与像素绘制，不处理任何算法逻辑。
        """
        try:
            # 1. 解析负载
            frame_id = payload.get('frame_id', 0)
            timestamp = payload.get('timestamp', 'N/A')
            image_data = payload.get('image_data') # 假定为 numpy ndarray (H, W, C), RGB 排布
            detections = payload.get('detections', [])

            # 2. QImage 内存映射与渲染
            if isinstance(image_data, np.ndarray):
                h, w, ch = image_data.shape
                bytes_per_line = ch * w
                # 将 numpy 数组转为 QImage。若底层库输出为 BGR，需改用 Format_BGR888 
                q_img = QImage(image_data.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_img)

                # 使用 QPainter 在 Pixmap 上绘制缺陷 BBox (解耦外部库的绘图工具)
                if detections:
                    painter = QPainter(pixmap)
                    font = QFont("Arial", 12, QFont.Bold)
                    painter.setFont(font)
                    
                    for det in detections:
                        cls_name = det.get('class', 'Unknown')
                        conf = det.get('conf', 0.0)
                        x1, y1, x2, y2 = det.get('bbox', [0,0,0,0])
                        
                        # 按类别动态设置画笔颜色（此处简化为红色统一标定）
                        painter.setPen(QPen(QColor(255, 0, 0), 3))
                        painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
                        
                        # 绘制 Label 底色与文字
                        text = f"{cls_name} {conf:.2f}"
                        painter.setPen(QPen(QColor(255, 255, 255)))
                        painter.setBackgroundMode(Qt.OpaqueMode)
                        painter.setBackground(QColor(255, 0, 0))
                        painter.drawText(int(x1), int(y1) - 5, text)
                        
                    painter.end()

                # 自适应缩放并渲染至 UI 画布
                scaled_pixmap = pixmap.scaled(self.label_canvas.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label_canvas.setPixmap(scaled_pixmap)

            # 3. 同步插入 QTableWidget
            for det in detections:
                row_idx = self.table_results.rowCount()
                self.table_results.insertRow(row_idx)
                
                # 填充字段 (序号、时间戳、帧ID、分类、置信度、坐标)
                bbox_str = f"({det.get('bbox')[0]:.1f}, {det.get('bbox')[1]:.1f}, {det.get('bbox')[2]:.1f}, {det.get('bbox')[3]:.1f})"
                
                items = [
                    QTableWidgetItem(str(row_idx + 1)),
                    QTableWidgetItem(str(timestamp)),
                    QTableWidgetItem(str(frame_id)),
                    QTableWidgetItem(str(det.get('class'))),
                    QTableWidgetItem(f"{det.get('conf'):.4f}"),
                    QTableWidgetItem(bbox_str)
                ]
                
                for col_idx, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table_results.setItem(row_idx, col_idx, item)
                    
            # 自动滚动至最新行
            self.table_results.scrollToBottom()
            
        except Exception as e:
            # 静默降级：渲染层的异常不应导致主程序崩溃，抛出至日志或总线即可
            event_bus.inference_error.emit(f"UI 渲染管道异常: {str(e)}")

    @pyqtSlot(int, int)
    def _update_progress_bar(self, current, total):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_throughput.setText(f"处理进度: {current} / {total} 帧")
        else:
            # 应对实时视频流或摄像头等无总帧数场景
            self.lbl_throughput.setText(f"已处理帧数: {current}")

    @pyqtSlot(str)
    def _handle_error(self, err_msg):
        QMessageBox.critical(self, "系统运行时异常", err_msg)
        self._reset_ui_state()

    @pyqtSlot()
    def _reset_ui_state(self):
        self.btn_start_task.setEnabled(True)
        self.btn_stop_task.setEnabled(False)
        self.lbl_status.setText("状态: 就绪 (Ready)")
        self.lbl_status.setStyleSheet("color: #1565c0; font-weight: bold;")
        self.progress_bar.setValue(0)
        
        # 强制垃圾回收清理僵尸线程资源
        if self.worker:
            self.worker.deleteLater()
            self.worker = None