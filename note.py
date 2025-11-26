import tkinter as tk
from tkinter import filedialog, messagebox, font
import os

class SmartMedicalNotes:
    def __init__(self, parent_window=None):
        # 1. Determine if this is a standalone app or a popup
        if parent_window:
            self.window = tk.Toplevel(parent_window)
        else:
            self.window = tk.Tk()
            
        self.window.title("Surgeon's Digital Whiteboard")
        self.window.geometry("900x700")
        
        # 2. Setup Auto-Save Folder
        self.save_folder = "Patient_Records"
        try:
            if not os.path.exists(self.save_folder):
                os.makedirs(self.save_folder)
        except Exception as e:
            print(f"Warning: Could not create folder. {e}")

        # 3. Design & Colors
        self.colors = {
            'bg': '#F0F4F8',          
            'toolbar': '#E1F5FE',     
            'text_bg': '#FFFFFF',     
            'accent': '#0288D1',      
            'highlight_y': '#FFF9C4', 
            'highlight_g': '#C8E6C9', 
            'highlight_b': '#B3E5FC'  
        }

        self.window.configure(bg=self.colors['bg'])

        # 4. Create Toolbar
        self.toolbar = tk.Frame(self.window, bg=self.colors['toolbar'], bd=1, relief=tk.RAISED)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # 5. Add Tools
        self.create_formatting_tools()
        self.create_sticker_tools()

        # 6. Main Text Area
        text_frame = tk.Frame(self.window, bg=self.colors['bg'], padx=20, pady=20)
        text_frame.pack(expand=True, fill=tk.BOTH)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            text_frame,
            bg=self.colors['text_bg'],
            fg="#333333",
            font=("Calibri", 14),
            selectbackground=self.colors['accent'],
            selectforeground="white",
            undo=True,
            yscrollcommand=scrollbar.set,
            padx=15, pady=15, bd=0,
            highlightthickness=1,
            highlightbackground="#B0BEC5"
        )
        self.text_area.pack(expand=True, fill=tk.BOTH)
        scrollbar.config(command=self.text_area.yview)

        # 7. Configure Highlighting Tags
        self.text_area.tag_configure("highlight_yellow", background=self.colors['highlight_y'])
        self.text_area.tag_configure("highlight_green", background=self.colors['highlight_g'])
        self.text_area.tag_configure("highlight_blue", background=self.colors['highlight_b'])
        self.text_area.tag_configure("bold", font=("Calibri", 14, "bold"))
        self.text_area.tag_configure("header", font=("Segoe UI", 24, "bold"), foreground=self.colors['accent'])

    def create_formatting_tools(self):
        # Header Label
        tk.Label(self.toolbar, text="Tools:", bg=self.colors['toolbar'], 
                 font=("Segoe UI", 10, "bold"), fg="#546E7A").pack(side=tk.LEFT, padx=10, pady=10)

        # Format Buttons
        self.create_tool_btn("𝐁", self.toggle_bold)
        self.create_tool_btn("H1", self.make_header)

        # Separator
        tk.Frame(self.toolbar, width=2, height=30, bg="#B0BEC5").pack(side=tk.LEFT, padx=10)

        # Color Buttons
        self.create_color_btn(self.colors['highlight_y'], "highlight_yellow")
        self.create_color_btn(self.colors['highlight_g'], "highlight_green")
        self.create_color_btn(self.colors['highlight_b'], "highlight_blue")

        # Clear Button
        self.create_tool_btn("✕", self.clear_format)
        
        # Save Button
        save_btn = tk.Button(self.toolbar, text="💾 Save Record", command=self.save_file, 
                             bg=self.colors['accent'], fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT)
        save_btn.pack(side=tk.RIGHT, padx=10, pady=5)

    def create_sticker_tools(self):
        tk.Frame(self.toolbar, width=2, height=30, bg="#B0BEC5").pack(side=tk.LEFT, padx=10)
        tk.Label(self.toolbar, text="Stickers:", bg=self.colors['toolbar'], 
                 font=("Segoe UI", 10, "bold"), fg="#546E7A").pack(side=tk.LEFT, padx=5)

        stickers = ["🩺", "💊", "🩹", "💉", "🫀", "🧠", "✅", "⚠️"]
        for s in stickers:
            btn = tk.Button(
                self.toolbar, text=s, font=("Segoe UI Emoji", 14), bg=self.colors['toolbar'], 
                bd=0, cursor="hand2", command=lambda x=s: self.add_sticker(x)
            )
            btn.pack(side=tk.LEFT, padx=2)

    def create_tool_btn(self, text, command):
        btn = tk.Button(self.toolbar, text=text, width=3, command=command, bg="white", relief=tk.GROOVE)
        btn.pack(side=tk.LEFT, padx=2)

    def create_color_btn(self, color, tag_name):
        btn = tk.Button(self.toolbar, bg=color, width=3, relief=tk.FLAT, 
                        command=lambda: self.apply_highlight(tag_name))
        btn.pack(side=tk.LEFT, padx=2)

    # --- Button Logic ---
    def add_sticker(self, sticker):
        self.text_area.insert(tk.INSERT, f" {sticker} ")

    def apply_highlight(self, tag_name):
        try: self.text_area.tag_add(tag_name, "sel.first", "sel.last")
        except tk.TclError: pass

    def toggle_bold(self):
        try:
            current_tags = self.text_area.tag_names("sel.first")
            if "bold" in current_tags: self.text_area.tag_remove("bold", "sel.first", "sel.last")
            else: self.text_area.tag_add("bold", "sel.first", "sel.last")
        except tk.TclError: pass

    def make_header(self):
        try: self.text_area.tag_add("header", "sel.first", "sel.last")
        except tk.TclError: pass

    def clear_format(self):
        try:
            for tag in ["highlight_yellow", "highlight_green", "highlight_blue", "bold", "header"]:
                self.text_area.tag_remove(tag, "sel.first", "sel.last")
        except tk.TclError: pass

    def save_file(self):
        # Ensure directory exists before saving
        if not os.path.exists(self.save_folder):
            try:
                os.makedirs(self.save_folder)
            except OSError:
                messagebox.showerror("Error", "Cannot create 'Patient_Records' folder.")
                return

        file_path = filedialog.asksaveasfilename(
            initialdir=self.save_folder,
            initialfile="Patient_Log",
            defaultextension=".txt", 
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.text_area.get("1.0", tk.END))
                messagebox.showinfo("Success", "Note saved to Patient Records!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

if __name__ == "__main__":
    app = SmartMedicalNotes()
    app.window.mainloop()