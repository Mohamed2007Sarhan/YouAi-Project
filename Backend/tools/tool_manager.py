import logging
import json
import traceback

logger = logging.getLogger("ToolManager")

class ToolManager:
    """
    Central registry and execution engine for all AI tools (Function Calling).
    Provides OpenAI-compatible JSON schemas and routes tool execution
    to the underlying system, memory, and automation modules.
    """
    def __init__(self):
        self.device_control = None
        self.memory_manager = None
        self.twin_orchestrator = None

        # Lazy load to avoid circular imports
        try:
            from Backend.automation.device_control import DeviceControl
            self.device_control = DeviceControl()
        except ImportError as e:
            logger.warning(f"DeviceControl not available: {e}")

        try:
            from Backend.memory.memory_management import GiantMemoryManager
            self.memory_manager = GiantMemoryManager()
        except ImportError as e:
            logger.warning(f"GiantMemoryManager not available: {e}")

        try:
            from Backend.services.twin_orchestrator import TwinOrchestrator
            self.twin_orchestrator = TwinOrchestrator()
        except ImportError as e:
            logger.warning(f"TwinOrchestrator not available: {e}")

    def get_schemas(self):
        """Returns the list of OpenAI tool schemas."""
        tools = []
        
        # 1. Device Control
        if self.device_control:
            tools.extend([
                {
                    "type": "function",
                    "function": {
                        "name": "run_terminal_command",
                        "description": "Execute a terminal command in a reusable session that can stay open across multiple commands.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "The command string to run (e.g. 'dir', 'ping google.com', 'tasklist')."},
                                "session_id": {"type": "string", "description": "Optional existing terminal session ID. If omitted, a new session is created."},
                                "keep_open": {"type": "boolean", "description": "Whether to keep terminal session open after command. Default true."},
                                "visible_to_user": {"type": "boolean", "description": "Whether output should be shown to user. Default true."}
                            },
                            "required": ["command"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "open_terminal_session",
                        "description": "Open a persistent terminal session and return its session_id.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "visible_to_user": {"type": "boolean", "description": "Whether this session is visible in user-facing output. Default true."}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "close_terminal_session",
                        "description": "Close a previously opened terminal session by session_id.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "session_id": {"type": "string", "description": "Terminal session ID to close."}
                            },
                            "required": ["session_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "device_move_mouse",
                        "description": "Move the mouse pointer to specific coordinates.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer", "description": "X coordinate."},
                                "y": {"type": "integer", "description": "Y coordinate."},
                                "duration": {"type": "number", "description": "Move duration in seconds (optional)."}
                            },
                            "required": ["x", "y"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "device_click",
                        "description": "Click the mouse on the user's screen.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer", "description": "X coordinate (optional)."},
                                "y": {"type": "integer", "description": "Y coordinate (optional)."},
                                "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button to click."},
                                "clicks": {"type": "integer", "description": "Number of clicks (default 1)."}
                            }
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "device_type_text",
                        "description": "Type text on the user's keyboard.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "The text to type."}
                            },
                            "required": ["text"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "device_press_key",
                        "description": "Press a specific key on the keyboard (e.g., 'enter', 'tab', 'esc').",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "The key to press."}
                            },
                            "required": ["key"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "open_app",
                        "description": "Open an application or program using the OS run command.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "app_command": {"type": "string", "description": "Command to start app (e.g., 'start notepad', 'calc', 'start msedge')."},
                                "process_name": {"type": "string", "description": "Optional executable name to verify it opened (e.g., 'notepad.exe')."}
                            },
                            "required": ["app_command"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_screen",
                        "description": "Take a screenshot of the user's screen and analyze its contents to 'see' what is happening. Use this when the user asks you to look at the screen.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
            ])

        # 2. Memory Manager
        if self.memory_manager:
            tools.append({
                "type": "function",
                "function": {
                    "name": "insert_memory_record",
                    "description": "Save an important fact, relationship, preference, or event about the user into long-term memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "The memory category (e.g., 'personal_identity', 'relationships_graph', 'goals_intentions', 'habit_system')."},
                            "data_json": {"type": "string", "description": "A JSON string containing the key-value pairs representing the memory traits to insert."}
                        },
                        "required": ["category", "data_json"]
                    }
                }
            })

        # 3. Social Fetch
        if self.twin_orchestrator:
            tools.append({
                "type": "function",
                "function": {
                    "name": "fetch_recent_social_data",
                    "description": "Fetch and profile the latest emails, telegram messages, tweets, and browser cookies to update the user's digital twin.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })

        return tools

    def execute(self, tool_name: str, arguments_str: str) -> str:
        """Executes the mapped function and returns the string result."""
        try:
            args = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError as e:
            return f"[TOOL ERROR] Invalid JSON arguments: {e}"

        logger.info(f"Executing tool: {tool_name} with args: {args}")

        try:
            if tool_name == "run_terminal_command" and self.device_control:
                return self.device_control.run_terminal_command(
                    command=args.get("command", ""),
                    session_id=args.get("session_id"),
                    keep_open=args.get("keep_open", True),
                    visible_to_user=args.get("visible_to_user", True),
                )

            elif tool_name == "open_terminal_session" and self.device_control:
                return self.device_control.open_terminal_session(
                    visible_to_user=args.get("visible_to_user", True)
                )

            elif tool_name == "close_terminal_session" and self.device_control:
                return self.device_control.close_terminal_session(args.get("session_id", ""))

            elif tool_name == "device_move_mouse" and self.device_control:
                return self.device_control.move_mouse(
                    x=args.get("x"),
                    y=args.get("y"),
                    duration=args.get("duration", 1.0),
                )

            elif tool_name == "device_click" and self.device_control:
                return self.device_control.click(
                    x=args.get("x"), y=args.get("y"), 
                    button=args.get("button", "left"), 
                    clicks=args.get("clicks", 1)
                )

            elif tool_name == "device_type_text" and self.device_control:
                return self.device_control.type_text(args.get("text", ""))

            elif tool_name == "device_press_key" and self.device_control:
                return self.device_control.press_key(args.get("key", ""))

            elif tool_name == "open_app" and self.device_control:
                return self.device_control.open_app(
                    app_command=args.get("app_command", ""), 
                    process_name=args.get("process_name")
                )

            elif tool_name == "analyze_screen":
                return self._analyze_screen()

            elif tool_name == "insert_memory_record" and self.memory_manager:
                cat = args.get("category", "")
                data_val = args.get("data_json", {})
                
                if isinstance(data_val, dict):
                    data = data_val
                elif isinstance(data_val, str):
                    try:
                        data = json.loads(data_val)
                    except json.JSONDecodeError:
                        data = {"notes": data_val}
                else:
                    data = {"notes": str(data_val)}

                record_id = self.memory_manager.insert_record(cat, data)
                if record_id == -1:
                    return f"[ERROR] Failed to insert memory. Ensure the JSON keys match the valid columns for category '{cat}'."
                return f"[SUCCESS] Inserted memory into {cat} with ID: {record_id}"

            elif tool_name == "fetch_recent_social_data" and self.twin_orchestrator:
                raw_data = self.twin_orchestrator.fetch_recent_data()
                if raw_data:
                    self.twin_orchestrator.profile_and_store(raw_data)
                    return "[SUCCESS] Fetched and profiled recent social data successfully."
                else:
                    return "[INFO] No new social data found."

            else:
                return f"[TOOL ERROR] Tool '{tool_name}' is not recognized or its dependency is unavailable."

        except Exception as e:
            err_msg = traceback.format_exc()
            logger.error(f"Error executing tool {tool_name}:\n{err_msg}")
            return f"[TOOL ERROR] Exception during execution: {e}"

    def _analyze_screen(self):
        """Take a screenshot, encode as base64, and send to NVIDIA vision API."""
        import requests, base64, os
        try:
            from mss import mss
        except ImportError:
            return "[ERROR] mss library not installed. Cannot take screenshot."

        screenshot_path = "logs/temp_screen.png"
        os.makedirs("logs", exist_ok=True)
        try:
            with mss() as sct:
                sct.shot(output=screenshot_path)
        except Exception as e:
            return f"[ERROR] Failed to take screenshot: {e}"

        # Resize image to prevent massive payload hanging the API
        try:
            from PIL import Image
            with Image.open(screenshot_path) as img:
                img.thumbnail((1280, 720)) # Resize to max 720p to save bandwidth
                img.save(screenshot_path, format="PNG")
        except ImportError:
            pass # Ignore if PIL is not available
        except Exception as e:
            pass # Ignore resize errors

        def read_b64(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        try:
            b64_image = read_b64(screenshot_path)
        except Exception as e:
            return f"[ERROR] Failed to read screenshot file: {e}"

        invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": "Bearer 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",
            "Accept": "application/json"
        }
        
        # Using a reliable Vision model on NIM. 
        payload = {
            "model": "meta/llama-3.2-90b-vision-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the contents of this screen in detail. If there are specific messages, windows, or code, mention them. Write the description in Arabic."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
            "stream": False
        }

        try:
            response = requests.post(invoke_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                description = data["choices"][0]["message"]["content"]
                return f"[SCREENSHOT ANALYSIS SUCCESS]\n{description}"
            else:
                return f"[ERROR] Vision API failed: {response.status_code} - {response.text}"
        except Exception as e:
            return f"[ERROR] Vision request failed: {e}"
