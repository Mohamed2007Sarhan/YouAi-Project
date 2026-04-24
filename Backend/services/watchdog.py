import os
import sys
import time
import subprocess
import logging

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Backend.llms.nvidia_llm import NvidiaLLM

# Setup logging for the Watchdog
logging.basicConfig(level=logging.INFO, format="%(asctime)s [Watchdog] %(levelname)s: %(message)s")
logger = logging.getLogger("ExternalRun")

class SelfRepairWatchdog:
    """
    A supervisor that runs the main AI application.
    If the application crashes, it captures the traceback,
    uses the LLM to diagnose and generate a patch, applies it, and restarts.
    """
    def __init__(self, script_to_run="Start.py"):
        self.script_to_run = script_to_run
        self.llm = NvidiaLLM()
        self.max_retries = 5 # Increased retries for complex self-repair

    def run(self):
        retries = 0
        while retries < self.max_retries:
            logger.info(f"Starting {self.script_to_run} (Attempt {retries + 1}/{self.max_retries})...")
            
            # Run the main script as a subprocess
            # Use 'py' on windows if possible
            cmd = ["py", self.script_to_run] if os.name == 'nt' else ["python3", self.script_to_run]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for it to finish or crash
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                logger.info("Application exited cleanly.")
                break
            else:
                logger.error(f"Application crashed with Exit Code {process.returncode}")
                logger.error(f"Traceback Captured:\n{stderr}")
                
                # Perform Self-Repair
                logger.warning("Initiating Intelligent Self-Repair Protocol...")
                success = self.diagnose_and_repair(stderr)
                
                if success:
                    logger.info("Patch applied successfully. Re-evaluating system state...")
                    retries = 0 # Reset retries on success
                else:
                    logger.error("Self-Repair engine could not find a definitive fix.")
                    retries += 1
                    time.sleep(3)
        
        if retries >= self.max_retries:
            logger.critical("Maximum self-repair attempts reached. Manual intervention required.")

    def diagnose_and_repair(self, traceback_text: str) -> bool:
        """Uses the LLM to analyze the traceback and suggest a file edit."""
        # Get context from the codebase to help LLM
        # (This makes it an 'intelligent entity' that sees its own environment)
        code_context = ""
        try:
            # Just read the first few files to give context
            for f in ["Start.py", "Backend/memory/question_generator.py"]:
                if os.path.exists(f):
                    with open(f, "r", encoding="utf-8") as file:
                        code_context += f"\n--- {f} ---\n{file.read()[:1000]}\n"
        except: pass

        prompt = (
            "You are an Intelligent Self-Healing AI Entity. "
            "Your master process crashed. You must analyze the error and fix your own code.\n\n"
            f"ERROR TRACEBACK:\n{traceback_text}\n\n"
            f"CODE CONTEXT:\n{code_context}\n\n"
            "Identify the file causing the error. Provide the EXACT full code of the fixed file.\n"
            "Format:\n"
            "FILE: <path_to_file>\n"
            "CONTENT:\n"
            "```python\n<full_fixed_code>\n```\n"
        )
        
        try:
            logger.info("Analyzing system failure...")
            response = self.llm.chat([{"role": "system", "content": prompt}], use_reviser=False, temperature=0.1)
            
            if "FILE:" in response and "CONTENT:" in response:
                file_path = response.split("CONTENT:")[0].replace("FILE:", "").strip()
                
                if "```python" in response:
                    code = response.split("```python")[1].split("```")[0].strip()
                elif "```" in response:
                    code = response.split("```")[1].split("```")[0].strip()
                else:
                    return False
                    
                if os.path.exists(file_path) and code:
                    logger.info(f"Applying intelligent patch to: {file_path}")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(code)
                    return True
            return False
        except Exception as e:
            logger.error(f"Self-Repair logic error: {e}")
            return False

if __name__ == "__main__":
    watchdog = SelfRepairWatchdog()
    watchdog.run()
