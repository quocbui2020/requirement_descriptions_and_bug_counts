import pyautogui
import time
import threading
import keyboard

pyautogui.FAILSAFE = False # Disable Fail-Safe to prevent 'FailSafeException'

def press_key(interval, key):
    while not stop_event.is_set():
        pyautogui.press(key)
        time.sleep(interval)

def on_stop_key_combination():
    print("Stop key combination pressed. Exiting...")
    stop_event.set()

if __name__ == "__main__":
    interval = 6  # Interval in seconds
    key = 'f13'  # Key to press
    
    # Create an event to stop the key pressing thread
    stop_event = threading.Event()
    
    # Start the key pressing thread
    key_press_thread = threading.Thread(target=press_key, args=(interval, key))
    key_press_thread.start()
    
    # Set up a hotkey combination to stop the program (e.g., Ctrl+Shift+Q)
    keyboard.add_hotkey('ctrl+shift+q', on_stop_key_combination)
    
    # Wait for the key press thread to finish
    key_press_thread.join()
    
    print("Program exited.")
