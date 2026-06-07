import os
import cv2
import json
import traceback
from datetime import datetime
from PyQt5.QtCore import QThread
from utils.signals import event_bus
from backend.database import DatabaseManager

# 引入真实适配器
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
            # ================= 初始化落盘会话 =================
            save_result = self.config.get('save_result', False)
            output_dir = self.config.get('output_dir', '')
            session_save_path = "" # 初始化为空字符串，防止后续传 None 报错

            # ====== 任务ID与累加器初始化 ======
            task_id = datetime.now().strftime("Task_%Y%m%d_%H%M%S")
            db_manager = DatabaseManager()
            throughput_count = 0
            defect_stats = {
                "crazing": 0, "inclusion": 0, "patches": 0, 
                "pitted_surface": 0, "rolled-in_scale": 0, "scratches": 0
            }
            # ======================================
            
            if save_result and output_dir:
                # 按照时间戳创建独立的任务文件夹
                session_name = datetime.now().strftime("%Y%m%d_%H%M%S_Task")
                session_save_path = os.path.join(output_dir, session_name)
                os.makedirs(session_save_path, exist_ok=True)
            # =========================================================

            # 1. 初始化引擎与预热模型
            self.engine = UltralyticsAdapter(
                model_path=self.config.get('model_path'),
                conf_thres=self.config.get('conf', 0.5),
                iou_thres=self.config.get('iou', 0.45),
                backend=self.config.get('hardware', 'CUDA')
            )
            
            # ========== 核心修复：将真实落盘路径作为第三个参数发射给 UI ==========
            event_bus.engine_ready.emit(True, f"YOLO 模型挂载成功。算力后端: {self.engine.device}", session_save_path)

            # 2. 获取数据源并测算总数
            source = self.config.get('source_path')
            total_frames = self._estimate_total_frames(source)

            # 3. 消费推理生成器
            generator = self.engine.stream_predict(source)
            
            for payload in generator:
                if not self._is_running:
                    event_bus.inference_error.emit("推理任务已被用户主动终止。")
                    break

                # ====== 更新吞吐量与缺陷统计 ======
                throughput_count += 1
                detections = payload.get('detections', [])
                for det in detections:
                    cls_name = det.get('class')
                    if cls_name in defect_stats:
                        defect_stats[cls_name] += 1
                    # 容错：防止模型输出下划线而丢数据
                    elif cls_name == "rolled_in_scale":
                        defect_stats["rolled-in_scale"] += 1
                # ======================================
                
                # ================= 执行落盘保存 =================
                if save_result and session_save_path:
                    self._save_payload(payload, session_save_path)
                # =========================================================

                # 推送渲染数据至 UI
                event_bus.inference_result.emit(payload)
                event_bus.inference_progress.emit(payload['frame_id'] + 1, total_frames)
            
            # ====== 任务循环正常结束后，存入数据库 ======
            final_status = "完成" if self._is_running else "已终止"
            
            if throughput_count > 0:
                db_manager.save_task_record(task_id, throughput_count, defect_stats, final_status)
            # ==============================================

        except Exception as e:
            error_trace = traceback.format_exc()
            event_bus.inference_error.emit(f"推理引擎异常崩溃:\n{str(e)}\n\nTraceback:\n{error_trace}")
            
        finally:
            if self.engine:
                self.engine.release()
            event_bus.inference_finished.emit()

    def _save_payload(self, payload, save_dir):
        """核心落盘逻辑：将单帧图像及检测结果序列化到本地。"""
        try:
            frame_id = payload.get('frame_id', 0)
            image_data = payload.get('image_data') 
            detections = payload.get('detections', [])
            
            # 1. 保存图像文件 (如果包含有效数据)
            if image_data is not None:
                img_bgr = cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR) 
                img_path = os.path.join(save_dir, f"frame_{frame_id:06d}.jpg")
                cv2.imwrite(img_path, img_bgr)
            
            # 2. 保存结构化缺陷数据 (如果有检测到目标才保存，减少垃圾文件)
            if detections:
                json_path = os.path.join(save_dir, f"frame_{frame_id:06d}.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(detections, f, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            print(f"落盘失败 (Frame {payload.get('frame_id')}): {str(e)}")

    def _estimate_total_frames(self, source):
        if source in ['0', 0]: return 0
        
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