import os
import sys
import json
import logging
from typing import Dict, Any, List

# Ensure project root is on sys.path so Backend.* imports resolve
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DigitalTwinOrchestrator")

# ---------------------------------------------------------------------------
# Importing optional API clients (graceful fallback if not configured)
# ---------------------------------------------------------------------------
GmailClient = None
TelegramBotClient = None
TwitterClient = None
NvidiaLLM = None
GiantMemoryManager = None
SCHEMA_MAPPING = {}

try:
    from Backend.llms.nvidia_llm import NvidiaLLM
except ImportError as e:
    logger.error(f"Could not import NvidiaLLM. Core LLM features will fail: {e}")

try:
    from Backend.memory.memory_management import GiantMemoryManager
    from Backend.memory.memory_schema import SCHEMA_MAPPING
except ImportError as e:
    logger.error(f"Could not import Memory Manager. Storage features will fail: {e}")

SCHEMA_PROMPT_INJECT = """
You are a master psychological profiler, emotional analyst, and cognitive mirroring engine.
I will provide you with raw communication data from a human (emails, telegram messages, tweets, etc.). 
Your job is to deeply analyze this data to extract insights about them and return a pure JSON payload matching my required database schema.

The schema expects updates to the following categories. If the raw text does not provide information for a specific field, leave the string empty "".

{
    "personal_identity": {"name": "", "age": "", "language": "", "profession": "", "skills": "[]", "interests": "[]", "photo_metadata": ""},
    "cognitive_profile": {"thinking_style": "", "decision_making_style": "", "reaction_speed": "", "risk_level": ""},
    "communication_memory": {"message_content": "", "communication_style": "", "important_people_mentioned": "[]", "relationship_context": ""},
    "life_events_timeline": {"event_name": "", "event_date": "", "event_details": "", "impact_level": ""},
    "work_productivity": {"job_role": "", "current_tasks": "[]", "projects": "[]", "past_decisions": "", "productivity_patterns": ""},
    "financial_memory": {"income_level": "", "expenses_log": "[]", "transactions": "[]", "financial_goals": ""},
    "relationships_graph": {"person_name": "", "closeness_level": "", "relationship_nature": "", "notes": ""},
    "knowledge_learning": {"learned_topic": "", "experience_level": "", "past_mistakes": "", "lessons_learned": ""},
    "goals_intentions": {"goal_name": "", "action_plan": "", "intentions": "", "progress_status": ""},
    "decision_history": {"decision_context": "", "reasoning": "", "was_it_correct": "", "lessons_learned": ""},
    "values_principles": {"core_principles": "", "red_lines": "", "acceptable_risks": ""},
    "biases_weaknesses": {"known_biases": "", "weaknesses": "", "manipulation_triggers": ""},
    "emotional_patterns": {"sadness_triggers": "", "happiness_triggers": "", "stress_triggers": "", "pressure_reaction": ""},
    "habit_system": {"daily_habits": "[]", "routine": "", "active_hours": ""},
    "problem_solving_style": {"solving_approach": "", "starting_point": "", "is_step_by_step": ""},
    "risk_profile": {"risk_appetite": "", "when_to_risk": "", "when_to_withdraw": ""},
    "attention_focus_model": {"focus_areas": "", "distractions": "", "focus_duration": ""},
    "personality_layers": {"layer_name": "", "traits": "", "activation_triggers": ""},
    "memory_importance_config": {"rule_name": "", "retention_period_days": "", "forgetting_action": ""},
    "prediction_model": {"scenario": "", "expected_action": "", "expected_reaction": "", "future_decisions": ""},
    "evolution_tracking": {"trait_changed": "", "past_state": "", "current_state": "", "reason_for_change": ""},
    "language_tone_engine": {"speaking_style": "", "catchphrases": "[]", "explanation_style": ""},
    "meta_thinking": {"self_reflection_level": "", "self_doubt_frequency": "", "opinion_flexibility": ""},
    "action_patterns": {"execution_speed": "", "procrastination_tendency": "", "execution_style": ""},
    "context_switching": {"work_life_balance_style": "", "seriousness_to_humor_switch": "", "switch_triggers": ""}
}

CRITICAL OUTPUT RULES:
- If the raw data includes [WHATSAPP_EXPORT], [WHATSAPP_WEB], or long [TELEGRAM] lines, use them to infer communication style and phrasing.
- If raw data includes [SOCIAL_MEDIA_ACCOUNTS] or social profile blocks, treat them as trusted collection-tool inputs and use them to improve identity inference.
- Never use the literal words "unknown", "Unknown", "N/A", "n/a", or "undefined" as field values.
- If you cannot infer something from the data, use an empty string "" (not a placeholder word).
- For personal_identity: infer real name, language, and profession from email signatures, display names, Telegram/Twitter handles, and browser domain hints when possible.
- Prefer concrete inferences over empty strings when the evidence supports them.

Only return the JSON. No markdown, no markdown backticks (` ```json `), strictly pure JSON. Be extremely thorough in your analysis.
"""

def _sanitize_value(val):
    """Strip placeholder 'unknown' style strings so we never store them."""
    if isinstance(val, str):
        t = val.strip().lower()
        if t in ("unknown", "n/a", "none", "null", "undefined", "[unknown]"):
            return ""
        return val.strip()
    if isinstance(val, dict):
        return {k: _sanitize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_value(v) for v in val]
    return val


class TwinOrchestrator:
    def __init__(self):
        self.llm = NvidiaLLM()
        self.db = GiantMemoryManager()
        self.social_fetch_failures: List[Dict[str, str]] = []
        
        # Load API clients safely
        try:
            self.gmail = GmailClient()
        except:
            self.gmail = None
            logger.warning("Gmail API not configured properly.")
            
        try:
            self.telegram = TelegramBotClient()
        except:
            self.telegram = None
            logger.warning("Telegram API not configured properly.")
            
        try:
            self.twitter = TwitterClient()
            self.twitter_handle = os.getenv("TWITTER_USERNAME")
        except:
            self.twitter = None
            logger.warning("Twitter API not configured properly.")

    def fetch_recent_data(self, progress_callback=None):
        """
        Collects raw human data from browser cookies (full encrypted save + LLM-safe summary),
        Gmail, Telegram, Twitter.
        progress_callback(percent: int, message: str) optional for UI progress bars.
        """
        raw_context = []

        def prog(pct: int, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        prog(5, "Extracting cookies from all browsers…")
        try:
            from Backend.tools.browser_cookie_collector import extract_all_browser_cookies

            _payload, cookie_summary = extract_all_browser_cookies(progress=prog)
            raw_context.append(cookie_summary)
            logger.info(
                "Browser cookie summary for LLM: ~%s chars (domains + per-browser counts; no secret values).",
                len(cookie_summary),
            )
        except Exception as e:
            logger.warning("Browser cookie extraction failed: %s", e)
            raw_context.append(f"[BROWSER_COOKIES] Extraction failed: {e}\n")

        prog(22, "Optional WhatsApp text (export or Web)…")
        try:
            from Backend.tools.whatsapp_context import collect_whatsapp_context

            wa_block = collect_whatsapp_context()
            if wa_block.strip():
                raw_context.append(wa_block)
                logger.info("WhatsApp context appended (~%s chars).", len(wa_block))
        except Exception as e:
            logger.warning("WhatsApp context skipped: %s", e)

        prog(28, "Fetching Gmail…")
        logger.info("Fetching Gmail Data...")
        if self.gmail:
            unread_res = self.gmail.get_unread_emails(max_results=25)
            if unread_res.get("success"):
                for email in unread_res["data"]:
                    raw_context.append(
                        f"[GMAIL] Subject: {email['subject']} | Sender: {email['sender']} | Snippet: {email['snippet']}"
                    )

        prog(48, "Fetching Telegram…")
        logger.info("Fetching Telegram Data...")
        if self.telegram:
            drained = self.telegram.drain_updates(max_messages=200, timeout=25)
            if drained:
                raw_context.extend(drained)
                logger.info("Telegram: collected %s bot-visible message line(s).", len(drained))
            else:
                updates = self.telegram.get_updates(timeout=8)
                if updates.get("success") and updates["data"].get("result"):
                    for item in updates["data"]["result"]:
                        msg = item.get("message", {})
                        if "text" in msg:
                            fu = msg.get("from") or {}
                            uid = fu.get("id")
                            sender = (
                                fu.get("username")
                                or fu.get("first_name")
                                or (f"user_{uid}" if uid is not None else "telegram_peer")
                            )
                            raw_context.append(f"[TELEGRAM] From {sender}: {msg['text']}")
            if not any("[TELEGRAM]" in x for x in raw_context):
                logger.info(
                    "Telegram Bot API: no messages in queue. "
                    "Bots only see chats where someone wrote to your bot — not your full account history."
                )

        prog(68, "Fetching Twitter / X…")
        logger.info("Fetching Twitter Data...")
        if self.twitter and self.twitter_handle:
            query = f"from:{self.twitter_handle}"
            res = self.twitter.search_recent_tweets(query, max_results=15)
            inner = (res.get("data") or {}) if res.get("success") else {}
            tweets = inner.get("data") or []
            for tweet in tweets:
                raw_context.append(f"[TWITTER] {tweet.get('text', '')}")

        prog(76, "Fetching public social profiles…")
        try:
            from Backend.tools.social_profile_extract import extract_public_profile

            social_urls = []
            # Optional explicit env links
            for env_key, p in (
                ("YOUAI_FACEBOOK_URL", "facebook"),
                ("YOUAI_INSTAGRAM_URL", "instagram"),
            ):
                u = (os.getenv(env_key) or "").strip()
                if u:
                    social_urls.append((p, u, "env"))

            # Optional links from linked_accounts table
            try:
                linked = self.db.get_records("linked_accounts", min_importance=0)
                for rec in linked[:60]:
                    plat = (rec.get("platform_name") or "").strip().lower()
                    ident = (rec.get("account_identifier") or "").strip()
                    if not ident:
                        continue
                    if ident.startswith("http://") or ident.startswith("https://"):
                        url = ident
                    elif "facebook" in plat:
                        url = f"https://www.facebook.com/{ident.lstrip('@')}"
                    elif "instagram" in plat:
                        url = f"https://www.instagram.com/{ident.lstrip('@')}/"
                    else:
                        continue
                    social_urls.append(("facebook" if "facebook" in plat else "instagram", url, "linked_accounts"))
            except Exception:
                pass

            # New dedicated table: social_media_accounts (model-facing collection source)
            try:
                sma = self.db.get_records("social_media_accounts", min_importance=0)
                for rec in sma[:80]:
                    plat = (rec.get("platform_name") or "").strip().lower()
                    purl = (rec.get("profile_url") or "").strip()
                    ident = (rec.get("account_identifier") or "").strip()
                    url = ""
                    if purl.startswith("http://") or purl.startswith("https://"):
                        url = purl
                    elif ident.startswith("http://") or ident.startswith("https://"):
                        url = ident
                    elif "facebook" in plat and ident:
                        url = f"https://www.facebook.com/{ident.lstrip('@')}"
                    elif ("instagram" in plat or "insta" in plat) and ident:
                        url = f"https://www.instagram.com/{ident.lstrip('@')}/"
                    if url:
                        hint_platform = "facebook" if "facebook" in plat else "instagram"
                        social_urls.append((hint_platform, url, "social_media_accounts"))
            except Exception:
                pass

            # Dedup links
            seen = set()
            dedup = []
            for p, u, s in social_urls:
                key = u.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    dedup.append((p, u, s))

            if dedup:
                self.db.create_custom_table(
                    "social_profiles",
                    ["platform_name", "profile_url", "display_name", "bio", "source"],
                )
                for p, u, src in dedup[:20]:
                    res = extract_public_profile(u, platform_hint=p)
                    if res.get("success"):
                        txt = res.get("summary_text") or ""
                        if txt:
                            raw_context.append(txt)
                        try:
                            self.db.insert_record(
                                "social_profiles",
                                {
                                    "platform_name": res.get("platform", p),
                                    "profile_url": u,
                                    "display_name": res.get("display_name", ""),
                                    "bio": res.get("bio", ""),
                                    "source": src,
                                    "importance": 1,
                                },
                            )
                        except Exception:
                            pass
                    else:
                        err_txt = str(res.get("error", "unknown"))
                        logger.info("Public social fetch skipped for %s: %s", u, err_txt)
                        self.social_fetch_failures.append(
                            {
                                "platform": p,
                                "url": u,
                                "source": src,
                                "error": err_txt,
                            }
                        )
        except Exception as e:
            logger.warning("Social profile extraction skipped: %s", e)

        prog(82, "Assembling context…")
        # Include user-provided social account identifiers (even if no public URL fetch)
        try:
            sma = self.db.get_records("social_media_accounts", min_importance=0)
            if sma:
                lines = ["[SOCIAL_MEDIA_ACCOUNTS] User-provided social accounts for model tools:"]
                for r in sma[:80]:
                    lines.append(
                        "  - "
                        + f"{(r.get('platform_name') or '').strip()}: "
                        + f"{(r.get('account_identifier') or '').strip()} "
                        + f"{('(url: ' + (r.get('profile_url') or '').strip() + ')') if (r.get('profile_url') or '').strip() else ''}"
                    )
                raw_context.append("\n".join(lines) + "\n")
        except Exception:
            pass

        # Include linked accounts (safe summary) as additional identity hints
        try:
            vault = self.db.get_records("connected_user_vault", min_importance=0)
            if vault:
                lines = ["[VAULT_ACCOUNTS] Linked accounts (safe summary; no passwords):"]
                for r in vault[:40]:
                    plat = (r.get("platform_name") or "").strip()
                    ident = (r.get("account_identifier") or "").strip()
                    pem = (r.get("primary_email") or "").strip()
                    if plat or ident:
                        lines.append(f"  - {plat}: {ident} (primary: {pem})")
                raw_context.append("\n".join(lines) + "\n")
        except Exception:
            pass

        context = "\n".join(raw_context)
        # Debug: write what we actually sent for profiling (no secrets: cookies summary has domains only)
        try:
            dbg_dir = os.path.join(project_root, "data")
            os.makedirs(dbg_dir, exist_ok=True)
            dbg_path = os.path.join(dbg_dir, "last_llm_context.txt")
            with open(dbg_path, "w", encoding="utf-8", errors="ignore") as f:
                if len(context) > 250_000:
                    f.write("[...truncated...]\n")
                    f.write(context[-250_000:])
                else:
                    f.write(context)
            logger.info("Debug context written to: %s", dbg_path)
        except Exception:
            pass

        return context

    def process_webhook_data(self, platform: str, text: str):
        """
        Placeholder for live Webhook processing.
        When WhatsApp or Meta receives a webhook event, pipeline the message here to be
        anonymized/aggregated and eventually passed to the LLM.
        """
        logger.info(f"Received live data from {platform}: {text}")
        context = f"[{platform.upper()}] {text}"
        self.profile_and_store(context)

    def profile_and_store(self, raw_context: str, progress_callback=None):
        """Passes aggregated data to LLM, parses the JSON, and stores it into GiantMemory."""
        if not raw_context.strip():
            logger.info("No raw context to process.")
            return

        def prog(pct: int, msg: str):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        prog(88, "Profiling with AI (LLM)…")
        logger.info("Sending data to NvidiaLLM for deep profiling...")
        
        messages = [
            {"role": "system", "content": SCHEMA_PROMPT_INJECT},
            {"role": "user", "content": f"Here is the raw data:\n\n{raw_context}\n\nAnalyze this deeply and return pure JSON representing the human's cognition and life events."}
        ]

        try:
            response_json_str = self.llm.chat(messages, temperature=0.2)

            # Robust JSON cleaning
            cleaned_str = response_json_str.strip()
            if "```json" in cleaned_str:
                cleaned_str = cleaned_str.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_str:
                cleaned_str = cleaned_str.split("```")[1].split("```")[0].strip()
            
            # Remove potential leading/trailing junk
            start_idx = cleaned_str.find("{")
            end_idx = cleaned_str.rfind("}")
            if start_idx != -1 and end_idx != -1:
                cleaned_str = cleaned_str[start_idx:end_idx+1]

            try:
                parsed_data = json.loads(cleaned_str)
            except json.JSONDecodeError:
                logger.error("Initial JSON parse failed. Attempting deep fix...")
                # Fallback: extract any JSON-like structure
                import re
                json_match = re.search(r'\{.*\}', cleaned_str, re.DOTALL)
                if json_match:
                    parsed_data = json.loads(json_match.group())
                else:
                    raise

            parsed_data = _sanitize_value(parsed_data)
            logger.info("Successfully received and parsed profiling JSON from LLM.")

            # Dump into Giant Memory
            self._store_traits_in_db(parsed_data)
            prog(100, "Done.")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM Output into JSON. Error: {e}")
            logger.debug(f"Raw Output: {response_json_str}")
            prog(100, "Finished with errors.")
            raise
        except Exception as e:
            logger.error(f"Error during profiling: {e}")
            prog(100, "Finished with errors.")
            raise

    def _store_traits_in_db(self, parsed_data: Dict[str, Any]):
        """Iterates over JSON dictionary and stores values if at least one field is provided."""
        stored_vectors = 0
        
        for category, traits in parsed_data.items():
            if category not in SCHEMA_MAPPING:
                logger.warning(f"Unrecognized schema category: {category}")
                continue
            if not isinstance(traits, dict):
                logger.warning(f"Skipping non-dict category: {category}")
                continue
            traits = _sanitize_value(traits)
            # Never let the LLM set importance/is_archived — 0 hides rows from get_records(min_importance=1)
            traits = {k: v for k, v in traits.items() if k not in ("importance", "is_archived")}

            # Check if there is actual data inside and not just empty strings/lists
            has_data = any(
                val for val in traits.values() if val not in ["", "[]", "none", "None", None]
            )
            
            if has_data:
                try:
                    record_id = self.db.insert_record(category, traits)
                    logger.info(f"Stored Memory Vector in [{category}] -> Record ID: {record_id}")
                    stored_vectors += 1
                except Exception as e:
                    logger.error(f"Failed to store vector in {category}: {e}")
                    
        logger.info(f"Total Trait Vectors Safely Stored & Encrypted: {stored_vectors}")

    def deep_setup(self):
        """Perform a final holistic review of the digital twin memory and generate a welcome message."""
        logger.info("Initiating Deep Setup Review...")
        from Backend.memory.persona_builder import build_persona_prompt
        
        try:
            full_persona = build_persona_prompt()
            llm = NvidiaLLM()
            
            prompt = (
                "You have just completed the initialization of this Digital Twin. "
                "Based on the following persona profile, generate a short, extremely natural, and welcoming "
                "first message to the user. Use the user's preferred language (Arabic/English). "
                "Sound like a real person saying hello for the first time as a twin.\n\n"
                f"PERSONA PROFILE:\n{full_persona}"
            )
            
            response = llm.chat([{"role": "system", "content": prompt}], is_talking_to_user=True)
            logger.info("Deep Setup complete. Greeting generated.")
            return response
        except Exception as e:
            logger.error(f"Deep Setup failed: {e}")
            return "Initialization complete. I am ready."

if __name__ == "__main__":
    logger.info("Starting Info_get Digital Twin Orchestrator...")
    orchestrator = TwinOrchestrator()
    
    logger.info("Gathering historical and recent data from connected platforms...")
    collected_data = orchestrator.fetch_recent_data()
    
    if collected_data:
        logger.info(f"Successfully collected {len(collected_data.split(chr(10)))} sources of interaction.")
        orchestrator.profile_and_store(collected_data)
    else:
        logger.info("No new data found to process.")
        
    logger.info("Process Complete.")
