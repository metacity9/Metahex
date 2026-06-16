import tkinter as tk
import os
import sys
import time
from PIL import ImageGrab
from HexEditor import AdvancedHexEditor

def main():
    root = tk.Tk()
    app = AdvancedHexEditor(root)
    
    test_file = "testiii.hex"
    if os.path.exists(test_file):
        app.execute_load_core(test_file)
    
    def capture():
        # Force redraw and focus
        root.update_idletasks()
        root.focus_force()
        time.sleep(0.5)
        
        # Get coordinates of the window
        x = root.winfo_rootx()
        y = root.winfo_rooty()
        width = root.winfo_width()
        height = root.winfo_height()
        
        # Add a small buffer or grab the exact window bbox
        bbox = (x, y, x + width, y + height)
        
        # Create output directory if it doesn't exist
        os.makedirs("assets", exist_ok=True)
        
        # Grab screenshot
        screenshot = ImageGrab.grab(bbox=bbox)
        screenshot.save("assets/screenshot.png")
        print("Screenshot saved to assets/screenshot.png")
        
        # Close the window
        root.destroy()
        
    root.after(1000, capture)
    root.mainloop()

if __name__ == "__main__":
    main()
