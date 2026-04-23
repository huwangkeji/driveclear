#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DriveClear Pro 打包脚本
用于将Python程序打包成独立的exe文件
"""

import os
import sys
import shutil
import subprocess

def install_dependencies():
    """安装依赖包"""
    print("=" * 50)
    print("正在安装依赖包...")
    print("=" * 50)
    
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    print("依赖安装完成!")

def build_exe():
    """打包成exe文件"""
    print("=" * 50)
    print("开始打包 DriveClear Pro...")
    print("=" * 50)
    
    # 确保logs目录存在
    os.makedirs("logs", exist_ok=True)
    
    # PyInstaller命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=DriveClearPro",
        "--onefile",                    # 单文件模式
        "--windowed",                   # 无控制台窗口
        "--icon=NONE",                  # 图标(可选)
        "--add-data=logs;logs",         # 包含logs目录
        "--clean",                      # 清理临时文件
        "--noconfirm",                  # 覆盖输出目录
        "driveclear_pro.py"
    ]
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("✓ 打包成功!")
        print("=" * 50)
        print(f"输出文件: dist/DriveClearPro.exe")
        print("=" * 50)
        
        # 复制到当前目录
        if os.path.exists("dist/DriveClearPro.exe"):
            shutil.copy2("dist/DriveClearPro.exe", ".")
            print("已将 exe 文件复制到项目根目录")
    else:
        print("\n" + "=" * 50)
        print("✗ 打包失败!")
        print("=" * 50)

def main():
    """主函数"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("\n" + "╔" + "═" * 48 + "╗")
    print("║" + " " * 10 + "DriveClear Pro 打包工具" + " " * 13 + "║")
    print("║" + " " * 15 + "v2.0" + " " * 24 + "║")
    print("╚" + "═" * 48 + "╝\n")
    
    try:
        install_dependencies()
        build_exe()
    except KeyboardInterrupt:
        print("\n\n用户取消操作!")
    except Exception as e:
        print(f"\n错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
