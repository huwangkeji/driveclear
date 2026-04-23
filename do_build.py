#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("开始打包 DriveClear Pro...")

# 确保logs目录存在
os.makedirs("logs", exist_ok=True)

result = subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--name=DriveClearPro",
    "--onefile",
    "--windowed",
    "--clean",
    "--noconfirm",
    "driveclear_pro.py"
], capture_output=True, text=True)

print("STDOUT:", result.stdout[-2000:])
print("STDERR:", result.stderr[-2000:])
print("Return code:", result.returncode)

if result.returncode == 0:
    print("\n打包成功!")
    if os.path.exists("dist/DriveClearPro.exe"):
        shutil.copy2("dist/DriveClearPro.exe", ".")
        size_mb = os.path.getsize("DriveClearPro.exe") / 1024 / 1024
        print(f"exe文件已复制到项目根目录 ({size_mb:.1f} MB)")
