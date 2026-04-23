# 硬盘终结者 v2.0 - DriveClear Pro

> 加速报废每一块硬盘，让数据永无可存

基于原始 EPC SOFT (2009) 磁盘填充器进行二次开发的现代化桌面应用，通过覆盖磁盘可用空间彻底清除已删除文件的数据痕迹，使数据恢复软件无法还原。

---

## 目录结构

```
driveclear/
│
├── DriveClearPro.exe          # 最终可执行文件（打包后的完整程序）
├── driveclear_pro.py          # 主程序源代码（所有功能逻辑均在此文件）
├── requirements.txt           # Python 依赖包列表
│
├── app_icon.ico               # 应用图标（Windows .ico 格式，用于打包）
├── app_icon.png               # 应用图标（PNG 格式，程序运行时由 QPainter 动态绘制）
│
├── do_build.py                # 快捷打包脚本（仅执行 PyInstaller 打包）
├── build_exe.py               # 完整打包脚本（含依赖安装 + PyInstaller 打包）
├── DriveClearPro.spec         # PyInstaller 打包配置文件（自动生成）
├── build_output.txt           # 历史打包输出日志
│
├── build/                     # 构建临时目录（PyInstaller 中间产物）
│   └── DriveClearPro/         #   编译缓存、依赖分析、字节码等
│       ├── *.pyc              #     Python 字节码文件
│       ├── *.toc              #     依赖表（Table of Contents）
│       ├── *.pkg              #     打包容数据
│       ├── *.pyz              #     Python 压缩归档
│       └── *.zip              #     基础库压缩包
│
├── dist/                      # PyInstaller 默认输出目录（exe 已复制到根目录，此目录通常为空）
│
├── logs/                      # 运行日志目录（程序运行时自动创建和写入）
│   ├── driveclear_YYYYMMDD.log  #   按日期分类的详细运行日志
│   └── summary.log               #   历史操作汇总统计
│
└── README.md                  # 本说明文档
```

---

## 文件详解

### 核心文件

| 文件 | 说明 |
|------|------|
| `DriveClearPro.exe` | 打包好的独立可执行文件，双击即可运行，无需安装 Python 环境 |
| `driveclear_pro.py` | 程序全部源代码，包含 UI 界面、磁盘填充线程、速度控制、老板键等所有功能模块 |
| `requirements.txt` | Python 依赖声明：`PyQt5>=5.15.0`、`PyInstaller>=6.0.0` |

### 图标文件

| 文件 | 说明 |
|------|------|
| `app_icon.ico` | Windows ICO 格式图标，用于 PyInstaller 打包时嵌入 exe 文件 |
| `app_icon.png` | PNG 格式图标备用文件（程序实际图标由代码中 `create_app_icon()` 动态绘制） |

### 构建相关

| 文件 | 说明 |
|------|------|
| `do_build.py` | 快捷打包脚本，直接调用 PyInstaller 进行打包，适合日常开发使用 |
| `build_exe.py` | 完整打包脚本，先自动安装 `requirements.txt` 中的依赖再执行打包，适合首次构建 |
| `DriveClearPro.spec` | PyInstaller 生成的打包规格文件，记录了打包参数和依赖分析结果 |
| `build_output.txt` | 之前的打包控制台输出记录，用于排查打包问题 |

### 目录说明

| 目录 | 说明 |
|------|------|
| `build/` | PyInstaller 构建过程中的临时工作目录，存放编译中间产物（字节码、依赖表、压缩归档等），可安全删除，下次打包会自动重建 |
| `dist/` | PyInstaller 默认的 exe 输出目录，打包完成后 exe 会被复制到项目根目录，此目录通常为空 |
| `logs/` | 程序运行日志目录，每次启动程序时自动创建，包含按日期分类的详细日志和历史汇总 |

---

## 功能特性

### 基础功能

- **驱动器选择** — 自动扫描系统所有可用磁盘分区，显示文件系统类型和可用空间
- **一键填充** — 向目标磁盘写入随机数据，覆盖已删除文件的数据扇区
- **安全清理** — 填充完成后自动删除所有临时文件，磁盘空间恢复原状
- **数据校验** — 可选开启 SM3 校验，验证写入数据的完整性

### 高级功能

- **写入速度控制** — 四种模式可选：
  - 🐢 低速：50~200 MB/s
  - 🚗 中速：160~350 MB/s
  - 🚀 高速：300~950 MB/s
  - 🔍 自适应：自动探测硬盘类型（M.2 SSD / SATA SSD / 机械硬盘），匹配最佳写入速度

- **循环填充** — 支持 1~999 次循环，每轮自动清理后重新填充，更彻底清除数据痕迹

- **倒计时停止** — 设定分钟/小时后自动停止运行，无需人工值守

- **老板键** — 自定义全局快捷键一键隐藏/显示窗口：
  - 使用 Windows 全局热键 API（`RegisterHotKey`），窗口隐藏后仍可触发恢复
  - 支持自定义组合键录制（需包含至少一个修饰键 Ctrl/Alt/Shift）
  - 默认快捷键：`Ctrl+Alt+H`

- **单实例运行** — 程序只允许运行一个实例，重复打开时弹窗提示

### 日志系统

- 界面实时日志（黑色背景 + 绿色等彩色文字）
- 文件持久化日志（按日期存储于 `logs/` 目录）
- 操作汇总统计（写入量、耗时、平均速度）

### 系统托盘

- 最小化到系统托盘，双击恢复窗口
- 右键菜单：显示主窗口 / 退出

---

## 使用方法

### 直接运行（推荐）

1. 双击 `DriveClearPro.exe`
2. 在下拉框选择目标磁盘分区
3. 按需点击「⚙ 高级设置」配置选项
4. 点击「▶ 开始填充」

### 从源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行程序
python driveclear_pro.py

# 打包为 exe
python do_build.py
```

---

## 技术栈

| 技术 | 说明 |
|------|------|
| Python 3.14 | 主开发语言 |
| PyQt5 | GUI 框架（窗口、控件、事件系统） |
| PyInstaller | 打包工具，生成独立 exe |
| Windows API | 全局热键（`RegisterHotKey`/`UnregisterHotKey`）、互斥体（`CreateMutexW`） |
| WMI / PowerShell | 磁盘类型探测（自适应速度模式） |
| ctypes | 调用 Windows 系统接口（磁盘空间、全局热键等） |

---

## 程序架构

```
DriveClearPro (QMainWindow)
│
├── init_ui()                    初始化界面布局与样式
├── refresh_drives()             扫描并刷新磁盘列表
├── start_processing()           启动填充任务
├── run_next_cycle()             执行下一轮循环
├── stop_operation()             停止当前操作
│
├── _register_boss_key()         注册 Windows 全局热键
├── _unregister_boss_key()       取消注册全局热键
├── _toggle_boss_key()           老板键切换（隐藏/显示）
├── nativeEvent()                处理 WM_HOTKEY 消息
│
├── show_settings_dialog()       高级设置对话框
├── show_help()                  帮助说明对话框
├── show_about()                 关于对话框
│
├── setup_system_tray()          系统托盘图标与菜单
├── on_countdown_tick()          倒计时每秒更新
│
└── DiskFillerThread (QThread)   磁盘填充工作线程
    ├── run()                    主工作循环（写入 + 速度控制）
    ├── detect_disk_type()       磁盘类型探测（WMI → PowerShell → 速度测试）
    ├── get_adaptive_config()    自适应速度配置
    └── get_disk_space()         获取磁盘空间信息
```

---

## 注意事项

⚠️ **重要警告**

- 此工具会**覆盖磁盘可用空间**，请确保已备份重要数据
- **不要对系统盘（C:）使用**，除非你明确知道后果
- 操作期间请勿访问或写入目标磁盘分区
- 程序仅支持 **Windows** 系统
- 程序限制单实例运行，不可多开

---

## 开发信息

| 项目 | 内容 |
|------|------|
| 原始作者 | EPC SOFT (2009) |
| 二次开发 | 沧州虎王科技 |
| 联系方式 | zesso@qq.com |
| B站主页 | https://space.bilibili.com/352977016 |
| GitHub | https://github.com/huwangkeji |
| 版本 | v2.0 |
