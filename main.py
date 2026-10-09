# -*- coding: utf-8 -*-
"""
情侣纪念册 (Love Diary)
-------------------------------------------------
一个可以在安卓手机上运行的情侣纪念软件：
  1. 照片日记：存放有意义的照片，标注日期 / 事件 / 想法 / 标签 / 心情
  2. 首页：在一起天数、下一个纪念日倒计时、那年今日、快捷功能
  3. 纪念日：生日、周年、百日等，自动倒计时（支持每年重复 / 一次性）
  4. 心愿清单：想一起做的 100 件事，打卡完成进度
  5. 时光胶囊：写给未来的信，到日子才能打开
  6. 搜索：按事件 / 想法 / 标签关键词检索
  7. 设置：双方名字、在一起的日期

技术栈：Python + Kivy 2.3.1 + KivyMD 2.0.0 + SQLite + Pillow + plyer
打包：使用 buildozer 打包成安卓 APK（见《打包与使用说明.md》）
"""

import os
import sqlite3
from datetime import datetime, date

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, ObjectProperty
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDButton, MDButtonText, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogContentContainer,
    MDDialogHeadlineText,
    MDDialogSupportingText,
)
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.filemanager import MDFileManager
from PIL import Image as PilImage

# ----------------------------------------------------------
# 全局颜色 (rgba, 0~1)
# ----------------------------------------------------------
PINK = (236 / 255, 64 / 255, 122 / 255, 1)      # 主题粉
SOFT_PINK = (252 / 255, 228 / 255, 236 / 255, 1)
DARK = (70 / 255, 40 / 255, 55 / 255, 1)        # 深色文字
GRAY = (0.45, 0.45, 0.45, 1)                    # 灰色文字
WHITE = (1, 1, 1, 1)

MOODS = ["😄", "😊", "😌", "😢", "😠"]


# ==========================================================
# 工具函数
# ==========================================================
def parse_date(text):
    """把 'YYYY-MM-DD' 字符串解析为 date，格式错误抛异常。"""
    return datetime.strptime(text.strip(), "%Y-%m-%d").date()


def wrap_label(text, **kwargs):
    """可自动换行、高度自适应的 MDLabel。"""
    label = MDLabel(text=text, size_hint_y=None, **kwargs)
    label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    label.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
    return label


# ==========================================================
# 数据库层
# ==========================================================
class Database:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._init_schema()
        self._init_defaults()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _init_schema(self):
        c = self._conn()
        cur = c.cursor()
        # 照片日记
        cur.execute('''CREATE TABLE IF NOT EXISTS diary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            img_path TEXT,
            event_date TEXT,
            event TEXT,
            thought TEXT,
            tags TEXT DEFAULT "",
            mood TEXT DEFAULT "",
            created_at TEXT)''')
        # 纪念日
        cur.execute('''CREATE TABLE IF NOT EXISTS anniversary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            event_date TEXT,
            yearly INTEGER DEFAULT 1,
            note TEXT DEFAULT "")''')
        # 心愿清单
        cur.execute('''CREATE TABLE IF NOT EXISTS wish(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            done INTEGER DEFAULT 0,
            done_date TEXT DEFAULT "",
            created_at TEXT)''')
        # 时光胶囊
        cur.execute('''CREATE TABLE IF NOT EXISTS capsule(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            open_date TEXT,
            created_at TEXT,
            opened INTEGER DEFAULT 0,
            opened_at TEXT DEFAULT "")''')
        # 设置
        cur.execute('''CREATE TABLE IF NOT EXISTS settings(
            k TEXT PRIMARY KEY,
            v TEXT)''')
        c.commit()
        c.close()

    def _init_defaults(self):
        if not self.all_settings():
            today = str(date.today())
            self.set_setting("name1", "Ta")
            self.set_setting("name2", "我")
            self.set_setting("start_date", today)
            self.add_anniversary("恋爱纪念日", today, 1, "")

    # ---------------- 设置 ----------------
    def get_setting(self, key, default=None):
        c = self._conn()
        row = c.execute("SELECT v FROM settings WHERE k=?", (key,)).fetchone()
        c.close()
        return row[0] if row else default

    def all_settings(self):
        c = self._conn()
        rows = c.execute("SELECT k,v FROM settings").fetchall()
        c.close()
        return {k: v for k, v in rows}

    def set_setting(self, key, value):
        c = self._conn()
        c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (key, str(value)))
        c.commit()
        c.close()

    # ---------------- 照片日记 ----------------
    def insert_diary(self, img_path, event_date, event, thought, tags, mood):
        c = self._conn()
        cur = c.cursor()
        cur.execute('''INSERT INTO diary(img_path,event_date,event,thought,tags,mood,created_at)
                       VALUES(?,?,?,?,?,?,?)''',
                    (img_path, event_date, event, thought, tags, mood,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
        new_id = cur.lastrowid
        c.close()
        return new_id

    def update_diary(self, rid, img_path, event_date, event, thought, tags, mood):
        c = self._conn()
        c.execute('''UPDATE diary SET img_path=?,event_date=?,event=?,thought=?,tags=?,mood=?
                     WHERE id=?''',
                  (img_path, event_date, event, thought, tags, mood, rid))
        c.commit()
        c.close()

    def delete_diary(self, rid):
        c = self._conn()
        c.execute("DELETE FROM diary WHERE id=?", (rid,))
        c.commit()
        c.close()

    def get_diary(self, rid):
        c = self._conn()
        row = c.execute("SELECT * FROM diary WHERE id=?", (rid,)).fetchone()
        c.close()
        return row

    def all_diary(self):
        c = self._conn()
        rows = c.execute("SELECT * FROM diary ORDER BY event_date DESC, id DESC").fetchall()
        c.close()
        return rows

    def search_diary(self, keyword):
        like = f"%{keyword.strip()}%"
        c = self._conn()
        rows = c.execute('''SELECT * FROM diary
                            WHERE event LIKE ? OR thought LIKE ? OR tags LIKE ?
                            ORDER BY event_date DESC, id DESC''',
                         (like, like, like)).fetchall()
        c.close()
        return rows

    def memories_today(self):
        """往年今天（同月同日）的日记。"""
        today = date.today()
        mmdd = today.strftime("%m-%d")
        c = self._conn()
        rows = c.execute('''SELECT * FROM diary
                            WHERE strftime('%m-%d',event_date)=? AND event_date<?
                            ORDER BY event_date DESC''',
                         (mmdd, f"{today.year}-01-01")).fetchall()
        c.close()
        return rows

    # ---------------- 纪念日 ----------------
    def add_anniversary(self, name, event_date, yearly, note=""):
        c = self._conn()
        cur = c.cursor()
        cur.execute("INSERT INTO anniversary(name,event_date,yearly,note) VALUES(?,?,?,?)",
                    (name, event_date, yearly, note))
        c.commit()
        new_id = cur.lastrowid
        c.close()
        return new_id

    def all_anniversary(self):
        c = self._conn()
        rows = c.execute("SELECT * FROM anniversary ORDER BY event_date ASC").fetchall()
        c.close()
        return rows

    def delete_anniversary(self, rid):
        c = self._conn()
        c.execute("DELETE FROM anniversary WHERE id=?", (rid,))
        c.commit()
        c.close()

    # ---------------- 心愿清单 ----------------
    def add_wish(self, content):
        c = self._conn()
        cur = c.cursor()
        cur.execute("INSERT INTO wish(content,created_at) VALUES(?,?)",
                    (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
        new_id = cur.lastrowid
        c.close()
        return new_id

    def all_wish(self):
        c = self._conn()
        rows = c.execute("SELECT * FROM wish ORDER BY done ASC, id DESC").fetchall()
        c.close()
        return rows

    def toggle_wish(self, wid):
        c = self._conn()
        row = c.execute("SELECT done FROM wish WHERE id=?", (wid,)).fetchone()
        new_done = 0 if row[0] else 1
        done_date = str(date.today()) if new_done else ""
        c.execute("UPDATE wish SET done=?,done_date=? WHERE id=?",
                  (new_done, done_date, wid))
        c.commit()
        c.close()

    def delete_wish(self, wid):
        c = self._conn()
        c.execute("DELETE FROM wish WHERE id=?", (wid,))
        c.commit()
        c.close()

    # ---------------- 时光胶囊 ----------------
    def add_capsule(self, content, open_date):
        c = self._conn()
        cur = c.cursor()
        cur.execute("INSERT INTO capsule(content,open_date,created_at) VALUES(?,?,?)",
                    (content, open_date, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
        new_id = cur.lastrowid
        c.close()
        return new_id

    def all_capsule(self):
        c = self._conn()
        rows = c.execute("SELECT * FROM capsule ORDER BY id DESC").fetchall()
        c.close()
        return rows

    def open_capsule(self, cid):
        c = self._conn()
        c.execute("UPDATE capsule SET opened=1,opened_at=? WHERE id=?",
                  (str(date.today()), cid))
        c.commit()
        c.close()

    def delete_capsule(self, cid):
        c = self._conn()
        c.execute("DELETE FROM capsule WHERE id=?", (cid,))
        c.commit()
        c.close()


# ==========================================================
# 界面布局 KV
# ==========================================================
KV = r'''
#:import get_color_from_hex kivy.utils.get_color_from_hex

# ---------- 根窗口：ScreenManager 包含全部页面 ----------
ScreenManager:
    HomeScreen:
    AlbumScreen:
    AnniversaryScreen:
    ProfileScreen:
    DiaryEditScreen:
    DiaryDetailScreen:
    SearchScreen:
    WishScreen:
    CapsuleScreen:
    SettingsScreen:

# ---------- 底部 Tab / 快捷图标按钮 ----------
<TabItem>:
    orientation: "vertical"
    spacing: 0
    padding: [0, dp(5), 0, dp(2)]
    md_bg_color: "#FFFFFF"
    MDIcon:
        icon: root.icon
        pos_hint: {"center_x": .5}
        font_size: "25sp"
        color: root.icon_color
    MDLabel:
        text: root.text
        halign: "center"
        font_size: "12sp"
        color: root.icon_color
        size_hint_y: None
        height: dp(20)

# ================= 首页 =================
<HomeScreen>:
    on_enter: app.refresh_home(self)
    name: "home"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(12), 0]
            MDLabel:
                text: "情侣纪念册"
                bold: True
                font_size: "22sp"
                color: 1,1,1,1
        ScrollView:
            MDBoxLayout:
                id: content
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
        MDBoxLayout:
            size_hint_y: 0.09
            md_bg_color: "#FFFFFF"
            TabItem:
                icon: "home"
                text: "首页"
                icon_color: get_color_from_hex("#EC407A")
                on_press: app.switch_tab("home")
            TabItem:
                icon: "image-multiple"
                text: "相册"
                on_press: app.switch_tab("album")
            TabItem:
                icon: "heart"
                text: "纪念日"
                on_press: app.switch_tab("anniversary")
            TabItem:
                icon: "account"
                text: "我的"
                on_press: app.switch_tab("profile")

# ================= 相册 =================
<AlbumScreen>:
    on_enter: app.refresh_album(self)
    name: "album"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(4), 0]
            MDLabel:
                text: "我们的相册"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
            MDIconButton:
                icon: "plus"
                icon_color: 1,1,1,1
                on_press: app.new_diary()
        ScrollView:
            MDBoxLayout:
                id: album_list
                orientation: "vertical"
                padding: dp(12)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
        MDBoxLayout:
            size_hint_y: 0.09
            md_bg_color: "#FFFFFF"
            TabItem:
                icon: "home"
                text: "首页"
                on_press: app.switch_tab("home")
            TabItem:
                icon: "image-multiple"
                text: "相册"
                icon_color: get_color_from_hex("#EC407A")
                on_press: app.switch_tab("album")
            TabItem:
                icon: "heart"
                text: "纪念日"
                on_press: app.switch_tab("anniversary")
            TabItem:
                icon: "account"
                text: "我的"
                on_press: app.switch_tab("profile")

# ================= 纪念日 =================
<AnniversaryScreen>:
    on_enter: app.refresh_anniversary(self)
    name: "anniversary"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(4), 0]
            MDLabel:
                text: "纪念日"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
            MDIconButton:
                icon: "plus"
                icon_color: 1,1,1,1
                on_press: app.add_anniversary_dialog()
        ScrollView:
            MDBoxLayout:
                id: anniv_list
                orientation: "vertical"
                padding: dp(12)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
        MDBoxLayout:
            size_hint_y: 0.09
            md_bg_color: "#FFFFFF"
            TabItem:
                icon: "home"
                text: "首页"
                on_press: app.switch_tab("home")
            TabItem:
                icon: "image-multiple"
                text: "相册"
                on_press: app.switch_tab("album")
            TabItem:
                icon: "heart"
                text: "纪念日"
                icon_color: get_color_from_hex("#EC407A")
                on_press: app.switch_tab("anniversary")
            TabItem:
                icon: "account"
                text: "我的"
                on_press: app.switch_tab("profile")

# ================= 我的 =================
<ProfileScreen>:
    on_enter: app.refresh_profile(self)
    name: "profile"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(12), 0]
            MDLabel:
                text: "我的"
                bold: True
                font_size: "22sp"
                color: 1,1,1,1
        ScrollView:
            MDBoxLayout:
                id: menu
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                MDCard:
                    orientation: "vertical"
                    theme_bg_color: "Custom"
                    padding: dp(16)
                    spacing: dp(4)
                    radius: [dp(16)]
                    md_bg_color: "#FCE4EC"
                    size_hint_y: None
                    height: dp(90)
                    MDLabel:
                        id: profile_header
                        halign: "center"
                        font_size: "18sp"
                        bold: True
                        color: app.PINK
                MDCard:
                    theme_bg_color: "Custom"
                    md_bg_color: "#FFFFFF"
                    orientation: "horizontal"
                    padding: dp(10)
                    radius: [dp(14)]
                    size_hint_y: None
                    height: dp(56)
                    on_press: app.open_wish()
                    MDIcon:
                        icon: "playlist-check"
                        color: app.PINK
                        size_hint_x: None
                        width: dp(36)
                    MDLabel:
                        text: "心愿清单"
                        font_size: "16sp"
                        color: app.DARK
                    MDIcon:
                        icon: "chevron-right"
                        color: app.GRAY
                        size_hint_x: None
                        width: dp(28)
                MDCard:
                    theme_bg_color: "Custom"
                    md_bg_color: "#FFFFFF"
                    orientation: "horizontal"
                    padding: dp(10)
                    radius: [dp(14)]
                    size_hint_y: None
                    height: dp(56)
                    on_press: app.open_capsule()
                    MDIcon:
                        icon: "lock-clock"
                        color: app.PINK
                        size_hint_x: None
                        width: dp(36)
                    MDLabel:
                        text: "时光胶囊"
                        font_size: "16sp"
                        color: app.DARK
                    MDIcon:
                        icon: "chevron-right"
                        color: app.GRAY
                        size_hint_x: None
                        width: dp(28)
                MDCard:
                    theme_bg_color: "Custom"
                    md_bg_color: "#FFFFFF"
                    orientation: "horizontal"
                    padding: dp(10)
                    radius: [dp(14)]
                    size_hint_y: None
                    height: dp(56)
                    on_press: app.open_search()
                    MDIcon:
                        icon: "magnify"
                        color: app.PINK
                        size_hint_x: None
                        width: dp(36)
                    MDLabel:
                        text: "搜索日记"
                        font_size: "16sp"
                        color: app.DARK
                    MDIcon:
                        icon: "chevron-right"
                        color: app.GRAY
                        size_hint_x: None
                        width: dp(28)
                MDCard:
                    theme_bg_color: "Custom"
                    md_bg_color: "#FFFFFF"
                    orientation: "horizontal"
                    padding: dp(10)
                    radius: [dp(14)]
                    size_hint_y: None
                    height: dp(56)
                    on_press: app.open_settings()
                    MDIcon:
                        icon: "cog-outline"
                        color: app.PINK
                        size_hint_x: None
                        width: dp(36)
                    MDLabel:
                        text: "设置"
                        font_size: "16sp"
                        color: app.DARK
                    MDIcon:
                        icon: "chevron-right"
                        color: app.GRAY
                        size_hint_x: None
                        width: dp(28)
                MDCard:
                    theme_bg_color: "Custom"
                    md_bg_color: "#FFFFFF"
                    orientation: "horizontal"
                    padding: dp(10)
                    radius: [dp(14)]
                    size_hint_y: None
                    height: dp(56)
                    on_press: app.about_dialog()
                    MDIcon:
                        icon: "information-outline"
                        color: app.PINK
                        size_hint_x: None
                        width: dp(36)
                    MDLabel:
                        text: "关于"
                        font_size: "16sp"
                        color: app.DARK
                    MDIcon:
                        icon: "chevron-right"
                        color: app.GRAY
                        size_hint_x: None
                        width: dp(28)
        MDBoxLayout:
            size_hint_y: 0.09
            md_bg_color: "#FFFFFF"
            TabItem:
                icon: "home"
                text: "首页"
                on_press: app.switch_tab("home")
            TabItem:
                icon: "image-multiple"
                text: "相册"
                on_press: app.switch_tab("album")
            TabItem:
                icon: "heart"
                text: "纪念日"
                on_press: app.switch_tab("anniversary")
            TabItem:
                icon: "account"
                text: "我的"
                icon_color: get_color_from_hex("#EC407A")
                on_press: app.switch_tab("profile")

# ================= 新增 / 编辑日记 =================
<DiaryEditScreen>:
    name: "diary_edit"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(12), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                id: edit_title
                text: "记一笔"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                Image:
                    id: preview
                    source: ""
                    size_hint_y: None
                    height: dp(210)
                    fit_mode: "contain"
                MDButton:
                    on_press: app.pick_image()
                    MDButtonText:
                        text: "选择照片"
                MDTextField:
                    id: date_input
                    hint_text: "日期 (YYYY-MM-DD)"
                    text: ""
                MDTextField:
                    id: title_input
                    hint_text: "事件标题（必填）"
                MDTextField:
                    id: thought_input
                    hint_text: "此刻的想法..."
                    multiline: True
                    size_hint_y: None
                    height: dp(120)
                MDTextField:
                    id: tags_input
                    hint_text: "标签（逗号分隔，如：旅行,美食）"
                MDLabel:
                    text: "今天的心情"
                    font_size: "15sp"
                    bold: True
                    color: app.DARK
                    size_hint_y: None
                    height: dp(26)
                MDGridLayout:
                    cols: 5
                    spacing: dp(2)
                    size_hint_y: None
                    height: dp(52)
                    MDButton:
                        on_press: app.set_mood("😄")
                        MDButtonText:
                            text: "😄"
                    MDButton:
                        on_press: app.set_mood("😊")
                        MDButtonText:
                            text: "😊"
                    MDButton:
                        on_press: app.set_mood("😌")
                        MDButtonText:
                            text: "😌"
                    MDButton:
                        on_press: app.set_mood("😢")
                        MDButtonText:
                            text: "😢"
                    MDButton:
                        on_press: app.set_mood("😠")
                        MDButtonText:
                            text: "😠"
                MDLabel:
                    id: mood_show
                    text: "未选择心情"
                    font_size: "14sp"
                    color: app.GRAY
                    size_hint_y: None
                    height: dp(24)
                MDButton:
                    on_press: app.save_diary()
                    MDButtonText:
                        text: "保存"

# ================= 日记详情 =================
<DiaryDetailScreen>:
    name: "diary_detail"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(12), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                text: "日记详情"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(12)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                Image:
                    id: big_img
                    source: ""
                    size_hint_y: None
                    height: dp(280)
                    fit_mode: "contain"
                MDLabel:
                    id: info
                    text: ""
                    font_size: "16sp"
                    color: app.DARK
                    size_hint_y: None
        MDBoxLayout:
            size_hint_y: 0.09
            padding: dp(12)
            spacing: dp(10)
            MDButton:
                on_press: app.edit_current()
                MDButtonText:
                    text: "编辑"
            MDButton:
                on_press: app.ask_delete_current()
                MDButtonText:
                    text: "删除"

# ================= 搜索 =================
<SearchScreen>:
    on_enter: app.refresh_search_hint(self)
    name: "search"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(12), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                text: "搜索日记"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
        MDBoxLayout:
            orientation: "horizontal"
            padding: [dp(12), dp(8)]
            spacing: dp(6)
            size_hint_y: None
            height: dp(60)
            MDTextField:
                id: keyword
                hint_text: "输入事件 / 想法 / 标签关键词"
                on_text_validate: app.run_search()
            MDIconButton:
                icon: "magnify"
                on_press: app.run_search()
        ScrollView:
            MDBoxLayout:
                id: results
                orientation: "vertical"
                padding: [dp(12), 0]
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height

# ================= 心愿清单 =================
<WishScreen>:
    on_enter: app.refresh_wish(self)
    name: "wish"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(12), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                text: "心愿清单"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
        MDBoxLayout:
            orientation: "horizontal"
            padding: [dp(12), dp(6)]
            spacing: dp(6)
            size_hint_y: None
            height: dp(60)
            MDTextField:
                id: wish_input
                hint_text: "想一起做的事，如：一起看一次日出"
            MDIconButton:
                icon: "plus"
                on_press: app.add_wish()
        ScrollView:
            MDBoxLayout:
                id: wish_list
                orientation: "vertical"
                padding: [dp(12), 0]
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height

# ================= 时光胶囊 =================
<CapsuleScreen>:
    on_enter: app.refresh_capsule(self)
    name: "capsule"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(4), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                text: "时光胶囊"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
            MDIconButton:
                icon: "plus"
                icon_color: 1,1,1,1
                on_press: app.add_capsule_dialog()
        ScrollView:
            MDBoxLayout:
                id: capsule_list
                orientation: "vertical"
                padding: dp(12)
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height

# ================= 设置 =================
<SettingsScreen>:
    on_enter: app.load_settings(self)
    name: "settings"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: "#FFF3F7"
        MDBoxLayout:
            size_hint_y: 0.085
            md_bg_color: "#EC407A"
            padding: [dp(8), 0, dp(12), 0]
            MDIconButton:
                icon: "arrow-left"
                icon_color: 1,1,1,1
                on_press: app.go_back()
            MDLabel:
                text: "设置"
                bold: True
                font_size: "20sp"
                color: 1,1,1,1
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: dp(14)
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                MDTextField:
                    id: name1
                    hint_text: "你的名字 / 昵称"
                MDTextField:
                    id: name2
                    hint_text: "Ta 的名字 / 昵称"
                MDTextField:
                    id: start_date
                    hint_text: "在一起的日期 (YYYY-MM-DD)"
                MDButton:
                    on_press: app.save_settings()
                    MDButtonText:
                        text: "保存设置"
                MDLabel:
                    id: datapath
                    text: ""
                    font_size: "12sp"
                    color: app.GRAY
'''


# ==========================================================
# 屏幕类
# ==========================================================
class TabItem(ButtonBehavior, MDBoxLayout):
    icon = StringProperty("circle")
    text = StringProperty("")
    icon_color = ObjectProperty(GRAY)


class HomeScreen(Screen):
    pass


class AlbumScreen(Screen):
    pass


class AnniversaryScreen(Screen):
    pass


class ProfileScreen(Screen):
    pass


class DiaryEditScreen(Screen):
    pass


class DiaryDetailScreen(Screen):
    pass


class SearchScreen(Screen):
    pass


class WishScreen(Screen):
    pass


class CapsuleScreen(Screen):
    pass


class SettingsScreen(Screen):
    pass


# ==========================================================
# 主应用
# ==========================================================
class LoveDiaryApp(MDApp):
    # 暴露给 KV 使用
    PINK = PINK
    DARK = DARK
    GRAY = GRAY

    # ---------- 生命周期 ----------
    def build(self):
        self.title = "情侣纪念册"
        if platform != "android":
            Window.size = (430, 820)

        # 数据目录：安卓上为 App 私有目录；允许环境变量覆盖（测试用）
        self.data_root = os.environ.get("PD_DATA_DIR", self.user_data_dir)
        self.photos_dir = os.path.join(self.data_root, "photos")
        os.makedirs(self.photos_dir, exist_ok=True)

        self.db = Database(os.path.join(self.data_root, "love_diary.db"))

        # 日记编辑状态
        self.edit_id = None          # None=新增，否则为编辑的记录 id
        self.edit_img_path = None    # 当前选中（待保存）的图片
        self.orig_img_path = None    # 编辑前的旧图片
        self.mood = ""
        self.view_id = None

        # 文件管理器（plyer 不可用时的兜底）
        self.file_manager = MDFileManager(
            exit_manager=lambda *a: self.file_manager.close(),
            select_path=self._fm_select_path)

        root = Builder.load_string(KV)

        # 自动化测试：构造样例数据并遍历所有页面
        if os.environ.get("PHOTO_DIARY_TEST"):
            self._prepare_test_data()
            self._schedule_test_traverse()

        return root

    # ---------- 通用导航 ----------
    def on_start(self):
        # 首次进入时 on_enter 在界面布局完成前就触发，可能无法正常构建，
        # 因此在布局完成后兜底刷新一次当前页
        Clock.schedule_once(self._refresh_current_page, 0.2)

    def _refresh_current_page(self, dt=None):
        if not self.root:
            return
        mapping = {
            "home": self.refresh_home,
            "album": self.refresh_album,
            "anniversary": self.refresh_anniversary,
            "profile": self.refresh_profile,
            "wish": self.refresh_wish,
            "capsule": self.refresh_capsule,
            "settings": self.load_settings,
        }
        fn = mapping.get(self.root.current)
        if fn:
            fn()

    def switch_tab(self, name):
        self.root.current = name

    def go_back(self, *args):
        # 子页面统一返回相册
        self.root.current = "album"

    def toast(self, text):
        dlg = MDDialog(MDDialogSupportingText(text=text))
        dlg.open()
        Clock.schedule_once(lambda dt: dlg.dismiss(), 1.6)

    # ---------- 图片选择 ----------
    def pick_image(self):
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._on_file_chosen,
                                  filters=["*.jpg", "*.jpeg", "*.png"])
        except Exception:
            self.file_manager.show(os.path.expanduser("~"))

    def _on_file_chosen(self, selection):
        if selection:
            self._apply_selected_image(selection[0])

    def _fm_select_path(self, path):
        self.file_manager.close()
        self._apply_selected_image(path)

    def _apply_selected_image(self, path):
        self.edit_img_path = path
        self.root.get_screen("diary_edit").ids.preview.source = path

    def import_photo(self, src):
        """把选中的图片压缩后复制到 App 图片目录，返回新路径。"""
        dst = os.path.join(
            self.photos_dir,
            "p_" + datetime.now().strftime("%Y%m%d%H%M%S%f") + ".jpg")
        im = PilImage.open(src).convert("RGB")
        im.thumbnail((1440, 1440))
        im.save(dst, "JPEG", quality=85)
        return dst

    # ---------- 日期 / 纪念日计算 ----------
    def _together_days(self):
        try:
            start = parse_date(self.db.get_setting("start_date", str(date.today())))
            return max(0, (date.today() - start).days)
        except Exception:
            return 0

    def _anniv_next_date(self, event_date_text, yearly):
        """返回该纪念日下一次到来的日期；一次性且已过返回 None。"""
        today = date.today()
        d = parse_date(event_date_text)
        if yearly:
            try:
                nd = d.replace(year=today.year)
            except ValueError:
                nd = date(today.year, 2, 28)
            if nd < today:
                try:
                    nd = d.replace(year=today.year + 1)
                except ValueError:
                    nd = date(today.year + 1, 2, 28)
            return nd
        return d if d >= today else None

    def anniv_status(self, event_date_text, yearly):
        today = date.today()
        nd = self._anniv_next_date(event_date_text, yearly)
        if nd is None:
            past = (today - parse_date(event_date_text)).days
            return f"已过去 {past} 天"
        delta = (nd - today).days
        if delta == 0:
            return "就是今天 ❤"
        return f"还有 {delta} 天"

    def next_anniversary(self):
        """所有纪念日中距离今天最近的一个，返回 (名称, 天数)。"""
        today = date.today()
        best = None
        for _id, name, ds, yearly, note in self.db.all_anniversary():
            try:
                nd = self._anniv_next_date(ds, yearly)
            except Exception:
                continue
            if nd is None:
                continue
            delta = (nd - today).days
            if best is None or delta < best[1]:
                best = (name, delta)
        return best

    # ---------- 卡片构造 ----------
    def _section_title(self, text):
        return MDLabel(text=text, font_size="17sp", bold=True, color=DARK,
                       size_hint_y=None, height=dp(28))

    def _card(self, bg="#FFFFFF", **kwargs):
        """创建背景色可靠生效的 MDCard。

        KivyMD 2.0 的 MDCard 默认 theme_bg_color="Primary"，会强制使用
        主题的 surfaceContainerHighest（灰紫）而忽略 md_bg_color；
        设置 theme_bg_color="Custom" 后自定义背景色才会真正生效。
        """
        card = MDCard(theme_bg_color="Custom", **kwargs)
        card.md_bg_color = bg
        card._bg_color = bg
        return card

    def _hint_card(self, text):
        card = self._card(padding=dp(14), radius=[dp(14)], size_hint_y=None,
                          height=dp(58))
        card.add_widget(MDLabel(text=text, font_size="14sp", color=GRAY))
        return card

    def _empty_label(self, text):
        lab = MDLabel(text=text, halign="center", font_size="15sp",
                      color=GRAY, size_hint_y=None, height=dp(120))
        return lab

    def _quick_item(self, icon, text, callback):
        item = TabItem(icon=icon, text=text, md_bg_color="#FFFFFF",
                       padding=[0, dp(10), 0, dp(6)])
        item.bind(on_press=lambda *a: callback())
        return item

    def _mini_diary_card(self, rec):
        rid, img, edate, event, thought, tags, mood, created = rec
        card = self._card(orientation="horizontal", padding=dp(8), spacing=dp(10),
                      radius=[dp(14)], size_hint_y=None, height=dp(90))
        card.add_widget(Image(source=img, size_hint_x=None, width=dp(80),
                              fit_mode="cover"))
        card.add_widget(MDLabel(text=f"{edate[:4]}年\n{mood} {event}",
                                font_size="14sp", color=DARK))
        card.bind(on_press=lambda *a: self.open_diary(rid))
        return card

    def _diary_card(self, rec):
        rid, img, edate, event, thought, tags, mood, created = rec
        card = self._card(orientation="vertical", padding=dp(8), spacing=dp(6),
                      radius=[dp(16)], size_hint_y=None)
        card.add_widget(Image(source=img, size_hint_y=None, height=dp(210),
                              fit_mode="cover"))
        card.add_widget(MDLabel(text=f"{mood} {edate}  {event}",
                                font_size="16sp", bold=True, color=DARK,
                                size_hint_y=None, height=dp(28)))
        if thought:
            card.add_widget(wrap_label(thought, font_size="14sp", color=GRAY))
        if tags:
            card.add_widget(MDLabel(text=f"标签：{tags}", font_size="12sp",
                                    color=PINK, size_hint_y=None, height=dp(22)))
        card.bind(minimum_height=lambda inst, h: setattr(inst, "height", h))
        card.bind(on_press=lambda *a: self.open_diary(rid))
        return card

    # ---------- 首页 ----------
    def refresh_home(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("home")
        box = screen.ids.content
        # 启动早期 on_enter 触发时布局尚未完成（宽度异常），延迟到就绪后再构建
        if box.width < 200:
            Clock.schedule_once(lambda dt: self.refresh_home(screen), 0.15)
            return
        box.clear_widgets()

        name1 = self.db.get_setting("name1", "Ta")
        name2 = self.db.get_setting("name2", "我")
        days = self._together_days()

        header = MDBoxLayout(orientation="vertical", padding=dp(20), spacing=dp(4),
                        radius=[dp(20)], md_bg_color="#FCE4EC",
                        size_hint_y=None, height=dp(150))
        header.add_widget(MDLabel(text="❤", halign="center", font_size="38sp",
                                  color=PINK, size_hint_y=None, height=dp(50)))
        header.add_widget(MDLabel(text=f"{name1}  ❤  {name2}", halign="center",
                                  font_size="22sp", bold=True, color=DARK,
                                  size_hint_y=None, height=dp(34)))
        header.add_widget(MDLabel(text=f"已相爱 {days} 天", halign="center",
                                  font_size="16sp", color=PINK,
                                  size_hint_y=None, height=dp(28)))
        box.add_widget(header)

        nxt = self.next_anniversary()
        if nxt:
            name, delta = nxt
            card = self._card(orientation="vertical", padding=dp(16), spacing=dp(4),
                          radius=[dp(16)], size_hint_y=None, height=dp(92))
            card.add_widget(MDLabel(text="🎉 下一个纪念日", font_size="14sp",
                                    color=GRAY, size_hint_y=None, height=dp(24)))
            t = "就是今天，记得说爱你 ❤" if delta == 0 else f"{name}，还有 {delta} 天"
            card.add_widget(MDLabel(text=t, font_size="18sp", bold=True,
                                    color=DARK, size_hint_y=None, height=dp(32)))
            box.add_widget(card)

        box.add_widget(self._section_title("那年今日"))
        memories = self.db.memories_today()
        if not memories:
            box.add_widget(self._hint_card("往年的今天还没有故事，一起去创造一个吧～"))
        else:
            for rec in memories:
                box.add_widget(self._mini_diary_card(rec))

        box.add_widget(self._section_title("快捷功能"))
        grid = MDGridLayout(cols=3, spacing=dp(10), size_hint_y=None,
                            height=dp(190))
        items = [
            ("camera-plus", "记一笔", self.new_diary),
            ("heart", "纪念日", lambda: self.switch_tab("anniversary")),
            ("playlist-check", "心愿单", self.open_wish),
            ("lock-clock", "时光胶囊", self.open_capsule),
            ("magnify", "搜一搜", self.open_search),
            ("image-multiple", "相册", lambda: self.switch_tab("album")),
        ]
        for icon, text, cb in items:
            grid.add_widget(self._quick_item(icon, text, cb))
        box.add_widget(grid)

    # ---------- 相册 ----------
    def refresh_album(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("album")
        container = screen.ids.album_list
        container.clear_widgets()
        records = self.db.all_diary()
        if not records:
            container.add_widget(self._empty_label("还没有照片\n点击右上角 + 记下第一笔吧～"))
            return
        current_month = None
        for rec in records:
            month = rec[2][:7]
            if month != current_month:
                current_month = month
                year, mn = month.split("-")
                container.add_widget(MDLabel(
                    text=f"{year} 年 {int(mn)} 月", bold=True, color=PINK,
                    size_hint_y=None, height=dp(30)))
            container.add_widget(self._diary_card(rec))

    # ---------- 纪念日 ----------
    def refresh_anniversary(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("anniversary")
        container = screen.ids.anniv_list
        container.clear_widgets()
        rows = self.db.all_anniversary()
        if not rows:
            container.add_widget(self._empty_label("还没有纪念日\n点击右上角 + 添加吧～"))
            return
        for rid, name, ds, yearly, note in rows:
            card = self._card(orientation="vertical", padding=dp(14), spacing=dp(4),
                          radius=[dp(16)], size_hint_y=None, height=dp(118))
            row = MDBoxLayout(spacing=dp(8))
            row.add_widget(MDLabel(text=name, font_size="18sp", bold=True,
                                   color=DARK))
            trash = MDIconButton(icon="trash-can-outline",
                                 on_press=lambda *a, rid=rid:
                                 (self.db.delete_anniversary(rid),
                                  self.refresh_anniversary()))
            row.add_widget(trash)
            card.add_widget(row)
            kind = "每年重复" if yearly else "一次性"
            card.add_widget(MDLabel(text=f"{ds}  ·  {kind}", font_size="13sp",
                                    color=GRAY, size_hint_y=None, height=dp(22)))
            try:
                status = self.anniv_status(ds, yearly)
            except Exception:
                status = ""
            card.add_widget(MDLabel(text=status, font_size="16sp", bold=True,
                                    color=PINK, size_hint_y=None, height=dp(26)))
            container.add_widget(card)

    def add_anniversary_dialog(self, *args):
        state = {"yearly": 1}

        name_field = MDTextField(hint_text="名称（如：在一起100天、Ta的生日）")
        date_field = MDTextField(hint_text="日期 (YYYY-MM-DD)",
                                 text=str(date.today()))
        type_label = MDLabel(text="类型：每年重复", font_size="14sp",
                             color=PINK, size_hint_y=None, height=dp(26))

        def choose_yearly(*a):
            state["yearly"] = 1
            type_label.text = "类型：每年重复（生日 / 周年）"

        def choose_once(*a):
            state["yearly"] = 0
            type_label.text = "类型：一次性（百日 / 特定日子）"

        type_row = MDBoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        by = MDButton(on_press=choose_yearly)
        by.add_widget(MDButtonText(text="每年重复"))
        bo = MDButton(on_press=choose_once)
        bo.add_widget(MDButtonText(text="一次性"))
        type_row.add_widget(by)
        type_row.add_widget(bo)

        content = MDBoxLayout(orientation="vertical", spacing=dp(8),
                              padding=dp(12), size_hint_y=None, height=dp(290))
        content.add_widget(name_field)
        content.add_widget(date_field)
        content.add_widget(type_row)
        content.add_widget(type_label)

        def save(*a):
            if not name_field.text.strip():
                self.toast("请填写名称")
                return
            try:
                parse_date(date_field.text)
            except Exception:
                self.toast("日期格式应为 YYYY-MM-DD")
                return
            self.db.add_anniversary(name_field.text.strip(),
                                    date_field.text.strip(),
                                    state["yearly"])
            dialog.dismiss()
            self.refresh_anniversary()
            self.toast("已添加")

        save_btn = MDButton(on_press=save)
        save_btn.add_widget(MDButtonText(text="保存"))
        cancel_btn = MDButton(on_press=lambda *a: dialog.dismiss())
        cancel_btn.add_widget(MDButtonText(text="取消"))

        dialog = MDDialog(
            MDDialogHeadlineText(text="添加纪念日"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(cancel_btn, save_btn))
        dialog.open()

    # ---------- 我的 ----------
    def refresh_profile(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("profile")
        name1 = self.db.get_setting("name1", "Ta")
        name2 = self.db.get_setting("name2", "我")
        days = self._together_days()
        screen.ids.profile_header.text = \
            f"{name1} ❤ {name2}\n已相爱 {days} 天"

    def open_wish(self, *args):
        self.root.current = "wish"

    def open_capsule(self, *args):
        self.root.current = "capsule"

    def open_search(self, *args):
        self.root.current = "search"

    def open_settings(self, *args):
        self.root.current = "settings"

    def about_dialog(self, *args):
        dlg = MDDialog(
            MDDialogHeadlineText(text="关于情侣纪念册"),
            MDDialogSupportingText(
                text="专为两个人设计的纪念小软件：\n照片日记、纪念日、心愿清单、时光胶囊。\n所有数据只保存在本机，请放心记录 ❤"))
        dlg.open()

    # ---------- 新增 / 编辑日记 ----------
    def new_diary(self, *args):
        self.edit_id = None
        self.orig_img_path = None
        self.edit_img_path = None
        self.mood = ""
        screen = self.root.get_screen("diary_edit")
        screen.ids.edit_title.text = "记一笔"
        screen.ids.preview.source = ""
        screen.ids.date_input.text = str(date.today())
        screen.ids.title_input.text = ""
        screen.ids.thought_input.text = ""
        screen.ids.tags_input.text = ""
        screen.ids.mood_show.text = "未选择心情"
        self.root.current = "diary_edit"

    def edit_diary(self, rid):
        rec = self.db.get_diary(rid)
        if not rec:
            return
        _id, img, edate, event, thought, tags, mood, created = rec
        self.edit_id = rid
        self.orig_img_path = img
        self.edit_img_path = img
        self.mood = mood
        screen = self.root.get_screen("diary_edit")
        screen.ids.edit_title.text = "编辑日记"
        screen.ids.preview.source = img
        screen.ids.date_input.text = edate
        screen.ids.title_input.text = event
        screen.ids.thought_input.text = thought
        screen.ids.tags_input.text = tags
        screen.ids.mood_show.text = f"当前心情：{mood}" if mood else "未选择心情"
        self.root.current = "diary_edit"

    def set_mood(self, mood):
        self.mood = mood
        self.root.get_screen("diary_edit").ids.mood_show.text = f"当前心情：{mood}"

    def save_diary(self, *args):
        screen = self.root.get_screen("diary_edit")
        try:
            parse_date(screen.ids.date_input.text)
        except Exception:
            self.toast("日期格式应为 YYYY-MM-DD")
            return
        title = screen.ids.title_input.text.strip()
        if not title:
            self.toast("请填写事件标题")
            return

        thought = screen.ids.thought_input.text.strip()
        tags = screen.ids.tags_input.text.strip()
        edate = screen.ids.date_input.text.strip()

        try:
            if self.edit_id is None:
                if not self.edit_img_path:
                    self.toast("请选择照片")
                    return
                final_img = self.import_photo(self.edit_img_path)
                self.db.insert_diary(final_img, edate, title, thought, tags,
                                     self.mood)
            else:
                if self.edit_img_path and self.edit_img_path != self.orig_img_path:
                    final_img = self.import_photo(self.edit_img_path)
                else:
                    final_img = self.orig_img_path
                self.db.update_diary(self.edit_id, final_img, edate, title,
                                     thought, tags, self.mood)
        except Exception as exc:
            self.toast(f"保存失败：{exc}")
            return

        self.toast("保存成功")
        self.switch_tab("album")

    # ---------- 日记详情 ----------
    def open_diary(self, rid):
        rec = self.db.get_diary(rid)
        if not rec:
            return
        _id, img, edate, event, thought, tags, mood, created = rec
        self.view_id = rid
        screen = self.root.get_screen("diary_detail")
        screen.ids.big_img.source = img
        screen.ids.info.text = (
            f"{mood}\n日期：{edate}\n事件：{event}\n"
            f"标签：{tags if tags else '无'}\n\n{thought}")
        self.root.current = "diary_detail"

    def edit_current(self, *args):
        if self.view_id is not None:
            self.edit_diary(self.view_id)

    def ask_delete_current(self, *args):
        yes_btn = MDButton()
        yes_btn.add_widget(MDButtonText(text="确认删除"))
        no_btn = MDButton()
        no_btn.add_widget(MDButtonText(text="取消"))
        dialog = MDDialog(
            MDDialogHeadlineText(text="删除这篇日记？"),
            MDDialogSupportingText(text="删除后不可恢复，确定吗？"),
            MDDialogButtonContainer(no_btn, yes_btn))
        yes_btn.bind(on_press=lambda *a: (
            dialog.dismiss(),
            self.db.delete_diary(self.view_id),
            self.switch_tab("album"),
            self.toast("已删除")))
        no_btn.bind(on_press=lambda *a: dialog.dismiss())
        dialog.open()

    # ---------- 搜索 ----------
    def refresh_search_hint(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("search")
        container = screen.ids.results
        if not container.children:
            container.add_widget(self._empty_label("输入关键词，搜索两个人的回忆～"))

    def run_search(self, *args):
        keyword = self.root.get_screen("search").ids.keyword.text
        container = self.root.get_screen("search").ids.results
        container.clear_widgets()
        if not keyword.strip():
            container.add_widget(self._empty_label("请输入关键词"))
            return
        records = self.db.search_diary(keyword)
        if not records:
            container.add_widget(self._empty_label("没有找到匹配的日记～"))
            return
        for rec in records:
            container.add_widget(self._diary_card(rec))

    # ---------- 心愿清单 ----------
    def add_wish(self, *args):
        field = self.root.get_screen("wish").ids.wish_input
        content = field.text.strip()
        if not content:
            self.toast("请填写心愿内容")
            return
        self.db.add_wish(content)
        field.text = ""
        self.refresh_wish()

    def refresh_wish(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("wish")
        container = screen.ids.wish_list
        container.clear_widgets()
        rows = self.db.all_wish()
        done = sum(1 for w in rows if w[2])

        progress_card = self._card(orientation="vertical", padding=dp(14),
                               spacing=dp(8), radius=[dp(14)],
                               size_hint_y=None, height=dp(88))
        progress_card.add_widget(MDLabel(
            text=f"已完成 {done}/{len(rows)} 件一起想做的事",
            font_size="15sp", bold=True, color=DARK,
            size_hint_y=None, height=dp(26)))
        bar = MDLinearProgressIndicator(value=(done / len(rows) if rows else 0),
                                        size_hint_y=None, height=dp(10))
        progress_card.add_widget(bar)
        container.add_widget(progress_card)

        for wid, content, is_done, done_date, created in rows:
            card = self._card(orientation="horizontal", padding=dp(8), spacing=dp(4),
                          radius=[dp(12)], size_hint_y=None, height=dp(56))
            icon_btn = MDIconButton(
                icon="heart" if is_done else "checkbox-blank-circle-outline",
                on_press=lambda *a, wid=wid: (self.db.toggle_wish(wid),
                                              self.refresh_wish()))
            card.add_widget(icon_btn)
            text = f"❤ {content}" + (f"（{done_date}）" if done_date else "") \
                if is_done else content
            card.add_widget(MDLabel(text=text, font_size="15sp",
                                    color=PINK if is_done else DARK))
            trash = MDIconButton(
                icon="trash-can-outline",
                on_press=lambda *a, wid=wid: (self.db.delete_wish(wid),
                                              self.refresh_wish()))
            card.add_widget(trash)
            container.add_widget(card)

    # ---------- 时光胶囊 ----------
    def refresh_capsule(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("capsule")
        container = screen.ids.capsule_list
        container.clear_widgets()
        rows = self.db.all_capsule()
        if not rows:
            container.add_widget(self._empty_label("还没有时光胶囊\n点击右上角 + 写给未来的你们～"))
            return
        today = date.today()
        for cid, content, open_date, created, opened, opened_at in rows:
            card = self._card(orientation="vertical", padding=dp(14), spacing=dp(6),
                          radius=[dp(16)], size_hint_y=None)
            card.add_widget(MDLabel(text=f"写给 {open_date} 的信",
                                    font_size="17sp", bold=True, color=DARK,
                                    size_hint_y=None, height=dp(28)))
            if opened:
                card.add_widget(wrap_label(content, font_size="15sp",
                                           color=DARK))
                card.add_widget(MDLabel(text=f"已于 {opened_at} 开启",
                                        font_size="12sp", color=GRAY,
                                        size_hint_y=None, height=dp(20)))
            else:
                try:
                    delta = (parse_date(open_date) - today).days
                except Exception:
                    delta = 0
                if delta > 0:
                    msg = f"🔒 还有 {delta} 天才能开启"
                else:
                    msg = "✨ 可以开启了，点击卡片打开"
                card.add_widget(MDLabel(text=msg, font_size="15sp",
                                        color=PINK, size_hint_y=None,
                                        height=dp(28)))
                card.bind(on_press=lambda *a, cid=cid, delta=delta:
                          self._try_open_capsule(cid, delta))
            card.bind(minimum_height=lambda inst, h: setattr(inst, "height", h))
            container.add_widget(card)

    def _try_open_capsule(self, cid, delta):
        if delta <= 0:
            self.db.open_capsule(cid)
            self.refresh_capsule()
            self.toast("胶囊已开启 ❤")

    def add_capsule_dialog(self, *args):
        content_field = MDTextField(hint_text="想对未来的你们说的话……",
                                    multiline=True, size_hint_y=None,
                                    height=dp(150))
        future = (date.today().replace(year=date.today().year + 1))
        date_field = MDTextField(hint_text="开启日期 (YYYY-MM-DD)",
                                 text=str(future))
        content = MDBoxLayout(orientation="vertical", spacing=dp(8),
                              padding=dp(12), size_hint_y=None, height=dp(250))
        content.add_widget(content_field)
        content.add_widget(date_field)

        def save(*a):
            if not content_field.text.strip():
                self.toast("写点什么再封存吧")
                return
            try:
                parse_date(date_field.text)
            except Exception:
                self.toast("日期格式应为 YYYY-MM-DD")
                return
            self.db.add_capsule(content_field.text.strip(),
                                date_field.text.strip())
            dialog.dismiss()
            self.refresh_capsule()
            self.toast("胶囊已封存 ❤")

        save_btn = MDButton(on_press=save)
        save_btn.add_widget(MDButtonText(text="封存"))
        cancel_btn = MDButton(on_press=lambda *a: dialog.dismiss())
        cancel_btn.add_widget(MDButtonText(text="取消"))
        dialog = MDDialog(
            MDDialogHeadlineText(text="时光胶囊"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(cancel_btn, save_btn))
        dialog.open()

    # ---------- 设置 ----------
    def load_settings(self, screen=None, *args):
        if screen is None:
            screen = self.root.get_screen("settings")
        screen.ids.name1.text = self.db.get_setting("name1", "Ta")
        screen.ids.name2.text = self.db.get_setting("name2", "我")
        screen.ids.start_date.text = self.db.get_setting(
            "start_date", str(date.today()))
        screen.ids.datapath.text = "所有数据与照片都安全保存在本机，无需联网"

    def save_settings(self, *args):
        screen = self.root.get_screen("settings")
        try:
            parse_date(screen.ids.start_date.text)
        except Exception:
            self.toast("日期格式应为 YYYY-MM-DD")
            return
        self.db.set_setting("name1", screen.ids.name1.text.strip() or "Ta")
        self.db.set_setting("name2", screen.ids.name2.text.strip() or "我")
        self.db.set_setting("start_date", screen.ids.start_date.text.strip())
        self.toast("设置已保存")

    # ==========================================================
    # 自动化测试（仅 PHOTO_DIARY_TEST 环境变量下执行）
    # ==========================================================
    def _prepare_test_data(self):
        test_img = os.path.join(self.data_root, "_test_src.jpg")
        PilImage.new("RGB", (500, 360), (255, 170, 200)).save(test_img)
        saved = self.import_photo(test_img)
        self.db.insert_diary(saved, str(date.today()), "测试事件",
                             "测试想法内容", "测试", "😄")
        self.db.add_anniversary("测试纪念日", str(date.today()), 1, "")
        self.db.add_wish("一起看一次日出")
        self.db.add_capsule("测试胶囊内容", str(date.today()))

    def _schedule_test_traverse(self):
        def go(name):
            def _go(dt):
                if self.root is not None:
                    self.root.current = name
            return _go

        Clock.schedule_once(go("album"), 0.4)
        Clock.schedule_once(go("anniversary"), 0.8)
        Clock.schedule_once(lambda dt: self.new_diary(), 1.2)
        Clock.schedule_once(go("wish"), 1.6)
        Clock.schedule_once(go("capsule"), 2.0)
        Clock.schedule_once(go("search"), 2.4)
        Clock.schedule_once(lambda dt: self.run_search(), 2.7)
        Clock.schedule_once(go("settings"), 3.0)
        Clock.schedule_once(go("profile"), 3.4)
        Clock.schedule_once(go("home"), 3.8)
        Clock.schedule_once(lambda dt: self.stop(), 4.3)


if __name__ == "__main__":
    LoveDiaryApp().run()
#（注：内容由AI生成）
