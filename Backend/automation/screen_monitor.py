import time
import threading
import logging
from typing import Callable, List, Dict, Optional

logger = logging.getLogger("ScreenMonitor")

import numpy as np
try:
    import mss
    import mss.tools
except ImportError:
    logging.error("mss not installed. Please run: pip install mss")
    mss = None

try:
    import cv2
except ImportError:
    logging.error("opencv-python not installed. Please run: pip install opencv-python")
    cv2 = None

class ScreenMonitor:
    """
    Simulates human observation. Monitors specific regions of the screen for changes.
    When a change is detected (e.g. a new message arrives), it triggers a callback.
    """
    def __init__(self, threshold: float = 10.0, check_interval: float = 2.0):
        """
        :param threshold: The Mean Squared Error (MSE) threshold to trigger a change event.
        :param check_interval: How often (in seconds) to capture the screen.
        """
        self.regions: Dict[str, Dict[str, int]] = {}
        self.callbacks: Dict[str, Callable[[str, np.ndarray], None]] = {}
        self.threshold = threshold
        self.check_interval = check_interval
        self._is_running = False
        self._thread = None
        self._previous_frames: Dict[str, np.ndarray] = {}

    def add_region(self, name: str, left: int, top: int, width: int, height: int, callback: Callable[[str, np.ndarray], None]):
        """
        Add a region to monitor.
        :param callback: Function to call when change is detected. Args: (region_name, new_frame_image)
        """
        self.regions[name] = {"left": left, "top": top, "width": width, "height": height}
        self.callbacks[name] = callback
        logger.info(f"Added monitoring region: {name} ({width}x{height} at {left},{top})")

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Screen Monitor started.")

    def stop(self):
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Screen Monitor stopped.")

    def _monitor_loop(self):
        # Create mss instance inside the thread
        try:
            with mss.mss() as sct:
                while self._is_running:
                    for name, region in self.regions.items():
                        try:
                            # Capture screen region
                            sct_img = sct.grab(region)
                            # Convert to numpy array (BGRA) and then to Grayscale for comparison
                            frame = np.array(sct_img)
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

                            if name in self._previous_frames:
                                prev_gray = self._previous_frames[name]
                                # Compute Mean Squared Error between the two images
                                err = np.sum((gray.astype("float") - prev_gray.astype("float")) ** 2)
                                err /= float(gray.shape[0] * gray.shape[1])

                                if err > self.threshold:
                                    logger.info(f"Visual change detected in region '{name}' (MSE: {err:.2f})")
                                    # Trigger the callback in a new thread so it doesn't block monitoring
                                    cb = self.callbacks.get(name)
                                    if cb:
                                        threading.Thread(target=cb, args=(name, frame), daemon=True).start()
                            
                            # Update previous frame
                            self._previous_frames[name] = gray

                        except Exception as e:
                            logger.error(f"Error monitoring region {name}: {e}")

                    time.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"Global monitor loop error: {e}")

if __name__ == "__main__":
    # Example Usage
    logging.basicConfig(level=logging.INFO)
    
    def on_change(region_name, image):
        print(f"Callback triggered for {region_name}! Image shape: {image.shape}")
        
    monitor = ScreenMonitor(threshold=50.0, check_interval=1.0)
    # Monitor a 400x400 box at top left
    monitor.add_region("chat_window_1", 0, 0, 400, 400, on_change)
    monitor.start()
    
    try:
        print("Monitoring... Move things around in the top left 400x400 area to test.")
        time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
