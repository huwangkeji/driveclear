#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DriveClear Pro - 磁盘填充器增强版
二次开发版本 - 增加循环次数、定时启动/关闭、日志记录、蓝色现代风格UI
"""

import sys
import os
import time
import random
import threading
import logging
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QComboBox, QLabel,
                              QSpinBox, QCheckBox, QTextEdit, QProgressBar,
                              QGroupBox, QFileDialog, QMessageBox,
                              QSystemTrayIcon, QMenu, QAction, QFrame, QSplitter,
                              QStyle, QDialog, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF, QEvent
from PyQt5.QtGui import (QIcon, QFont, QColor, QPalette, QPixmap, QPainter, 
                          QLinearGradient, QRadialGradient, QPen, QBrush, 
                          QPolygonF, QKeySequence)

# Windows 全局热键 API
if os.name == 'nt':
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    # RegisterHotKey / UnregisterHotKey
    MOD_ALT      = 0x0001
    MOD_CONTROL  = 0x0002
    MOD_SHIFT    = 0x0004
    MOD_WIN      = 0x0008
    WM_HOTKEY    = 0x0312

# 单实例互斥体名称
MUTEX_NAME = "Global\\DriveClearPro_SingleInstance_2026"

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"driveclear_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_app_icon():
    """用 QPainter 绘制应用图标（蓝色圆形+磁盘+闪电）"""
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    # === 1. 外圆背景 - 蓝色渐变 ===
    grad = QRadialGradient(128, 120, 130)
    grad.setColorAt(0, QColor(70, 150, 225))
    grad.setColorAt(0.65, QColor(35, 105, 185))
    grad.setColorAt(1, QColor(15, 55, 115))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(8, 8, 240, 240)
    
    # === 2. 外圆高光 ===
    highlight = QRadialGradient(110, 80, 110)
    highlight.setColorAt(0, QColor(255, 255, 255, 70))
    highlight.setColorAt(0.5, QColor(255, 255, 255, 15))
    highlight.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(highlight))
    p.drawEllipse(8, 8, 240, 240)
    
    # === 3. 硬盘盘片（银色圆形）===
    plate_grad = QRadialGradient(128, 115, 82)
    plate_grad.setColorAt(0, QColor(235, 240, 245))
    plate_grad.setColorAt(0.5, QColor(205, 215, 225))
    plate_grad.setColorAt(0.8, QColor(175, 190, 205))
    plate_grad.setColorAt(1, QColor(145, 160, 180))
    p.setBrush(QBrush(plate_grad))
    p.setPen(QPen(QColor(100, 120, 150), 2.5))
    p.drawEllipse(46, 36, 164, 164)
    
    # 盘片同心环纹理
    p.setPen(QPen(QColor(155, 170, 195, 100), 1))
    p.setBrush(Qt.NoBrush)
    for radius in [22, 38, 52, 64, 74]:
        p.drawEllipse(128-radius, 118-radius, radius*2, radius*2)
    
    # 中心轴孔
    p.setBrush(QBrush(QColor(25, 85, 165)))
    p.setPen(QPen(QColor(15, 55, 120), 2))
    p.drawEllipse(113, 103, 30, 30)
    
    # 中心轴高光
    p.setBrush(QBrush(QColor(85, 145, 215, 160)))
    p.setPen(Qt.NoPen)
    p.drawEllipse(118, 107, 12, 12)
    
    # === 4. 闪电符号（右下角，金色）===
    bolt_points = [
        QPointF(178, 148),
        QPointF(153, 188),
        QPointF(168, 188),
        QPointF(143, 238),
        QPointF(180, 192),
        QPointF(163, 192),
    ]
    bolt_poly = QPolygonF(bolt_points)
    
    # 发光层
    p.setBrush(QBrush(QColor(255, 220, 50, 50)))
    p.setPen(Qt.NoPen)
    glow = QPolygonF([
        QPointF(183, 145), QPointF(148, 191), QPointF(163, 191),
        QPointF(138, 241), QPointF(183, 195), QPointF(158, 195),
    ])
    p.drawPolygon(glow)
    
    # 闪电主体
    bolt_grad = QLinearGradient(143, 148, 180, 238)
    bolt_grad.setColorAt(0, QColor(255, 235, 80))
    bolt_grad.setColorAt(0.5, QColor(255, 200, 30))
    bolt_grad.setColorAt(1, QColor(230, 165, 0))
    p.setBrush(QBrush(bolt_grad))
    p.setPen(QPen(QColor(195, 145, 0), 1.5))
    p.drawPolygon(bolt_poly)
    
    p.end()
    return QIcon(pixmap)


class DiskFillerThread(QThread):
    """磁盘填充工作线程 - 支持速度控制"""
    progress_signal = pyqtSignal(int)  # 进度百分比
    status_signal = pyqtSignal(str)  # 状态信息
    speed_signal = pyqtSignal(float)  # 速度 MB/s
    remaining_signal = pyqtSignal(str)  # 剩余空间
    finished_signal = pyqtSignal(bool, str)  # 完成信号 (成功, 统计信息)
    
    # 速度模式配置: (名称, 目标速度MB/s下限, 目标速度MB/s上限)
    SPEED_PROFILES = {
        0: ("低速", 50, 200),
        1: ("中速", 160, 350),
        2: ("高速", 300, 950),
        3: ("自适应", 0, 0),  # 0表示自动探测
    }
    
    def __init__(self, drive_path, verify_data=True, speed_mode=3, parent=None):
        super().__init__(parent)
        self.drive_path = drive_path
        self.verify_data = verify_data
        self.speed_mode = speed_mode
        self.is_running = False
        self.total_written = 0  # 总写入字节数
        self.total_deleted = 0  # 总删除字节数
        self.created_files = []  # 创建的临时文件列表
        self.detected_disk_type = ""  # 自适应探测到的磁盘类型
    
    def detect_disk_type(self):
        """探测磁盘类型（M.2 SSD / SATA SSD / 机械硬盘）"""
        try:
            if os.name == 'nt':
                import ctypes
                import subprocess as sp
                
                drive_letter = self.drive_path.rstrip('\\')[0]
                
                # 方法1: 使用 WMI 获取磁盘介质类型
                try:
                    result = sp.run(
                        ['wmic', 'diskdrive', 'get', 'MediaType,Model,Size', '/format:csv'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[1:]:
                            parts = line.strip().split(',')
                            if len(parts) >= 3:
                                media_type = parts[0].strip().lower()
                                model = parts[1].strip().lower()
                                if 'fixed' in media_type or 'ssd' in media_type or 'nvme' in model or 'm.2' in model:
                                    if 'nvme' in model or 'm.2' in model:
                                        return "M.2 SSD"
                                    elif 'ssd' in media_type or 'ssd' in model or 'solid' in media_type:
                                        return "SATA SSD"
                        # 如果没找到明确的SSD标识，检查是否有HDD关键字
                        for line in lines[1:]:
                            parts = line.strip().split(',')
                            if len(parts) >= 2:
                                model = parts[1].strip().lower() if len(parts) >= 2 else ""
                                if 'hdd' in model or 'hard' in model:
                                    return "机械硬盘(HDD)"
                except:
                    pass
                
                # 方法2: 通过 PowerShell 获取物理磁盘类型
                try:
                    result = sp.run(
                        ['powershell', '-Command',
                         'Get-PhysicalDisk | Select-Object MediaType,BusType,FriendlyName | ConvertTo-Csv -NoTypeInformation'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        for line in lines[1:]:
                            parts = [p.strip().strip('"') for p in line.split(',')]
                            if len(parts) >= 2:
                                media = parts[0].lower()
                                bus = parts[1].lower() if len(parts) > 1 else ""
                                if 'ssd' in media:
                                    if 'nvme' in bus or 'nvme' in str(parts):
                                        return "M.2 SSD"
                                    else:
                                        return "SATA SSD"
                                elif 'hdd' in media:
                                    return "机械硬盘(HDD)"
                except:
                    pass
                
                # 方法3: 简单速度探测 - 写入测试
                return self._speed_probe()
                
        except:
            pass
        return self._speed_probe()
    
    def _speed_probe(self):
        """通过短时间写入测试探测磁盘类型"""
        try:
            test_file = os.path.join(self.drive_path, "_dc_probe.tmp")
            test_size = 32 * 1024 * 1024  # 32MB测试
            data = os.urandom(test_size)
            
            start = time.time()
            with open(test_file, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            elapsed = time.time() - start
            
            try:
                os.remove(test_file)
            except:
                pass
            
            speed = (test_size / 1024 / 1024) / elapsed if elapsed > 0 else 0
            
            if speed > 500:
                return "M.2 SSD"
            elif speed > 200:
                return "SATA SSD"
            else:
                return "机械硬盘(HDD)"
        except:
            return "未知(按中速)"
    
    def get_adaptive_config(self):
        """根据磁盘类型返回自适应写入配置"""
        disk_type = self.detect_disk_type()
        self.detected_disk_type = disk_type
        
        if "M.2" in disk_type:
            # M.2 NVMe SSD: 大块写入，不限速
            return 64 * 1024 * 1024, 512 * 1024 * 1024, 0, disk_type
        elif "SATA" in disk_type:
            # SATA SSD: 中等块写入，轻微限速
            return 32 * 1024 * 1024, 512 * 1024 * 1024, 0, disk_type
        elif "机械" in disk_type or "HDD" in disk_type:
            # 机械硬盘: 较小块写入，限速避免卡顿
            return 16 * 1024 * 1024, 256 * 1024 * 1024, 0, disk_type
        else:
            # 未知: 按中速
            return 32 * 1024 * 1024, 512 * 1024 * 1024, 0, disk_type
    
    def run(self):
        """执行磁盘填充操作 - 支持速度控制"""
        self.is_running = True
        
        # 根据速度模式确定写入参数
        profile = self.SPEED_PROFILES.get(self.speed_mode, self.SPEED_PROFILES[3])
        mode_name = profile[0]
        
        if self.speed_mode == 3:
            # 自适应模式：探测磁盘类型
            chunk_size, file_target_size, target_speed, disk_type = self.get_adaptive_config()
            self.status_signal.emit(f"自适应模式: 检测到 {disk_type}")
        else:
            # 固定速度模式
            target_speed_min = profile[1]
            target_speed_max = profile[2]
            target_speed = (target_speed_min + target_speed_max) / 2
            disk_type = f"{mode_name}模式"
            
            # 根据目标速度调整块大小
            if target_speed >= 300:
                chunk_size = 64 * 1024 * 1024
                file_target_size = 512 * 1024 * 1024
            elif target_speed >= 160:
                chunk_size = 32 * 1024 * 1024
                file_target_size = 512 * 1024 * 1024
            else:
                chunk_size = 16 * 1024 * 1024
                file_target_size = 256 * 1024 * 1024
        
        try:
            # 获取初始磁盘空间
            total_space, initial_free = self.get_disk_space()
            if initial_free <= 0:
                self.status_signal.emit("错误: 磁盘没有可用空间!")
                self.finished_signal.emit(False, "磁盘空间不足")
                return
            
            self.status_signal.emit(f"========== 开始填充 ==========")
            self.status_signal.emit(f"目标磁盘: {self.drive_path}")
            self.status_signal.emit(f"写入模式: {disk_type} ({mode_name})")
            self.status_signal.emit(f"可用空间: {self.format_size(initial_free)}")
            
            start_time = time.time()
            last_update_time = start_time
            last_written = 0
            written_this_session = 0
            temp_files = []
            file_index = 0
            
            # 预生成随机数据模板
            data_pattern = os.urandom(chunk_size)
            
            self.status_signal.emit(f"正在写入数据 ({mode_name})...")
            
            while self.is_running:
                try:
                    # 创建新的临时文件
                    temp_file = os.path.join(self.drive_path, f"dc_{file_index:04d}.tmp")
                    file_index += 1
                    
                    current_file_size = 0
                    
                    with open(temp_file, 'wb') as f:
                        # 写入直到达到目标大小或磁盘满
                        while self.is_running and current_file_size < file_target_size:
                            # 写入数据块
                            f.write(data_pattern)
                            current_file_size += chunk_size
                            written_this_session += chunk_size
                            self.total_written += chunk_size
                            
                            # 速度控制（非自适应模式才限速）
                            if self.speed_mode != 3 and target_speed > 0:
                                now = time.time()
                                elapsed_so_far = now - start_time
                                if elapsed_so_far > 0:
                                    actual_speed = (written_this_session / 1024 / 1024) / elapsed_so_far
                                    # 如果实际速度超过目标速度上限，sleep降速
                                    if actual_speed > target_speed * 1.05:
                                        # 计算需要等待多久
                                        target_elapsed = written_this_session / 1024 / 1024 / target_speed
                                        sleep_time = target_elapsed - elapsed_so_far
                                        if sleep_time > 0:
                                            time.sleep(min(sleep_time, 0.1))  # 每次最多睡100ms，保持响应
                            
                            # 每500ms更新一次UI（减少开销）
                            now = time.time()
                            if now - last_update_time >= 0.5:
                                elapsed = now - start_time
                                if elapsed > 0:
                                    speed = ((written_this_session - last_written) / 1024 / 1024) / (now - last_update_time)
                                    self.speed_signal.emit(speed)
                                    
                                last_written = written_this_session
                                last_update_time = now
                                
                                # 更新进度
                                progress = int((written_this_session / initial_free) * 98) if initial_free > 0 else 0
                                progress = min(max(progress, 1), 98)
                                self.progress_signal.emit(progress)
                                
                                # 更新状态
                                self.status_signal.emit(
                                    f"写入中: {self.format_size(written_this_session)} | "
                                    f"速度: {speed:.1f} MB/s | 文件数: {len(temp_files)+1}"
                                )
                    
                    # 记录成功创建的文件
                    if os.path.exists(temp_file):
                        actual_size = os.path.getsize(temp_file)
                        temp_files.append(temp_file)
                        
                        # 检查剩余空间（每写完一个文件检查一次）
                        _, free_space = self.get_disk_space()
                        self.remaining_signal.emit(self.format_size(free_space))
                        
                        # 如果剩余空间小于2个块大小，停止
                        if free_space < chunk_size * 2:
                            self.status_signal.emit(f"磁盘即将填满 (剩余: {self.format_size(free_space)})")
                            break
                    else:
                        break
                        
                except OSError as e:
                    errno_val = getattr(e, 'errno', 0)
                    err_str = str(e).lower()
                    
                    if 'no space' in err_str or 'disk full' in err_str or errno_val == 28 or errno_val == 112:
                        self.status_signal.emit("磁盘空间已填满!")
                        break
                    elif 'access' in err_str or errno_val == 13:
                        self.status_signal.emit(f"权限不足，尝试其他位置: {str(e)}")
                        break
                    else:
                        self.status_signal.emit(f"IO错误: {str(e)}")
                        break
                except Exception as e:
                    self.status_signal.emit(f"意外错误: {str(e)}")
                    break
            
            # 尝试写入最后一点小空间
            if self.is_running:
                try:
                    _, final_free = self.get_disk_space()
                    if final_free > 1024 * 100:  # 至少100KB
                        temp_file = os.path.join(self.drive_path, f"dc_{file_index:04d}.tmp")
                        write_size = min(final_free - 1024, 10 * 1024 * 1024)  # 最多再写10MB
                        if write_size > 0:
                            with open(temp_file, 'wb') as f:
                                f.write(os.urandom(write_size))
                            self.total_written += write_size
                            written_this_session += write_size
                            temp_files.append(temp_file)
                            self.status_signal.emit(f"收尾写入: {self.format_size(write_size)}")
                except:
                    pass
            
            self.created_files = temp_files
            elapsed_total = time.time() - start_time
            
            # 数据验证
            if self.verify_data and self.is_running and len(temp_files) > 0:
                self.status_signal.emit(f"验证 {len(temp_files)} 个文件...")
                verified_count = sum(1 for tf in temp_files if os.path.exists(tf) and os.path.getsize(tf) > 0)
                self.status_signal.emit(f"验证完成: {verified_count}/{len(temp_files)} 文件正常")
            
            # 清理临时文件
            self.status_signal.emit("正在清理临时文件...")
            deleted_size = 0
            deleted_count = 0
            for tf in temp_files:
                try:
                    if os.path.exists(tf):
                        size = os.path.getsize(tf)
                        os.remove(tf)
                        deleted_size += size
                        self.total_deleted += size
                        deleted_count += 1
                except:
                    pass
            
            # 完成
            self.progress_signal.emit(100)
            
            avg_speed = (written_this_session / 1024 / 1024) / elapsed_total if elapsed_total > 0 else 0
            stats = (
                f"========== 填充完成 ==========\n"
                f"写入模式: {disk_type} ({mode_name})\n"
                f"总写入: {self.format_size(self.total_written)}\n"
                f"总删除: {self.format_size(deleted_size)}\n"
                f"文件数: {len(temp_files)} (已清理: {deleted_count})\n"
                f"耗时: {elapsed_total:.1f} 秒\n"
                f"平均速度: {avg_speed:.1f} MB/s\n"
                f"================================"
            )
            
            self.status_signal.emit(stats.replace('\n', ' | '))
            logger.info(stats.replace('=', '').replace('\n', ' | '))
            self.finished_signal.emit(True, stats)
            
        except Exception as e:
            error_msg = f"致命错误: {str(e)}"
            self.status_signal.emit(error_msg)
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            self.finished_signal.emit(False, error_msg)
        
        self.is_running = False
    
    def stop(self):
        """停止操作"""
        self.is_running = False
    
    def get_disk_space(self):
        """获取磁盘空间信息"""
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(self.drive_path),
                    None,
                    ctypes.byref(total_bytes),
                    ctypes.byref(free_bytes)
                )
                total = total_bytes.value
                free = free_bytes.value
            else:  # Linux/Mac
                stat = os.statvfs(self.drive_path)
                total = stat.f_blocks * stat.f_frsize
                free = stat.f_bavail * stat.f_frsize
            return total, free
        except Exception as e:
            self.status_signal.emit(f"获取磁盘空间失败: {str(e)}")
            return 0, 0
    
    @staticmethod
    def format_size(size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"


class DriveClearPro(QMainWindow):
    """DriveClear Pro 主窗口"""
    
    # 全局热键ID
    HOTKEY_ID = 1
    
    def __init__(self):
        super().__init__()
        self.work_thread = None
        self.current_cycle = 0
        self.total_cycles_completed = 0
        self.total_data_written_all = 0
        
        # 初始化设置变量
        self.settings_verify = True          # SM3校验开关
        self.settings_enable_cycle = False   # 是否启用循环
        self.settings_cycles = 1             # 循环次数
        self.settings_countdown_stop = False # 倒计时停止
        self.settings_countdown_value = 30   # 倒计时数值
        self.settings_countdown_unit = 1     # 倒计时单位: 0=分钟, 1=小时
        self.settings_speed_mode = 3         # 速度模式: 0=低速, 1=中速, 2=高速, 3=自适应
        self.settings_boss_key_enabled = False   # 老板键开关
        self.settings_boss_key_modifiers = Qt.ControlModifier | Qt.AltModifier  # 默认 Ctrl+Alt
        self.settings_boss_key_key = Qt.Key_H   # 默认 H键，组合为 Ctrl+Alt+H
        self._boss_key_recording = False        # 是否正在录制快捷键
        self._window_hidden_by_boss = False     # 是否被老板键隐藏
        
        # 全局热键相关
        self._hotkey_registered = False      # 全局热键是否已注册
        
        # 倒计时相关
        self.countdown_timer = None          # 倒计时QTimer
        self.countdown_remaining_sec = 0     # 剩余秒数
        
        # 创建应用图标（在 UI 初始化之前，这样 tray 可以使用）
        self.app_icon = create_app_icon()
        
        self.init_ui()
        self.refresh_drives()
        self.setup_system_tray()
        
        # 设置窗口和托盘图标
        self.setWindowIcon(self.app_icon)
        self.tray_icon.setIcon(self.app_icon)
        
        # 注册老板键全局快捷键（使用 Windows API）
        self._register_boss_key()
        
    def _register_boss_key(self):
        """注册/更新老板键全局快捷键（使用 Windows RegisterHotKey API）"""
        # 先移除旧的
        self._unregister_boss_key()
        
        if not self.settings_boss_key_enabled:
            return
        
        if os.name != 'nt':
            logger.warning("老板键仅支持 Windows 系统")
            return
        
        try:
            # 将 Qt 修饰键转换为 Win32 MOD 标志
            win_mod = 0
            mod = self.settings_boss_key_modifiers
            if mod & Qt.ControlModifier:
                win_mod |= MOD_CONTROL
            if mod & Qt.AltModifier:
                win_mod |= MOD_ALT
            if mod & Qt.ShiftModifier:
                win_mod |= MOD_SHIFT
            if mod & Qt.MetaModifier:
                win_mod |= MOD_WIN
            
            # Qt Key -> Win32 VK
            vk = self._qt_key_to_win_vk(self.settings_boss_key_key)
            
            result = user32.RegisterHotKey(
                int(self.winId()),   # 窗口句柄
                self.HOTKEY_ID,      # 热键ID
                win_mod,             # 修饰键
                vk                   # 虚拟键码
            )
            
            if result:
                self._hotkey_registered = True
                logger.info(f"老板键注册成功: {self._get_boss_key_display_text()}")
            else:
                err = ctypes.GetLastError()
                logger.warning(f"老板键注册失败 (错误码: {err})，可能快捷键已被占用")
                self.log_message(f" 老板键注册失败，快捷键可能已被其他程序占用", "error")
        except Exception as e:
            logger.warning(f"注册老板键失败: {e}")
    
    def _unregister_boss_key(self):
        """取消注册老板键"""
        if self._hotkey_registered and os.name == 'nt':
            try:
                user32.UnregisterHotKey(int(self.winId()), self.HOTKEY_ID)
                self._hotkey_registered = False
            except:
                pass
    
    def _qt_key_to_win_vk(self, qt_key):
        """将 Qt 键码转换为 Windows 虚拟键码"""
        # 字母键 A-Z: VK_A=0x41 ~ VK_Z=0x5A
        if Qt.Key_A <= qt_key <= Qt.Key_Z:
            return 0x41 + (qt_key - Qt.Key_A)
        # 数字键 0-9: VK_0=0x30 ~ VK_9=0x39
        if Qt.Key_0 <= qt_key <= Qt.Key_9:
            return 0x30 + (qt_key - Qt.Key_0)
        # F1-F12: VK_F1=0x70 ~ VK_F12=0x7B
        if Qt.Key_F1 <= qt_key <= Qt.Key_F12:
            return 0x70 + (qt_key - Qt.Key_F1)
        # 特殊键映射
        special = {
            Qt.Key_Space: 0x20,
            Qt.Key_Return: 0x0D,
            Qt.Key_Escape: 0x1B,
            Qt.Key_Backspace: 0x08,
            Qt.Key_Tab: 0x09,
            Qt.Key_Insert: 0x2D,
            Qt.Key_Delete: 0x2E,
            Qt.Key_Home: 0x24,
            Qt.Key_End: 0x23,
            Qt.Key_PageUp: 0x21,
            Qt.Key_PageDown: 0x22,
            Qt.Key_Up: 0x26,
            Qt.Key_Down: 0x28,
            Qt.Key_Left: 0x25,
            Qt.Key_Right: 0x27,
            Qt.Key_CapsLock: 0x14,
            Qt.Key_NumLock: 0x90,
            Qt.Key_ScrollLock: 0x91,
        }
        return special.get(qt_key, qt_key & 0xFF)
    
    def _get_boss_key_combination(self):
        """获取老板键组合的 QKeySequence 字符串"""
        mod = self.settings_boss_key_modifiers
        key = self.settings_boss_key_key
        
        parts = []
        if mod & Qt.ControlModifier:
            parts.append("Ctrl")
        if mod & Qt.AltModifier:
            parts.append("Alt")
        if mod & Qt.ShiftModifier:
            parts.append("Shift")
        if mod & Qt.MetaModifier:
            parts.append("Meta")
        
        # 键名映射
        key_names = {
            Qt.Key_A: "A", Qt.Key_B: "B", Qt.Key_C: "C", Qt.Key_D: "D",
            Qt.Key_E: "E", Qt.Key_F: "F", Qt.Key_G: "G", Qt.Key_H: "H",
            Qt.Key_I: "I", Qt.Key_J: "J", Qt.Key_K: "K", Qt.Key_L: "L",
            Qt.Key_M: "M", Qt.Key_N: "N", Qt.Key_O: "O", Qt.Key_P: "P",
            Qt.Key_Q: "Q", Qt.Key_R: "R", Qt.Key_S: "S", Qt.Key_T: "T",
            Qt.Key_U: "U", Qt.Key_V: "V", Qt.Key_W: "W", Qt.Key_X: "X",
            Qt.Key_Y: "Y", Qt.Key_Z: "Z",
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
            Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
            Qt.Key_8: "8", Qt.Key_9: "9",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3", Qt.Key_F4: "F4",
            Qt.Key_F5: "F5", Qt.Key_F6: "F6", Qt.Key_F7: "F7", Qt.Key_F8: "F8",
            Qt.Key_F9: "F9", Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
            Qt.Key_Space: "Space", Qt.Key_Escape: "Esc",
            Qt.Key_Backspace: "Backspace", Qt.Key_Return: "Return",
            Qt.Key_Tab: "Tab",
        }
        
        key_name = key_names.get(key, chr(key) if key < 256 else f"0x{key:x}")
        parts.append(key_name)
        
        return "+".join(parts)
    
    def _get_boss_key_display_text(self):
        """获取老板键显示文本"""
        return self._get_boss_key_combination()
    
    def _toggle_boss_key(self):
        """老板键切换：隐藏/显示窗口"""
        if self._window_hidden_by_boss:
            # 恢复窗口
            self.show()
            self.activateWindow()
            self.raise_()
            self._window_hidden_by_boss = False
            self.statusBar().showMessage("窗口已恢复")
        else:
            # 隐藏窗口
            self.hide()
            self._window_hidden_by_boss = True
            self.statusBar().showMessage("窗口已隐藏 (老板键)")
    
    def nativeEvent(self, eventType, message):
        """处理 Windows 原生消息（全局热键）"""
        if os.name == 'nt' and eventType == b"windows_generic_MSG":
            try:
                # 兼容不同 PyQt5 版本：message 可能是 int 或 sip.voidptr
                msg_addr = int(message)
                msg = ctypes.wintypes.MSG.from_address(msg_addr)
                if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                    self._toggle_boss_key()
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)
    
    def keyPressEvent(self, event):
        """键盘事件"""
        super().keyPressEvent(event)
        
    def init_ui(self):
        """初始化用户界面 - 蓝色现代风格（紧凑版）"""
        self.setWindowTitle("硬盘终结者 - 沧州虎王科技")
        self.setMinimumSize(720, 520)
        
        # 设置蓝色主题样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f4f8;
            }
            QWidget {
                font-family: 'Microsoft YaHei UI', 'Segoe UI', Arial;
                font-size: 12px;
                color: #1a1a2e;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 8px;
                background-color: white;
                color: #1a5276;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: white;
                color: #1a5276;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 18px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f6dad;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QPushButton#btnStop {
                background-color: #e74c3c;
            }
            QPushButton#btnStop:hover {
                background-color: #c0392b;
            }
            QPushButton#btnRefresh {
                background-color: #27ae60;
            }
            QPushButton#btnRefresh:hover {
                background-color: #1e8449;
            }
            QPushButton#btnSettings {
                background-color: #9b59b6;
            }
            QPushButton#btnSettings:hover {
                background-color: #8e44ad;
            }
            QPushButton#btnBilibili {
                background-color: #fb7299;
            }
            QPushButton#btnBilibili:hover {
                background-color: #e85d82;
            }
            QPushButton#btnGithub {
                background-color: #333333;
            }
            QPushButton#btnGithub:hover {
                background-color: #24292e;
            }
            QPushButton#btnHelp {
                background-color: #f39c12;
                color: white;
                border-radius: 16px;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton#btnHelp:hover {
                background-color: #e67e22;
            }
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px 12px;
                background-color: white;
                min-width: 120px;
                color: #1a1a2e;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox:focus {
                border-color: #2980b9;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #3498db;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #3498db;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
                color: #1a1a2e;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 12px;
                min-height: 24px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #ebf5fb;
                color: #1a5276;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            QSpinBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 5px 8px;
                background-color: white;
                color: #1a1a2e;
                min-height: 20px;
                font-size: 12px;
            }
            QSpinBox:hover {
                border-color: #3498db;
            }
            QSpinBox:focus {
                border-color: #2980b9;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #ecf0f1;
                border: none;
                width: 20px;
            }
            QSpinBox::up-button:hover {
                background-color: #3498db;
            }
            QSpinBox::down-button:hover {
                background-color: #3498db;
            }
            QSpinBox::up-arrow {
                width: 8px;
                height: 8px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #7f8c8d;
            }
            QSpinBox::down-arrow {
                width: 8px;
                height: 8px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #7f8c8d;
            }
            QSpinBox::up-button:hover QSpinBox::up-arrow {
                border-bottom-color: white;
            }
            QSpinBox::down-button:hover QSpinBox::down-arrow {
                border-top-color: white;
            }
            QCheckBox {
                spacing: 6px;
                color: #1a1a2e;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #3498db;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
            }
            QLineEdit, QTextEdit {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                padding: 6px;
                background-color: white;
                color: #1a1a2e;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #3498db;
            }
            QProgressBar {
                border: none;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                color: white;
                background-color: #ecf0f1;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2980b9);
                border-radius: 5px;
            }
            QLabel {
                color: #1a1a2e;
            }
            QLabel#titleLabel {
                font-size: 22px;
                font-weight: bold;
                color: #1a5276;
                padding: 5px;
            }
            QLabel#infoLabel {
                color: #555555;
                font-size: 12px;
            }
            QLabel#labelRunStatus {
                font-size: 13px;
                font-weight: bold;
                padding: 8px 10px;
                border-radius: 5px;
            }
            QTextEdit#logText {
                background-color: #1a1a2e;
                color: #00ff88;
                font-family: 'Consolas', 'Courier New', monospace;
                border: 2px solid #3498db;
                border-radius: 8px;
                font-size: 11px;
            }
            QDialog {
                background-color: #ffffff;
            }
        """)
        
        # 中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(10)
        
        # === 标题区域 ===
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("硬盘终结者")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        btn_settings = QPushButton("⚙ 高级设置")
        btn_settings.setObjectName("btnSettings")
        btn_settings.clicked.connect(self.show_settings_dialog)
        header_layout.addWidget(btn_settings)
        
        btn_help = QPushButton("?")
        btn_help.setObjectName("btnHelp")
        btn_help.setFixedSize(32, 32)
        btn_help.setToolTip("帮助 - 查看功能说明")
        btn_help.clicked.connect(self.show_help)
        header_layout.addWidget(btn_help)
        
        main_layout.addWidget(header_widget)
        
        subtitle_label = QLabel("加速报废每一块硬盘，让数据永无可存")
        subtitle_label.setObjectName("infoLabel")
        subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)
        
        # 主内容区域 - 使用水平分割
        content_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板 - 紧凑版
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        # 驱动器选择组
        drive_group = QGroupBox("驱动器选择")
        drive_layout = QHBoxLayout(drive_group)
        
        drive_layout.addWidget(QLabel("选择目标磁盘:"))
        self.combo_drive = QComboBox()
        drive_layout.addWidget(self.combo_drive, 1)
        
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("btnRefresh")
        btn_refresh.clicked.connect(self.refresh_drives)
        drive_layout.addWidget(btn_refresh)
        
        left_layout.addWidget(drive_group)
        
        # 磁盘信息组
        info_group = QGroupBox("磁盘信息")
        info_grid = QGridLayout(info_group)
        info_grid.setSpacing(6)
        
        info_grid.addWidget(QLabel("文件系统:"), 0, 0)
        self.label_fs_info = QLabel("--")
        self.label_fs_info.setStyleSheet("font-weight: bold; color: #2980b9; padding: 2px; font-size: 12px;")
        info_grid.addWidget(self.label_fs_info, 0, 1)
        
        info_grid.addWidget(QLabel("可用空间:"), 1, 0)
        self.label_free_space = QLabel("--")
        self.label_free_space.setStyleSheet("font-weight: bold; color: #27ae60; padding: 2px; font-size: 12px;")
        info_grid.addWidget(self.label_free_space, 1, 1)
        
        info_grid.addWidget(QLabel("剩余待填充:"), 2, 0)
        self.label_remaining = QLabel("--")
        self.label_remaining.setStyleSheet("font-weight: bold; color: #e67e22; padding: 2px; font-size: 12px;")
        info_grid.addWidget(self.label_remaining, 2, 1)
        
        info_grid.addWidget(QLabel("写入速度:"), 3, 0)
        self.label_speed = QLabel("-- MB/s")
        self.label_speed.setStyleSheet("font-weight: bold; color: #9b59b6; padding: 2px; font-size: 12px;")
        info_grid.addWidget(self.label_speed, 3, 1)
        
        left_layout.addWidget(info_group)
        
        # 进度组（含合并的运行状态）
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(6)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # 进度文字行：当前轮次 + 运行状态（合并显示）
        status_row = QHBoxLayout()
        status_row.setSpacing(15)
        
        status_row.addWidget(QLabel("当前进度:"))
        self.label_current_cycle = QLabel("就绪")
        self.label_current_cycle.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 13px;")
        status_row.addWidget(self.label_current_cycle)
        
        status_row.addStretch()
        
        # 运行状态标签（合并到进度区）
        self.label_run_status = QLabel("⏸ 就绪")
        self.label_run_status.setObjectName("labelRunStatus")
        self.update_run_status("就绪", "idle")
        status_row.addWidget(self.label_run_status)
        
        progress_layout.addLayout(status_row)
        
        left_layout.addWidget(progress_group)
        
        # 按钮组
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        
        self.btn_start = QPushButton("▶ 开始填充")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self.on_start_clicked)
        self.btn_start.setMinimumHeight(45)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(45)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_about = QPushButton("ℹ 关于软件")
        self.btn_about.setObjectName("btnAbout")
        self.btn_about.clicked.connect(self.show_about)
        self.btn_about.setMinimumHeight(45)
        btn_layout.addWidget(self.btn_about)
        
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()
        
        # 右侧面板 - 日志
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        
        self.text_log = QTextEdit()
        self.text_log.setObjectName("logText")
        self.text_log.setReadOnly(True)
        self.text_log.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.text_log)
        
        # 日志操作按钮
        log_btn_layout = QHBoxLayout()
        
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.setStyleSheet("background-color: #95a5a6; padding: 4px 12px; min-width: 70px;")
        btn_clear_log.clicked.connect(lambda: self.text_log.clear())
        log_btn_layout.addWidget(btn_clear_log)
        
        btn_open_log = QPushButton("打开日志文件夹")
        btn_open_log.setStyleSheet("background-color: #95a5a6; padding: 4px 12px; min-width: 100px;")
        btn_open_log.clicked.connect(self.open_log_folder)
        log_btn_layout.addWidget(btn_open_log)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        right_layout.addWidget(log_group)
        
        # 添加到分割器
        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([360, 340])
        
        main_layout.addWidget(content_splitter, 1)
        
        # 状态栏
        self.statusBar().showMessage("就绪 - 硬盘终结者 v2.0")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
        """)
        
        # 初始化日志
        self.log_message(" 硬盘终结者 v2.0 已启动", "info")
        self.log_message(" 支持功能: 循环填充 | 倒计时停止 | 速度控制 | 日志记录 | 数据统计", "info")
        self.log_message("=" * 50, "separator")
        
    def show_settings_dialog(self):
        """显示高级设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("高级设置 - 硬盘终结者")
        dialog.setWindowIcon(self.app_icon)
        dialog.setMinimumSize(440, 480)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1a1a2e;
                font-size: 13px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: #f8f9fa;
                color: #1a5276;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }
            QCheckBox {
                color: #1a1a2e;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #bdc3c7;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #2980b9;
                image: none;
            }
            QSpinBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px 8px;
                background-color: white;
                color: #1a1a2e;
                font-size: 13px;
                min-height: 24px;
            }
            QSpinBox:hover {
                border-color: #3498db;
            }
            QSpinBox:focus {
                border-color: #2980b9;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #ecf0f1;
                border: none;
                width: 22px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #3498db;
            }
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px 12px;
                background-color: white;
                color: #1a1a2e;
                font-size: 13px;
                min-width: 90px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox:focus {
                border-color: #2980b9;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #3498db;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #3498db;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
                color: #1a1a2e;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 12px;
                min-height: 26px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #ebf5fb;
                color: #1a5276;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#btnCancel {
                background-color: #95a5a6;
            }
            QPushButton#btnCancel:hover {
                background-color: #7f8c8d;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        
        # === 写入速度设置 ===
        speed_group = QGroupBox("写入速度设置")
        speed_layout = QVBoxLayout(speed_group)
        
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("速度模式:"))
        combo_speed = QComboBox()
        combo_speed.addItems(["🐢 低速 (50~200 MB/s)", "🚗 中速 (160~350 MB/s)", "🚀 高速 (300~950 MB/s)", "🔍 自适应 (自动探测)"])
        combo_speed.setCurrentIndex(self.settings_speed_mode)
        combo_speed.setMinimumWidth(220)
        speed_row.addWidget(combo_speed)
        speed_row.addStretch()
        speed_layout.addLayout(speed_row)
        
        speed_tip = QLabel("自适应模式将自动探测硬盘类型(M.2/SATA/机械盘)并匹配最佳速度")
        speed_tip.setStyleSheet("color: #666666; font-size: 11px; padding-left: 10px;")
        speed_tip.setWordWrap(True)
        speed_layout.addWidget(speed_tip)
        
        layout.addWidget(speed_group)
        
        # === 数据校验选项 ===
        verify_group = QGroupBox("数据校验选项")
        verify_layout = QVBoxLayout(verify_group)
        
        check_verify = QCheckBox("启用磁盘容量鉴定 (SM3校验)")
        check_verify.setChecked(self.settings_verify)
        check_verify.setToolTip("开启后将对写入的数据进行SM3哈希校验，确保数据完整性")
        verify_layout.addWidget(check_verify)
        layout.addWidget(verify_group)
        
        # === 循环次数设置 ===
        cycle_group = QGroupBox("循环次数设置")
        cycle_layout = QVBoxLayout(cycle_group)
        
        check_cycle = QCheckBox("启用多次循环填充")
        check_cycle.setChecked(self.settings_enable_cycle)
        check_cycle.setToolTip("勾选后将重复执行磁盘填充操作指定次数")
        cycle_layout.addWidget(check_cycle)
        
        cycle_row = QHBoxLayout()
        cycle_row.addWidget(QLabel("   循环次数:"))
        spin_cycles = QSpinBox()
        spin_cycles.setRange(1, 999)
        spin_cycles.setValue(self.settings_cycles)
        spin_cycles.setEnabled(self.settings_enable_cycle)
        spin_cycles.setMinimumWidth(100)
        cycle_row.addWidget(spin_cycles)
        cycle_row.addStretch()
        cycle_layout.addLayout(cycle_row)
        
        tip_label = QLabel("提示: 每次循环都会先清理上一次创建的临时文件")
        tip_label.setStyleSheet("color: #666666; font-size: 11px; padding-left: 10px;")
        cycle_layout.addWidget(tip_label)
        
        check_cycle.stateChanged.connect(
            lambda state: spin_cycles.setEnabled(state == Qt.Checked)
        )
        layout.addWidget(cycle_group)
        
        # === 倒计时停止设置 ===
        countdown_group = QGroupBox("倒计时停止设置")
        countdown_layout = QVBoxLayout(countdown_group)
        
        countdown_row = QHBoxLayout()
        check_countdown_stop = QCheckBox("倒计时自动停止:")
        check_countdown_stop.setChecked(self.settings_countdown_stop)
        countdown_row.addWidget(check_countdown_stop)
        
        spin_countdown = QSpinBox()
        spin_countdown.setRange(1, 999)
        spin_countdown.setValue(self.settings_countdown_value)
        spin_countdown.setEnabled(self.settings_countdown_stop)
        spin_countdown.setMinimumWidth(80)
        countdown_row.addWidget(spin_countdown)
        
        combo_unit = QComboBox()
        combo_unit.addItems(["分钟", "小时"])
        combo_unit.setCurrentIndex(self.settings_countdown_unit)
        combo_unit.setEnabled(self.settings_countdown_stop)
        combo_unit.setMinimumWidth(80)
        countdown_row.addWidget(combo_unit)
        
        countdown_row.addStretch()
        countdown_layout.addLayout(countdown_row)
        
        countdown_tip = QLabel("提示: 开始填充后，倒计时结束将自动停止运行")
        countdown_tip.setStyleSheet("color: #666666; font-size: 11px; padding-left: 10px;")
        countdown_layout.addWidget(countdown_tip)
        
        check_countdown_stop.stateChanged.connect(
            lambda state: (spin_countdown.setEnabled(state == Qt.Checked),
                          combo_unit.setEnabled(state == Qt.Checked))
        )
        
        layout.addWidget(countdown_group)
        
        # === 老板键设置 ===
        boss_group = QGroupBox("老板键设置")
        boss_layout = QVBoxLayout(boss_group)
        
        boss_enable_row = QHBoxLayout()
        check_boss_key = QCheckBox("启用老板键")
        check_boss_key.setChecked(self.settings_boss_key_enabled)
        check_boss_key.setToolTip("启用后可按自定义组合键一键隐藏/显示窗口")
        boss_enable_row.addWidget(check_boss_key)
        boss_enable_row.addStretch()
        boss_layout.addLayout(boss_enable_row)
        
        boss_key_row = QHBoxLayout()
        boss_key_row.addWidget(QLabel("   快捷键:"))
        
        self._boss_key_label = QLabel(f"当前: {self._get_boss_key_display_text()}")
        self._boss_key_label.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 13px; padding: 2px 8px;")
        boss_key_row.addWidget(self._boss_key_label)
        
        self._boss_record_btn = QPushButton("录制快捷键")
        self._boss_record_btn.setObjectName("btnRecord")
        self._boss_record_btn.setMinimumWidth(100)
        self._boss_record_btn.setToolTip("点击后按下组合键进行录制")
        self._boss_record_btn.setEnabled(self.settings_boss_key_enabled)
        self._boss_record_btn.clicked.connect(self._start_boss_key_recording)
        boss_key_row.addWidget(self._boss_record_btn)
        
        boss_key_row.addStretch()
        boss_layout.addLayout(boss_key_row)
        
        boss_tip = QLabel("提示: 按下老板键可立即隐藏/显示窗口，避免被他人看到屏幕内容")
        boss_tip.setStyleSheet("color: #666666; font-size: 11px; padding-left: 10px;")
        boss_tip.setWordWrap(True)
        boss_layout.addWidget(boss_tip)
        
        check_boss_key.stateChanged.connect(
            lambda state: self._boss_record_btn.setEnabled(state == Qt.Checked)
        )
        
        layout.addWidget(boss_group)
        
        # === 按钮区域 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("确定保存")
        btn_ok.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_ok)
        
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # 显示对话框
        result = dialog.exec_()
        if result == QDialog.Accepted:
            # 保存设置到变量
            self.settings_verify = check_verify.isChecked()
            self.settings_enable_cycle = check_cycle.isChecked()
            self.settings_cycles = spin_cycles.value()
            self.settings_countdown_stop = check_countdown_stop.isChecked()
            self.settings_countdown_value = spin_countdown.value()
            self.settings_countdown_unit = combo_unit.currentIndex()
            self.settings_speed_mode = combo_speed.currentIndex()
            self.settings_boss_key_enabled = check_boss_key.isChecked()
            
            # 重新注册老板键
            self._register_boss_key()
            
            # 格式化倒计时信息
            unit_str = "分钟" if self.settings_countdown_unit == 0 else "小时"
            countdown_info = f"{self.settings_countdown_value}{unit_str}" if self.settings_countdown_stop else "无"
            
            # 格式化速度信息
            speed_names = ["低速", "中速", "高速", "自适应"]
            speed_info = speed_names[self.settings_speed_mode]
            
            self.log_message(" 设置已保存: 校验={}, 循环={}, 速度={}, 倒计时={}, 老板键={}".format(
                "开" if self.settings_verify else "关",
                self.settings_cycles if self.settings_enable_cycle else 1,
                speed_info,
                countdown_info,
                self._get_boss_key_display_text() if self.settings_boss_key_enabled else "关"
            ), "info")
        
    def _start_boss_key_recording(self):
        """打开快捷键录制对话框"""
        record_dialog = QDialog(self)
        record_dialog.setWindowTitle("录制快捷键")
        record_dialog.setWindowIcon(self.app_icon)
        record_dialog.setFixedSize(380, 180)
        record_dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1a1a2e;
            }
        """)
        
        layout = QVBoxLayout(record_dialog)
        layout.setSpacing(15)
        
        tip_label = QLabel("请按下组合键 (至少包含一个修饰键)\n例如: Ctrl+Alt+H, Ctrl+Shift+F1")
        tip_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a5276;")
        tip_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(tip_label)
        
        key_display = QLabel("等待输入...")
        key_display.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #e74c3c; "
            "padding: 15px; border: 2px dashed #e74c3c; border-radius: 8px; background-color: #fff5f5;"
        )
        key_display.setAlignment(Qt.AlignCenter)
        layout.addWidget(key_display)
        
        hint_label = QLabel("按 Esc 取消录制")
        hint_label.setStyleSheet("color: #999; font-size: 11px;")
        hint_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint_label)
        
        # 记录结果
        result = {"modifiers": None, "key": None}
        
        def on_key_press(event):
            key = event.key()
            modifiers = event.modifiers()
            
            # Esc 取消
            if key == Qt.Key_Escape:
                record_dialog.reject()
                return
            
            # 忽略单独的修饰键
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
                return
            
            # 至少需要一个修饰键
            if modifiers == Qt.NoModifier:
                key_display.setText("请同时按住修饰键 (Ctrl/Alt/Shift)")
                return
            
            # 保存组合键
            result["modifiers"] = modifiers
            result["key"] = key
            
            # 临时更新显示
            old_mod = self.settings_boss_key_modifiers
            old_key = self.settings_boss_key_key
            self.settings_boss_key_modifiers = modifiers
            self.settings_boss_key_key = key
            key_display.setText(self._get_boss_key_display_text())
            self.settings_boss_key_modifiers = old_mod
            self.settings_boss_key_key = old_key
            
            # 延迟关闭，让用户看到效果
            QTimer.singleShot(500, record_dialog.accept)
        
        record_dialog.keyPressEvent = on_key_press
        
        if record_dialog.exec_() == QDialog.Accepted and result["modifiers"] is not None:
            # 应用录制结果
            self.settings_boss_key_modifiers = result["modifiers"]
            self.settings_boss_key_key = result["key"]
            
            # 更新UI
            if hasattr(self, '_boss_key_label'):
                self._boss_key_label.setText(f"当前: {self._get_boss_key_display_text()}")
    
    def setup_system_tray(self):
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip("硬盘终结者")
        
        tray_menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._tray_show_window)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
    def _tray_show_window(self):
        """通过托盘菜单显示窗口"""
        if self._window_hidden_by_boss:
            self._window_hidden_by_boss = False
        self.show()
        self.activateWindow()
        self.raise_()
    
    def on_tray_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self._window_hidden_by_boss:
                # 老板键隐藏状态下，双击托盘恢复窗口
                self.show()
                self.activateWindow()
                self.raise_()
                self._window_hidden_by_boss = False
                self.statusBar().showMessage("窗口已恢复")
            elif self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
                
    def refresh_drives(self):
        """刷新驱动器列表"""
        self.combo_drive.clear()
        
        if os.name == 'nt':  # Windows
            import ctypes
            drives = []
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                if bitmask & 1:
                    drive = f"{letter}:\\"
                    drives.append(drive)
                bitmask >>= 1
            
            for drive in drives:
                self.combo_drive.addItem(drive)
        else:  # Linux/Mac
            for mount in ['/mnt', '/media', '/Volumes']:
                if os.path.exists(mount):
                    for item in os.listdir(mount):
                        path = os.path.join(mount, item)
                        if os.path.ismount(path):
                            self.combo_drive.addItem(path)
            
            # 也添加根目录
            self.combo_drive.addItem("/")
        
        if self.combo_drive.count() > 0:
            self.on_drive_changed(0)
            
        self.combo_drive.currentIndexChanged.connect(self.on_drive_changed)
        
    def on_drive_changed(self, index):
        """驱动器选择改变"""
        if index < 0:
            return
            
        drive = self.combo_drive.currentText()
        if not drive:
            return
            
        try:
            if os.name == 'nt':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                
                # 获取卷信息
                volume_name_buf = ctypes.create_unicode_buffer(256)
                fs_name_buf = ctypes.create_unicode_buffer(256)
                
                result = kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(drive),
                    volume_name_buf,
                    256,
                    None, None, None,
                    fs_name_buf,
                    256
                )
                
                if result:
                    vol_name = volume_name_buf.value or "未命名"
                    fs_type = fs_name_buf.value or "Unknown"
                    self.label_fs_info.setText(f"{vol_name}, {fs_type}")
                else:
                    self.label_fs_info.setText("未知")
                
                # 获取磁盘空间
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive),
                    None,
                    ctypes.byref(total_bytes),
                    ctypes.byref(free_bytes)
                )
                
                free_gb = free_bytes.value / (1024**3)
                self.label_free_space.setText(f"{free_gb:.2f} GB ({free_bytes.value / (1024**2):.0f} MB)")
                self.label_remaining.setText(f"{free_gb:.2f} GB")
            else:
                # Linux/Mac
                stat = os.statvfs(drive)
                free_space = stat.f_bavail * stat.f_frsize
                total_space = stat.f_blocks * stat.f_frsize
                
                free_gb = free_space / (1024**3)
                self.label_fs_info.setText(f"Linux/Mac Filesystem")
                self.label_free_space.setText(f"{free_gb:.2f} GB ({free_space / (1024**2):.0f} MB)")
                self.label_remaining.setText(f"{free_gb:.2f} GB")
                
            self.log_message(f" 已选择驱动器: {drive}", "info")
            
        except Exception as e:
            self.log_message(f"获取磁盘信息失败: {str(e)}", "error")
            
    def log_message(self, message, msg_type="normal"):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "info": "#34db98",
            "success": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff6666",
            "separator": "#888888",
            "normal": "#ffffff"
        }
        
        color = color_map.get(msg_type, "#ffffff")
        formatted_msg = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        self.text_log.append(formatted_msg)
        
        # 同时写入日志文件
        log_level = {"info": logging.INFO, "error": logging.ERROR, 
                     "warning": logging.WARNING, "success": logging.INFO}
        logger.log(log_level.get(msg_type, logging.INFO), message.strip())
        
    def on_start_clicked(self):
        """开始按钮点击"""
        if self.work_thread and self.work_thread.isRunning():
            return
        self.start_processing()
        
    def start_processing(self):
        """开始处理"""
        drive = self.combo_drive.currentText()
        if not drive:
            QMessageBox.warning(self, "警告", "请先选择一个驱动器!")
            return
            
        # 获取循环次数
        if self.settings_enable_cycle:
            cycles = self.settings_cycles
        else:
            cycles = 1
            
        self.current_cycle = 0
        self.total_data_written_all = 0
        
        # 速度模式信息
        speed_names = ["低速", "中速", "高速", "自适应"]
        speed_info = speed_names[self.settings_speed_mode]
        
        self.log_message(f"=" * 50, "separator")
        self.log_message(f" 开始处理: {drive}", "info")
        self.log_message(f" 循环次数: {cycles}", "info")
        self.log_message(f" 写入速度: {speed_info}", "info")
        self.log_message(f" 数据校验: {'开启' if self.settings_verify else '关闭'}", "info")
        
        # 更新状态为运行中
        self.update_run_status(f"正在处理: {drive} - 第1轮", "running")
        
        # 设置倒计时停止
        if self.settings_countdown_stop:
            unit_sec = 60 if self.settings_countdown_unit == 0 else 3600
            self.countdown_remaining_sec = self.settings_countdown_value * unit_sec
            unit_str = "分钟" if self.settings_countdown_unit == 0 else "小时"
            self.log_message(f" 倒计时停止: {self.settings_countdown_value}{unit_str} 后自动停止", "warning")
            
            # 启动倒计时定时器（每秒更新）
            self.countdown_timer = QTimer(self)
            self.countdown_timer.timeout.connect(self.on_countdown_tick)
            self.countdown_timer.start(1000)
        
        self.run_next_cycle()
        
    def run_next_cycle(self):
        """运行下一个循环"""
        if self.settings_enable_cycle:
            cycles = self.settings_cycles
        else:
            cycles = 1
            
        self.current_cycle += 1
        
        drive = self.combo_drive.currentText()
        
        self.log_message(f"--- 第 {self.current_cycle}/{cycles} 轮循环 ---", "info")
        self.label_current_cycle.setText(f"第 {self.current_cycle}/{cycles} 轮")
        
        # 更新运行状态
        self.update_run_status(f"正在填充: {drive} - 第 {self.current_cycle}/{cycles} 轮", "running")
        
        self.work_thread = DiskFillerThread(drive, self.settings_verify, self.settings_speed_mode)
        
        # 连接信号
        self.work_thread.progress_signal.connect(self.update_progress)
        self.work_thread.status_signal.connect(self.log_message)
        self.work_thread.speed_signal.connect(self.update_speed)
        self.work_thread.remaining_signal.connect(self.update_remaining)
        self.work_thread.finished_signal.connect(self.on_cycle_finished)
        
        # 更新UI状态
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.combo_drive.setEnabled(False)
        
        self.work_thread.start()
        
    def on_cycle_finished(self, success, stats):
        """一轮循环完成"""
        if self.work_thread:
            self.total_data_written_all += self.work_thread.total_written
            
        if self.settings_enable_cycle:
            cycles = self.settings_cycles
        else:
            cycles = 1
        
        self.log_message(stats, "success" if success else "error")
        
        if self.current_cycle < cycles and success:
            self.log_message(f" 准备进行第 {self.current_cycle + 1} 轮循环...", "info")
            self.update_run_status(f"等待下一轮 - 第 {self.current_cycle + 1}/{cycles} 轮", "waiting")
            QTimer.singleShot(2000, self.run_next_cycle)
        else:
            self.on_all_finished(success)
            
    def on_countdown_tick(self):
        """倒计时每秒触发"""
        if self.countdown_remaining_sec > 0:
            self.countdown_remaining_sec -= 1
            # 格式化剩余时间
            hours = self.countdown_remaining_sec // 3600
            minutes = (self.countdown_remaining_sec % 3600) // 60
            seconds = self.countdown_remaining_sec % 60
            if hours > 0:
                time_str = f"{hours}小时{minutes}分{seconds}秒"
            elif minutes > 0:
                time_str = f"{minutes}分{seconds}秒"
            else:
                time_str = f"{seconds}秒"
            
            # 更新状态栏显示倒计时
            self.statusBar().showMessage(f"运行中 | 倒计时停止: 剩余 {time_str}")
            
            # 更新运行状态标签（附加倒计时信息）
            if self.work_thread and self.work_thread.is_running:
                drive = self.combo_drive.currentText()
                if self.settings_enable_cycle:
                    cycles = self.settings_cycles
                else:
                    cycles = 1
                self.label_run_status.setText(f"▶ 正在填充: {drive} - 第 {self.current_cycle}/{cycles} 轮 | ⏱ {time_str}")
        else:
            # 倒计时结束，自动停止
            self.on_countdown_finished()
    
    def on_countdown_finished(self):
        """倒计时结束，自动停止"""
        self.log_message(" 倒计时结束，自动停止运行!", "warning")
        # 停止倒计时定时器
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        self.stop_operation()
        
    def on_all_finished(self, success):
        """所有任务完成"""
        final_stats = (
            f"========== 全部完成 ==========\n"
            f"总循环次数: {self.current_cycle}\n"
            f"总写入数据: {self.format_size(self.total_data_written_all)}\n"
            f"状态: {'成功' if success else '有错误'}\n"
            f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        # 统计信息直接输出到日志
        self.log_message(final_stats, "success")
        
        # 更新运行状态
        status_msg = "全部完成!" if success else "完成(有错误)"
        self.update_run_status(status_msg, "success" if success else "error")
        
        # 重置UI
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.combo_drive.setEnabled(True)
        self.work_thread = None
        
        # 写入最终日志
        with open(os.path.join(LOG_DIR, "summary.log"), 'a', encoding='utf-8') as f:
            f.write(f"\n[{datetime.now()}] {final_stats}\n")
        
        self.statusBar().showMessage("处理完成!")
        
        # 停止倒计时定时器
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        
    def update_speed(self, speed_mb):
        """更新速度显示"""
        self.label_speed.setText(f"{speed_mb:.2f} MB/s")
        
    def update_remaining(self, text):
        """更新剩余空间显示"""
        self.label_remaining.setText(text)
    
    def update_run_status(self, status_text, status_type="idle"):
        """更新运行状态提示（合并到进度区域）"""
        style_map = {
            "idle": ("⏸", "#ecf0f1", "#7f8c8d"),
            "running": ("▶", "#d4edda", "#155724"),
            "waiting": ("⏳", "#fff3cd", "#856404"),
            "error": ("❌", "#f8d7da", "#721c24"),
            "success": ("✓", "#d4edda", "#155724"),
            "warning": ("⚠", "#fff3cd", "#856404"),
            "stopped": ("■", "#e2e3e5", "#383d41"),
        }
        
        icon, bg_color, text_color = style_map.get(status_type, style_map["idle"])
        self.label_run_status.setText(f"{icon} {status_text}")
        self.label_run_status.setStyleSheet(f"""
            background-color: {bg_color};
            border-radius: 4px;
            padding: 4px 10px;
            color: {text_color};
        """)
        
    def on_stop_clicked(self):
        """停止按钮点击"""
        reply = QMessageBox.question(
            self, "确认停止",
            "确定要停止当前操作吗?\n已创建的临时文件将被清理。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.stop_operation()
            
    def show_help(self):
        """显示帮助对话框 - 功能说明"""
        dialog = QDialog(self)
        dialog.setWindowTitle("功能说明 - 硬盘终结者")
        dialog.setWindowIcon(self.app_icon)
        dialog.setMinimumSize(560, 620)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1a1a2e;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: #f8f9fa;
                color: #1a5276;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("📖 硬盘终结者 - 功能说明")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5276; padding: 5px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # --- 驱动器选择 ---
        g1 = QGroupBox("💾 驱动器选择")
        g1_layout = QVBoxLayout(g1)
        g1_layout.addWidget(QLabel(
            "选择需要清除数据痕迹的目标磁盘分区。\n"
            "点击「刷新」按钮可重新扫描可用磁盘。\n"
            "选中后会显示文件系统类型和可用空间。"
        ))
        layout.addWidget(g1)
        
        # --- 磁盘信息 ---
        g2 = QGroupBox("📊 磁盘信息")
        g2_layout = QVBoxLayout(g2)
        g2_layout.addWidget(QLabel(
            "实时显示当前磁盘的详细信息：\n"
            "• 文件系统：分区格式（如 NTFS、FAT32）\n"
            "• 可用空间：磁盘剩余容量\n"
            "• 剩余待填充：还需写入的数据量\n"
            "• 写入速度：当前数据写入速率"
        ))
        layout.addWidget(g2)
        
        # --- 处理进度 ---
        g3 = QGroupBox("📈 处理进度")
        g3_layout = QVBoxLayout(g3)
        g3_layout.addWidget(QLabel(
            "显示当前填充操作的进度和状态：\n"
            "• 进度条：整体完成百分比\n"
            "• 当前进度：第几轮/共几轮\n"
            "• 运行状态：实时状态（就绪/运行/等待/停止）\n"
            "• 开启倒计时后会显示剩余时间"
        ))
        layout.addWidget(g3)
        
        # --- 开始/停止按钮 ---
        g4 = QGroupBox("🎮 操作按钮")
        g4_layout = QVBoxLayout(g4)
        g4_layout.addWidget(QLabel(
            "• 开始填充：启动磁盘数据清除操作\n"
            "• 停止：安全终止当前运行的操作\n"
            "• 关于软件：查看版本信息和作者主页"
        ))
        layout.addWidget(g4)
        
        # --- 高级设置 ---
        g5 = QGroupBox("⚙ 高级设置")
        g5_layout = QVBoxLayout(g5)
        g5_layout.addWidget(QLabel(
            "• 写入速度：选择低速/中速/高速/自适应模式\n"
            "  - 低速: 50~200 MB/s\n"
            "  - 中速: 160~350 MB/s\n"
            "  - 高速: 300~950 MB/s\n"
            "  - 自适应: 自动探测硬盘类型匹配最佳速度\n"
            "• 数据校验：开启后对写入数据进行完整性验证\n"
            "• 循环填充：重复执行多次填充，更彻底清除痕迹\n"
            "  - 可设置循环次数（1~999次）\n"
            "• 倒计时停止：开始后按设定时间自动停止\n"
            "  - 可选择分钟或小时为单位\n"
            "• 老板键：自定义组合键一键隐藏/显示窗口\n"
            "  - 点击「录制快捷键」按钮后按下组合键\n"
            "  - 再次按下相同组合键可恢复窗口"
        ))
        layout.addWidget(g5)
        
        # --- 运行日志 ---
        g6 = QGroupBox("📝 运行日志")
        g6_layout = QVBoxLayout(g6)
        g6_layout.addWidget(QLabel(
            "记录所有操作信息，包括：\n"
            "• 启动/停止时间、磁盘信息\n"
            "• 写入速度、填充进度\n"
            "• 统计汇总（写入量、耗时、速度）\n"
            "支持清空日志和打开日志文件夹"
        ))
        layout.addWidget(g6)
        
        # --- 工作原理 ---
        g7 = QGroupBox("🔬 工作原理")
        g7_layout = QVBoxLayout(g7)
        g7_layout.addWidget(QLabel(
            "本软件通过向磁盘可用空间写入随机数据来覆盖\n"
            "曾经删除文件的磁盘扇区，使数据恢复软件无法\n"
            "还原已删除的数据。填充完成后自动清理临时文件，\n"
            "磁盘空间恢复原状，但数据痕迹已被彻底覆盖。"
        ))
        layout.addWidget(g7)
        
        layout.addStretch()
        
        # 关闭按钮
        btn_close = QPushButton("我知道了")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)
        
        dialog.exec_()
        
    def stop_operation(self):
        """停止操作"""
        if self.work_thread and self.work_thread.isRunning():
            self.log_message(" 正在停止操作...", "warning")
            self.update_run_status("正在停止...", "warning")
            self.work_thread.stop()
            self.work_thread.wait(3000)
            
            # 强制清理残留文件
            if self.work_thread.created_files:
                cleaned = 0
                for f in self.work_thread.created_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                            cleaned += 1
                    except:
                        pass
                if cleaned > 0:
                    self.log_message(f" 已清理 {cleaned} 个临时文件", "info")
            
            self.log_message(" 操作已停止", "warning")
        
        # 停止倒计时定时器
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None
        
        # 更新运行状态为已停止
        self.update_run_status("已停止 - 可重新开始", "stopped")
        
        # 重置UI
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.combo_drive.setEnabled(True)
        self.progress_bar.setValue(0)
        self.work_thread = None
        self.statusBar().showMessage("已停止")
        
    def open_log_folder(self):
        """打开日志文件夹"""
        if os.name == 'nt':
            os.startfile(LOG_DIR)
        else:
            import subprocess
            subprocess.run(['xdg-open', LOG_DIR])
            
    def show_about(self):
        """显示关于对话框（含作者主页按钮）"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 硬盘终结者")
        dialog.setWindowIcon(self.app_icon)
        dialog.setMinimumSize(450, 420)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #1a1a2e;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#btnBilibili {
                background-color: #fb7299;
            }
            QPushButton#btnBilibili:hover {
                background-color: #e85d82;
            }
            QPushButton#btnGithub {
                background-color: #24292e;
            }
            QPushButton#btnGithub:hover {
                background-color: #1a1e22;
            }
            QPushButton#btnClose {
                background-color: #95a5a6;
            }
            QPushButton#btnClose:hover {
                background-color: #7f8c8d;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("硬盘终结者 v2.0")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a5276;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 副标题
        subtitle = QLabel("磁盘填充器增强版")
        subtitle.setStyleSheet("font-size: 14px; color: #555;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #3498db;")
        layout.addWidget(line)
        
        # 作者信息
        info_layout = QGridLayout()
        info_layout.setSpacing(8)
        
        info_layout.addWidget(QLabel("原始作者:"), 0, 0)
        info_layout.addWidget(QLabel("<b>EPC SOFT</b> (2009)"), 0, 1)
        
        info_layout.addWidget(QLabel("二次开发:"), 1, 0)
        info_layout.addWidget(QLabel("<b>沧州虎王科技</b>"), 1, 1)
        
        info_layout.addWidget(QLabel("联系作者:"), 2, 0)
        info_layout.addWidget(QLabel("zesso@qq.com"), 2, 1)
        
        layout.addLayout(info_layout)
        
        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color: #3498db;")
        layout.addWidget(line2)
        
        # 作者主页按钮
        homepage_label = QLabel("作者主页:")
        homepage_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(homepage_label)
        
        homepage_layout = QHBoxLayout()
        homepage_layout.setSpacing(15)
        
        btn_bilibili = QPushButton("📺 B站主页")
        btn_bilibili.setObjectName("btnBilibili")
        btn_bilibili.setMinimumHeight(40)
        btn_bilibili.clicked.connect(lambda: webbrowser.open("https://space.bilibili.com/352977016"))
        homepage_layout.addWidget(btn_bilibili)
        
        btn_github = QPushButton("💻 GitHub 主页")
        btn_github.setObjectName("btnGithub")
        btn_github.setMinimumHeight(40)
        btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/huwangkeji"))
        homepage_layout.addWidget(btn_github)
        
        homepage_layout.addStretch()
        layout.addLayout(homepage_layout)
        
        # 分隔线
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        line3.setStyleSheet("color: #3498db;")
        layout.addWidget(line3)
        
        # 软件原理
        principle = QLabel(
            "本软件通过覆盖磁盘可用空间来彻底清除曾经删除的文件痕迹，\n"
            "使磁盘恢复软件无法恢复已删除的数据。"
        )
        principle.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        principle.setWordWrap(True)
        layout.addWidget(principle)
        
        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("btnClose")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)
        
        dialog.exec_()
        
    @staticmethod
    def format_size(size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(size_bytes) < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.work_thread and self.work_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "程序正在运行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.work_thread.stop()
                self.work_thread.wait(2000)
            else:
                event.ignore()
                return
        
        # 取消注册全局热键
        self._unregister_boss_key()
        
        self.tray_icon.hide()
        event.accept()


def main():
    """程序入口"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # === 单实例检测（Windows 互斥体） ===
    mutex_handle = None
    if os.name == 'nt':
        kernel32 = ctypes.windll.kernel32
        mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            QMessageBox.critical(
                None, "程序已运行",
                "硬盘终结者已经在运行中！\n\n请不要重复打开，如需使用请切换到已运行的窗口。"
            )
            sys.exit(1)
    
    window = DriveClearPro()
    window.show()
    
    exit_code = app.exec_()
    
    # 释放互斥体
    if mutex_handle and os.name == 'nt':
        ctypes.windll.kernel32.ReleaseMutex(mutex_handle)
        ctypes.windll.kernel32.CloseHandle(mutex_handle)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
