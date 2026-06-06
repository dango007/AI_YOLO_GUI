import traceback
from PyQt5.QtCore import QThread
from utils.signals import event_bus

# 引入我们刚才编写的真实适配器
from backend.yolo_engine import UltralyticsAdapter

class InferenceWorker(QThread):
    def __init__(self, config_dict):
        """
        :param config_dict: UI 传递的扁平化配置字典
        """
        super().__init__()
        self.config = config_dict
        self._is_running = True
        self.engine = None

    def stop(self):
        """UI 层触发中断时的安全退出标志位"""
        self._is_running = False

    def run(self):
        try:
            # 1. 初始化引擎与预热模型 (这会阻塞当前线程，但不会卡死 UI主线程)
            self.engine = UltralyticsAdapter(
                model_path=self.config.get('model_path'),
                conf_thres=self.config.get('conf', 0.5),
                iou_thres=self.config.get('iou', 0.45),
                backend=self.config.get('hardware', 'CUDA')
            )
            event_bus.engine_ready.emit(True, f"YOLO 模型挂载成功。算力后端: {self.engine.device}")

            # 2. 获取数据源并测算总数 (用于进度条)
            source = self.config.get('source_path')
            total_frames = self._estimate_total_frames(source)

            # 3. 消费推理生成器
            generator = self.engine.stream_predict(source)
            
            for payload in generator:
                if not self._is_running:
                    event_bus.inference_error.emit("推理任务已被用户主动终止。")
                    break
                
                # 推送渲染数据至 UI
                event_bus.inference_result.emit(payload)
                
                # 推送进度
                current_frame = payload['frame_id'] + 1
                event_bus.inference_progress.emit(current_frame, total_frames)

        except Exception as e:
            # 捕获 YOLO 内部崩溃、显存溢出 (CUDA OOM) 或文件读取异常
            error_trace = traceback.format_exc()
            event_bus.inference_error.emit(f"推理引擎异常崩溃:\n{str(e)}\n\nTraceback:\n{error_trace}")
            
        finally:
            # 强制显存清场
            if self.engine:
                self.engine.release()
            event_bus.inference_finished.emit()

    def _estimate_total_frames(self, source):
        """
        估算任务总帧数，辅助 UI 渲染进度条。
        (非核心业务，使用简易嗅探逻辑)
        """
        if source in ['0', 0]: return 0 # 实时流无总数
        
        import os
        import cv2
        
        if os.path.isdir(source):
            valid_exts = {'.jpg', '.png', '.jpeg', '.bmp'}
            return len([f for f in os.listdir(source) if os.path.splitext(f)[-1].lower() in valid_exts])
            
        if os.path.isfile(source):
            ext = os.path.splitext(source)[-1].lower()
            if ext in {'.mp4', '.avi', '.mkv'}:
                cap = cv2.VideoCapture(source)
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                return total if total > 0 else 0
            elif ext in {'.jpg', '.png', '.jpeg', '.bmp'}:
                return 1
                
        return 0