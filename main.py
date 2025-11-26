import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys

# Import the Notes class
try:
    from note import SmartMedicalNotes
except ImportError:
    pass 

class InformationCenter:
    """Displays System Info and Saved Patient Records"""
    def __init__(self, parent_window):
        self.window = tk.Toplevel(parent_window)
        self.window.title("Information & Records Center")
        self.window.geometry("800x600")
        self.window.configure(bg="#E3F2FD")

        tk.Label(self.window, text="Records Center", font=("Montserrat", 20, "bold"), bg="#E3F2FD", fg="#0D47A1").pack(pady=20)
        
        # List files button
        tk.Button(self.window, text="Open Patient Records Folder", 
                  command=lambda: os.startfile("Patient_Records") if os.path.exists("Patient_Records") else os.makedirs("Patient_Records"),
                  bg="#1565C0", fg="white", font=("Segoe UI", 12)).pack(pady=20)

class MedicalVRMenu:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical VR Suite 2.0")
        self.root.state('zoomed')
        
        # Colors
        self.colors = {
            "bg_dark": "#0D47A1", "bg_light": "#E3F2FD", "accent": "#00BCD4",
            "text_dark": "#1A237E", "btn_primary": "#1565C0", "btn_hover": "#1976D2",
            "btn_notes": "#FF6F00", "btn_info": "#00695C"
        }
        
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.main_frame, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.create_gradient_background(self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        
        self.content_frame = tk.Frame(self.main_frame, bg='')
        self.content_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Title
        tk.Label(self.content_frame, text="Medical VR Simulation", font=("Montserrat", 48, "bold"),
                 fg=self.colors["bg_dark"], bg=self.colors["bg_light"]).pack(pady=(40, 5))
        
        tk.Frame(self.content_frame, width=200, height=4, bg=self.colors["accent"]).pack(pady=15)

        # VR Modules
        module_frame = tk.Frame(self.content_frame, bg='')
        module_frame.pack(expand=True, pady=30)
        
        # Tuple format: (Name, Icon, Description)
        vr_functions = [
            ("Heart", "❤️", "Cardiac\nSurgery"), 
            ("Liver", "🟤", "Hepatic\nProcedures"), # <--- This button links to liver.py
            ("Tooth", "🦷", "Dental\nTraining"), 
            ("Flow", "💧", "Vascular\nFlow"),
            ("Nose", "👃", "ENT\nSurgery"), 
            ("Arm", "💪", "Orthopedic\nTrauma")
        ]
        
        for text, icon, desc in vr_functions:
            self.create_card_button(module_frame, text, icon, desc).pack(side=tk.LEFT, padx=15)
        
        # Action Bar
        action_bar = tk.Frame(self.content_frame, bg='')
        action_bar.pack(side=tk.BOTTOM, pady=40)
        
        self.create_action_button(action_bar, "📝 Notes / Whiteboard", self.colors["btn_notes"], self.open_notes).pack(side=tk.LEFT, padx=20)
        self.create_action_button(action_bar, "ℹ️ Records & Info", self.colors["btn_info"], self.open_info_center).pack(side=tk.LEFT, padx=20)
        
        # Exit
        tk.Button(self.content_frame, text="Exit App", command=self.root.destroy, 
                  font=("Segoe UI", 12), bg="#FFEBEE", fg="#C62828", bd=0, padx=20, pady=5).pack(side=tk.BOTTOM, pady=10)

    def create_gradient_background(self, width, height):
        for i in range(0, height, 2):
            r = int(227 + (255 - 227) * (i/height))
            g = int(242 + (255 - 242) * (i/height))
            b = int(253 + (255 - 253) * (i/height))
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.canvas.create_rectangle(0, i, width, i+2, fill=color, outline=color)

    def create_card_button(self, parent, title, icon, desc):
        # Increased height slightly to accommodate larger button
        container = tk.Frame(parent, bg='white', width=180, height=260, highlightbackground="#CFD8DC", highlightthickness=1)
        container.pack_propagate(False)
        
        tk.Label(container, text=icon, font=("Segoe UI Emoji", 40), bg='white').pack(pady=(20, 5))
        tk.Label(container, text=title, font=("Segoe UI", 16, "bold"), fg=self.colors["text_dark"], bg='white').pack()
        tk.Label(container, text=desc, font=("Segoe UI", 10), fg="#90A4AE", bg='white').pack(pady=(0, 10))
        
        # --- UPDATED LAUNCH BUTTON (LARGER) ---
        btn = tk.Button(container, text="LAUNCH", font=("Segoe UI", 12, "bold"), bg=self.colors["btn_primary"], fg="white",
                        relief=tk.FLAT, width=14, pady=5, cursor="hand2", 
                        command=lambda: self.launch_unity(title)) 
        btn.pack(side=tk.BOTTOM, pady=20)
        
        container.bind("<Enter>", lambda e: container.config(highlightbackground=self.colors["accent"], highlightthickness=2))
        container.bind("<Leave>", lambda e: container.config(highlightbackground="#CFD8DC", highlightthickness=1))
        return container

    def create_action_button(self, parent, text, color, command):
        # --- UPDATED ACTION BUTTONS (LARGER) ---
        btn = tk.Button(parent, text=text, font=("Segoe UI", 14, "bold"), bg=color, fg="white", 
                        relief=tk.FLAT, padx=40, pady=15, cursor="hand2", command=command)
        btn.bind("<Enter>", lambda e: btn.config(bg=self.colors["accent"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        return btn

    def open_notes(self):
        try: SmartMedicalNotes(self.root)
        except NameError: messagebox.showerror("Error", "note.py not found.")

    def open_info_center(self):
        InformationCenter(self.root)

    # ---------------------------------------------------------
    # FUNCTION TO LAUNCH LIVER.PY
    # ---------------------------------------------------------
    def launch_unity(self, module):
        if module == "Liver":
            # We look for liver.py in the same folder as this script
            current_directory = os.path.dirname(os.path.abspath(__file__))
            path_to_file = os.path.join(current_directory, "liver.py")
            
            if os.path.exists(path_to_file):
                try:
                    print(f"Opening {path_to_file}...")
                    # Run the file using the same python interpreter
                    subprocess.Popen([sys.executable, path_to_file])
                except Exception as e:
                    messagebox.showerror("Execution Error", f"Failed to run liver.py:\n{e}")
            else:
                messagebox.showerror("File Not Found", f"Could not find the file:\n{path_to_file}\n\nPlease make sure liver.py is in the same folder.")
        
        else:
            # Placeholder for other buttons
            messagebox.showinfo("Simulation", f"Launching standard VR module for: {module}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MedicalVRMenu(root)
    root.mainloop()