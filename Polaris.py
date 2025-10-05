import os
import glob
import tkinter as tk
from tkinter import messagebox, Toplevel
from PIL import Image, ImageTk
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue
print('commit test')#git test
SCREENSHOT_FOLDER = os.path.expanduser(r"~\\Pictures\\Screenshots")

markers = []
last_screenshot = None
marker_mode = False
current_hidden_screenshot = None

# --- Queue for incoming screenshots ---
screenshot_queue = queue.Queue()

# --- Deduplication set: path + modified time ---
processed_screenshots = set()  # (path, mtime)
def get_latest_screenshot():
    files = glob.glob(os.path.join(SCREENSHOT_FOLDER, "*.png"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def update_map(latest):
    global last_screenshot
    last_screenshot = latest
    img = Image.open(latest)
    img = img.resize((2560, 1440))
    photo = ImageTk.PhotoImage(img)

    canvas.image = photo
    bg_id = canvas.create_image(0, 0, image=photo, anchor="nw")
    canvas.tag_lower(bg_id)
    root.title(f"Current Map: {os.path.basename(latest)}")
    print("Map updated:", latest)

def prepare_hidden_marker(latest):
    global current_hidden_screenshot, marker_mode

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    current_hidden_screenshot = os.path.join(SCREENSHOT_FOLDER, f"hidden_{timestamp}.png")

    img = Image.open(latest)
    img.save(current_hidden_screenshot)

    marker_mode = True
    canvas.bind("<Button-1>", place_marker)
    print("Hidden screenshot ready for marker:", current_hidden_screenshot)

def place_marker(event):
    global marker_mode, current_hidden_screenshot
    if not marker_mode or not current_hidden_screenshot:
        return

    marker_id = canvas.create_oval(
        event.x - 10, event.y - 10, event.x + 10, event.y + 10,
        fill="red", outline="black"
    )
    markers.append({
        "x": event.x,
        "y": event.y,
        "image_path": current_hidden_screenshot,
        "id": marker_id
    })

    # Preview on hover
    def show_preview(e, img_path=current_hidden_screenshot):
        if hasattr(e.widget, "preview_window"):
            return
        preview_window = Toplevel(root)
        preview_window.title("Blocked Area")
        preview_window.geometry("+%d+%d" % (root.winfo_pointerx() + 20, root.winfo_pointery() + 20))
        img = Image.open(img_path)
        img.thumbnail((800, 600))
        preview_img = ImageTk.PhotoImage(img)
        label = tk.Label(preview_window, image=preview_img)
        label.image = preview_img
        label.pack()
        e.widget.preview_window = preview_window

    def hide_preview(e):
        if hasattr(e.widget, "preview_window"):
            e.widget.preview_window.destroy()
            del e.widget.preview_window

    canvas.tag_bind(marker_id, "<Enter>", show_preview)
    canvas.tag_bind(marker_id, "<Leave>", hide_preview)

    marker_mode = False
    canvas.unbind("<Button-1>")
    print("Marker placed at:", event.x, event.y)

def exit_program(event=None):
    root.destroy()

# --- Watchdog handler ---
class ScreenshotHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith(".png"):
            # Ignore new events if a dialog is open (hard lockout)
            if getattr(root, "prompt_open", False):
                return
            screenshot_queue.put(event.src_path)

# --- Process queue ---
def process_queue():
    if getattr(root, "prompt_open", False):
        root.after(200, process_queue)
        return

    if not screenshot_queue.empty():
        latest = screenshot_queue.get()
        mtime = os.path.getmtime(latest)

        # Skip if already processed
        if (latest, mtime) in processed_screenshots:
            root.after(200, process_queue)
            return

        root.prompt_open = True
        answer = messagebox.askyesno("New Screenshot", "Add marker?")
        if answer:
            prepare_hidden_marker(latest)
        else:
            update_map(latest)

        processed_screenshots.add((latest, mtime))  # mark as processed
        root.prompt_open = False

    root.after(200, process_queue)

# --- Tkinter setup ---
root = tk.Tk()
root.title("Northstar: Quietus of the Knights")


canvas = tk.Canvas(root, width=2560, height=1440)
canvas.pack()

root.bind("<Escape>", exit_program)

# Watchdog observer
event_handler = ScreenshotHandler()
observer = Observer()
observer.schedule(event_handler, SCREENSHOT_FOLDER, recursive=False)
observer.start()

# Load map if one exists
latest = get_latest_screenshot()
if latest:
    update_map(latest)
    processed_screenshots.add((latest, os.path.getmtime(latest)))

# Initialize prompt flag and start processing queue
root.prompt_open = False
process_queue()

try:
    root.mainloop()
finally:
    observer.stop()
    observer.join()
