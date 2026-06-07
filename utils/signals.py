from PyQt5.QtCore import QObject, pyqtSignal

class GlobalEventBus(QObject):
    # 推理引擎信号
    # 注意：此处必须声明为接受三个参数 (bool, str, str)
    engine_ready = pyqtSignal(bool, str, str)             # 引擎初始化状态 (成功/失败, 信息, 真实落盘目录)
    inference_progress = pyqtSignal(int, int)             # 进度 (当前帧/总量)
    inference_result = pyqtSignal(dict)                   # 单帧检测结果 (包含 BBox, 置信度等)
    inference_error = pyqtSignal(str)                     # 运行时异常捕获
    inference_finished = pyqtSignal()                     # 任务生命周期结束
    theme_changed = pyqtSignal(str)                       # 主题切换热更新
    
    # 系统与数据库信号
    db_error = pyqtSignal(str)
    auth_success = pyqtSignal(dict)                       # 返回用户上下文 (包含 RBAC 角色)
    
# 全局单例
event_bus = GlobalEventBus()