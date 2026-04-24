import os
import json
import browser_cookie3
import getpass
import sys

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Backend.memory.memory_management import GiantMemoryManager

# ANSI color codes for a beautiful CLI experience
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

PLATFORMS = [
    "Google / Gmail",
    "Meta / Facebook",
    "Instagram",
    "X / Twitter",
    "WhatsApp Web",
    "Telegram Web",
    "Microsoft / Outlook",
    "Apple",
    "Spotify",
    "LinkedIn"
]

def banner():
    print(Colors.OKCYAN + Colors.BOLD)
    print("=" * 70)
    print("      Omni-Connect: Advanced User Identity & Credential Vault      ")
    print("=" * 70)
    print("This module elegantly connects your personal accounts to the AI System.")
    print("All credentials will be heavily encrypted and saved in your AI memory.")
    print("=" * 70 + Colors.ENDC)

def extract_browser_cookies() -> dict:
    """
    Extract cookies from every browser supported by browser_cookie3 (same pipeline as Info_get).
    Full encrypted snapshot: memory/browser_cookies_snapshot.enc
    """
    print(f"\n{Colors.WARNING}[*] Scanning all browsers for cookies (full pull)…{Colors.ENDC}")
    try:
        from Backend.tools.browser_cookie_collector import ENCRYPTED_PATH, extract_all_browser_cookies

        payload, summary = extract_all_browser_cookies(progress=None)
        total = payload.get("total_cookie_rows", 0)
        print(f"{Colors.OKGREEN}  [+] Cookie rows collected: {total}.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}  [i] Encrypted snapshot: {ENCRYPTED_PATH}{Colors.ENDC}")
        return {
            "full_extraction": True,
            "total_cookie_rows": total,
            "encrypted_snapshot_path": str(ENCRYPTED_PATH),
            "llm_safe_summary": summary[:2000],
            "per_browser_counts": {
                k: (v.get("count") if isinstance(v, dict) else 0)
                for k, v in (payload.get("browsers") or {}).items()
            },
        }
    except Exception as e:
        print(f"{Colors.FAIL}  [-] Full cookie extraction failed: {e}{Colors.ENDC}")
        cookies_data = {}
        browsers = {
            "Chrome": browser_cookie3.chrome,
            "Firefox": browser_cookie3.firefox,
            "Edge": browser_cookie3.edge,
            "Brave": browser_cookie3.brave,
            "Opera": browser_cookie3.opera,
            "Safari": browser_cookie3.safari,
        }
        for b_name, b_func in browsers.items():
            try:
                cj = b_func()
                cookies_data[b_name] = f"Extracted {len(cj)} cookies"
                print(f"{Colors.OKGREEN}  [+] {b_name}: {len(cj)} cookies{Colors.ENDC}")
            except Exception:
                pass
        if not cookies_data:
            print(f"{Colors.FAIL}  [-] No browser sessions could be extracted.{Colors.ENDC}")
        return cookies_data

def collect_credentials() -> tuple[str, dict]:
    """Collects user credentials via interactive CLI."""
    print(f"\n{Colors.OKBLUE}--- Primary Setup ---{Colors.ENDC}")
    primary_email = input(f"{Colors.BOLD}Enter your primary Email Address: {Colors.ENDC}").strip()
    
    while True:
        unified_choice = input(f"{Colors.BOLD}Do you use a unified (single) password for most of your accounts? (y/n): {Colors.ENDC}").strip().lower()
        if unified_choice in ['y', 'n']:
            break

    credentials = {}
    
    if unified_choice == 'y':
        unified_pass = getpass.getpass(f"{Colors.BOLD}Enter your Unified Password: {Colors.ENDC}")
        for plat in PLATFORMS:
            credentials[plat] = {"email": primary_email, "password": unified_pass, "is_unified": True}
        print(f"{Colors.OKGREEN}[+] Unified password temporarily linked to {len(PLATFORMS)} major platforms.{Colors.ENDC}")
        
    else:
        print(f"\n{Colors.WARNING}[*] Switching to highly-customized setup. Let's link your accounts individually.{Colors.ENDC}")
        for plat in PLATFORMS:
            print(f"\n{Colors.OKCYAN}--- Linking {plat} ---{Colors.ENDC}")
            choice = input(f"Do you have a {plat} account that you want to connect? (y/n): ").strip().lower()
            if choice == 'y':
                spec_email = input(f"Email/Username for {plat} [Press Enter to use: {primary_email}]: ").strip()
                if not spec_email:
                    spec_email = primary_email
                spec_pass = getpass.getpass(f"Password for {plat}: ")
                credentials[plat] = {"email": spec_email, "password": spec_pass, "is_unified": False}
            else:
                print(f"Skipping {plat}...")

    return primary_email, credentials

def save_to_memory(email: str, credentials: dict, cookies_data: dict):
    """Encrypts and injects collected credentials directly into AI Giant Memory."""
    print(f"\n{Colors.WARNING}[*] Booting up AES-256 Memory Encryption Engine...{Colors.ENDC}")
    
    try:
        # Point to the existing memory folder dynamically
        memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
        if not os.path.exists(memory_dir):
            os.makedirs(memory_dir) # Failsafe
            
        manager = GiantMemoryManager(
            db_path="ai_giant_memory.db",
            env_path=".env.memory"
        )
        
        # Dynamically map the highly sensitive user credentials table
        table_name = "connected_user_vault"
        columns = ["primary_email", "platform_name", "account_identifier", "encrypted_password", "cookies_metadata"]
        manager.create_custom_table(table_name, columns)
        
        print(f"{Colors.OKGREEN}[+] Validated Vault Schema. Injecting encrypted records...{Colors.ENDC}")
        
        for plat, data in credentials.items():
            manager.insert_record(table_name, {
                "primary_email": email,
                "platform_name": plat,
                "account_identifier": data["email"],
                "encrypted_password": data["password"], # memory_management natively encrypts blob layers
                "cookies_metadata": json.dumps(cookies_data)
            })
            
        print(f"\n{Colors.HEADER}{Colors.BOLD}[SUCCESS]{Colors.ENDC} {Colors.OKCYAN}All {len(credentials)} user accounts have been successfully linked and cryptographically secured in the AI Brain.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}Your APIs will now extract sessions locally and securely when initiating routines.{Colors.ENDC}")

    except Exception as e:
        print(f"{Colors.FAIL}[!] Critical Vault Error: {e}{Colors.ENDC}")


def main():
    try:
        banner()
        cookies_data = extract_browser_cookies()
        primary_email, credentials = collect_credentials()
        
        if credentials:
            save_to_memory(primary_email, credentials, cookies_data)
        else:
            print(f"\n{Colors.WARNING}[!] No credentials provided. Shutting down Omni-Connect.{Colors.ENDC}")
            
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}[!] Operation aborted by user.{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()
