[app]

# 应用标识（必须全小写、无空格，安卓包名后缀）
package.name = lovediary

# 安卓包名（reverse-domain 风格，随便写一个就行）
package.domain = org.xiangce

# 应用标题
title = 情侣纪念册

# 应用版本
version = 1.0.0

# 主入口（本项目只有一个 main.py）
source.dir = .
source.include_exts = py

# 需要收集到 APK 里的 Python 依赖
# python3 不指定版本时，python-for-android 会自动用兼容的默认版本
# kivy / kivymd / pillow 是核心
# plyer 在代码里延迟导入，选加（用 plyer 的 filechooser 会比 Kivy 自带的更像原生）
requirements = python3,kivy==2.3.1,kivymd==2.0.0,pillow,plyer

# 安卓权限：选照片需要读外部存储
# Android 13+ 用 READ_MEDIA_IMAGES，老版本用 READ_EXTERNAL_STORAGE
android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES

# 应用最低 / 目标 Android SDK
android.minapi = 21
android.api = 33
# 固定 NDK 版本：25b 是 p4a 2024.01 验证最充分的版本
# （最新的 28c 编译 SDL2/Kivy 原生库有兼容问题）
android.ndk = 25b
# 固定 python-for-android 到稳定发布版（默认拉取的开发版不稳定）
p4a.url = https://github.com/kivy/python-for-android.git
p4a.branch = release-2024.01.21
# 只编译 arm64 架构（2019 年以后的手机都支持，构建更快、更省资源）
android.archs = arm64-v8a
# 自动接受 Android SDK 许可证（CI 环境无交互，必须设为 True）
android.accept_sdk_license = True

# 屏幕方向：竖屏（情侣纪念册看照片，竖屏更合适）
android.orientation = portrait

# 全屏：沉浸式
android.fullscreen = 0

# Kivy 的窗口 flag（默认就行，不用改）
android.allow_backup = True

# ----------------------------------------------------------
# 以下为 buildozer 默认值，一般不需要改
# ----------------------------------------------------------

[buildozer]
log_level = 2
warn_on_root = 1
