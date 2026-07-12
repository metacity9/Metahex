"""
========================================================================
Project:     Meta Hex Editor
Version:     1.3
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

class AdvancedHexEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Meta Hex Editor v1.3")
        self.root.geometry("1200x780")
        
        # 코어 데이터 구조
        self.memory = {} 
        self.selected_cells = set()  
        self.drag_start = None
        self.cursor_pos = None
        self._coords_need_update = True
        self._last_rendered_row_count = 0
        
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
        self.recent_files = self.load_recent_files()
        self.presets = self.load_presets()
        self.is_preset_panel_visible = False
        
        self.setup_styles()
        self.create_widgets()
        self.clear_memory()


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
        self.style.configure("TCombobox", fieldbackground=self.entry_bg, background=self.btn_bg, foreground=self.entry_fg)

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
        self.file_menu.add_command(label="Export to BIN...", command=self.export_to_bin)
        self.file_menu.add_command(label="Export to Intel HEX...", command=self.export_to_intel_hex)
        self.file_menu.add_command(label="Export to Motorola S-Record...", command=self.export_to_motorola_srec)
        self.file_menu.add_command(label="Export to String HEX...", command=self.export_to_string_hex)
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
        self.tools_menu.add_command(label="Location Presets", command=self.toggle_preset_panel)
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

        self.preset_panel = tk.Frame(self.right_container, bg=self.panel_bg, width=250, bd=1, relief=tk.SOLID, highlightbackground=self.grid_line)
        preset_title = tk.Label(self.preset_panel, text="📌 Location Presets", bg=self.panel_bg, fg=self.accent_color, font=("Segoe UI", 11, "bold"), pady=10)
        preset_title.pack(fill=tk.X)
        form_frame = tk.Frame(self.preset_panel, bg=self.panel_bg, pady=5, padx=10)
        form_frame.pack(fill=tk.X)
        tk.Label(form_frame, text="Name:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.preset_name_entry = tk.Entry(form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Segoe UI", 9))
        self.preset_name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        tk.Label(form_frame, text="Addr:", bg=self.panel_bg, fg="#9BA1A6", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.preset_addr_entry = tk.Entry(form_frame, bg=self.entry_bg, fg=self.entry_fg, insertbackground="white", font=("Consolas", 9))
        self.preset_addr_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        tk.Button(form_frame, text="Add Preset", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.accent_color, command=self.add_preset, relief=tk.FLAT).grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        form_frame.columnconfigure(1, weight=1)
        list_frame = tk.Frame(self.preset_panel, bg=self.panel_bg, padx=10, pady=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.preset_listbox = tk.Listbox(list_frame, bg=self.entry_bg, fg=self.entry_fg, selectbackground=self.selection_bg, selectforeground=self.selection_fg, font=("Consolas", 9), bd=0, highlightthickness=1, highlightcolor=self.btn_bg)
        self.preset_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.preset_listbox.bind("<Double-Button-1>", self.goto_preset)
        list_scroll = ttk.Scrollbar(list_frame, command=self.preset_listbox.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preset_listbox.config(yscrollcommand=list_scroll.set)
        btn_frame = tk.Frame(self.preset_panel, bg=self.panel_bg, pady=10, padx=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Delete Selected", bg="#B91C1C", fg="white", activebackground="#991B1B", command=self.delete_preset, relief=tk.FLAT).pack(fill=tk.X, pady=2)
        
        io_frame = tk.Frame(btn_frame, bg=self.panel_bg)
        io_frame.pack(fill=tk.X, pady=2)
        tk.Button(io_frame, text="Export Presets", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.export_presets, relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Button(io_frame, text="Import Presets", bg=self.btn_bg, fg=self.btn_fg, activebackground=self.btn_active_bg, command=self.import_presets, relief=tk.FLAT).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))
        
        self.update_preset_list()

        self.canvas = tk.Canvas(self.main_container, bg=self.grid_bg, bd=0, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_cell_click)
        self.canvas.bind("<B1-Motion>", self.on_cell_drag)
        self.canvas.bind("<Double-Button-1>", self.on_cell_double_click)
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
        self.status_var.set("Ready. TLi Hex Editor initialized.")
        status_lbl = tk.Label(bottom_bar, textvariable=self.status_var, bg=self.nav_bg, fg=self.accent_color, anchor="w", font=("Segoe UI", 9))
        status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        unit_toggle_btn = tk.Button(bottom_bar, text="[ Dec / Hex ]", bg=self.btn_bg, fg=self.accent_color, activebackground=self.btn_active_bg, font=("Consolas", 8, "bold"), relief=tk.FLAT, command=self.toggle_size_display_unit, padx=4, pady=0)
        unit_toggle_btn.pack(side=tk.RIGHT, padx=5)

        self.size_var = tk.StringVar()
        self.size_var.set("File Size: 0 Bytes | Valid Data: 0 Bytes")
        size_lbl = tk.Label(bottom_bar, textvariable=self.size_var, bg=self.nav_bg, fg=self.fg_color, font=("Consolas", 9, "bold"), padx=5)
        size_lbl.pack(side=tk.RIGHT, fill=tk.Y)

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
        self.base_entry.delete(0, tk.END)
        self.base_entry.insert(0, "0")
        self.file_label.config(text="File: No File Loaded")
        self.update_file_size_label()
        self.redraw_grid()

    def update_file_size_label(self):
        if not self.memory:
            self.size_var.set("File Size: 0 Bytes | Valid Data: 0 Bytes")
            self.update_window_title()
            return
        valid_bytes = len(self.memory)
        if self.display_in_hex_unit:
            fs_str = f"0x{self.physical_file_size:X}"
            vd_str = f"0x{valid_bytes:X}"
        else:
            fs_str = f"{self.physical_file_size:,}"
            vd_str = f"{valid_bytes:,}"
        self.size_var.set(f"File Size: {fs_str} Bytes | Valid Data: {vd_str} Bytes")
        self.update_window_title()

    def update_window_title(self):
        modified_str = " *" if self.is_modified else ""
        if self.current_file_path:
            self.root.title(f"Meta Hex Editor v1.2 - [{self.current_file_name}]{modified_str}")
        else:
            self.root.title(f"Meta Hex Editor v1.2{modified_str}")

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
        min_a = min(self.memory.keys())
        max_a = max(self.memory.keys())
        
        filled_cnt = 0
        for addr in range(min_a, max_a + 1):
            if addr not in self.memory:
                self.memory[addr] = pad_byte
                filled_cnt += 1
                
        if filled_cnt > 0:
            self.is_modified = True
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
            self.update_file_size_label()
            self.redraw_grid()
            self.status_var.set(f"Deleted {deleted_count} byte(s). Data cleared to unmapped state.")

    def lazy_create_grid(self, needed_rows):
        if not hasattr(self, 'grid_header_rect'):
            self.grid_header_rect = self.canvas.create_rectangle(0, 0, 0, 0, fill=self.bg_color, outline=self.grid_line)
            self.grid_header_addr_text = self.canvas.create_text(0, 0, text="Address", fill=self.accent_color, font=("Consolas", 10, "bold"))
            self.grid_header_col_texts = []
            for col in range(16):
                t_id = self.canvas.create_text(0, 0, text=f"{col:02X}", fill=self.fg_color, font=("Consolas", 11, "bold"))
                self.grid_header_col_texts.append(t_id)
            self.grid_rows = []
            
        current_rows = len(self.grid_rows)
        if needed_rows > current_rows:
            self._coords_need_update = True
            for r_offset in range(current_rows, needed_rows):
                addr_rect = self.canvas.create_rectangle(0, 0, 0, 0, fill=self.bg_color, outline=self.grid_line)
                addr_text = self.canvas.create_text(0, 0, fill=self.accent_color, font=("Consolas", 10))
                cell_rects = []
                cell_texts = []
                for c_idx in range(16):
                    r_id = self.canvas.create_rectangle(0, 0, 0, 0, fill=self.grid_bg, outline=self.grid_line)
                    t_id = self.canvas.create_text(0, 0, font=("Consolas", 11))
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
            self.sb_canvas.delete("all")
            self._last_rendered_row_count = 0
            return

        self.min_address = (min(self.memory.keys()) // 16) * 16
        self.max_address = ((max(self.memory.keys()) // 16) + 1) * 16
        self.row_count = (self.max_address - self.min_address) // 16
        
        canvas_height = self.canvas.winfo_height()
        if canvas_height <= 0: canvas_height = 500
        self.visible_rows_count = (canvas_height - self.header_height) // self.cell_height + 1
        
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
            
            if need_coords:
                self.canvas.coords(row_data['addr_text'], self.addr_width // 2, y + self.cell_height // 2)
            self.canvas.itemconfig(row_data['addr_text'], text=f"0x{visual_base_addr:06X}", state=tk.NORMAL)
            
            for c_idx in range(16):
                curr_addr = base_addr + c_idx
                cx = self.addr_width + (c_idx * self.cell_width)
                
                is_selected = (r_idx, c_idx) in self.selected_cells
                fill_color = self.selection_bg if is_selected else self.grid_bg
                text_color = self.selection_fg if is_selected else self.fg_color
                
                val = self.memory.get(curr_addr, None)
                val_str = f"{val:02X}" if val is not None else "--"
                if val is None: text_color = self.btn_bg
                
                rect_id = row_data['cell_rects'][c_idx]
                text_id = row_data['cell_texts'][c_idx]
                
                if need_coords:
                    self.canvas.coords(rect_id, cx, y, cx + self.cell_width, y + self.cell_height)
                self.canvas.itemconfig(rect_id, fill=fill_color, outline=self.grid_line, state=tk.NORMAL)
                
                if need_coords:
                    self.canvas.coords(text_id, cx + self.cell_width // 2, y + self.cell_height // 2)
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

        # Redraw scrollbar
        self.sb_canvas.delete("all")
        sb_height = self.sb_canvas.winfo_height()
        if sb_height <= 0: sb_height = canvas_height
        self.sb_canvas.create_rectangle(0, 0, 24, sb_height, fill=self.entry_bg, outline=self.bg_color)
        
        if self.row_count > 0:
            ratio = min(1.0, self.visible_rows_count / self.row_count)
            thumb_height = int(sb_height * ratio)
            if thumb_height < 40: thumb_height = 40
            track_space = sb_height - thumb_height
            scroll_percent = start_row / (self.row_count - self.visible_rows_count) if self.row_count > self.visible_rows_count else 0
            thumb_y1 = int(track_space * scroll_percent)
            thumb_y2 = thumb_y1 + thumb_height
            self.sb_canvas.create_rectangle(2, thumb_y1, 22, thumb_y2, fill=self.btn_bg, outline="", width=1, tags="thumb")

    def on_sb_click(self, event):
        if not self.memory: return
        sb_height = self.sb_canvas.winfo_height()
        items = self.sb_canvas.find_withtag("thumb")
        if items:
            y1 = self.sb_canvas.coords(items[0])[1]
            y2 = self.sb_canvas.coords(items[0])[3]
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
        return "break"

    def ensure_cell_visible(self, r, c):
        if r < self.top_visible_row:
            self.top_visible_row = r
        elif r >= self.top_visible_row + self.visible_rows_count - 2:
            self.top_visible_row = r - self.visible_rows_count + 3
        self.sanitize_visible_row()

    def on_cell_double_click(self, event):
        coords = self.get_cell_coords(event)
        if not coords: return
        r_idx, c_idx = coords
        self.cursor_pos = coords
        self.drag_start = coords
        addr = self.get_addr_from_coords(r_idx, c_idx)
        cx = self.addr_width + (c_idx * self.cell_width)
        cy = self.header_height + ((r_idx - self.top_visible_row) * self.cell_height)
        
        entry = tk.Entry(self.canvas, width=3, justify='center', font=("Consolas", 11), bg=self.entry_bg, fg=self.entry_fg, insertbackground="white")
        entry.insert(0, f"{self.memory.get(addr, 0):02X}")
        entry.place(x=cx+2, y=cy+2, width=self.cell_width-4, height=self.cell_height-4)
        entry.focus_set()
        entry.select_range(0, tk.END)
        
        def save_inline_edit(event=None):
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
                            self.update_file_size_label()
            except ValueError: pass
            entry.destroy()
            self.redraw_grid()
                
        entry.bind("<Return>", save_inline_edit)
        entry.bind("<KP_Enter>", save_inline_edit) 
        entry.bind("<Escape>", lambda e: entry.destroy()) 
        entry.bind("<FocusOut>", save_inline_edit)

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

    def load_string_hex(self, path):
        self.memory = {}
        current_offset = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "//" in line: line = line.split("//")[0]
                line = line.strip()
                if not line: continue
                if line.startswith("@"):
                    current_offset = int(line.replace("@", "").strip(), 16)
                    continue
                for token in line.split():
                    if len(token) % 2 != 0: token = "0" + token
                    for i in range(0, len(token), 2):
                        self.memory[current_offset] = int(token[i:i+2], 16)
                        current_offset += 1

    def load_binary(self, path):
        self.memory = {}
        with open(path, "rb") as f:
            bindata = f.read()
        for addr, val in enumerate(bindata):
            self.memory[addr] = val

    def action_quick_save(self):
        if not self.memory:
            messagebox.showwarning("Warning", "No data to save.", parent=self.root)
            return
        if not self.current_file_path:
            self.export_to_bin()
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

    def write_bin_file_physical_with_guide(self, path):
        min_addr = min(self.memory.keys())
        max_addr = max(self.memory.keys())
        
        include_offset = False
        if min_addr > 0:
            msg = (f"데이터 시작 주소가 0x{min_addr:X} 입니다.\n\n"
                   f"[Yes] : 0번지부터 시작 주소 전까지 빈 공간을 0x00으로 채워 파일 Offset을 유지합니다.\n"
                   f"[No]  : 시작 주소 이전 빈 공간을 제외하고 실제 데이터 영역만 촘촘하게 압축 저장합니다.")
            include_offset = messagebox.askyesno("Offset Option Guide", msg, parent=self.root)
            
        start_loop = 0 if include_offset else min_addr
        out_bytes = bytearray(self.memory.get(addr, 0x00) for addr in range(start_loop, max_addr + 1))
        
        with open(path, "wb") as f:
            f.write(out_bytes)
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def write_hex_file_physical(self, path):
        sorted_addresses = sorted(self.memory.keys())
        if not sorted_addresses: return
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"// Saved from TLi Hex Editor\n")
            last_written_base = -1
            line_bytes = []
            
            for addr in sorted_addresses:
                base_16 = (addr // 16) * 16
                if base_16 != last_written_base:
                    was_full = (len(line_bytes) == 16)
                    if line_bytes:
                        f.write(" ".join(line_bytes) + "\n")
                        line_bytes = []
                    if last_written_base == -1 or base_16 != (last_written_base + 16) or not was_full:
                        f.write(f"@{base_16:04X}\n") 
                    last_written_base = base_16
                
                expected_idx = base_16 + len(line_bytes)
                while expected_idx < addr:
                    line_bytes.append("00")
                    expected_idx += 1
                line_bytes.append(f"{self.memory[addr]:02X}")
                if len(line_bytes) == 16:
                    f.write(" ".join(line_bytes) + "\n")
                    line_bytes = []
            if line_bytes: f.write(" ".join(line_bytes) + "\n")
        
        self.physical_file_size = os.path.getsize(path)
        self.update_file_size_label()

    def write_intel_hex_file(self, path):
        sorted_addrs = sorted(self.memory.keys())
        if not sorted_addrs: return
        
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
                for j in range(16):
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

    def write_motorola_srec_file(self, path):
        sorted_addrs = sorted(self.memory.keys())
        if not sorted_addrs: return
        
        max_addr = sorted_addrs[-1]
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
                for j in range(16):
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
        if not self.memory: return
        default_save_name = os.path.splitext(self.current_file_name)[0] + ".bin"
        path = filedialog.asksaveasfilename(initialfile=default_save_name, defaultextension=".bin", filetypes=[("Binary (*.bin)", "*.bin"), ("Binary (*.BIN)", "*.BIN")], parent=self.root)
        if not path: return
        try:
            self.write_bin_file_physical_with_guide(path)
            self.current_format = "bin"
            self.current_file_path = path
            self.current_file_name = os.path.basename(path)
            self.file_label.config(text=f"File: {self.current_file_name}")
            messagebox.showinfo("Success", "Exported successfully.", parent=self.root)
        except Exception as e: messagebox.showerror("Error", str(e), parent=self.root)

    def export_to_intel_hex(self):
        if not self.memory: return
        default_save_name = os.path.splitext(self.current_file_name)[0] + ".hex"
        path = filedialog.asksaveasfilename(initialfile=default_save_name, defaultextension=".hex", filetypes=[("Intel HEX (*.hex)", "*.hex"), ("Intel HEX (*.HEX)", "*.HEX")], parent=self.root)
        if not path: return
        try:
            self.write_intel_hex_file(path)
            self.current_format = "intel_hex"
            self.current_file_path = path
            self.current_file_name = os.path.basename(path)
            self.file_label.config(text=f"File: {self.current_file_name}")
            messagebox.showinfo("Success", "Exported successfully.", parent=self.root)
        except Exception as e: messagebox.showerror("Error", str(e), parent=self.root)

    def export_to_motorola_srec(self):
        if not self.memory: return
        default_save_name = os.path.splitext(self.current_file_name)[0] + ".srec"
        path = filedialog.asksaveasfilename(initialfile=default_save_name, defaultextension=".srec", filetypes=[("Motorola S-Record (*.srec, *.s19, *.mot)", ("*.srec", "*.s19", "*.mot")), ("Motorola S-Record (*.SREC, *.S19, *.MOT)", ("*.SREC", "*.S19", "*.MOT"))], parent=self.root)
        if not path: return
        try:
            self.write_motorola_srec_file(path)
            self.current_format = "srec"
            self.current_file_path = path
            self.current_file_name = os.path.basename(path)
            self.file_label.config(text=f"File: {self.current_file_name}")
            messagebox.showinfo("Success", "Exported successfully.", parent=self.root)
        except Exception as e: messagebox.showerror("Error", str(e), parent=self.root)

    def export_to_string_hex(self):
        if not self.memory: return
        default_save_name = os.path.splitext(self.current_file_name)[0] + ".txt"
        path = filedialog.asksaveasfilename(initialfile=default_save_name, defaultextension=".txt", filetypes=[("String HEX (*.txt, *.strhex)", ("*.txt", "*.strhex")), ("String HEX (*.TXT, *.STRHEX)", ("*.TXT", "*.STRHEX"))], parent=self.root)
        if not path: return
        try:
            self.write_hex_file_physical(path)
            self.current_format = "string_hex"
            self.current_file_path = path
            self.current_file_name = os.path.basename(path)
            self.file_label.config(text=f"File: {self.current_file_name}")
            messagebox.showinfo("Success", "Exported successfully.", parent=self.root)
        except Exception as e: messagebox.showerror("Error", str(e), parent=self.root)

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

    def on_cell_click(self, event):
        self.canvas.focus_set()
        coords = self.get_cell_coords(event)
        if coords:
            self.selected_cells.clear()
            self.selected_cells.add(coords)
            self.drag_start = coords
            self.cursor_pos = coords
            self.redraw_grid()

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
            new_min_address = (min(self.memory.keys()) // 16) * 16
            addr_offset = curr_addr - new_min_address
            new_r = addr_offset // 16
            new_c = addr_offset % 16
            self.selected_cells.clear()
            self.selected_cells.add((new_r, new_c))
            self.drag_start = (new_r, new_c)
            self.cursor_pos = (new_r, new_c)
            
            if new_r < self.top_visible_row or new_r >= self.top_visible_row + self.visible_rows_count - 1:
                self.top_visible_row = max(0, new_r - self.visible_rows_count // 2)
                self.sanitize_visible_row()

        self.update_file_size_label()
        self.redraw_grid()

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
            else:
                messagebox.showwarning("Nav Error", "Address out of bounds in current map.", parent=self.root)
        except ValueError: messagebox.showerror("Error", "Invalid hex address.", parent=self.root)

    def action_search(self):
        query = self.search_entry.get().strip()
        if not query: return
        sorted_addrs = sorted(self.memory.keys())
        try:
            clean_query = query.replace(" ", "")
            if all(c in "0123456789abcdefABCDEF" for c in clean_query) and len(clean_query) >= 2:
                target_bytes = [int(clean_query[i:i+2], 16) for i in range(0, len(clean_query), 2)]
                for i in range(len(sorted_addrs) - len(target_bytes) + 1):
                    if [self.memory.get(sorted_addrs[i+j]) for j in range(len(target_bytes))] == target_bytes:
                        hit_addr = sorted_addrs[i] + self.address_base_set
                        self.goto_entry.delete(0, tk.END); self.goto_entry.insert(0, f"{hit_addr:X}")
                        self.action_goto_address(); return
        except Exception: pass
        mem_string = "".join(chr(self.memory[a]) if 32 <= self.memory[a] <= 126 else "?" for a in sorted_addrs)
        idx = mem_string.find(query)
        if idx != -1:
            hit_addr = sorted_addrs[idx] + self.address_base_set
            self.goto_entry.delete(0, tk.END); self.goto_entry.insert(0, f"{hit_addr:X}")
            self.action_goto_address()
        else: messagebox.showinfo("Search", "Pattern not found.", parent=self.root)

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
        
        data = bytearray()
        for addr in range(start_addr, end_addr + 1):
            data.append(self.memory.get(addr, 0x00))
            
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
            start_addr = min(self.memory.keys())
            end_addr = max(self.memory.keys())

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
        
        lbl_ver = tk.Label(dialog, text="Version 1.2", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 10))
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
    # Location Presets Features
    # ==========================================
    def update_preset_list(self):
        self.preset_listbox.delete(0, tk.END)
        for p in self.presets:
            self.preset_listbox.insert(tk.END, f"[{p['addr']}] {p['name']}")

    def toggle_preset_panel(self):
        if self.is_preset_panel_visible:
            self.preset_panel.pack_forget()
            self.is_preset_panel_visible = False
        else:
            self.preset_panel.pack(side=tk.RIGHT, fill=tk.Y)
            self.is_preset_panel_visible = True
            
            if self.selected_cells:
                r, c = sorted(list(self.selected_cells))[0]
                addr = self.get_addr_from_coords(r, c)
                self.preset_addr_entry.delete(0, tk.END)
                self.preset_addr_entry.insert(0, f"0x{addr:X}")
            self.preset_name_entry.focus_set()

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

if __name__ == "__main__":
    import sys
    root = tk.Tk()
    app = AdvancedHexEditor(root)
    
    if len(sys.argv) > 1:
        file_to_load = sys.argv[1]
        if os.path.exists(file_to_load):
            root.after(100, lambda: app.execute_load_core(file_to_load))
            
    root.mainloop()
