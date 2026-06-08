import os
import re
import cv2
import json
import numpy as np
from PyQt5.QtWidgets import (QWidget, QMessageBox, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QLabel, QPushButton, QLineEdit,
                             QSlider, QComboBox, QRadioButton, QCheckBox,
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QFileDialog, QHeaderView, QSplitter, QFormLayout, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSlot, QSettings
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont

from backend.inference_engine import InferenceWorker
from utils.signals import event_bus

class InferenceDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._current_image = None
        self._current_detections = []
        self.current_session_dir = None
        self.actual_output_dir = None
        self._setup_ui()
        self._bind_signals()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10) # 增加全局呼吸感
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel") # 挂载语义化 ID，继承统一底色
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

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

        group_task = QGroupBox("任务编排 (Task Orchestration)")
        v_task = QVBoxLayout(group_task)
        
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
        
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("挂载输入数据路径...")
        self.btn_load_input = QPushButton("浏览")
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_path)
        input_row.addWidget(self.btn_load_input)

        self.chk_save_res = QCheckBox("持久化输出结果至本地目录")
        
        btn_row = QHBoxLayout()
        self.btn_start_task = QPushButton("启动推理 (Start)")
        self.btn_start_task.setProperty("type", "primary") # 剥离硬编码，交由 QSS 渲染
        self.btn_start_task.setCursor(Qt.PointingHandCursor)
        
        self.btn_stop_task = QPushButton("中断任务 (Stop)")
        self.btn_stop_task.setProperty("type", "danger")
        self.btn_stop_task.setEnabled(False)
        self.btn_stop_task.setCursor(Qt.PointingHandCursor)
        
        btn_row.addWidget(self.btn_start_task)
        btn_row.addWidget(self.btn_stop_task)

        v_task.addLayout(source_row)
        v_task.addLayout(input_row)
        v_task.addWidget(self.chk_save_res)
        v_task.addLayout(btn_row)
        left_layout.addWidget(group_task)

        group_monitor = QGroupBox("系统状态与监控 (Monitoring)")
        v_monitor = QVBoxLayout(group_monitor)
        
        self.lbl_status = QLabel("状态: 就绪 (Ready)")
        self.lbl_status.setProperty("status", "normal") # 赋予初始状态
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        self.lbl_throughput = QLabel("吞吐量: 0 FPS / 总计: 0 帧")
        
        v_monitor.addWidget(self.lbl_status)
        v_monitor.addWidget(self.progress_bar)
        v_monitor.addWidget(self.lbl_throughput)
        left_layout.addWidget(group_monitor)
        
        left_layout.addStretch()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.label_canvas = QLabel("等待数据接入...")
        self.label_canvas.setObjectName("videoCanvas") # 剥离硬编码背景
        self.label_canvas.setAlignment(Qt.AlignCenter)
        self.label_canvas.setMinimumSize(640, 480)
        
        self.table_results = QTableWidget(0, 6)
        self.table_results.setCornerButtonEnabled(False) 
        self.table_results.setHorizontalHeaderLabels(["序号", "时间戳", "帧ID", "缺陷分类", "置信度", "坐标 (x1,y1,x2,y2)"])
        self.table_results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_results.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_results.setSelectionBehavior(QTableWidget.SelectRows)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.label_canvas)
        right_splitter.addWidget(self.table_results)
        right_splitter.setStretchFactor(0, 7)
        right_splitter.setStretchFactor(1, 3)
        right_splitter.setHandleWidth(2) # 优化分割线宽度
        
        right_layout.addWidget(right_splitter)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setHandleWidth(2)
        main_layout.addWidget(splitter)

    def _bind_signals(self):
        self.slider_conf.valueChanged.connect(lambda v: self.lbl_conf_val.setText(f"{v/100.0:.2f}"))
        self.slider_iou.valueChanged.connect(lambda v: self.lbl_iou_val.setText(f"{v/100.0:.2f}"))
        self.btn_load_model.clicked.connect(self._browse_model)
        self.btn_load_input.clicked.connect(self._browse_input)
        self.btn_start_task.clicked.connect(self._start_inference)
        self.btn_stop_task.clicked.connect(self._stop_inference)
        
        event_bus.engine_ready.connect(self._on_engine_ready)
        event_bus.inference_result.connect(self._update_canvas_and_table)
        event_bus.inference_progress.connect(self._update_progress_bar)
        event_bus.inference_error.connect(self._handle_error)
        event_bus.inference_finished.connect(self._reset_ui_state)
        self.table_results.itemSelectionChanged.connect(self._on_table_row_selected)

    def _set_status(self, text, status_type):
        """统一的状态更新管线，触发 QSS 重绘"""
        self.lbl_status.setText(text)
        self.lbl_status.setProperty("status", status_type)
        self.lbl_status.style().polish(self.lbl_status) # 必须调用 polish 强制刷新样式

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型权重", "", "Model Files (*.pt *.onnx)")
        if path: self.model_path.setText(path)

    def _browse_input(self):
        if self.radio_dir.isChecked():
            path = QFileDialog.getExistingDirectory(self, "选择输入目录")
        elif self.radio_vid.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "选择视频", "", "Video Files (*.mp4 *.avi *.mkv)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择图像", "", "Images (*.png *.jpg *.bmp)")
        if path: self.input_path.setText(path)

    def _start_inference(self):
        if not self.model_path.text():
            QMessageBox.warning(self, "校验失败", "必须指定模型权重路径。")
            return
            
        settings = QSettings("IndustrialAI", "DefectEngine")
        default_dir = os.path.join(os.path.expanduser("~"), "DefectEngine_Output")
        target_output_dir = settings.value("project/output_dir", default_dir)
        os.makedirs(target_output_dir, exist_ok=True)

        self.current_session_dir = None
        self.actual_output_dir = None

        config = {
            'source_path': self.input_path.text(),
            'model_path': self.model_path.text(),
            'conf': self.slider_conf.value() / 100.0,
            'iou': self.slider_iou.value() / 100.0,
            'hardware': self.combo_backend.currentText(),
            'save_result': self.chk_save_res.isChecked(),
            'output_dir': target_output_dir  
        }

        self.btn_start_task.setEnabled(False)
        self.btn_stop_task.setEnabled(True)
        self.table_results.setRowCount(0)
        
        self._set_status("状态: 引擎初始化中...", "warning")

        self.worker = InferenceWorker(config)
        self.worker.start()

    def _stop_inference(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._set_status("状态: 正在终止线程...", "warning")

    @pyqtSlot(bool, str, str)
    def _on_engine_ready(self, status, msg, actual_dir=None):
        if status:
            self._set_status("状态: 推理中 (Running)", "success")
            if actual_dir:
                self.actual_output_dir = actual_dir
                self.current_session_dir = actual_dir 
        else:
            self._handle_error(msg)

    @pyqtSlot(dict)
    def _update_canvas_and_table(self, payload):
        try:
            frame_id = payload.get('frame_id', 0)
            timestamp = payload.get('timestamp', 'N/A')
            image_data = payload.get('image_data')
            detections = payload.get('detections', [])

            if hasattr(timestamp, 'strftime'):
                timestamp = timestamp.strftime("%H:%M:%S.%f")[:-3]

            if isinstance(image_data, np.ndarray):
                self._render_canvas(image_data, detections)
                self._current_image = image_data.copy()
                self._current_detections = detections

            for det in detections:
                row_idx = self.table_results.rowCount()
                self.table_results.insertRow(row_idx)
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
                    
            self.table_results.scrollToBottom()
            
        except Exception as e:
            print(f"[Render Error] UI 渲染管道异常: {str(e)}")

    @pyqtSlot(int, int)
    def _update_progress_bar(self, current, total):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.lbl_throughput.setText(f"处理进度: {current} / {total} 帧")
        else:
            self.lbl_throughput.setText(f"已处理帧数: {current}")

    @pyqtSlot(str)
    def _handle_error(self, err_msg):
        QMessageBox.critical(self, "系统运行时异常", err_msg)
        self._reset_ui_state()

    @pyqtSlot()
    def _reset_ui_state(self):
        self.btn_start_task.setEnabled(True)
        self.btn_stop_task.setEnabled(False)
        self.progress_bar.setValue(0)
        self._set_status("状态: 就绪 (Ready)", "normal")
        
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _render_canvas(self, image_data, detections, highlight_bbox_str=None):
        if not isinstance(image_data, np.ndarray):
            return

        if not image_data.flags['C_CONTIGUOUS']:
            image_data = np.ascontiguousarray(image_data)

        h, w, ch = image_data.shape
        bytes_per_line = ch * w
        q_img = QImage(image_data.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)

        highlight_bbox = None
        if isinstance(highlight_bbox_str, tuple) and len(highlight_bbox_str) == 4:
            highlight_bbox = tuple(map(float, highlight_bbox_str))
        elif isinstance(highlight_bbox_str, str):
            nums = re.findall(r"[\d.]+", highlight_bbox_str)
            if len(nums) == 4:
                highlight_bbox = tuple(map(float, nums))

        if detections:
            painter = QPainter(pixmap)
            font = QFont("Arial", 12, QFont.Bold)
            painter.setFont(font)
            
            for det in detections:
                cls_name = det.get('class', 'Unknown')
                conf = det.get('conf', 0.0)
                bbox = det.get('bbox', [0,0,0,0])
                x1, y1, x2, y2 = map(round, bbox)
                
                is_highlighted = False
                if highlight_bbox:
                    is_highlighted = all(abs(a - b) < 0.2 for a, b in zip(bbox, highlight_bbox))
                
                if is_highlighted:
                    box_color = QColor(255, 235, 59)
                    painter.setPen(QPen(box_color, 5))
                else:
                    box_color = QColor(255, 0, 0)
                    painter.setPen(QPen(box_color, 3))
                
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)
                
                text = f"{cls_name} {conf:.2f}"
                label_y = max(12, y1 - 5)
                text_color = QColor(0, 0, 0) if is_highlighted else QColor(255, 255, 255)
                painter.setPen(QPen(text_color))
                painter.setBackgroundMode(Qt.OpaqueMode)
                painter.setBackground(box_color)
                painter.drawText(x1, label_y, text)
                
            painter.end()

        scaled_pixmap = pixmap.scaled(self.label_canvas.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label_canvas.setPixmap(scaled_pixmap)

    def _on_table_row_selected(self):
        if self.worker and self.worker.isRunning():
            return

        selected_items = self.table_results.selectedItems()
        if not selected_items:
            if self._current_image is not None:
                self._render_canvas(self._current_image, self._current_detections)
            return
        
        row = selected_items[0].row()
        
        item_id = self.table_results.item(row, 2)
        item_bbox = self.table_results.item(row, 5)
        if not item_id or not item_bbox:
            return
            
        frame_id_str = item_id.text()
        bbox_str = item_bbox.text()
        
        try:
            nums = re.findall(r"[\d.]+", bbox_str)
            highlight_bbox_tuple = tuple(map(float, nums)) if len(nums) == 4 else None

            session_dir = self.actual_output_dir or self.current_session_dir
            
            if not session_dir:
                if self._current_image is not None:
                    self._render_canvas(self._current_image, self._current_detections, highlight_bbox_str=highlight_bbox_tuple)
                return
                
            frame_id = int(frame_id_str)
            img_path = os.path.join(session_dir, f"frame_{frame_id:06d}.jpg")
            json_path = os.path.join(session_dir, f"frame_{frame_id:06d}.json")
            
            if not os.path.exists(img_path) or not os.path.exists(json_path):
                if self._current_image is not None:
                    self._render_canvas(self._current_image, self._current_detections, highlight_bbox_str=highlight_bbox_tuple)
                return
                
            img_data = np.fromfile(img_path, dtype=np.uint8)
            img_bgr = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            
            if img_bgr is None: return
            
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            
            with open(json_path, 'r', encoding='utf-8') as f:
                detections = json.load(f)
            
            self._render_canvas(img_rgb, detections, highlight_bbox_str=highlight_bbox_tuple)
                
        except Exception as e:
            print(f"高亮重绘失败: {str(e)}")