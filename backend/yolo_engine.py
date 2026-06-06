import os
import time
import numpy as np
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

class UltralyticsAdapter:
    def __init__(self, model_path, conf_thres=0.5, iou_thres=0.45, backend='CUDA'):
        """
        初始化 YOLO 引擎并加载权重
        """
        if not YOLO:
            raise RuntimeError("未检测到 ultralytics 库，请执行 pip install ultralytics 安装。")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型权重文件不存在: {model_path}")

        self.conf = conf_thres
        self.iou = iou_thres
        
        # 硬件设备映射
        self.device = self._map_device(backend)
        
        # 加载模型 (支持 .pt 或导出的 .onnx/.engine)
        self.model = YOLO(model_path, task='detect')
        
    def _map_device(self, backend_str):
        """将 UI 的算力选项映射为 YOLO 可识别的 device 参数"""
        backend_str = backend_str.upper()
        if "CPU" in backend_str:
            return 'cpu'
        elif "CUDA" in backend_str or "GPU" in backend_str:
            return '0' # 默认使用单卡 GPU_0
        elif "TENSORRT" in backend_str:
            return '0' # TensorRT 通常也挂载在 GPU 上，具体需模型已导出为 .engine
        return 'cpu'

    def stream_predict(self, source_path):
        """
        流式推理发生器 (Generator)。
        使用 stream=True 避免 OOM (内存溢出)，适用于长视频或海量图片的目录检测。
        """
        # 针对不同数据源的特殊处理
        # source_path 可以是 0 (摄像头), 'dir/', 'video.mp4', 'image.jpg'
        if source_path == '0' or source_path == 0:
            source = 0 # 强制转为整数以调用本机摄像头
        else:
            source = source_path

        # 调用原生 YOLO 推理生成器
        results_generator = self.model.predict(
            source=source,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            stream=True,      # 工业级核心：开启流式处理，避免内存爆炸
            verbose=False     # 关闭控制台高频打印，交由 GUI 日志接管
        )

        for frame_idx, result in enumerate(results_generator):
            # 1. 提取原始图像帧 (Numpy 格式，HWC, BGR 排布)
            # 注意: YOLO 内部使用 cv2 读取，图像格式为 BGR
            orig_img_bgr = result.orig_img
            
            # 为了 PyQt5 QImage 渲染，将其转换为 RGB 排布
            img_rgb = np.ascontiguousarray(orig_img_bgr[:, :, ::-1])
            
            # 2. 提取并结构化检测框 (BBox)
            detections = []
            if result.boxes is not None:
                # 获取坐标 (x1, y1, x2, y2), 置信度和类别索引
                boxes = result.boxes.xyxy.cpu().numpy()
                confs = result.boxes.conf.cpu().numpy()
                clss = result.boxes.cls.cpu().numpy()
                names = result.names # 类别字典映射
                
                for box, conf, cls_idx in zip(boxes, confs, clss):
                    detections.append({
                        'class': names[int(cls_idx)],
                        'conf': float(conf),
                        'bbox': box.tolist() # [x1, y1, x2, y2]
                    })
            
            # 3. 封装标准 Payload 向上层 Yield
            payload = {
                'frame_id': frame_idx,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                'image_data': img_rgb,
                'detections': detections
            }
            
            yield payload
            
    def release(self):
        """释放显存资源 (对于 Python 主要是切断引用交由 GC 处理)"""
        if self.model:
            del self.model
            self.model = None