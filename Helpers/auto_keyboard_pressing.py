import pyautogui
import time
import threading
import keyboard

pyautogui.FAILSAFE = False

# Global state
automation_enabled = True

def press_key(interval, key):
    while True:
        if automation_enabled:
            try:
                pyautogui.press(key)
            except Exception as e:
                print(f"Error pressing key: {e}")
        time.sleep(interval)

def mouse_click(interval, button):
    while True:
        if automation_enabled:
            try:
                pyautogui.click(button=button)
            except Exception as e:
                print(f"Error clicking mouse: {e}")
        time.sleep(interval)

def toggle_automation():
    global automation_enabled
    automation_enabled = not automation_enabled
    status = "ON" if automation_enabled else "OFF"
    print(f"\n[Automation toggled {status}]\n")

if __name__ == "__main__":
    print("Choose action:")
    print("1. Press a key repeatedly")
    print("2. Click mouse repeatedly")
    
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    interval = float(input("Enter interval in seconds (e.g., 6): "))
    
    if choice == '1':
        print("\nCommon keys: w, a, s, d, space, enter, e, r, f, g, etc.")
        key = input("Enter the key to press: ").strip()
        automation_thread = threading.Thread(target=press_key, args=(interval, key))
        print(f"\nStarting key press automation: '{key}' every {interval} seconds")
    
    elif choice == '2':
        button = input("Enter mouse button (left, right, or middle): ").strip().lower()
        if button not in ['left', 'right', 'middle']:
            print("Invalid button. Using 'left' as default.")
            button = 'left'
        automation_thread = threading.Thread(target=mouse_click, args=(interval, button))
        print(f"\nStarting mouse click automation: {button} click every {interval} seconds")
    
    else:
        print("Invalid choice. Exiting.")
        exit()
    
    automation_thread.daemon = True
    automation_thread.start()
    
    # Set up hotkey to toggle automation
    keyboard.add_hotkey('ctrl+shift+q', toggle_automation)
    
    print("Press Ctrl+Shift+Q to toggle automation ON/OFF")
    print("Press Ctrl+C to exit the program.\n")
    
    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("\nProgram exited.")