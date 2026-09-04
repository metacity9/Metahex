"""
========================================================================
Project:     Meta Hex Editor
Version:     1.4
Website:     https://tool.metacode9.com/
Author:      metacode9
Description: A high-performance, virtual-scrolling Hex Editor 
             built with Python and Tkinter.

------------------------------------------------------------------------
License: MIT License

Copyright (c) 2026 metacode9. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a 
copy of this software and associated documentation files (the "Software"), 
to deal in the Software without restriction, including without limitation 
the rights to use, copy, modify, merge, publish, distribute, sublicense, 
and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included 
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS 
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
DEALINGS IN THE SOFTWARE.
========================================================================
"""
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import copy
import json

# Pre-computed 256-byte Hex string lookup table (O(1) rendering cache)
HEX_BYTE_LUT = [f"{b:02X}" for b in range(256)]

class AdvancedHexEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Meta Hex Editor v1.4")
        self.root.geometry("1200x780")
        
        # 코어 데이터 구조
        self.memory = {} 
        self.selected_cells = set()  
        self.drag_start = None
        self.cursor_pos = None
        self._coords_need_update = True
        self._last_rendered_row_count = 0
        
        # Performance Cache (Bounds & Search)
        self._bounds_dirty = True
        self._cached_min_key = 0
        self._cached_max_key = 0
        self._cached_search_data = None
        self._sb_track_id = None
        self._sb_thumb_id = None
        
        # Undo/Redo 스택
        self.undo_stack = []
        self.max_undo_depth = 50
        
        # 파일 및 주소 제어 변수
        self.current_file_path = ""
        self.current_file_name = "Untitled"
        self.last_file_type = "bin"  # 이 변수가 직전 파일 타입을 기억합니다.
        self.current_format = "bin"
        self.is_modified = False     
        self.address_base_set = 0x0
        self.physical_file_size = 0  
        self.display_in_hex_unit = False  
        
        # 가상 스크롤 레이아웃 매개변수
        self.cell_width = 44
        self.cell_height = 30
        self.addr_width = 115
        self.header_height = 32
        
        self.top_visible_row = 0  
        self.max_address = 0
        self.min_address = 0
        self.row_count = 0
        self.visible_rows_count = 25 
        
        self.sb_dragging = False
        self.sb_drag_start_y = 0
        self.sb_drag_start_row = 0
        
        self.config_file = "hexeditor_config.json"
        self.addr_prefix = self.load_config_value("addr_prefix", "@")
        self.comment_prefix = self.load_config_value("comment_prefix", "//")
        self.export_config = self.load_config_value("export_config", {})
        self.recent_files = self.load_recent_files()
        self.presets = self.load_presets()
        self.comments = []
        self.current_side_tab = "presets"
        self.is_preset_panel_visible = False
        
        self.setup_styles()
        self.create_widgets()
        self.clear_memory()


    def load_config_value(self, key, default=None):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(key, default)
        except: pass
        return default

    def update_config_file(self, key, value):
        data = {}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except: pass
        data[key] = value
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except: pass

    def load_presets(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("presets", [])
        except: pass
        return []

    def save_presets(self):
        self.update_config_file("presets", self.presets)

    def load_recent_files(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("recent_files", [])
        except: pass
        return []

    def save_recent_files(self):
        self.update_config_file("recent_files", self.recent_files)

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]
        self.save_recent_files()
        self.update_recent_menu()

    def update_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        for fpath in self.recent_files:
            if os.path.exists(fpath):
                self.recent_menu.add_command(label=fpath, command=lambda p=fpath: self.execute_load_core(p))
        if self.recent_menu.index("end") is None:
            self.recent_menu.add_command(label="No recent files", state="disabled")

    def setup_styles(self):
        # Modern Dark Slate Theme Color Palette
        self.bg_color = "#1E1F22"       # Main background
        self.fg_color = "#CFD3D6"       # General text
        self.accent_color = "#8180FF"   # Accent violet/indigo
        self.grid_bg = "#18181A"        # Hex grid background
        self.grid_line = "#2B2D31"      # Hex grid borders
        self.selection_bg = "#3A3B7E"   # Selected cells background
        self.selection_fg = "#FFFFFF"   # Selected cells text
        
        self.nav_bg = "#2B2D31"         # Navigation bar background
        self.entry_bg = "#111214"       # Input boxes background
        self.entry_fg = "#E3E6E8"       # Input boxes text
        
        self.btn_bg = "#35373C"         # Standard buttons background
        self.btn_fg = "#E3E6E8"         # Standard buttons text
        self.btn_active_bg = "#404249"  # Button click state
        
        self.panel_bg = "#1E1F22"       # Side panels background
        
        self.root.configure(bg=self.bg_color)
        self.style = ttk.Style()
        self.style.theme_use('default')
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("TCombobox",
                             fieldbackground=self.entry_bg,
                             background=self.btn_bg,
                             foreground=self.entry_fg,
                             arrowcolor=self.fg_color,
                             bordercolor=self.btn_bg,
                             darkcolor=self.btn_bg,
                             lightcolor=self.btn_bg)
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", self.entry_bg), ("disabled", self.panel_bg), ("focus", self.entry_bg)],
                       foreground=[("readonly", self.entry_fg), ("disabled", "#666666"), ("focus", self.entry_fg)],
                       selectbackground=[("readonly", self.entry_bg)],
                       selectforeground=[("readonly", self.entry_fg)],
                       arrowcolor=[("readonly", self.fg_color), ("disabled", "#666666")])

        # Configure popup Listbox colors for ttk Comboboxes
        self.root.option_add("*TCombobox*Listbox.background", self.entry_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", self.entry_fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.selection_bg)
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.selection_fg)
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

    def create_widgets(self):


        # ==========================================
        # 중간 컨트롤 툴바
        # ==========================================
        nav_bar = tk.Frame(self.root, bg=self.nav_bg, height=40)
        nav_bar.pack(fill=tk.X, padx=10, pady=2)
        
        self.file_mb = tk.Menubutton(nav_bar, text=" File ▾ ", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"), activebackground=self.btn_bg, activeforeground=self.accent_color, cursor="hand2")
        self.file_mb.pack(side=tk.LEFT, padx=5)

        self.file_menu = tk.Menu(self.file_mb, tearoff=0, bg=self.nav_bg, fg=self.fg_color, activebackground=self.btn_bg, activeforeground=self.accent_color, font=("Segoe UI", 9), bd=1)
        self.file_mb.config(menu=self.file_menu)

        self.file_menu.add_command(label="Load File...", command=self.load_file_unified)
        self.file_menu.add_command(label="Save", command=self.action_quick_save)
        self.file_menu.add_command(label="Export...", command=self.open_export_dialog)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Export to BIN...", command=lambda: self.open_export_dialog(default_format="bin"))
        self.file_menu.add_command(label="Export to Intel HEX...", command=lambda: self.open_export_dialog(default_format="intel_hex"))
        self.file_menu.add_command(label="Export to Motorola S-Record...", command=lambda: self.open_export_dialog(default_format="srec"))
        self.file_menu.add_command(label="Export to String HEX...", command=lambda: self.open_export_dialog(default_format="string_hex"))
        self.file_menu.add_separator()
        
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0, bg=self.nav_bg, fg=self.fg_color, activebackground=self.btn_bg, activeforeground=self.accent_color, font=("Segoe UI", 9), bd=1)
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.update_recent_menu()
        
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit)
        
        tk.Label(nav_bar, text=" |", bg=self.nav_bg, fg=self.btn_bg).pack(side=tk.LEFT)
        
        self.tools_mb = tk.Menubutton(nav_bar, text=" Tools ▾ ", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"), activebackground=self.btn_bg, activeforeground=self.accent_color, cursor="hand2")
        self.tools_mb.pack(side=tk.LEFT, padx=5)
        self.tools_menu = tk.Menu(self.tools_mb, tearoff=0, bg=self.nav_bg, fg=self.fg_color, activebackground=self.btn_bg, activeforeground=self.accent_color, font=("Segoe UI", 9), bd=1)
        self.tools_mb.config(menu=self.tools_menu)
        self.tools_menu.add_command(label="Presets / Comments", command=self.toggle_preset_panel)
        self.tools_menu.add_command(label="Format Settings...", command=self.open_format_settings_dialog)
        self.tools_menu.add_command(label="Data Verification...", command=self.open_verification_dialog)
        
        tk.Label(nav_bar, text=" |", bg=self.nav_bg, fg=self.btn_bg).pack(side=tk.LEFT)
        
        self.help_mb = tk.Menubutton(nav_bar, text=" Help ▾ ", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 10, "bold"), activebackground=self.btn_bg, activeforeground=self.accent_color, cursor="hand2")
        self.help_mb.pack(side=tk.LEFT, padx=5)
        self.help_menu = tk.Menu(self.help_mb, tearoff=0, bg=self.nav_bg, fg=self.fg_color, activebackground=self.btn_bg, activeforeground=self.accent_color, font=("Segoe UI", 9), bd=1)
        self.help_mb.config(menu=self.help_menu)
        self.help_menu.add_command(label="About...", command=self.show_about_dialog)
        
        tk.Label(nav_bar, text="Go to Addr(Hex):", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
        self.goto_entry = tk.Entry(nav_bar, width=10, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10))
        self.goto_entry.pack(side=tk.LEFT, padx=3, pady=5)
        self.goto_entry.bind("<Return>", lambda e: self.action_goto_address())
        self.goto_entry.bind("<KP_Enter>", lambda e: self.action_goto_address())
        tk.Button(nav_bar, text="Go", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, activeforeground=self.accent_color, command=self.action_goto_address, pady=0, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)
        
        tk.Label(nav_bar, text=" | Find:", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
        self.search_entry = tk.Entry(nav_bar, width=12, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10))
        self.search_entry.pack(side=tk.LEFT, padx=3, pady=5)
        self.search_entry.bind("<Return>", lambda e: self.action_search())
        self.search_entry.bind("<KP_Enter>", lambda e: self.action_search())
        tk.Button(nav_bar, text="Find", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, activeforeground=self.accent_color, command=self.action_search, pady=0, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        tk.Label(nav_bar, text=" | Padding(Hex):", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)
        self.padding_entry = tk.Entry(nav_bar, width=4, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10, "bold"), justify='center')
        self.padding_entry.pack(side=tk.LEFT, padx=2, pady=5)
        self.padding_entry.insert(0, "00")
        tk.Button(nav_bar, text="Fill Space", bg=self.btn_bg, fg=self.btn_fg, font=("Segoe UI", 8, "bold"), command=self.action_apply_padding, pady=0, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        tk.Label(nav_bar, text=" | Addr Base(Hex):", bg=self.nav_bg, fg=self.fg_color, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.base_entry = tk.Entry(nav_bar, width=10, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10, "bold"))
        self.base_entry.pack(side=tk.LEFT, padx=3, pady=5)
        self.base_entry.insert(0, "0")
        self.base_entry.bind("<Return>", lambda e: self.action_apply_base_address())
        self.base_entry.bind("<KP_Enter>", lambda e: self.action_apply_base_address())
        tk.Button(nav_bar, text="Apply", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.action_apply_base_address, pady=0, relief=tk.FLAT).pack(side=tk.LEFT, padx=2)

        self.file_label = tk.Label(nav_bar, text="File: No File Loaded", bg=self.nav_bg, fg=self.fg_color, font=("Consolas", 10, "bold"), relief=tk.RIDGE, padx=10)
        self.file_label.pack(side=tk.RIGHT, padx=5, pady=5)

        # ==========================================
        # 메인 그리드 캔버스 영역
        # ==========================================
        self.main_container = tk.Frame(self.root, bg=self.bg_color)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.right_container = tk.Frame(self.main_container, bg=self.bg_color)
        self.right_container.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sb_canvas = tk.Canvas(self.right_container, width=24, bg="#111214", bd=0, highlightthickness=0)
        self.sb_canvas.pack(side=tk.LEFT, fill=tk.Y)

        self.preset_panel = tk.Frame(self.right_container, bg=self.panel_bg, width=280, bd=1, relief=tk.SOLID, highlightbackground=self.grid_line)
        self.preset_panel.pack_propagate(False)
        
        # Panel Tab Header (Equal width tabs)
        panel_tab_frame = tk.Frame(self.preset_panel, bg=self.btn_bg)
        panel_tab_frame.pack(fill=tk.X)
        panel_tab_frame.columnconfigure(0, weight=1, uniform="tab_btn")
        panel_tab_frame.columnconfigure(1, weight=1, uniform="tab_btn")

        self.tab_preset_btn = tk.Button(panel_tab_frame, text="📌 Presets", bg=self.panel_bg, fg=self.accent_color, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, command=self.show_preset_tab)
        self.tab_preset_btn.grid(row=0, column=0, sticky="nsew", ipady=6)
        self.tab_comment_btn = tk.Button(panel_tab_frame, text="💬 Comments", bg=self.btn_bg, fg=self.fg_color, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, command=self.show_comment_tab)
        self.tab_comment_btn.grid(row=0, column=1, sticky="nsew", ipady=6)

        # 1. Presets View
        self.preset_view = tk.Frame(self.preset_panel, bg=self.panel_bg)
        self.preset_view.pack(fill=tk.BOTH, expand=True)

        form_frame = tk.Frame(self.preset_view, bg=self.panel_bg, pady=5, padx=10)
        form_frame.pack(fill=tk.X)
        tk.Label(form_frame, text="Name:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.preset_name_entry = tk.Entry(form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Segoe UI", 9))
        self.preset_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        tk.Label(form_frame, text="Addr:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.preset_addr_entry = tk.Entry(form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 9))
        self.preset_addr_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        tk.Button(form_frame, text="Add Preset", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.accent_color, command=self.add_preset, relief=tk.FLAT).grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        form_frame.columnconfigure(1, weight=1)
        
        list_frame = tk.Frame(self.preset_view, bg=self.panel_bg, padx=10, pady=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.preset_listbox = tk.Listbox(list_frame, bg=self.entry_bg, fg=self.entry_fg, selectbackground=self.selection_bg, selectforeground=self.selection_fg, font=("Consolas", 9), bd=0, highlightthickness=1, highlightcolor=self.btn_bg)
        self.preset_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preset_listbox.bind("<Double-Button-1>", self.goto_preset)
        list_scroll = ttk.Scrollbar(list_frame, command=self.preset_listbox.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preset_listbox.config(yscrollcommand=list_scroll.set)
        
        btn_frame = tk.Frame(self.preset_view, bg=self.panel_bg, pady=8, padx=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Delete Selected", bg="#B91C1C", fg="white", activebackground="#991B1B", command=self.delete_preset, relief=tk.FLAT).pack(fill=tk.X, pady=2)
        
        io_frame = tk.Frame(btn_frame, bg=self.panel_bg)
        io_frame.pack(fill=tk.X, pady=2)
        tk.Button(io_frame, text="Export Presets", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.export_presets, relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(io_frame, text="Import Presets", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.import_presets, relief=tk.FLAT).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))
        
        # 2. Comments View
        self.comment_view = tk.Frame(self.preset_panel, bg=self.panel_bg)

        c_form_frame = tk.Frame(self.comment_view, bg=self.panel_bg, pady=5, padx=10)
        c_form_frame.pack(fill=tk.X)
        tk.Label(c_form_frame, text="Comment:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.comment_text_entry = tk.Entry(c_form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Segoe UI", 9))
        self.comment_text_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        tk.Label(c_form_frame, text="Addr:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.comment_addr_entry = tk.Entry(c_form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 9))
        self.comment_addr_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        tk.Button(c_form_frame, text="Add Comment", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.accent_color, command=self.add_comment, relief=tk.FLAT).grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        c_form_frame.columnconfigure(1, weight=1)
        
        c_list_frame = tk.Frame(self.comment_view, bg=self.panel_bg, padx=10, pady=5)
        c_list_frame.pack(fill=tk.BOTH, expand=True)
        self.comment_listbox = tk.Listbox(c_list_frame, bg=self.entry_bg, fg=self.entry_fg, selectbackground=self.selection_bg, selectforeground=self.selection_fg, font=("Consolas", 9), bd=0, highlightthickness=1, highlightcolor=self.btn_bg)
        self.comment_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.comment_listbox.bind("<Double-Button-1>", self.goto_comment)
        c_list_scroll = ttk.Scrollbar(c_list_frame, command=self.comment_listbox.yview)
        c_list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.comment_listbox.config(yscrollcommand=c_list_scroll.set)
        
        c_btn_frame = tk.Frame(self.comment_view, bg=self.panel_bg, pady=8, padx=10)
        c_btn_frame.pack(fill=tk.X)
        tk.Button(c_btn_frame, text="Delete Selected", bg="#B91C1C", fg="white", activebackground="#991B1B", command=self.delete_comment, relief=tk.FLAT).pack(fill=tk.X, pady=2)
        tk.Button(c_btn_frame, text="Clear All Comments", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.clear_comments, relief=tk.FLAT).pack(fill=tk.X, pady=2)

        self.update_preset_list()
        self.update_comments_list()

        self.canvas = tk.Canvas(self.main_container, bg=self.grid_bg, bd=0, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_cell_click)
        self.canvas.bind("<B1-Motion>", self.on_cell_drag)
        self.canvas.bind("<Double-Button-1>", self.on_cell_double_click)
        self.canvas.bind("<Return>", self.on_canvas_enter)
        self.canvas.bind("<KP_Enter>", self.on_canvas_enter)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind("<Up>", self.handle_arrow_key)
        self.canvas.bind("<Down>", self.handle_arrow_key)
        self.canvas.bind("<Left>", self.handle_arrow_key)
        self.canvas.bind("<Right>", self.handle_arrow_key)
        self.canvas.bind("<Shift-Up>", self.handle_arrow_key)
        self.canvas.bind("<Shift-Down>", self.handle_arrow_key)
        self.canvas.bind("<Shift-Left>", self.handle_arrow_key)
        self.canvas.bind("<Shift-Right>", self.handle_arrow_key)
        
        self.sb_canvas.bind("<Button-1>", self.on_sb_click)
        self.sb_canvas.bind("<B1-Motion>", self.on_sb_drag)
        self.sb_canvas.bind("<ButtonRelease-1>", self.on_sb_release)
        self.sb_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        
        self.root.bind("<Prior>", self.action_page_up)     
        self.root.bind("<Next>", self.action_page_down)    
        self.root.bind("<Control-c>", self.action_copy)
        self.root.bind("<Control-C>", self.action_copy)
        self.root.bind("<Control-v>", self.action_paste)
        self.root.bind("<Control-V>", self.action_paste)
        self.root.bind("<Control-z>", self.action_undo)
        self.root.bind("<Control-Z>", self.action_undo)
        self.root.bind("<Delete>", self.action_delete_data)

        # ==========================================
        # 하단 통합 바
        # ==========================================
        bottom_bar = tk.Frame(self.root, bg=self.nav_bg, height=30)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready. Meta Hex Editor initialized.")
        status_lbl = tk.Label(bottom_bar, textvariable=self.status_var, bg=self.nav_bg, fg=self.accent_color, anchor="w", font=("Segoe UI", 9))
        
        unit_toggle_btn = tk.Button(bottom_bar, text="[ Dec / Hex ]", bg=self.btn_bg, fg=self.accent_color, activebackground=self.btn_active_bg, font=("Consolas", 8, "bold"), relief=tk.FLAT, command=self.toggle_size_display_unit, padx=4, pady=0)
        unit_toggle_btn.pack(side=tk.RIGHT, padx=5)

        self.size_var = tk.StringVar()
        self.size_var.set("File Size: 0 Bytes | Valid Data: 0 Bytes")
        size_lbl = tk.Label(bottom_bar, textvariable=self.size_var, bg=self.nav_bg, fg=self.fg_color, font=("Consolas", 9, "bold"), padx=5)
        size_lbl.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(bottom_bar, text="|", bg=self.nav_bg, fg=self.btn_bg).pack(side=tk.RIGHT, padx=3)

        self.cursor_var = tk.StringVar(value="Addr: -")
        self.cursor_lbl = tk.Label(bottom_bar, textvariable=self.cursor_var, bg=self.nav_bg, fg=self.accent_color, font=("Consolas", 9, "bold"), padx=5)
        self.cursor_lbl.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(bottom_bar, text="|", bg=self.nav_bg, fg=self.btn_bg).pack(side=tk.RIGHT, padx=3)

        status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

    def toggle_size_display_unit(self):
        self.display_in_hex_unit = not self.display_in_hex_unit
        self.update_file_size_label()
        self.status_var.set(f"Size Unit Switched to {'Hexadecimal' if self.display_in_hex_unit else 'Decimal'}.")

    def clear_memory(self):
        self.memory = {}
        self.selected_cells.clear()
        self.drag_start = None
        self.cursor_pos = None
        self.undo_stack.clear() 
        self.row_count = 0
        self.top_visible_row = 0
        self.current_file_path = ""
        self.current_file_name = "Untitled"
        self.is_modified = False
        self.address_base_set = 0x0
        self.physical_file_size = 0
        self._bounds_dirty = True
        self._cached_search_data = None
        if hasattr(self, '_sb_track_id') and self._sb_track_id:
            self.sb_canvas.delete("all")
            self._sb_track_id = None
            self._sb_thumb_id = None
        self.base_entry.delete(0, tk.END)
        self.base_entry.insert(0, "0")
        self.file_label.config(text="File: No File Loaded")
        if hasattr(self, 'cursor_var'):
            self.cursor_var.set("Addr: -")
        self.update_file_size_label()
        self.redraw_grid()

    def _update_memory_bounds(self):
        if not self.memory:
            self.min_address = 0
            self.max_address = 0
            self.row_count = 0
            self._cached_min_key = 0
            self._cached_max_key = 0
            self._bounds_dirty = False
            self._cached_search_data = None
            return
        
        min_k = min(self.memory.keys())
        max_k = max(self.memory.keys())
        self._cached_min_key = min_k
        self._cached_max_key = max_k
        self.min_address = (min_k // 16) * 16
        self.max_address = ((max_k // 16) + 1) * 16
        self.row_count = (self.max_address - self.min_address) // 16
        self._bounds_dirty = False
        self._cached_search_data = None

    def _ensure_memory_bounds(self):
        if getattr(self, '_bounds_dirty', True):
            self._update_memory_bounds()

    def _get_searchable_bytes(self):
        if not self.memory:
            return None, None
        if getattr(self, '_cached_search_data', None) is not None:
            return self._cached_search_data
            
        self._ensure_memory_bounds()
        min_k = self._cached_min_key
        max_k = self._cached_max_key
        span = max_k - min_k + 1
        
        if span <= 64 * 1024 * 1024:
            buf = bytearray(span)
            mem = self.memory
            for addr, val in mem.items():
                buf[addr - min_k] = val
            self._cached_search_data = (bytes(buf), min_k)
            return self._cached_search_data
        else:
            sorted_keys = sorted(self.memory.keys())
            buf = bytes(self.memory[k] for k in sorted_keys)
            self._cached_search_data = (buf, sorted_keys)
            return self._cached_search_data

    def update_file_size_label(self):
        if not self.memory:
            self.size_var.set("File Size: 0 Bytes | Valid Data: 0 Bytes")
            self.update_window_title()
            return
        self._ensure_memory_bounds()
        valid_bytes = len(self.memory)
        memory_span = self._cached_max_key - self._cached_min_key + 1
        effective_file_size = max(self.physical_file_size, memory_span)
        if self.display_in_hex_unit:
            fs_str = f"0x{effective_file_size:X}"
            vd_str = f"0x{valid_bytes:X}"
        else:
            fs_str = f"{effective_file_size:,}"
            vd_str = f"{valid_bytes:,}"
        self.size_var.set(f"File Size: {fs_str} Bytes | Valid Data: {vd_str} Bytes")
        self.update_window_title()

    def update_window_title(self):
        modified_str = " *" if self.is_modified else ""
        if self.current_file_path:
            self.root.title(f"Meta Hex Editor v1.4 - [{self.current_file_name}]{modified_str}")
        else:
            self.root.title(f"Meta Hex Editor v1.4{modified_str}")

    def save_to_undo_stack(self):
        snapshot = copy.deepcopy(self.memory)
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_undo_depth:
            self.undo_stack.pop(0)

    def action_undo(self, event=None):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo.")
            return
        self.memory = self.undo_stack.pop()
        self.is_modified = True
        self._bounds_dirty = True
        self.update_file_size_label()
        self.redraw_grid()
        self.status_var.set("Undo performed successfully.")

    def action_apply_base_address(self):
        raw_val = self.base_entry.get().strip().replace("0x", "").replace("0X", "")
        if not raw_val:
            val_to_set = 0x0
        else:
            try:
                val_to_set = int(raw_val, 16)
            except ValueError:
                messagebox.showerror("Error", "Invalid Hex address value.", parent=self.root)
                return
                
        confirm = messagebox.askyesno("Confirm Address Base", f"주소 시작 오프셋 기준값(Base)을 0x{val_to_set:X}으로 변경하시겠습니까?", parent=self.root)
        if not confirm:
            return
            
        self.address_base_set = val_to_set
        self.status_var.set(f"Absolute Address Base Configured: 0x{self.address_base_set:X}")
        self.redraw_grid()

    def action_apply_padding(self):
        if not self.memory:
            messagebox.showwarning("Warning", "No data to pad.", parent=self.root)
            return
        raw_pad = self.padding_entry.get().strip().replace("0x", "").replace("0X", "")
        try:
            pad_byte = int(raw_pad, 16)
            if not (0 <= pad_byte <= 255): raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Padding must be a 1-byte Hex value (00~FF).", parent=self.root)
            return
            
        confirm = messagebox.askyesno("Confirm Padding", f"비어있는 데이터 영역을 0x{pad_byte:02X} 값으로 채우시겠습니까?", parent=self.root)
        if not confirm:
            return

        self.save_to_undo_stack()
        self._ensure_memory_bounds()
        min_a = self._cached_min_key
        max_a = self._cached_max_key
        
        filled_cnt = 0
        for addr in range(min_a, max_a + 1):
            if addr not in self.memory:
                self.memory[addr] = pad_byte
                filled_cnt += 1
                
        if filled_cnt > 0:
            self.is_modified = True
            self._bounds_dirty = True
            self.update_file_size_label()
            self.redraw_grid()
            self.status_var.set(f"Padding complete. Filled {filled_cnt} byte(s) with 0x{pad_byte:02X}.")
            messagebox.showinfo("Success", f"비어있던 {filled_cnt}바이트 영역을 0x{pad_byte:02X} 값으로 채웠습니다.", parent=self.root)
        else:
            self.status_var.set("No empty gaps found to pad.")

    def action_delete_data(self, event=None):
        if not self.selected_cells or not self.memory:
            return
        self.save_to_undo_stack()
        deleted_count = 0
        for r_idx, c_idx in self.selected_cells:
            addr = self.get_addr_from_coords(r_idx, c_idx)
            if addr in self.memory:
                del self.memory[addr]
                deleted_count += 1
        if deleted_count > 0:
            self.is_modified = True
            self._bounds_dirty = True
            self.update_file_size_label()
            self.redraw_grid(force_coords=True)
            self.status_var.set(f"Deleted {deleted_count} byte(s). Data cleared to unmapped state.")

    def lazy_create_grid(self, needed_rows):
        if not hasattr(self, 'grid_header_rect'):
            self.grid_header_rect = self.canvas.create_rectangle(0, 0, self.addr_width + (self.cell_width * 16), self.header_height, fill=self.bg_color, outline=self.grid_line)
            self.grid_header_addr_text = self.canvas.create_text(self.addr_width // 2, self.header_height // 2, text="Address", fill=self.accent_color, font=("Consolas", 10, "bold"))
            self.grid_header_col_texts = []
            for col in range(16):
                x = self.addr_width + (col * self.cell_width)
                t_id = self.canvas.create_text(x + self.cell_width // 2, self.header_height // 2, text=f"{col:02X}", fill=self.fg_color, font=("Consolas", 11, "bold"))
                self.grid_header_col_texts.append(t_id)
            self.grid_rows = []
            
        current_rows = len(self.grid_rows)
        if needed_rows > current_rows:
            self._coords_need_update = True
            for r_offset in range(current_rows, needed_rows):
                y = self.header_height + (r_offset * self.cell_height)
                addr_rect = self.canvas.create_rectangle(0, y, self.addr_width, y + self.cell_height, fill=self.bg_color, outline=self.grid_line)
                addr_text = self.canvas.create_text(self.addr_width // 2, y + self.cell_height // 2, fill=self.accent_color, font=("Consolas", 10))
                cell_rects = []
                cell_texts = []
                for c_idx in range(16):
                    cx = self.addr_width + (c_idx * self.cell_width)
                    r_id = self.canvas.create_rectangle(cx, y, cx + self.cell_width, y + self.cell_height, fill=self.grid_bg, outline=self.grid_line)
                    t_id = self.canvas.create_text(cx + self.cell_width // 2, y + self.cell_height // 2, font=("Consolas", 11))
                    cell_rects.append(r_id)
                    cell_texts.append(t_id)
                self.grid_rows.append({
                    'addr_rect': addr_rect,
                    'addr_text': addr_text,
                    'cell_rects': cell_rects,
                    'cell_texts': cell_texts
                })

    def redraw_grid(self, force_coords=False):
        if not self.memory:
            self.canvas.delete("all")
            if hasattr(self, 'grid_header_rect'):
                delattr(self, 'grid_header_rect')
                delattr(self, 'grid_rows')
            self.canvas.create_text(200, 50, text="No data loaded. Please use Loading Area.", fill=self.fg_color, font=("Consolas", 11), anchor="w")
            if hasattr(self, '_sb_track_id') and self._sb_track_id:
                self.sb_canvas.delete("all")
                self._sb_track_id = None
                self._sb_thumb_id = None
            self._last_rendered_row_count = 0
            return

        self._ensure_memory_bounds()
        
        canvas_height = self.canvas.winfo_height()
        if canvas_height <= 100: canvas_height = 600
        self.visible_rows_count = max(10, (canvas_height - self.header_height) // self.cell_height + 1)
        
        # Lazy create grid items
        self.lazy_create_grid(self.visible_rows_count + 1)
        
        need_coords = force_coords or getattr(self, '_coords_need_update', False)
        self._coords_need_update = False
        
        # Update header coordinates
        if need_coords:
            self.canvas.coords(self.grid_header_rect, 0, 0, self.addr_width + (self.cell_width * 16), self.header_height)
        self.canvas.itemconfig(self.grid_header_rect, fill=self.bg_color, outline=self.grid_line, state=tk.NORMAL)
        
        if need_coords:
            self.canvas.coords(self.grid_header_addr_text, self.addr_width // 2, self.header_height // 2)
        self.canvas.itemconfig(self.grid_header_addr_text, state=tk.NORMAL)
        
        for col in range(16):
            x = self.addr_width + (col * self.cell_width)
            t_id = self.grid_header_col_texts[col]
            if need_coords:
                self.canvas.coords(t_id, x + self.cell_width // 2, self.header_height // 2)
            self.canvas.itemconfig(t_id, state=tk.NORMAL)
            
        start_row = max(0, self.top_visible_row)
        visible_rows_to_render = min(self.row_count - start_row, self.visible_rows_count)
        
        has_sel = bool(self.selected_cells)
        for r_offset in range(visible_rows_to_render):
            row_data = self.grid_rows[r_offset]
            r_idx = start_row + r_offset
            
            base_addr = self.min_address + (r_idx * 16)
            visual_base_addr = base_addr + self.address_base_set
            y = self.header_height + (r_offset * self.cell_height)
            
            # Show/update address
            if need_coords:
                self.canvas.coords(row_data['addr_rect'], 0, y, self.addr_width, y + self.cell_height)
                self.canvas.itemconfig(row_data['addr_rect'], fill=self.bg_color, outline=self.grid_line, state=tk.NORMAL)
                self.canvas.coords(row_data['addr_text'], self.addr_width // 2, y + self.cell_height // 2)
            self.canvas.itemconfig(row_data['addr_text'], text=f"0x{visual_base_addr:06X}", state=tk.NORMAL)
            
            sel_states = row_data.setdefault('sel_states', [False] * 16)
            
            for c_idx in range(16):
                curr_addr = base_addr + c_idx
                cx = self.addr_width + (c_idx * self.cell_width)
                
                is_selected = ((r_idx, c_idx) in self.selected_cells) if has_sel else False
                rect_id = row_data['cell_rects'][c_idx]
                text_id = row_data['cell_texts'][c_idx]
                
                if need_coords:
                    self.canvas.coords(rect_id, cx, y, cx + self.cell_width, y + self.cell_height)
                    self.canvas.coords(text_id, cx + self.cell_width // 2, y + self.cell_height // 2)
                    fill_color = self.selection_bg if is_selected else self.grid_bg
                    self.canvas.itemconfig(rect_id, fill=fill_color, outline=self.grid_line, state=tk.NORMAL)
                    sel_states[c_idx] = is_selected
                elif is_selected != sel_states[c_idx]:
                    fill_color = self.selection_bg if is_selected else self.grid_bg
                    self.canvas.itemconfig(rect_id, fill=fill_color)
                    sel_states[c_idx] = is_selected
                
                val = self.memory.get(curr_addr, None)
                val_str = HEX_BYTE_LUT[val] if val is not None else "--"
                text_color = self.selection_fg if is_selected else (self.fg_color if val is not None else self.btn_bg)
                self.canvas.itemconfig(text_id, text=val_str, fill=text_color, state=tk.NORMAL)

        # Hide any rows that were previously rendered but are now outside the visible range
        last_rendered = getattr(self, '_last_rendered_row_count', 0)
        if last_rendered > visible_rows_to_render:
            for r_offset in range(visible_rows_to_render, last_rendered):
                if r_offset < len(self.grid_rows):
                    row_data = self.grid_rows[r_offset]
                    self.canvas.itemconfig(row_data['addr_rect'], state=tk.HIDDEN)
                    self.canvas.itemconfig(row_data['addr_text'], state=tk.HIDDEN)
                    for c_idx in range(16):
                        self.canvas.itemconfig(row_data['cell_rects'][c_idx], state=tk.HIDDEN)
                        self.canvas.itemconfig(row_data['cell_texts'][c_idx], state=tk.HIDDEN)
        self._last_rendered_row_count = visible_rows_to_render

        # Redraw scrollbar (Zero-allocation coords update)
        sb_height = self.sb_canvas.winfo_height()
        if sb_height <= 0: sb_height = canvas_height
        
        if not hasattr(self, '_sb_track_id') or self._sb_track_id is None:
            self._sb_track_id = self.sb_canvas.create_rectangle(0, 0, 24, sb_height, fill=self.entry_bg, outline=self.bg_color)
            self._sb_thumb_id = self.sb_canvas.create_rectangle(2, 0, 22, 40, fill=self.btn_bg, outline="", width=1, tags="thumb")
        else:
            self.sb_canvas.coords(self._sb_track_id, 0, 0, 24, sb_height)
            self.sb_canvas.itemconfig(self._sb_track_id, state=tk.NORMAL)

        if self.row_count > 0:
            ratio = min(1.0, self.visible_rows_count / self.row_count)
            thumb_height = int(sb_height * ratio)
            if thumb_height < 40: thumb_height = 40
            track_space = sb_height - thumb_height
            scroll_percent = start_row / (self.row_count - self.visible_rows_count) if self.row_count > self.visible_rows_count else 0
            thumb_y1 = int(track_space * scroll_percent)
            thumb_y2 = thumb_y1 + thumb_height
            self.sb_canvas.coords(self._sb_thumb_id, 2, thumb_y1, 22, thumb_y2)
            self.sb_canvas.itemconfig(self._sb_thumb_id, state=tk.NORMAL)
        else:
            if hasattr(self, '_sb_thumb_id') and self._sb_thumb_id:
                self.sb_canvas.itemconfig(self._sb_thumb_id, state=tk.HIDDEN)

    def on_sb_click(self, event):
        if not self.memory: return
        sb_height = self.sb_canvas.winfo_height()
        if hasattr(self, '_sb_thumb_id') and self._sb_thumb_id:
            thumb_coords = self.sb_canvas.coords(self._sb_thumb_id)
            if thumb_coords and len(thumb_coords) >= 4:
                y1 = thumb_coords[1]
                y2 = thumb_coords[3]
                if y1 <= event.y <= y2:
                    self.sb_dragging = True
                    self.sb_drag_start_y = event.y
                    self.sb_drag_start_row = self.top_visible_row
                    return
        clicked_percent = event.y / sb_height
        self.top_visible_row = int(clicked_percent * self.row_count)
        self.sanitize_visible_row()
        self.redraw_grid()

    def on_sb_drag(self, event):
        if not self.sb_dragging: return
        sb_height = self.sb_canvas.winfo_height()
        delta_y = event.y - self.sb_drag_start_y
        items = self.sb_canvas.find_withtag("thumb")
        if not items: return
        thumb_height = self.sb_canvas.coords(items[0])[3] - self.sb_canvas.coords(items[0])[1]
        track_space = sb_height - thumb_height
        if track_space > 0:
            row_delta = int((delta_y / track_space) * (self.row_count - self.visible_rows_count))
            self.top_visible_row = self.sb_drag_start_row + row_delta
            self.sanitize_visible_row()
            self.redraw_grid()

    def on_sb_release(self, event):
        self.sb_dragging = False

    def on_mouse_wheel(self, event):
        if not self.memory: return
        if event.num == 4:    self.top_visible_row -= 2
        elif event.num == 5:  self.top_visible_row += 2
        else:
            if event.delta > 0: self.top_visible_row -= 2
            else: self.top_visible_row += 2
        self.sanitize_visible_row()
        self.redraw_grid()

    def action_page_up(self, event=None):
        if not self.memory: return
        self.top_visible_row -= max(5, self.visible_rows_count - 2)
        self.sanitize_visible_row()
        self.redraw_grid()

    def action_page_down(self, event=None):
        if not self.memory: return
        self.top_visible_row += max(5, self.visible_rows_count - 2)
        self.sanitize_visible_row()
        self.redraw_grid()

    def sanitize_visible_row(self):
        if self.top_visible_row < 0: self.top_visible_row = 0
        max_possible = self.row_count - 3
        if max_possible < 0: max_possible = 0
        if self.top_visible_row > max_possible: self.top_visible_row = max_possible

    def on_canvas_configure(self, event):
        if not self.memory:
            return
        h = event.height
        if not hasattr(self, "_last_canvas_height") or self._last_canvas_height != h:
            self._last_canvas_height = h
            self._coords_need_update = True
            if hasattr(self, "_resize_after_id") and self._resize_after_id:
                self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = self.root.after(15, self._handle_canvas_resize)

    def _handle_canvas_resize(self):
        self._resize_after_id = None
        self.redraw_grid()

    def handle_arrow_key(self, event):
        if not self.memory:
            return "break"
        
        if not hasattr(self, 'cursor_pos') or self.cursor_pos is None:
            if self.drag_start:
                self.cursor_pos = self.drag_start
            elif self.selected_cells:
                self.cursor_pos = sorted(list(self.selected_cells))[0]
            else:
                self.cursor_pos = (self.top_visible_row, 0)
                
        r, c = self.cursor_pos
        
        if event.keysym == "Up":
            r -= 1
        elif event.keysym == "Down":
            r += 1
        elif event.keysym == "Left":
            c -= 1
            if c < 0:
                c = 15
                r -= 1
        elif event.keysym == "Right":
            c += 1
            if c > 15:
                c = 0
                r += 1
                
        if r < 0:
            r = 0
            c = 0
        elif r >= self.row_count:
            r = self.row_count - 1
            c = 15
            
        self.cursor_pos = (r, c)
        
        shift_pressed = (event.state & 0x0001) != 0
        
        if shift_pressed:
            if not self.drag_start:
                self.drag_start = self.cursor_pos
            r_start, c_start = self.drag_start
            self.selected_cells.clear()
            for row in range(min(r_start, r), max(r_start, r) + 1):
                for col in range(min(c_start, c), max(c_start, c) + 1):
                    self.selected_cells.add((row, col))
        else:
            self.drag_start = self.cursor_pos
            self.selected_cells.clear()
            self.selected_cells.add(self.cursor_pos)
            
        self.ensure_cell_visible(r, c)
        self.redraw_grid()
        self.update_cursor_status()
        return "break"

    def ensure_cell_visible(self, r, c):
        if r < self.top_visible_row:
            self.top_visible_row = r
        elif r >= self.top_visible_row + self.visible_rows_count - 2:
            self.top_visible_row = r - self.visible_rows_count + 3
        self.sanitize_visible_row()

    def on_canvas_enter(self, event=None):
        if not self.memory: return "break"
        if hasattr(self, 'cursor_pos') and self.cursor_pos:
            r, c = self.cursor_pos
        elif self.selected_cells:
            r, c = sorted(list(self.selected_cells))[0]
        else:
            r, c = (0, 0)
        self.start_inline_edit(r, c)
        return "break"

    def on_cell_double_click(self, event):
        coords = self.get_cell_coords(event)
        if not coords: return
        r_idx, c_idx = coords
        self.cursor_pos = coords
        self.drag_start = coords
        self.selected_cells = {coords}
        self.update_cursor_status()
        self.start_inline_edit(r_idx, c_idx)

    def start_inline_edit(self, r_idx, c_idx):
        if not (0 <= r_idx < self.row_count and 0 <= c_idx < 16):
            return
        self.ensure_cell_visible(r_idx, c_idx)
        self.redraw_grid()
        
        addr = self.get_addr_from_coords(r_idx, c_idx)
        cx = self.addr_width + (c_idx * self.cell_width)
        cy = self.header_height + ((r_idx - self.top_visible_row) * self.cell_height)
        
        entry = tk.Entry(self.canvas, width=3, justify='center', font=("Consolas", 11), bg=self.entry_bg, fg=self.entry_fg, insertbackground="white")
        current_val = self.memory.get(addr, 0)
        entry.insert(0, f"{current_val:02X}")
        entry.place(x=cx+2, y=cy+2, width=self.cell_width-4, height=self.cell_height-4)
        entry.focus_set()
        entry.select_range(0, tk.END)
        
        def save_inline_edit(event=None, advance_next=False):
            if not entry.winfo_exists(): return
            try:
                val_str = entry.get().strip()
                if val_str:
                    val = int(val_str, 16)
                    if 0 <= val <= 255:
                        if self.memory.get(addr) != val:
                            self.save_to_undo_stack() 
                            self.memory[addr] = val
                            self.is_modified = True
                            self._bounds_dirty = True
            except ValueError: pass
            entry.destroy()
            
            if advance_next:
                next_addr = addr + 1
                if next_addr not in self.memory:
                    self.save_to_undo_stack()
                    self.memory[next_addr] = 0x00
                    self.is_modified = True
                    self._bounds_dirty = True
                
                self._ensure_memory_bounds()
                
                next_r = (next_addr - self.min_address) // 16
                next_c = (next_addr - self.min_address) % 16
                self.cursor_pos = (next_r, next_c)
                self.drag_start = (next_r, next_c)
                self.selected_cells = {(next_r, next_c)}
                
                self.ensure_cell_visible(next_r, next_c)
                self.update_file_size_label()
                self.redraw_grid(force_coords=True)
                self.root.after(10, lambda: self.start_inline_edit(next_r, next_c))
            else:
                self.update_file_size_label()
                self.redraw_grid(force_coords=True)
                
        entry.bind("<Return>", lambda e: save_inline_edit(advance_next=True))
        entry.bind("<KP_Enter>", lambda e: save_inline_edit(advance_next=True)) 
        entry.bind("<Escape>", lambda e: entry.destroy()) 
        entry.bind("<FocusOut>", lambda e: save_inline_edit(advance_next=False))

    # ==========================================
    # 파일 입출력 파트 (수정 완료)
    # ==========================================
    def load_file_unified(self):
        file_filters = [
            ("All Supported Files (*.bin, *.hex, *.srec, *.s19, *.mot, *.txt)", 
             ("*.bin", "*.BIN", "*.hex", "*.HEX", "*.srec", "*.SREC", "*.s19", "*.S19", "*.mot", "*.MOT", "*.txt", "*.TXT")),
            ("Binary Files (*.bin, *.dat)", ("*.bin", "*.BIN", "*.dat", "*.DAT")),
            ("Intel HEX Files (*.hex)", ("*.hex", "*.HEX")),
            ("Motorola S-Record Files (*.srec, *.s19, *.mot)", ("*.srec", "*.SREC", "*.s19", "*.S19", "*.mot", "*.MOT")),
            ("String HEX Files (*.txt, *.strhex)", ("*.txt", "*.TXT", "*.strhex", "*.STRHEX")),
            ("All Files (*.*)", "*.*")
        ]
        
        path = filedialog.askopenfilename(filetypes=file_filters, parent=self.root)
        if not path: return
        self.execute_load_core(path)

    def execute_load_core(self, path):
        try:
            self.memory = {}
            self.selected_cells.clear()
            self.drag_start = None
            self.cursor_pos = None
            self.undo_stack.clear() 
            self.top_visible_row = 0
            
            self.physical_file_size = os.path.getsize(path)
            
            first_char = ""
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_strip = line.strip()
                        if line_strip:
                            first_char = line_strip[0]
                            break
            except:
                pass
            
            if first_char == ':':
                self.current_format = "intel_hex"
                self.last_file_type = "intel_hex"
                self.load_intel_hex(path)
            elif first_char == 'S':
                self.current_format = "srec"
                self.last_file_type = "srec"
                self.load_motorola_srec(path)
            else:
                ext = os.path.splitext(path)[1].lower()
                if ext in [".txt", ".strhex", ".hex"]:
                    self.current_format = "string_hex"
                    self.last_file_type = "string_hex"
                    self.load_string_hex(path)
                else:
                    self.current_format = "bin"
                    self.last_file_type = "bin"
                    self.load_binary(path)
                    
            self.current_file_path = path
            self.add_recent_file(path)
            self.current_file_name = os.path.basename(path)
            self.is_modified = False 
            self.file_label.config(text=f"File: {self.current_file_name}")
            self.update_file_size_label()
            self.redraw_grid(force_coords=True)
            self.canvas.focus_set()
            if self.memory:
                self.cursor_pos = (0, 0)
                self.selected_cells = {(0, 0)}
                self.update_cursor_status()
            self.status_var.set(f"Loaded ({self.current_format}): {self.current_file_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed:\n{str(e)}", parent=self.root)

    def load_intel_hex(self, path):
        self.memory = {}
        extended_addr = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line.startswith(':'):
                    continue
                try:
                    line_bytes = bytes.fromhex(line[1:])
                except ValueError:
                    continue
                if not line_bytes:
                    continue
                
                # Verify checksum: sum of all bytes modulo 256 should be 0
                if sum(line_bytes) & 0xFF != 0:
                    pass
                
                count = line_bytes[0]
                addr_16 = (line_bytes[1] << 8) | line_bytes[2]
                record_type = line_bytes[3]
                data = line_bytes[4:-1]
                
                if record_type == 0:  # Data Record
                    phys_addr = extended_addr + addr_16
                    for idx, val in enumerate(data):
                        self.memory[phys_addr + idx] = val
                elif record_type == 1:  # EOF Record
                    break
                elif record_type == 2:  # Extended Segment Address
                    if len(data) >= 2:
                        extended_addr = ((data[0] << 8) | data[1]) << 4
                elif record_type == 4:  # Extended Linear Address
                    if len(data) >= 2:
                        extended_addr = ((data[0] << 8) | data[1]) << 16
        self._bounds_dirty = True

    def load_motorola_srec(self, path):
        self.memory = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line.startswith('S') or len(line) < 4:
                    continue
                
                rec_type = line[1]
                try:
                    line_bytes = bytes.fromhex(line[2:])
                except ValueError:
                    continue
                if not line_bytes:
                    continue
                
                count = line_bytes[0]
                if count != len(line_bytes) - 1:
                    continue
                
                # Checksum validation: sum of count + address + data + checksum should be 0xFF
                if sum(line_bytes) & 0xFF != 0xFF:
                    pass
                
                if rec_type == '1':
                    addr_len = 2
                elif rec_type == '2':
                    addr_len = 3
                elif rec_type == '3':
                    addr_len = 4
                else:
                    continue
                
                if len(line_bytes) < 1 + addr_len + 1:
                    continue
                
                addr = 0
                for i in range(addr_len):
                    addr = (addr << 8) | line_bytes[1 + i]
                
                data = line_bytes[1 + addr_len : -1]
                for idx, val in enumerate(data):
                    self.memory[addr + idx] = val
        self._bounds_dirty = True

    def load_string_hex(self, path):
        self.memory = {}
        self.comments = []
        current_offset = 0
        
        c_prefix = self.comment_prefix if self.comment_prefix else "//"
        a_prefix = self.addr_prefix if self.addr_prefix else "@"
        
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                comment_part = None
                # Check configured comment prefix and common comment delimiters
                for cp in [c_prefix, "//", ";", "#"]:
                    if cp in line:
                        idx = line.find(cp)
                        comment_part = line[idx + len(cp):].strip()
                        line = line[:idx]
                        break
                
                line_strip = line.strip()
                
                # Check address prefix
                matched_addr = False
                for ap in [a_prefix, "@"]:
                    if line_strip.startswith(ap):
                        try:
                            current_offset = int(line_strip[len(ap):].strip(), 16)
                            matched_addr = True
                            break
                        except ValueError: pass
                if matched_addr:
                    if comment_part:
                        self.comments.append({"addr": f"0x{current_offset:X}", "text": comment_part})
                    continue
                
                # Read data tokens
                tokens = line_strip.split()
                if tokens:
                    first_token_offset = current_offset
                    for token in tokens:
                        if len(token) % 2 != 0: token = "0" + token
                        for i in range(0, len(token), 2):
                            try:
                                self.memory[current_offset] = int(token[i:i+2], 16)
                            except ValueError: pass
                            current_offset += 1
                    if comment_part:
                        self.comments.append({"addr": f"0x{first_token_offset:X}", "text": comment_part})
                elif comment_part:
                    self.comments.append({"addr": f"0x{current_offset:X}", "text": comment_part})
                    
        self._bounds_dirty = True
        self.update_comments_list()
        if self.comments:
            if not self.is_preset_panel_visible:
                self.toggle_preset_panel()
            self.show_comment_tab()

    def load_binary(self, path):
        with open(path, "rb") as f:
            bindata = f.read()
        self.memory = dict(enumerate(bindata))
        self._bounds_dirty = True
        self._cached_search_data = (bindata, 0)

    def action_quick_save(self):
        if not self.memory:
            messagebox.showwarning("Warning", "No data to save.", parent=self.root)
            return
        if not self.current_file_path:
            self.open_export_dialog()
            return
            
        if self.is_modified:
            ans = messagebox.askyesno("Confirm Save", f"수정사항이 존재합니다.\n기존 파일 [{self.current_file_name}]에 덮어쓰시겠습니까?", parent=self.root)
            if not ans: return
            
        try:
            if self.current_format == "intel_hex":
                self.write_intel_hex_file(self.current_file_path)
            elif self.current_format == "srec":
                self.write_motorola_srec_file(self.current_file_path)
            elif self.current_format == "string_hex":
                self.write_hex_file_physical(self.current_file_path)
            else:
                self.write_bin_file_physical_with_guide(self.current_file_path)
                
            self.is_modified = False
            self.update_window_title()
            self.status_var.set("File overwritten successfully.")
            messagebox.showinfo("Success", "변경사항이 성공적으로 저장되었습니다.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self.root)

    def write_bin_file_physical_with_guide(self, path, include_offset=None):
        self._ensure_memory_bounds()
        min_addr = self._cached_min_key
        max_addr = self._cached_max_key
        
        if include_offset is None:
            include_offset = False
            if min_addr > 0:
                msg = (f"데이터 시작 주소가 0x{min_addr:X} 입니다.\n\n"
                       f"[Yes] : 0번지부터 시작 주소 전까지 빈 공간을 0x00으로 채워 파일 Offset을 유지합니다.\n"
                       f"[No]  : 시작 주소 이전 빈 공간을 제외하고 실제 데이터 영역만 촘촘하게 압축 저장합니다.")
                include_offset = messagebox.askyesno("Offset Option Guide", msg, parent=self.root)
            
        start_loop = 0 if include_offset else min_addr
        size = max_addr - start_loop + 1
        out_bytes = bytearray(size)
        mem = self.memory
        for addr in range(start_loop, max_addr + 1):
            val = mem.get(addr)
            if val:
                out_bytes[addr - start_loop] = val
        
        with open(path, "wb") as f:
            f.write(out_bytes)
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def write_hex_file_physical(self, path, options=None):
        sorted_addresses = sorted(self.memory.keys())
        if not sorted_addresses: return
        
        opts = options or {}
        addr_prefix = opts.get("addr_prefix", self.addr_prefix or "@")
        comment_prefix = opts.get("comment_prefix", self.comment_prefix or "//")
        unit_size = int(opts.get("unit_size", 1))
        bytes_per_line = int(opts.get("bytes_per_line", 16))
        delimiter = opts.get("delimiter", " ")
        byte_order = opts.get("byte_order", "big")
        addr_display = opts.get("addr_display", "discontinuous")
        include_comments = opts.get("include_comments", True)
        
        comment_map = {}
        if include_comments and hasattr(self, 'comments') and self.comments:
            for c in self.comments:
                try:
                    c_addr = int(c["addr"].replace("0x", "").replace("0X", ""), 16)
                    comment_map[c_addr] = c["text"]
                except: pass
        
        with open(path, "w", encoding="utf-8") as f:
            last_written_addr = None
            current_line_tokens = []
            current_line_comments = []
            
            def flush_current_line():
                nonlocal current_line_tokens, current_line_comments
                if not current_line_tokens: return
                line_str = delimiter.join(current_line_tokens)
                if current_line_comments:
                    line_str += f"   {comment_prefix} " + ", ".join(current_line_comments)
                f.write(line_str + "\n")
                current_line_tokens = []
                current_line_comments = []

            i = 0
            while i < len(sorted_addresses):
                addr = sorted_addresses[i]
                is_continuous = (last_written_addr is not None and addr == last_written_addr + 1)
                
                if not is_continuous:
                    flush_current_line()
                    if addr_display in ["discontinuous", "first_only", "every_line"]:
                        if addr_display != "first_only" or last_written_addr is None:
                            f.write(f"{addr_prefix}{addr:04X}\n")
                else:
                    if addr_display == "every_line" and not current_line_tokens:
                        f.write(f"{addr_prefix}{addr:04X}\n")

                unit_bytes = []
                for u in range(unit_size):
                    target_addr = addr + u
                    if target_addr in self.memory:
                        unit_bytes.append(self.memory[target_addr])
                    else:
                        unit_bytes.append(0x00)
                
                for u in range(unit_size):
                    target_addr = addr + u
                    if target_addr in comment_map:
                        current_line_comments.append(comment_map[target_addr])
                
                if byte_order == "little":
                    unit_bytes = unit_bytes[::-1]
                token = "".join(f"{b:02X}" for b in unit_bytes)
                current_line_tokens.append(token)
                
                last_written_addr = addr + unit_size - 1
                
                while i < len(sorted_addresses) and sorted_addresses[i] <= last_written_addr:
                    i += 1
                    
                if len(current_line_tokens) * unit_size >= bytes_per_line:
                    flush_current_line()
                    
            flush_current_line()
        
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def write_intel_hex_file(self, path, line_bytes=16):
        sorted_addrs = sorted(self.memory.keys())
        if not sorted_addrs: return
        
        line_bytes = int(line_bytes)
        with open(path, "w", encoding="utf-8") as f:
            extended_addr = 0
            i = 0
            while i < len(sorted_addrs):
                addr = sorted_addrs[i]
                upper_16 = (addr >> 16) & 0xFFFF
                if upper_16 != (extended_addr >> 16):
                    extended_addr = upper_16 << 16
                    val_high = (upper_16 >> 8) & 0xFF
                    val_low = upper_16 & 0xFF
                    checksum = (0x100 - ((2 + 0 + 0 + 4 + val_high + val_low) & 0xFF)) & 0xFF
                    f.write(f":02000004{val_high:02X}{val_low:02X}{checksum:02X}\n")
                
                chunk = []
                base_addr_16 = addr & 0xFFFF
                for j in range(line_bytes):
                    target_addr = (extended_addr | base_addr_16) + j
                    if target_addr in self.memory and (target_addr >> 16) == (extended_addr >> 16):
                        chunk.append(self.memory[target_addr])
                    else:
                        break
                
                if chunk:
                    count = len(chunk)
                    checksum_sum = count + ((base_addr_16 >> 8) & 0xFF) + (base_addr_16 & 0xFF) + 0 + sum(chunk)
                    checksum = (0x100 - (checksum_sum & 0xFF)) & 0xFF
                    data_str = "".join(f"{b:02X}" for b in chunk)
                    f.write(f":{count:02X}{base_addr_16:04X}00{data_str}{checksum:02X}\n")
                    
                    while i < len(sorted_addrs) and sorted_addrs[i] < (extended_addr | base_addr_16) + count:
                        i += 1
                else:
                    i += 1
            f.write(":00000001FF\n")
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def write_motorola_srec_file(self, path, line_bytes=16, forced_rec_type=None):
        sorted_addrs = sorted(self.memory.keys())
        if not sorted_addrs: return
        
        line_bytes = int(line_bytes)
        max_addr = sorted_addrs[-1]
        
        if forced_rec_type in ['1', '2', '3']:
            rec_type = forced_rec_type
            addr_len = 2 if rec_type == '1' else (3 if rec_type == '2' else 4)
            term_type = '9' if rec_type == '1' else ('8' if rec_type == '2' else '7')
        else:
            if max_addr <= 0xFFFF:
                rec_type = '1'
                addr_len = 2
                term_type = '9'
            elif max_addr <= 0xFFFFFF:
                rec_type = '2'
                addr_len = 3
                term_type = '8'
            else:
                rec_type = '3'
                addr_len = 4
                term_type = '7'
            
        with open(path, "w", encoding="utf-8") as f:
            header_text = "METCODE9"
            header_bytes = header_text.encode('ascii', errors='ignore')
            s0_count = len(header_bytes) + 3
            s0_sum = s0_count + sum(header_bytes)
            s0_checksum = (0xFF - (s0_sum & 0xFF)) & 0xFF
            s0_str = f"S0{s0_count:02X}0000" + "".join(f"{b:02X}" for b in header_bytes) + f"{s0_checksum:02X}\n"
            f.write(s0_str)
            
            i = 0
            record_count = 0
            while i < len(sorted_addrs):
                addr = sorted_addrs[i]
                chunk = []
                for j in range(line_bytes):
                    target_addr = addr + j
                    if target_addr in self.memory:
                        chunk.append(self.memory[target_addr])
                    else:
                        break
                
                if chunk:
                    count = len(chunk) + addr_len + 1
                    addr_bytes = []
                    for b_idx in range(addr_len):
                        addr_bytes.append((addr >> (8 * (addr_len - 1 - b_idx))) & 0xFF)
                    
                    sum_val = count + sum(addr_bytes) + sum(chunk)
                    checksum = (0xFF - (sum_val & 0xFF)) & 0xFF
                    
                    addr_str = "".join(f"{b:02X}" for b in addr_bytes)
                    data_str = "".join(f"{b:02X}" for b in chunk)
                    f.write(f"S{rec_type}{count:02X}{addr_str}{data_str}{checksum:02X}\n")
                    record_count += 1
                    
                    while i < len(sorted_addrs) and sorted_addrs[i] < addr + len(chunk):
                        i += 1
                else:
                    i += 1
            
            if record_count <= 0xFFFF:
                s5_count = 3
                s5_sum = s5_count + ((record_count >> 8) & 0xFF) + (record_count & 0xFF)
                s5_checksum = (0xFF - (s5_sum & 0xFF)) & 0xFF
                f.write(f"S503{record_count:04X}{s5_checksum:02X}\n")
            elif record_count <= 0xFFFFFF:
                s6_count = 4
                s6_sum = s6_count + ((record_count >> 16) & 0xFF) + ((record_count >> 8) & 0xFF) + (record_count & 0xFF)
                s6_checksum = (0xFF - (s6_sum & 0xFF)) & 0xFF
                f.write(f"S604{record_count:06X}{s6_checksum:02X}\n")
                
            term_addr_bytes = [0] * addr_len
            term_count = addr_len + 1
            term_sum = term_count + sum(term_addr_bytes)
            term_checksum = (0xFF - (term_sum & 0xFF)) & 0xFF
            term_addr_str = "00" * addr_len
            f.write(f"S{term_type}{term_count:02X}{term_addr_str}{term_checksum:02X}\n")
            
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def export_to_bin(self):
        self.open_export_dialog(default_format="bin")

    def export_to_intel_hex(self):
        self.open_export_dialog(default_format="intel_hex")

    def export_to_motorola_srec(self):
        self.open_export_dialog(default_format="srec")

    def export_to_string_hex(self):
        self.open_export_dialog(default_format="string_hex")

    def open_format_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Format Settings")
        dialog.geometry("380x240")
        dialog.configure(bg=self.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        w, h = 380, 240
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2)
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        lbl = tk.Label(dialog, text="Format Characters Setting", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 12, "bold"))
        lbl.pack(pady=(15, 10))

        frame = tk.Frame(dialog, bg=self.bg_color, padx=20)
        frame.pack(fill=tk.X)

        tk.Label(frame, text="Address Marker (Default: @):", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=6)
        entry_addr = tk.Entry(frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10), width=10)
        entry_addr.grid(row=0, column=1, sticky="w", padx=5, pady=6)
        entry_addr.insert(0, self.addr_prefix)

        tk.Label(frame, text="Comment Marker (Default: //):", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=6)
        entry_comment = tk.Entry(frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10), width=10)
        entry_comment.grid(row=1, column=1, sticky="w", padx=5, pady=6)
        entry_comment.insert(0, self.comment_prefix)

        def save_format_settings():
            ap = entry_addr.get().strip()
            cp = entry_comment.get().strip()
            if not ap: ap = "@"
            if not cp: cp = "//"
            self.addr_prefix = ap
            self.comment_prefix = cp
            self.update_config_file("addr_prefix", ap)
            self.update_config_file("comment_prefix", cp)
            self.status_var.set(f"Format settings updated: Addr='{ap}', Comment='{cp}'")
            messagebox.showinfo("Saved", "Settings saved successfully.", parent=dialog)
            dialog.destroy()

        btn_box = tk.Frame(dialog, bg=self.bg_color, pady=15)
        btn_box.pack()
        tk.Button(btn_box, text="Save", bg=self.accent_color, fg="white", activebackground=self.btn_active_bg, command=save_format_settings, relief=tk.FLAT, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_box, text="Cancel", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=dialog.destroy, relief=tk.FLAT, width=10).pack(side=tk.LEFT, padx=5)

    def open_export_dialog(self, default_format=None):
        if not self.memory:
            messagebox.showwarning("Warning", "No data to export.", parent=self.root)
            return

        fmt_initial = default_format or self.export_config.get("format", self.last_file_type)
        if fmt_initial not in ["string_hex", "bin", "intel_hex", "srec"]:
            fmt_initial = "string_hex"

        dialog = tk.Toplevel(self.root)
        dialog.title("Export Settings")
        dialog.geometry("620x660")
        dialog.configure(bg=self.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        w, h = 620, 660
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2)
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        title_lbl = tk.Label(dialog, text="Export File Configuration", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 13, "bold"))
        title_lbl.pack(pady=(12, 8))

        # Top Frame: Format Selection
        fmt_frame = tk.LabelFrame(dialog, text=" Export Format ", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        fmt_frame.pack(fill=tk.X, padx=15, pady=5)

        fmt_options = [
            ("String HEX (*.txt, *.hex, *.strhex)", "string_hex"),
            ("Binary File (*.bin)", "bin"),
            ("Intel HEX (*.hex)", "intel_hex"),
            ("Motorola S-Record (*.srec, *.s19, *.mot)", "srec")
        ]
        fmt_labels = [opt[0] for opt in fmt_options]
        fmt_map = {opt[0]: opt[1] for opt in fmt_options}
        fmt_rev_map = {opt[1]: opt[0] for opt in fmt_options}

        selected_fmt_label = tk.StringVar()
        selected_fmt_label.set(fmt_rev_map.get(fmt_initial, fmt_labels[0]))

        fmt_combo = ttk.Combobox(fmt_frame, textvariable=selected_fmt_label, values=fmt_labels, state="readonly", font=("Segoe UI", 9))
        fmt_combo.pack(fill=tk.X, padx=5, pady=2)

        # Options Container
        opt_container = tk.LabelFrame(dialog, text=" Format Options ", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        opt_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # Subframe: String HEX
        str_frame = tk.Frame(opt_container, bg=self.bg_color)
        
        # Unit Size
        tk.Label(str_frame, text="Unit Size:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=3)
        unit_var = tk.StringVar(value=str(self.export_config.get("unit_size", 1)) + " Byte")
        unit_combo = ttk.Combobox(str_frame, textvariable=unit_var, values=["1 Byte", "2 Bytes", "4 Bytes"], state="readonly", width=12)
        unit_combo.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        # Endianness
        tk.Label(str_frame, text="Byte Order:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        endian_var = tk.StringVar(value="Little Endian" if self.export_config.get("byte_order") == "little" else "Big Endian")
        endian_combo = ttk.Combobox(str_frame, textvariable=endian_var, values=["Big Endian", "Little Endian"], state="readonly", width=12)
        endian_combo.grid(row=0, column=3, sticky="w", padx=5, pady=3)

        # Bytes per Line
        tk.Label(str_frame, text="Bytes / Line:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=3)
        bpl_var = tk.StringVar(value=str(self.export_config.get("bytes_per_line", 16)))
        bpl_combo = ttk.Combobox(str_frame, textvariable=bpl_var, values=["1", "2", "4", "8", "16", "32"], state="readonly", width=12)
        bpl_combo.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        # Delimiter
        tk.Label(str_frame, text="Delimiter:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        delim_display_map = {" ": "Space (' ')", "\t": "Tab ('\\t')", ", ": "Comma (', ')", "": "None ('')"}
        saved_delim = self.export_config.get("delimiter", " ")
        delim_var = tk.StringVar(value=delim_display_map.get(saved_delim, "Space (' ')"))
        delim_combo = ttk.Combobox(str_frame, textvariable=delim_var, values=["Space (' ')", "Tab ('\\t')", "Comma (', ')", "None ('')"], state="readonly", width=12)
        delim_combo.grid(row=1, column=3, sticky="w", padx=5, pady=3)

        # Address Marker
        tk.Label(str_frame, text="Addr Prefix:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=3)
        addr_prefix_entry = tk.Entry(str_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10), width=14)
        addr_prefix_entry.grid(row=2, column=1, sticky="w", padx=5, pady=3)
        addr_prefix_entry.insert(0, self.addr_prefix)

        # Comment Marker
        tk.Label(str_frame, text="Comment Prefix:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=2, column=2, sticky="w", padx=(10, 0), pady=3)
        comment_prefix_entry = tk.Entry(str_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 10), width=14)
        comment_prefix_entry.grid(row=2, column=3, sticky="w", padx=5, pady=3)
        comment_prefix_entry.insert(0, self.comment_prefix)

        # Address Display Mode
        tk.Label(str_frame, text="Addr Display:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=3)
        addr_disp_var = tk.StringVar(value=self.export_config.get("addr_display_label", "Discontinuous Only"))
        addr_disp_combo = ttk.Combobox(str_frame, textvariable=addr_disp_var, values=["Discontinuous Only", "First Address Only", "Every Line", "None"], state="readonly", width=16)
        addr_disp_combo.grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=3)

        # Include Comments Checkbox
        inc_comments_var = tk.BooleanVar(value=self.export_config.get("include_comments", True))
        inc_comments_cb = tk.Checkbutton(str_frame, text="Include Comments", variable=inc_comments_var, bg=self.bg_color, fg=self.fg_color, selectcolor=self.entry_bg, activebackground=self.bg_color, activeforeground=self.accent_color, font=("Segoe UI", 9))
        inc_comments_cb.grid(row=3, column=3, sticky="w", padx=5, pady=3)

        # Subframe: Binary
        bin_frame = tk.Frame(opt_container, bg=self.bg_color)
        bin_offset_var = tk.StringVar(value=self.export_config.get("bin_offset", "compact"))
        tk.Label(bin_frame, text="Start Address & Space Handling:", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5, 3))
        tk.Radiobutton(bin_frame, text="Compact: Save only data range (starts from min valid address)", variable=bin_offset_var, value="compact", bg=self.bg_color, fg=self.fg_color, selectcolor=self.entry_bg, activebackground=self.bg_color, font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=3)
        tk.Radiobutton(bin_frame, text="Offset Fill: Pad with 0x00 from 0x00 to data start address", variable=bin_offset_var, value="fill", bg=self.bg_color, fg=self.fg_color, selectcolor=self.entry_bg, activebackground=self.bg_color, font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=3)

        # Subframe: Intel HEX
        hex_frame = tk.Frame(opt_container, bg=self.bg_color)
        tk.Label(hex_frame, text="Record Length:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5, pady=5)
        hex_bpl_var = tk.StringVar(value=str(self.export_config.get("hex_line_bytes", 16)) + " Bytes")
        hex_bpl_combo = ttk.Combobox(hex_frame, textvariable=hex_bpl_var, values=["16 Bytes", "32 Bytes"], state="readonly", width=12)
        hex_bpl_combo.pack(side=tk.LEFT, padx=5, pady=5)

        # Subframe: Motorola S-Record
        srec_frame = tk.Frame(opt_container, bg=self.bg_color)
        tk.Label(srec_frame, text="Record Type:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        srec_type_var = tk.StringVar(value=self.export_config.get("srec_rec_type", "Auto"))
        srec_type_combo = ttk.Combobox(srec_frame, textvariable=srec_type_var, values=["Auto", "S1 (16-bit)", "S2 (24-bit)", "S3 (32-bit)"], state="readonly", width=14)
        srec_type_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        tk.Label(srec_frame, text="Bytes / Line:", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(15, 5), pady=5)
        srec_bpl_var = tk.StringVar(value=str(self.export_config.get("srec_line_bytes", 16)) + " Bytes")
        srec_bpl_combo = ttk.Combobox(srec_frame, textvariable=srec_bpl_var, values=["16 Bytes", "32 Bytes"], state="readonly", width=12)
        srec_bpl_combo.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        # Preview Frame
        prev_frame = tk.LabelFrame(dialog, text=" Live Preview ", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        prev_frame.pack(fill=tk.X, padx=15, pady=5)

        prev_text = tk.Text(prev_frame, height=6, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 9), bd=0, relief=tk.FLAT)
        prev_text.pack(fill=tk.BOTH, expand=True)

        def switch_format_frame(*args):
            str_frame.pack_forget()
            bin_frame.pack_forget()
            hex_frame.pack_forget()
            srec_frame.pack_forget()
            
            curr_fmt = fmt_map.get(selected_fmt_label.get(), "string_hex")
            if curr_fmt == "string_hex":
                str_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            elif curr_fmt == "bin":
                bin_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            elif curr_fmt == "intel_hex":
                hex_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            elif curr_fmt == "srec":
                srec_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            update_preview()

        fmt_combo.bind("<<ComboboxSelected>>", switch_format_frame)

        def get_current_options():
            curr_fmt = fmt_map.get(selected_fmt_label.get(), "string_hex")
            u_sz = int(unit_var.get().split()[0]) if "Byte" in unit_var.get() else 1
            bo = "little" if "Little" in endian_var.get() else "big"
            try: bpl = int(bpl_var.get().strip())
            except: bpl = 16
            
            delim_map = {"Space (' ')": " ", "Tab ('\\t')": "\t", "Comma (', ')": ", ", "None ('')": ""}
            dl = delim_map.get(delim_var.get(), " ")
            
            ap = addr_prefix_entry.get().strip() or "@"
            cp = comment_prefix_entry.get().strip() or "//"
            
            disp_map = {"Discontinuous Only": "discontinuous", "First Address Only": "first_only", "Every Line": "every_line", "None": "none"}
            ad = disp_map.get(addr_disp_var.get(), "discontinuous")
            
            inc_c = inc_comments_var.get()
            
            h_bpl = 32 if "32" in hex_bpl_var.get() else 16
            s_bpl = 32 if "32" in srec_bpl_var.get() else 16
            
            s_rec = None
            if "S1" in srec_type_var.get(): s_rec = "1"
            elif "S2" in srec_type_var.get(): s_rec = "2"
            elif "S3" in srec_type_var.get(): s_rec = "3"
            
            return {
                "format": curr_fmt,
                "unit_size": u_sz,
                "byte_order": bo,
                "bytes_per_line": bpl,
                "delimiter": dl,
                "addr_prefix": ap,
                "comment_prefix": cp,
                "addr_display": ad,
                "addr_display_label": addr_disp_var.get(),
                "include_comments": inc_c,
                "bin_offset": bin_offset_var.get(),
                "hex_line_bytes": h_bpl,
                "srec_line_bytes": s_bpl,
                "srec_rec_type": srec_type_var.get(),
                "forced_rec_type": s_rec
            }

        def update_preview(*args):
            opts = get_current_options()
            curr_fmt = opts["format"]
            prev_text.delete("1.0", tk.END)
            
            if not self.memory:
                prev_text.insert(tk.END, "(No memory data to preview)")
                return
                
            self._ensure_memory_bounds()
            min_a = self._cached_min_key
            max_a = self._cached_max_key
            
            sample_addrs = []
            cur = min_a
            while len(sample_addrs) < 32 and cur <= max_a:
                if cur in self.memory:
                    sample_addrs.append(cur)
                cur += 1
            if not sample_addrs:
                sample_addrs = sorted(self.memory.keys())[:32]
            
            if curr_fmt == "string_hex":
                preview_lines = []
                u_sz = opts["unit_size"]
                bpl = opts["bytes_per_line"]
                dl = opts["delimiter"]
                ap = opts["addr_prefix"]
                cp = opts["comment_prefix"]
                ad = opts["addr_display"]
                bo = opts["byte_order"]
                inc_c = opts["include_comments"]
                
                c_map = {}
                if inc_c and hasattr(self, 'comments') and self.comments:
                    for c in self.comments:
                        try: c_map[int(c["addr"], 16)] = c["text"]
                        except: pass
                
                last_written = None
                tokens = []
                comments_line = []
                
                def flush_prev():
                    nonlocal tokens, comments_line
                    if not tokens: return
                    line_s = dl.join(tokens)
                    if comments_line: line_s += f"   {cp} " + ", ".join(comments_line)
                    preview_lines.append(line_s)
                    tokens = []
                    comments_line = []

                idx = 0
                while idx < len(sample_addrs):
                    a = sample_addrs[idx]
                    is_cont = (last_written is not None and a == last_written + 1)
                    if not is_cont:
                        flush_prev()
                        if ad in ["discontinuous", "first_only", "every_line"]:
                            if ad != "first_only" or last_written is None:
                                preview_lines.append(f"{ap}{a:04X}")
                    else:
                        if ad == "every_line" and not tokens:
                            preview_lines.append(f"{ap}{a:04X}")

                    ub = [self.memory.get(a + u, 0x00) for u in range(u_sz)]
                    for u in range(u_sz):
                        ta = a + u
                        if ta in c_map: comments_line.append(c_map[ta])
                    if bo == "little": ub = ub[::-1]
                    tokens.append("".join(f"{b:02X}" for b in ub))
                    last_written = a + u_sz - 1
                    
                    while idx < len(sample_addrs) and sample_addrs[idx] <= last_written:
                        idx += 1
                    if len(tokens) * u_sz >= bpl:
                        flush_prev()
                flush_prev()
                prev_text.insert(tk.END, "\n".join(preview_lines[:6]))

            elif curr_fmt == "bin":
                prev_text.insert(tk.END, f"Binary Stream Output\nStart Address: 0x{min_a:X}\nEnd Address: 0x{max_a:X}\nTotal Span: {max_a - min_a + 1:,} Bytes\nOffset Mode: {opts['bin_offset']}")
                
            elif curr_fmt == "intel_hex":
                line_b = opts["hex_line_bytes"]
                chunk = [self.memory[a] for a in sample_addrs[:line_b]]
                addr_16 = sample_addrs[0] & 0xFFFF
                count = len(chunk)
                checksum = (0x100 - ((count + (addr_16 >> 8) + (addr_16 & 0xFF) + sum(chunk)) & 0xFF)) & 0xFF
                line = f":{count:02X}{addr_16:04X}00" + "".join(f"{b:02X}" for b in chunk) + f"{checksum:02X}"
                prev_text.insert(tk.END, f":020000040000FA\n{line}\n:00000001FF")
                
            elif curr_fmt == "srec":
                line_b = opts["srec_line_bytes"]
                chunk = [self.memory[a] for a in sample_addrs[:line_b]]
                count = len(chunk) + 3
                addr = sample_addrs[0]
                addr_bytes = [(addr >> 8) & 0xFF, addr & 0xFF]
                sum_val = count + sum(addr_bytes) + sum(chunk)
                checksum = (0xFF - (sum_val & 0xFF)) & 0xFF
                line = f"S1{count:02X}{addr:04X}" + "".join(f"{b:02X}" for b in chunk) + f"{checksum:02X}"
                prev_text.insert(tk.END, f"S00B00004D4554434F44453913\n{line}\nS9030000FC")

        unit_combo.bind("<<ComboboxSelected>>", update_preview)
        endian_combo.bind("<<ComboboxSelected>>", update_preview)
        bpl_combo.bind("<<ComboboxSelected>>", update_preview)
        bpl_combo.bind("<KeyRelease>", update_preview)
        delim_combo.bind("<<ComboboxSelected>>", update_preview)
        addr_prefix_entry.bind("<KeyRelease>", update_preview)
        comment_prefix_entry.bind("<KeyRelease>", update_preview)
        addr_disp_combo.bind("<<ComboboxSelected>>", update_preview)
        inc_comments_cb.config(command=update_preview)
        bin_offset_var.trace_add("write", lambda *a: update_preview())
        hex_bpl_combo.bind("<<ComboboxSelected>>", update_preview)
        srec_type_combo.bind("<<ComboboxSelected>>", update_preview)
        srec_bpl_combo.bind("<<ComboboxSelected>>", update_preview)

        switch_format_frame()

        def do_export():
            opts = get_current_options()
            curr_fmt = opts["format"]
            
            # Save export config
            self.export_config = opts
            self.update_config_file("export_config", opts)
            self.update_config_file("addr_prefix", opts["addr_prefix"])
            self.update_config_file("comment_prefix", opts["comment_prefix"])
            self.addr_prefix = opts["addr_prefix"]
            self.comment_prefix = opts["comment_prefix"]
            
            base_name = os.path.splitext(self.current_file_name)[0]
            if not base_name or base_name == "Untitled": base_name = "export_output"
            
            if curr_fmt == "string_hex":
                ext = ".txt"
                f_types = [("String HEX (*.txt, *.hex, *.strhex)", ("*.txt", "*.hex", "*.strhex")), ("All Files (*.*)", "*.*")]
            elif curr_fmt == "bin":
                ext = ".bin"
                f_types = [("Binary (*.bin)", "*.bin"), ("All Files (*.*)", "*.*")]
            elif curr_fmt == "intel_hex":
                ext = ".hex"
                f_types = [("Intel HEX (*.hex)", "*.hex"), ("All Files (*.*)", "*.*")]
            elif curr_fmt == "srec":
                ext = ".srec"
                f_types = [("Motorola S-Record (*.srec, *.s19, *.mot)", ("*.srec", "*.s19", "*.mot")), ("All Files (*.*)", "*.*")]
            else:
                ext = ".bin"
                f_types = [("All Files (*.*)", "*.*")]

            path = filedialog.asksaveasfilename(
                initialfile=base_name + ext,
                defaultextension=ext,
                filetypes=f_types,
                parent=dialog
            )
            if not path: return

            try:
                if curr_fmt == "string_hex":
                    self.write_hex_file_physical(path, options=opts)
                    self.current_format = "string_hex"
                elif curr_fmt == "bin":
                    include_offset = (opts["bin_offset"] == "fill")
                    self.write_bin_file_physical_with_guide(path, include_offset=include_offset)
                    self.current_format = "bin"
                elif curr_fmt == "intel_hex":
                    self.write_intel_hex_file(path, line_bytes=opts["hex_line_bytes"])
                    self.current_format = "intel_hex"
                elif curr_fmt == "srec":
                    self.write_motorola_srec_file(path, line_bytes=opts["srec_line_bytes"], forced_rec_type=opts["forced_rec_type"])
                    self.current_format = "srec"

                self.last_file_type = self.current_format
                self.current_file_path = path
                self.current_file_name = os.path.basename(path)
                self.file_label.config(text=f"File: {self.current_file_name}")
                self.status_var.set(f"Exported successfully ({self.current_format}): {self.current_file_name}")
                messagebox.showinfo("Success", f"Exported successfully to:\n{path}", parent=self.root)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", str(e), parent=dialog)

        btn_bar = tk.Frame(dialog, bg=self.bg_color, pady=10)
        btn_bar.pack(fill=tk.X, padx=15)
        
        tk.Button(btn_bar, text=" Export... ", bg=self.accent_color, fg="white", font=("Segoe UI", 10, "bold"), activebackground=self.btn_active_bg, command=do_export, relief=tk.FLAT, padx=15, pady=4).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_bar, text=" Cancel ", bg=self.btn_bg, fg=self.btn_fg, font=("Segoe UI", 10), activebackground=self.btn_active_bg, command=dialog.destroy, relief=tk.FLAT, padx=15, pady=4).pack(side=tk.RIGHT, padx=5)

    def get_cell_coords(self, event):
        canvas_x = event.x
        canvas_y = event.y
        if canvas_y < self.header_height or canvas_x < self.addr_width: return None
        r_offset = int((canvas_y - self.header_height) // self.cell_height)
        r_idx = self.top_visible_row + r_offset
        c_idx = int((canvas_x - self.addr_width) // self.cell_width)
        if 0 <= r_idx < self.row_count and 0 <= c_idx < 16: return (r_idx, c_idx)
        return None

    def get_addr_from_coords(self, r_idx, c_idx):
        return self.min_address + (r_idx * 16) + c_idx

    def update_cursor_status(self):
        if not hasattr(self, 'cursor_var'):
            return
        if not self.memory or not hasattr(self, 'cursor_pos') or not self.cursor_pos:
            self.cursor_var.set("Addr: -")
            return
        
        r, c = self.cursor_pos
        raw_addr = self.get_addr_from_coords(r, c)
        visual_addr = raw_addr + self.address_base_set
        
        addr_fmt = f"0x{visual_addr:06X}" if visual_addr <= 0xFFFFFF else f"0x{visual_addr:08X}"
        raw_fmt = f"0x{raw_addr:06X}" if raw_addr <= 0xFFFFFF else f"0x{raw_addr:08X}"
        
        self.cursor_var.set(f"Addr: {addr_fmt}")
        
        val = self.memory.get(raw_addr, None)
        if len(self.selected_cells) > 1:
            sel_addrs = [self.get_addr_from_coords(sr, sc) + self.address_base_set for sr, sc in self.selected_cells]
            min_a, max_a = min(sel_addrs), max(sel_addrs)
            min_fmt = f"0x{min_a:06X}" if min_a <= 0xFFFFFF else f"0x{min_a:08X}"
            max_fmt = f"0x{max_a:06X}" if max_a <= 0xFFFFFF else f"0x{max_a:08X}"
            self.status_var.set(f"Cursor: {addr_fmt} | Selected: {len(self.selected_cells)} Bytes ({min_fmt} ~ {max_fmt})")
        else:
            if val is not None:
                ascii_char = chr(val) if 32 <= val <= 126 else "."
                self.status_var.set(f"Address: {addr_fmt} (Offset: {raw_fmt}) | Value: 0x{val:02X} (Dec: {val}, ASCII: '{ascii_char}')")
            else:
                self.status_var.set(f"Address: {addr_fmt} (Offset: {raw_fmt}) | Value: -- (Unmapped)")

    def on_cell_click(self, event):
        self.canvas.focus_set()
        coords = self.get_cell_coords(event)
        if coords:
            self.selected_cells.clear()
            self.selected_cells.add(coords)
            self.drag_start = coords
            self.cursor_pos = coords
            self.redraw_grid()
            self.update_cursor_status()

    def on_cell_drag(self, event):
        coords = self.get_cell_coords(event)
        if coords and self.drag_start:
            r_start, c_start = self.drag_start
            r_end, c_end = coords
            self.cursor_pos = coords
            self.selected_cells.clear()
            for r in range(min(r_start, r_end), max(r_start, r_end) + 1):
                for c in range(min(c_start, c_end), max(c_start, c_end) + 1):
                    self.selected_cells.add((r, c))
            self.redraw_grid()
            self.update_cursor_status()

    def action_copy(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, tk.Entry):
            return
        if not self.selected_cells: return
        sorted_cells = sorted(list(self.selected_cells))
        min_r, max_r = min(c[0] for c in sorted_cells), max(c[0] for c in sorted_cells)
        min_c, max_c = min(c[1] for c in sorted_cells), max(c[1] for c in sorted_cells)
        lines = []
        for r in range(min_r, max_r + 1):
            row_tokens = []
            for c in range(min_c, max_c + 1):
                if (r, c) in self.selected_cells:
                    addr = self.get_addr_from_coords(r, c)
                    row_tokens.append(f"{self.memory.get(addr, 0x00):02X}")
                else: row_tokens.append("00")
            lines.append(" ".join(row_tokens))
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))

    def action_paste(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, tk.Entry):
            return
        if not self.selected_cells: return
        try: cb_text = self.root.clipboard_get().strip()
        except tk.TclError: return
        
        self.save_to_undo_stack()
        start_cell = sorted(list(self.selected_cells))[0]
        start_r, start_c = start_cell
        curr_addr = self.get_addr_from_coords(start_r, start_c)
        tokens = cb_text.replace(',', ' ').split()
        for token in tokens:
            if len(token) % 2 != 0: token = "0" + token
            for i in range(0, len(token), 2):
                sub_token = token[i:i+2]
                try:
                    val = int(sub_token, 16)
                    if 0 <= val <= 255:
                        if self.memory.get(curr_addr) != val:
                            self.memory[curr_addr] = val
                            self.is_modified = True
                except ValueError: pass
                curr_addr += 1
                
        if self.memory:
            self._bounds_dirty = True
            self._ensure_memory_bounds()
            
            addr_offset = curr_addr - self.min_address
            new_r = addr_offset // 16
            new_c = addr_offset % 16
            self.selected_cells.clear()
            self.selected_cells.add((new_r, new_c))
            self.drag_start = (new_r, new_c)
            self.cursor_pos = (new_r, new_c)
            
            self.ensure_cell_visible(new_r, new_c)

        self.update_file_size_label()
        self.redraw_grid(force_coords=True)
        self.update_cursor_status()

    def action_goto_address(self):
        addr_str = self.goto_entry.get().strip().replace("0x", "").replace("0X", "")
        if not addr_str: return
        try:
            input_addr = int(addr_str, 16)
            target_addr = input_addr - self.address_base_set
            
            if not self.memory: return
            r_idx = (target_addr - self.min_address) // 16
            if 0 <= r_idx < self.row_count:
                self.top_visible_row = r_idx
                coords = (r_idx, target_addr % 16)
                self.selected_cells.clear()
                self.selected_cells.add(coords)
                self.drag_start = coords
                self.cursor_pos = coords
                self.sanitize_visible_row()
                self.redraw_grid()
                self.update_cursor_status()
            else:
                messagebox.showwarning("Nav Error", "Address out of bounds in current map.", parent=self.root)
        except ValueError: messagebox.showerror("Error", "Invalid hex address.", parent=self.root)

    def action_search(self):
        query = self.search_entry.get().strip()
        if not query or not self.memory:
            return
            
        search_data, index_map = self._get_searchable_bytes()
        if not search_data:
            messagebox.showinfo("Search", "Pattern not found.", parent=self.root)
            return

        hit_pos = -1
        # 1. First, check if query can be interpreted as a Hex byte sequence (e.g. "00 04 32", "000432", "AA BB CC")
        clean_hex = query.replace(" ", "").replace("0x", "").replace("0X", "")
        if len(clean_hex) >= 2 and len(clean_hex) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in clean_hex):
            try:
                target_bytes = bytes.fromhex(clean_hex)
                hit_pos = search_data.find(target_bytes)
            except ValueError:
                hit_pos = -1
                
        # 2. If not found or not hex, search as ASCII / UTF-8 text string
        if hit_pos == -1:
            try:
                text_bytes = query.encode("utf-8")
                hit_pos = search_data.find(text_bytes)
            except Exception:
                pass
            if hit_pos == -1:
                try:
                    text_bytes = query.encode("latin-1")
                    hit_pos = search_data.find(text_bytes)
                except Exception:
                    pass

        if hit_pos != -1:
            if isinstance(index_map, int):
                hit_addr = (index_map + hit_pos) + self.address_base_set
            else:
                hit_addr = index_map[hit_pos] + self.address_base_set
                
            self.goto_entry.delete(0, tk.END)
            self.goto_entry.insert(0, f"{hit_addr:X}")
            self.action_goto_address()
            self.status_var.set(f"Search match found at 0x{hit_addr:X}")
        else:
            messagebox.showinfo("Search", "Pattern not found.", parent=self.root)

    # ==========================================
    # Data Verification (Checksum & CRC) Features
    # ==========================================
    def _init_crc_tables(self):
        if hasattr(self, '_crc_tables_initialized'):
            return
        
        # CRC-8 (Poly 0x07)
        self._crc8_table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x07) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
            self._crc8_table.append(crc)
            
        # CRC-16 (Modbus/IBM Poly 0x8005 reflected -> 0xA001)
        self._crc16_table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
            self._crc16_table.append(crc)
            
        # CRC-16-CCITT (Poly 0x1021 unreflected)
        self._crc16_ccitt_table = []
        for i in range(256):
            crc = i << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
            self._crc16_ccitt_table.append(crc)
            
        # CRC-32 (Poly 0x04C11DB7 reflected -> 0xEDB88320)
        self._crc32_table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
            self._crc32_table.append(crc)
            
        self._crc_tables_initialized = True

    def calc_checksum_crc(self, alg, start_addr, end_addr, init_val_str):
        self._init_crc_tables()
        
        size = max(0, end_addr - start_addr + 1)
        data = bytearray(size)
        mem = self.memory
        for addr in range(start_addr, end_addr + 1):
            val = mem.get(addr)
            if val:
                data[addr - start_addr] = val
            
        try:
            init_val = int(init_val_str, 16)
        except ValueError:
            init_val = 0
            
        if alg == "Checksum 8-bit":
            res = (sum(data) + init_val) & 0xFF
            return f"0x{res:02X}", str(res)
        elif alg == "Checksum 16-bit":
            res = (sum(data) + init_val) & 0xFFFF
            return f"0x{res:04X}", str(res)
        elif alg == "CRC-8":
            crc = init_val & 0xFF
            for b in data:
                crc = self._crc8_table[crc ^ b]
            return f"0x{crc:02X}", str(crc)
        elif alg == "CRC-16":
            crc = init_val & 0xFFFF
            for b in data:
                crc = (crc >> 8) ^ self._crc16_table[(crc ^ b) & 0xFF]
            return f"0x{crc:04X}", str(crc)
        elif alg == "CRC-32":
            import binascii
            res = binascii.crc32(data, (init_val ^ 0xFFFFFFFF) & 0xFFFFFFFF) & 0xFFFFFFFF
            return f"0x{res:08X}", str(res)
        elif alg == "CRC-16-CCITT":
            crc = init_val & 0xFFFF
            for b in data:
                crc = ((crc << 8) ^ self._crc16_ccitt_table[((crc >> 8) ^ b) & 0xFF]) & 0xFFFF
            return f"0x{crc:04X}", str(crc)
            
        return "N/A", "N/A"

    def open_verification_dialog(self):
        start_addr = 0
        end_addr = 0
        if self.selected_cells:
            addrs = [self.get_addr_from_coords(r, c) for r, c in self.selected_cells]
            if addrs:
                start_addr = min(addrs)
                end_addr = max(addrs)
        elif self.memory:
            self._ensure_memory_bounds()
            start_addr = self._cached_min_key
            end_addr = self._cached_max_key

        dialog = tk.Toplevel(self.root)
        dialog.title("Data Verification")
        dialog.geometry("400x320")
        dialog.configure(bg=self.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")
        
        lbl_style = {"bg": self.bg_color, "fg": self.fg_color, "font": ("Segoe UI", 9)}
        entry_style = {"bg": self.entry_bg, "fg": self.entry_fg, "insertbackground": "white", "font": ("Consolas", 10)}
        
        frame_range = tk.LabelFrame(dialog, text=" Range (Hex) ", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        frame_range.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(frame_range, text="Start Address:", **lbl_style).grid(row=0, column=0, sticky="w", pady=2)
        entry_start = tk.Entry(frame_range, **entry_style, width=12)
        entry_start.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        entry_start.insert(0, f"0x{start_addr:X}")
        
        tk.Label(frame_range, text="End Address:", **lbl_style).grid(row=1, column=0, sticky="w", pady=2)
        entry_end = tk.Entry(frame_range, **entry_style, width=12)
        entry_end.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        entry_end.insert(0, f"0x{end_addr:X}")
        
        lbl_size = tk.Label(frame_range, text="Size: 0 Bytes", **lbl_style)
        lbl_size.grid(row=0, column=2, rowspan=2, padx=15, sticky="w")
        
        frame_params = tk.LabelFrame(dialog, text=" Parameters ", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        frame_params.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(frame_params, text="Algorithm:", **lbl_style).grid(row=0, column=0, sticky="w", pady=2)
        
        algs = ["Checksum 8-bit", "Checksum 16-bit", "CRC-8", "CRC-16", "CRC-32", "CRC-16-CCITT"]
        alg_var = tk.StringVar(value=algs[4])
        
        opt_alg = ttk.Combobox(frame_params, textvariable=alg_var, values=algs, state="readonly", width=18)
        opt_alg.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        tk.Label(frame_params, text="Initial Value (Hex):", **lbl_style).grid(row=1, column=0, sticky="w", pady=2)
        entry_init = tk.Entry(frame_params, **entry_style, width=12)
        entry_init.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        entry_init.insert(0, "FFFFFFFF")
        
        frame_res = tk.LabelFrame(dialog, text=" Result ", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
        frame_res.pack(fill=tk.X, padx=15, pady=5)
        
        entry_res = tk.Entry(frame_res, bg=self.entry_bg, fg=self.accent_color, font=("Consolas", 11, "bold"), bd=0, readonlybackground=self.entry_bg, width=25)
        entry_res.pack(side=tk.LEFT, padx=5, pady=5)
        
        def copy_result():
            val = entry_res.get()
            if val and " " in val:
                res_str = val.split()[0]
                self.root.clipboard_clear()
                self.root.clipboard_append(res_str)
                self.status_var.set(f"Copied verification result: {res_str}")
        
        btn_copy = tk.Button(frame_res, text="Copy", bg=self.btn_bg, fg=self.fg_color, activebackground=self.accent_color, command=copy_result)
        btn_copy.pack(side=tk.RIGHT, padx=5)
        
        def update_calc(*args):
            try:
                s_str = entry_start.get().strip().lower().replace("0x", "")
                e_str = entry_end.get().strip().lower().replace("0x", "")
                s_val = int(s_str, 16) if s_str else 0
                e_val = int(e_str, 16) if e_str else 0
                
                if s_val < 0: s_val = 0
                if e_val < s_val:
                    lbl_size.config(text="Size: 0 Bytes", fg="#EF4444")
                    entry_res.config(state=tk.NORMAL)
                    entry_res.delete(0, tk.END)
                    entry_res.insert(0, "Invalid range")
                    entry_res.config(state="readonly")
                    return
                
                size = e_val - s_val + 1
                lbl_size.config(text=f"Size: {size:,} Bytes", fg=self.fg_color)
                
                alg = alg_var.get()
                init_str = entry_init.get().strip().lower().replace("0x", "")
                hex_res, dec_res = self.calc_checksum_crc(alg, s_val, e_val, init_str)
                
                entry_res.config(state=tk.NORMAL)
                entry_res.delete(0, tk.END)
                entry_res.insert(0, f"{hex_res} ({dec_res})")
                entry_res.config(state="readonly")
            except ValueError:
                entry_res.config(state=tk.NORMAL)
                entry_res.delete(0, tk.END)
                entry_res.insert(0, "Invalid values")
                entry_res.config(state="readonly")

        def on_alg_change(event):
            alg = alg_var.get()
            entry_init.delete(0, tk.END)
            if alg in ["Checksum 8-bit", "CRC-8"]:
                entry_init.insert(0, "00")
            elif alg in ["Checksum 16-bit", "CRC-16", "CRC-16-CCITT"]:
                entry_init.insert(0, "0000")
            elif alg == "CRC-32":
                entry_init.insert(0, "FFFFFFFF")
            update_calc()
            
        opt_alg.bind("<<ComboboxSelected>>", on_alg_change)
        entry_start.bind("<KeyRelease>", lambda e: update_calc())
        entry_end.bind("<KeyRelease>", lambda e: update_calc())
        entry_init.bind("<KeyRelease>", lambda e: update_calc())
        
        update_calc()

    def show_about_dialog(self):
        import webbrowser
        dialog = tk.Toplevel(self.root)
        dialog.title("About")
        dialog.geometry("380x240")
        dialog.configure(bg=self.bg_color)
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")
        
        lbl_title = tk.Label(dialog, text="Meta Hex Editor", bg=self.bg_color, fg=self.accent_color, font=("Segoe UI", 14, "bold"))
        lbl_title.pack(pady=(15, 5))
        
        lbl_ver = tk.Label(dialog, text="Version 1.4", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 10))
        lbl_ver.pack()
        
        lbl_dev = tk.Label(dialog, text="Developer: Metacode9", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 10))
        lbl_dev.pack(pady=(10, 2))
        
        link_frame = tk.Frame(dialog, bg=self.bg_color)
        link_frame.pack()
        lbl_web = tk.Label(link_frame, text="Official Website: ", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 10))
        lbl_web.pack(side=tk.LEFT)
        
        lbl_url = tk.Label(link_frame, text="https://tool.metacode9.com/", bg=self.bg_color, fg=self.accent_color, cursor="hand2", font=("Segoe UI", 10, "underline"))
        lbl_url.pack(side=tk.LEFT)
        lbl_url.bind("<Button-1>", lambda e: webbrowser.open("https://tool.metacode9.com/"))
        
        lbl_copy = tk.Label(dialog, text="Copyright (c) 2026 Metacode9. All rights reserved.\nLicensed under the MIT License.", bg=self.bg_color, fg="#8A8F98", font=("Segoe UI", 9), justify="center")
        lbl_copy.pack(pady=(15, 10))
        
        btn_close = tk.Button(dialog, text="OK", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=dialog.destroy, relief=tk.FLAT, width=10)
        btn_close.pack()

    # ==========================================
    # Side Panel (Presets & Comments) Features
    # ==========================================
    def show_preset_tab(self):
        self.current_side_tab = "presets"
        self.tab_preset_btn.config(bg=self.panel_bg, fg=self.accent_color)
        self.tab_comment_btn.config(bg=self.btn_bg, fg=self.fg_color)
        self.comment_view.pack_forget()
        self.preset_view.pack(fill=tk.BOTH, expand=True)
        if self.selected_cells:
            r, c = sorted(list(self.selected_cells))[0]
            addr = self.get_addr_from_coords(r, c)
            self.preset_addr_entry.delete(0, tk.END)
            self.preset_addr_entry.insert(0, f"0x{addr:X}")
        self.preset_name_entry.focus_set()

    def show_comment_tab(self):
        self.current_side_tab = "comments"
        self.tab_comment_btn.config(bg=self.panel_bg, fg=self.accent_color)
        self.tab_preset_btn.config(bg=self.btn_bg, fg=self.fg_color)
        self.preset_view.pack_forget()
        self.comment_view.pack(fill=tk.BOTH, expand=True)
        if self.selected_cells:
            r, c = sorted(list(self.selected_cells))[0]
            addr = self.get_addr_from_coords(r, c)
            self.comment_addr_entry.delete(0, tk.END)
            self.comment_addr_entry.insert(0, f"0x{addr:X}")
        self.comment_text_entry.focus_set()

    def update_preset_list(self):
        self.preset_listbox.delete(0, tk.END)
        for p in self.presets:
            self.preset_listbox.insert(tk.END, f"[{p['addr']}] {p['name']}")

    def update_comments_list(self):
        if hasattr(self, 'comment_listbox'):
            self.comment_listbox.delete(0, tk.END)
            for c in self.comments:
                self.comment_listbox.insert(tk.END, f"[{c['addr']}] {c['text']}")

    def toggle_preset_panel(self):
        if self.is_preset_panel_visible:
            self.preset_panel.pack_forget()
            self.is_preset_panel_visible = False
        else:
            self.preset_panel.pack(side=tk.RIGHT, fill=tk.Y)
            self.is_preset_panel_visible = True
            
            if self.current_side_tab == "comments":
                self.show_comment_tab()
            else:
                self.show_preset_tab()

    def add_preset(self):
        name = self.preset_name_entry.get().strip()
        addr_str = self.preset_addr_entry.get().strip().replace("0x", "").replace("0X", "")
        if not name or not addr_str:
            messagebox.showwarning("Warning", "Please provide both Name and Address.", parent=self.root)
            return
        try:
            addr_val = int(addr_str, 16)
        except ValueError:
            messagebox.showwarning("Warning", "Invalid Address format.", parent=self.root)
            return
            
        self.presets.append({"name": name, "addr": f"0x{addr_val:X}"})
        self.save_presets()
        self.update_preset_list()
        self.preset_name_entry.delete(0, tk.END)
        
        self.status_var.set(f"Preset '{name}' added successfully.")

    def delete_preset(self):
        sel = self.preset_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.presets[idx]
        self.save_presets()
        self.update_preset_list()
        self.status_var.set("Preset deleted.")

    def goto_preset(self, event=None):
        sel = self.preset_listbox.curselection()
        if not sel: return
        idx = sel[0]
        addr_str = self.presets[idx]["addr"].replace("0x", "").replace("0X", "")
        
        self.goto_entry.delete(0, tk.END)
        self.goto_entry.insert(0, addr_str)
        self.action_goto_address()
        self.status_var.set(f"Jumped to preset: {self.presets[idx]['name']}")

    def export_presets(self):
        if not self.presets:
            messagebox.showwarning("Warning", "No presets to export.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files (*.json)", "*.json")],
            initialfile="presets.json",
            parent=self.root
        )
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, indent=4)
            self.status_var.set(f"Presets exported to {os.path.basename(path)}")
            messagebox.showinfo("Success", "Presets exported successfully.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export presets:\n{str(e)}", parent=self.root)

    def import_presets(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON Files (*.json)", "*.json")],
            parent=self.root
        )
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, list):
                raise ValueError("Presets file must contain a JSON list of preset objects.")
            
            valid_presets = []
            for item in loaded:
                if isinstance(item, dict) and "name" in item and "addr" in item:
                    valid_presets.append({"name": str(item["name"]), "addr": str(item["addr"])})
            
            if not valid_presets:
                raise ValueError("No valid presets found in JSON file.")
                
            self.presets.extend(valid_presets)
            self.save_presets()
            self.update_preset_list()
            self.status_var.set(f"Imported {len(valid_presets)} presets.")
            messagebox.showinfo("Success", f"Imported {len(valid_presets)} presets successfully.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import presets:\n{str(e)}", parent=self.root)

    def add_comment(self):
        text = self.comment_text_entry.get().strip()
        addr_str = self.comment_addr_entry.get().strip().replace("0x", "").replace("0X", "")
        if not text or not addr_str:
            messagebox.showwarning("Warning", "Please provide both Comment and Address.", parent=self.root)
            return
        try:
            addr_val = int(addr_str, 16)
        except ValueError:
            messagebox.showwarning("Warning", "Invalid Address format.", parent=self.root)
            return
            
        self.comments.append({"name": text, "addr": f"0x{addr_val:X}", "text": text})
        self.update_comments_list()
        self.comment_text_entry.delete(0, tk.END)
        self.status_var.set(f"Comment '{text}' added.")

    def delete_comment(self):
        sel = self.comment_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.comments[idx]
        self.update_comments_list()
        self.status_var.set("Comment deleted.")

    def clear_comments(self):
        if not self.comments: return
        if messagebox.askyesno("Confirm", "Clear all comments?", parent=self.root):
            self.comments.clear()
            self.update_comments_list()
            self.status_var.set("All comments cleared.")

    def goto_comment(self, event=None):
        sel = self.comment_listbox.curselection()
        if not sel: return
        idx = sel[0]
        c = self.comments[idx]
        addr_str = c["addr"].replace("0x", "").replace("0X", "")
        
        self.goto_entry.delete(0, tk.END)
        self.goto_entry.insert(0, addr_str)
        self.action_goto_address()
        self.status_var.set(f"Jumped to comment: {c.get('text', c.get('name', ''))}")

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = AdvancedHexEditor(root)
    
    if len(sys.argv) > 1:
        file_to_load = sys.argv[1]
        if os.path.exists(file_to_load):
            root.after(100, lambda: app.execute_load_core(file_to_load))
            
    root.mainloop()
