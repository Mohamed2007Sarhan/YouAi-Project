import logging
import subprocess
import time
import os
from typing import Optional
import queue
import threading
import uuid

try:
    import pyautogui
except ImportError:
    logging.error("pyautogui not installed. Run: pip install pyautogui")

logger = logging.getLogger("DeviceControl")

class DeviceControl:
    """
    Allows the AI to control the user's mouse and keyboard.
    Uses pyautogui. Failsafes are enabled by default (moving mouse to corner aborts).
    All actions return a status string so the AI knows if the action succeeded.
    """
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        self._terminal_sessions = {}
        self._terminal_lock = threading.Lock()

    def move_mouse(self, x: int, y: int, duration: float = 1.0) -> str:
        """Move the mouse to a specific screen coordinate."""
        try:
            logger.info(f"Moving mouse to ({x}, {y}) over {duration} seconds.")
            pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
            pos = pyautogui.position()
            return f"[SUCCESS] Mouse moved to ({pos.x}, {pos.y})."
        except Exception as e:
            return f"[ERROR] move_mouse failed: {e}"

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> str:
        """Click the mouse at current or specified coordinates."""
        try:
            logger.info(f"Clicking '{button}' button {clicks} times at ({x}, {y})")
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            else:
                pyautogui.click(button=button, clicks=clicks)
            return f"[SUCCESS] Clicked {button} button {clicks}x."
        except Exception as e:
            return f"[ERROR] click failed: {e}"

    def type_text(self, text: str, interval: float = 0.05) -> str:
        """Type text using the keyboard."""
        try:
            logger.info(f"Typing text: '{text}'")
            pyautogui.write(text, interval=interval)
            return f"[SUCCESS] Typed text: '{text}'."
        except Exception as e:
            return f"[ERROR] type_text failed: {e}"

    def press_key(self, key: str) -> str:
        """Press a single key (e.g., 'enter', 'tab', 'esc')."""
        try:
            logger.info(f"Pressing key: '{key}'")
            pyautogui.press(key)
            return f"[SUCCESS] Key '{key}' pressed."
        except Exception as e:
            return f"[ERROR] press_key failed: {e}"

    def hotkey(self, *keys) -> str:
        """Press a combination of keys (e.g., 'ctrl', 'c')."""
        try:
            logger.info(f"Pressing hotkey: {keys}")
            pyautogui.hotkey(*keys)
            return f"[SUCCESS] Hotkey {'+'.join(keys)} pressed."
        except Exception as e:
            return f"[ERROR] hotkey failed: {e}"

    def get_screen_size(self):
        """Returns the width and height of the primary monitor."""
        return pyautogui.size()

    def get_mouse_position(self):
        """Returns current X, Y coordinates of the mouse."""
        return pyautogui.position()

    def run_command(self, command: str, wait_for_open: bool = True, timeout: float = 5.0) -> str:
        """
        Execute a system command and verify it actually ran.
        For GUI apps (start ...), waits briefly and checks if a new process appeared.
        Returns a status string with real confirmation.
        """
        try:
            logger.info(f"Running system command: {command}")

            # For 'start' commands (opening GUI apps), use shell=True via subprocess.Popen
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if wait_for_open:
                time.sleep(timeout)  # Give time for app to open
                ret = proc.poll()
                # For shell=True launcher commands, ret=0 means the shell finished (app launched)
                if ret is None:
                    # Still running → it's a long-running process, that's fine
                    return f"[SUCCESS] Command is running: '{command}'"
                elif ret == 0:
                    return f"[SUCCESS] Command executed successfully: '{command}'"
                else:
                    stderr_out = proc.stderr.read().decode("utf-8", errors="ignore").strip()
                    return f"[ERROR] Command failed (exit {ret}): {stderr_out or command}"
            else:
                return f"[SUCCESS] Command launched (no-wait mode): '{command}'"

        except Exception as e:
            logger.error(f"Failed to run command: {e}")
            return f"[ERROR] run_command failed: {e}"

    def run_command_and_capture(self, command: str, timeout: float = 10.0) -> str:
        """
        Run a command synchronously and return its full stdout/stderr output.
        Use this for commands that produce text output (e.g. dir, tasklist, ping).
        """
        try:
            logger.info(f"Running capture command: {command}")
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            if result.returncode == 0:
                return f"[SUCCESS]\n{out}" if out else "[SUCCESS] Command completed with no output."
            else:
                return f"[ERROR] Exit {result.returncode}:\n{err or out}"
        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {timeout}s: {command}"
        except Exception as e:
            return f"[ERROR] run_command_and_capture failed: {e}"

    # -------------------------------------------------------------------
    # Persistent terminal sessions
    # -------------------------------------------------------------------
    def open_terminal_session(self, visible_to_user: bool = True) -> str:
        """
        Open a reusable PowerShell terminal session and keep it alive.
        """
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoLogo", "-NoExit", "-Command", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
            )

            session_id = uuid.uuid4().hex[:8]
            output_queue: "queue.Queue[str]" = queue.Queue()

            def _reader():
                try:
                    while proc.poll() is None:
                        line = proc.stdout.readline()
                        if not line:
                            continue
                        output_queue.put(line.rstrip("\n"))
                except Exception:
                    pass

            reader_thread = threading.Thread(target=_reader, daemon=True)
            reader_thread.start()

            session = {
                "proc": proc,
                "queue": output_queue,
                "reader_thread": reader_thread,
                "visible_to_user": bool(visible_to_user),
                "created_at": time.time(),
                "last_used": time.time(),
            }
            with self._terminal_lock:
                self._terminal_sessions[session_id] = session
            return f"[SUCCESS] Terminal session opened: {session_id} (visible_to_user={bool(visible_to_user)})"
        except Exception as e:
            return f"[ERROR] open_terminal_session failed: {e}"

    def run_terminal_command(
        self,
        command: str,
        session_id: Optional[str] = None,
        keep_open: bool = True,
        visible_to_user: bool = True,
        timeout: float = 8.0,
    ) -> str:
        """
        Execute command in a persistent terminal session.
        If no session_id is provided, creates one automatically.
        """
        if not command or not str(command).strip():
            return "[ERROR] Empty command."

        sid = session_id
        if not sid:
            opened = self.open_terminal_session(visible_to_user=visible_to_user)
            if opened.startswith("[ERROR]"):
                return opened
            sid = opened.split(":", 1)[1].strip().split(" ", 1)[0]

        with self._terminal_lock:
            session = self._terminal_sessions.get(sid)
        if not session:
            return f"[ERROR] Terminal session not found: {sid}"

        proc = session["proc"]
        out_q = session["queue"]
        marker = f"__YOUAI_CMD_END_{uuid.uuid4().hex[:10]}__"
        payload = f"{command}\nWrite-Output \"{marker}\"\n"

        try:
            proc.stdin.write(payload)
            proc.stdin.flush()
        except Exception as e:
            return f"[ERROR] Failed to write to terminal session {sid}: {e}"

        lines = []
        deadline = time.time() + max(1.0, timeout)
        while time.time() < deadline:
            try:
                line = out_q.get(timeout=0.2)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if marker in line:
                break
            lines.append(line)

        session["last_used"] = time.time()
        session["visible_to_user"] = bool(visible_to_user)
        output = "\n".join(lines).strip()
        visibility = "visible" if visible_to_user else "hidden"
        base_msg = f"[SUCCESS] session={sid} keep_open={bool(keep_open)} visibility={visibility}"

        if not keep_open:
            close_msg = self.close_terminal_session(sid)
            if close_msg.startswith("[ERROR]"):
                return f"{base_msg}\n[WARN] {close_msg}\n{output}".strip()
            base_msg = f"{base_msg}\n{close_msg}"

        if visible_to_user:
            return f"{base_msg}\n{output}".strip() if output else base_msg
        return base_msg if not output else f"{base_msg}\n[OUTPUT HIDDEN: {len(output)} chars]"

    def close_terminal_session(self, session_id: str) -> str:
        """
        Close a running persistent terminal session.
        """
        with self._terminal_lock:
            session = self._terminal_sessions.pop(session_id, None)
        if not session:
            return f"[ERROR] Terminal session not found: {session_id}"
        try:
            proc = session["proc"]
            if proc.poll() is None:
                proc.stdin.write("exit\n")
                proc.stdin.flush()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.terminate()
            return f"[SUCCESS] Terminal session closed: {session_id}"
        except Exception as e:
            return f"[ERROR] close_terminal_session failed: {e}"

    def check_process_running(self, process_name: str) -> bool:
        """Check if a process is currently running by name."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True, text=True, timeout=5
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False

    def open_app(self, app_command: str, process_name: Optional[str] = None, wait: float = 4.0) -> str:
        """
        Open an application and verify it opened.
        app_command: e.g. 'start notepad', 'start camera:', 'calc', 'explorer'
        process_name: e.g. 'notepad.exe', 'CalculatorApp.exe' — used to verify
        Returns a real status.
        """
        try:
            logger.info(f"Opening app: {app_command}")
            subprocess.Popen(app_command, shell=True)
            time.sleep(wait)

            if process_name:
                is_running = self.check_process_running(process_name)
                if is_running:
                    return f"[SUCCESS] '{process_name}' is now running."
                else:
                    return f"[WARN] Command sent but '{process_name}' not detected in running processes. It may have opened under a different process name, or failed to launch."
            else:
                return f"[SUCCESS] Command sent: '{app_command}'. No process name given to verify."
        except Exception as e:
            return f"[ERROR] open_app failed: {e}"
