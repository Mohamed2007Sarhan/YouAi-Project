import time
import logging
import threading
import pyperclip
import json
from typing import Dict, Any

from automation.screen_monitor import ScreenMonitor
from automation.device_control import DeviceControl
from llms.nvidia_llm import NvidiaLLM

logger = logging.getLogger("AutonomousAgent")

class AutonomousAgent:
    """
    Generalized Autonomous Agent with JSON-driven tool use and user-activity awareness.
    """
    def __init__(self):
        self.monitor = ScreenMonitor(threshold=75.0, check_interval=30.0)
        self.device = DeviceControl()
        self.llm = NvidiaLLM()
        self._lock = threading.Lock()
        self.system_language = "en-US"
        self.consecutive_failures = 0
        self.last_user_mouse_pos = self.device.get_mouse_position()

    def start_monitoring_region(self, name: str, left: int, top: int, width: int, height: int):
        self.monitor.add_region(name, left, top, width, height, self._on_change_detected)
        
    def start(self):
        self.monitor.start()
        logger.info("Autonomous Agent is now observing the screen (JSON Tool Mode).")

    def stop(self):
        self.monitor.stop()
        logger.info("Autonomous Agent stopped observing.")

    def _on_change_detected(self, region_name: str, frame: Any):
        # Step 0: Check if USER is active
        current_pos = self.device.get_mouse_position()
        if current_pos != self.last_user_mouse_pos:
            logger.info("User is active (mouse moved). Agent will not interfere.")
            self.last_user_mouse_pos = current_pos
            return
            
        if not self._lock.acquire(blocking=False):
            return

        try:
            logger.info(f"--- Autonomous Action Triggered: {region_name} ---")
            
            # Step 1: Click to focus
            region = self.monitor.regions[region_name]
            center_x = region["left"] + (region["width"] // 2)
            center_y = region["top"] + (region["height"] // 2)
            
            # Safe Zone check
            sw, sh = self.device.get_screen_size()
            if abs(center_x - sw//2) < 300 and abs(center_y - sh//2) < 300:
                center_x += 350
            
            self.device.move_mouse(center_x, center_y, duration=0.5)
            self.device.click()
            time.sleep(0.5)

            # Step 2: Extract context
            pyperclip.copy("") 
            self.device.hotkey('ctrl', 'a')
            time.sleep(0.2)
            self.device.hotkey('ctrl', 'c')
            time.sleep(0.5)
            
            context_text = pyperclip.paste().strip()
            
            if not context_text:
                self.consecutive_failures += 1
                if self.consecutive_failures >= 3:
                    logger.warning("Agent cooling down for 60s...")
                    time.sleep(60)
                    self.consecutive_failures = 0
                self.last_user_mouse_pos = self.device.get_mouse_position()
                return
            
            self.consecutive_failures = 0 
            
            # Step 3: Decide Action via LLM
            lang_inst = "Respond in Arabic." if "ar" in self.system_language.lower() else "Respond in English."
            prompt = (
                f"You are an Autonomous Digital Twin. {lang_inst}\n"
                "Review the screen text and decide if you should act. Return ONLY JSON:\n"
                '{"thought": "...", "action": "type|click|none", "target": "...", "reason": "..."}'
            )
            
            response = self.llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": context_text}], is_talking_to_user=False)
            
            try:
                cleaned = response.strip()
                if "```json" in cleaned: cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned: cleaned = cleaned.split("```")[1].split("```")[0].strip()
                
                plan = json.loads(cleaned)
                logger.info(f"AI Plan: {plan.get('thought')}")
                
                action = plan.get("action", "none")
                if action == "type":
                    self.device.type_text(plan.get("target", ""))
                    self.device.press_key('enter')
                elif action == "click":
                    self.device.click()
                
                # Update last known pos AFTER action
                self.last_user_mouse_pos = self.device.get_mouse_position()

            except Exception as e:
                logger.error(f"JSON Error: {e}")

        except Exception as e:
            logger.error(f"Agent Error: {e}")
        finally:
            self._lock.release()
