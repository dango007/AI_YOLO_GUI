import sqlite3
import hashlib
from utils.signals import event_bus

class DatabaseManager:
    def __init__(self, db_path="system_data.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 创建 users 表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                        last_login DATETIME
                    )
                ''')

                # 创建 tasks 表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        execution_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        throughput INTEGER DEFAULT 0,
                        crazing_count INTEGER DEFAULT 0,
                        inclusion_count INTEGER DEFAULT 0,
                        patches_count INTEGER DEFAULT 0,
                        pitted_surface_count INTEGER DEFAULT 0,
                        rolled_in_scale_count INTEGER DEFAULT 0,
                        scratches_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT '完成'
                    )
                ''')
                # 初始化默认账户 (工程缺省值)
                cursor.execute("SELECT count(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    self._insert_default_users(cursor)
                conn.commit()
        except sqlite3.Error as e:
            from utils.signals import event_bus
            event_bus.db_error.emit(f"数据库初始化失败: {str(e)}")

                


    def _insert_default_users(self, cursor):
        # 密码在此使用简单哈希作示范，工业级应用需接入加盐算法 (如 bcrypt)
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        user_hash = hashlib.sha256("user123".encode()).hexdigest()
        cursor.executemany(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            [('admin', admin_hash, 'admin'), ('user', user_hash, 'user')]
        )

    def authenticate(self, username, password):
        try:
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, username, role FROM users WHERE username=? AND password_hash=?", 
                    (username, pwd_hash)
                )
                user = cursor.fetchone()
                if user:
                    # 更新最后登录时间
                    cursor.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?", (user['id'],))
                    conn.commit()
                    return dict(user)
                return None
        except sqlite3.Error as e:
            event_bus.db_error.emit(f"认证系统故障: {str(e)}")
            return None
        
    def get_all_users(self):
            """获取全量用户台账"""
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    # 注意：我们之前的 DDL 中未包含 created_at 字段，UI 层已做兼容处理（显示 N/A）
                    cursor.execute("SELECT id, username, role, last_login FROM users")
                    return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                from utils.signals import event_bus
                event_bus.db_error.emit(f"获取用户列表失败: {str(e)}")
                return []

    def add_user(self, username, password, role):
        """新增用户事务，包含密码哈希与防重名校验"""
        try:
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, pwd_hash, role)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # 捕获 UNIQUE 约束异常（用户名已存在）
            return False
        except sqlite3.Error as e:
            from utils.signals import event_bus
            event_bus.db_error.emit(f"添加用户写入磁盘失败: {str(e)}")
            return False

    def delete_user(self, user_id):
        """物理删除指定用户账号"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            from utils.signals import event_bus
            event_bus.db_error.emit(f"执行账户删除事务失败: {str(e)}")
            return False
        
    def get_analysis_data(self, start_date, end_date, type_filter):
        """
        基于 NEU-DET 数据集标准，按时间与分类聚合查询。
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 修复1: 时间边界补偿 (防止截止日期当天的数据被截断)
                start_datetime = f"{start_date} 00:00:00"
                end_datetime = f"{end_date} 23:59:59"
                
                # 修复2: 对齐 NEU-DET 的 6 种缺陷维度
                query = """
                    SELECT task_id, execution_time, throughput, 
                           crazing_count, inclusion_count, patches_count, 
                           pitted_surface_count, rolled_in_scale_count, scratches_count, status
                    FROM tasks
                    WHERE execution_time >= ? AND execution_time <= ?
                """
                params = [start_datetime, end_datetime]
                
                # 动态条件拼装：如果前端下拉框选择了特定缺陷，只查出包含该缺陷的任务流
                if type_filter and "All" not in type_filter and "全部" not in type_filter:
                    if "crazing" in type_filter: query += " AND crazing_count > 0"
                    elif "inclusion" in type_filter: query += " AND inclusion_count > 0"
                    elif "patches" in type_filter: query += " AND patches_count > 0"
                    elif "pitted_surface" in type_filter: query += " AND pitted_surface_count > 0"
                    elif "rolled-in_scale" in type_filter: query += " AND rolled_in_scale_count > 0"
                    elif "scratches" in type_filter: query += " AND scratches_count > 0"
                    
                # 按时间倒序，最新的任务排在上面
                query += " ORDER BY execution_time DESC"
                
                cursor.execute(query, params)
                raw_rows = cursor.fetchall()
                
                history_rows = []
                # 初始化 NEU-DET 六维累加器
                totals = {
                    "crazing": 0, "inclusion": 0, "patches": 0, 
                    "pitted_surface": 0, "rolled-in_scale": 0, "scratches": 0
                }
                
                for row in raw_rows:
                    # 将 SQLite 行数据解包，严格保证顺序，前端将依此顺序插入表格
                    history_rows.append([
                        row['task_id'], 
                        row['execution_time'], 
                        row['throughput'],
                        row['crazing_count'], 
                        row['inclusion_count'], 
                        row['patches_count'], 
                        row['pitted_surface_count'], 
                        row['rolled_in_scale_count'], 
                        row['scratches_count'], 
                        row['status']
                    ])
                    # 累加图表数据
                    totals["crazing"] += row['crazing_count']
                    totals["inclusion"] += row['inclusion_count']
                    totals["patches"] += row['patches_count']
                    totals["pitted_surface"] += row['pitted_surface_count']
                    totals["rolled-in_scale"] += row['rolled_in_scale_count']
                    totals["scratches"] += row['scratches_count']
                    
                return {
                    "distribution": totals,
                    "history_rows": history_rows
                }
        except sqlite3.Error as e:
            from utils.signals import event_bus
            event_bus.db_error.emit(f"读取分析台账失败: {str(e)}")
            return {"distribution": {}, "history_rows": []}