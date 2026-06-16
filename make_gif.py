import tkinter as tk
import os
import sys
import time
from PIL import ImageGrab, Image
from HexEditor import AdvancedHexEditor

def main():
    root = tk.Tk()
    app = AdvancedHexEditor(root)
    
    test_file = "testiii.hex"
    if os.path.exists(test_file):
        app.execute_load_core(test_file)
        
    root.update_idletasks()
    root.focus_force()
    time.sleep(0.5)
    
    # Get coordinates of the window
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    width = root.winfo_width()
    height = root.winfo_height()
    bbox = (x, y, x + width, y + height)
    
    os.makedirs("assets", exist_ok=True)
    frames = []
    
    # Phase 1: Capture scroll animation (scrolling down and back up)
    # Total rows in testiii.hex (9688 bytes) is 9688 / 16 = 605 rows.
    # Let's scroll by 5 rows per frame
    step = 5
    max_scroll = min(100, app.row_count - app.visible_rows_count)
    
    # Scroll down
    for row in range(0, max_scroll, step):
        app.top_visible_row = row
        app.redraw_grid()
        root.update()
        time.sleep(0.05)
        # Capture frame
        img = ImageGrab.grab(bbox=bbox)
        frames.append(img)
        
    # Scroll back up
    for row in range(max_scroll, 0, -step):
        app.top_visible_row = row
        app.redraw_grid()
        root.update()
        time.sleep(0.05)
        # Capture frame
        img = ImageGrab.grab(bbox=bbox)
        frames.append(img)

    # Save frames as animated GIF
    if frames:
        frames[0].save(
            "assets/demo.gif",
            save_all=True,
            append_images=frames[1:],
            optimize=True,
            duration=100,  # 100ms per frame
            loop=0
        )
        print("GIF saved to assets/demo.gif")
        
    root.destroy()

if __name__ == "__main__":
    main()
