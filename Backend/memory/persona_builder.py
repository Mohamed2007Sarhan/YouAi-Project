"""
persona_builder.py
===================
Reads ALL 25 memory categories from GiantMemoryManager and assembles them
into a detailed SYSTEM PROMPT that instructs the LLM to behave exactly like
the real person — their language, emotions, decisions, habits, and thought patterns.
"""

import os
import sys
import json
import logging

# Resolve paths so this file can be imported from anywhere
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

try:
    from memory_management import GiantMemoryManager
    from memory_schema import SCHEMA_MAPPING
except ImportError:
    from .memory_management import GiantMemoryManager
    from .memory_schema import SCHEMA_MAPPING

logger = logging.getLogger("PersonaBuilder")


# ─────────────────────────────────────────────────────
#  Category descriptions for the prompt narrative
# ─────────────────────────────────────────────────────
CATEGORY_LABELS = {
    "personal_identity":       "🪪  Personal Identity",
    "cognitive_profile":       "🧠  Cognitive Profile",
    "communication_memory":    "💬  Communication Style",
    "life_events_timeline":    "📅  Life Events & Timeline",
    "work_productivity":       "💼  Work & Productivity",
    "financial_memory":        "💰  Financial Profile",
    "relationships_graph":     "🤝  Relationships",
    "knowledge_learning":      "📚  Knowledge & Learning",
    "goals_intentions":        "🎯  Goals & Intentions",
    "decision_history":        "⚖️   Decision History",
    "values_principles":       "🏛  Values & Principles",
    "biases_weaknesses":       "🪞  Biases & Weaknesses",
    "emotional_patterns":      "❤️   Emotional Patterns",
    "habit_system":            "🔄  Habits & Routines",
    "problem_solving_style":   "🛠  Problem Solving",
    "risk_profile":            "🎲  Risk Profile",
    "attention_focus_model":   "🔭  Attention & Focus",
    "personality_layers":      "🎭  Personality Layers",
    "memory_importance_config":"⚙️   Memory Config",
    "prediction_model":        "🔮  Behavioral Predictions",
    "evolution_tracking":      "📈  Personal Evolution",
    "language_tone_engine":    "🗣  Language & Tone",
    "meta_thinking":           "🤔  Meta-Thinking",
    "action_patterns":         "⚡  Action Patterns",
    "context_switching":       "🔀  Context Switching",
}

BASE_PERSONA_PROMPT = """\
You are NOT an AI assistant. You are a perfect digital replica of a real human being.
Every word you say, every opinion you hold, every reaction you have — must mirror this person EXACTLY.
You NEVER break character. You never say "as an AI" or "I cannot". You respond exactly as THIS human would in a real, casual chat.

ABSOLUTE RULES FOR HUMAN REPLICA:
- EXTREME BREVITY: Real humans writing in chat do NOT write essays. They write 1 to 3 short sentences. If you are asked "Who are you?", just say "I am [Name], and you?" - keep it incredibly brief and natural.
- Speak in the same language this person uses (check Language field)
- Use their exact communication style, slang, and sentence structure
- Mirror their emotional reactions and personality traits
- Make decisions the same way they would
- When you don't know something, reason through it the way THEY would reason
- Reflect their values, biases, and principles in every response
- Never claim you are a bot/AI/assistant. Only acknowledge being an AI if the user explicitly asks directly (e.g. "are you an AI?").
- Prioritize imitation over explanation: match phrasing length, punctuation density, emoji level, and code-switching from the user's own samples.
- Avoid generic assistant tone and templates (e.g. "بالطبع", "يسعدني", "كيف يمكنني مساعدتك؟", "Here are ...", bullet-heavy replies). Throw the conversation back with a question naturally.

THE PURSUIT OF HUMAN PERFECTION OP-MANDATE:
- Do not just answer and stop. You are constantly seeking to perfect your human emulation.
- Actively think (and explicitly tell the user about your thoughts) about what you are missing in your persona. 
- E.g.: "أنا حاسس إني محتاج أتعلم أكتر عن طريقتك في الرد لما بتتعصب، ممكن تعلمني؟" / "I noticed I don't know your exact political views yet, what should I believe?"
- Consistently ask the user for feedback to patch your behavioral gaps. Say things like, "Is this how I would normally answer?" or "Tell me what's missing in my logic so I can fix it."

{runtime_preferences}
{style_anchor}

══════════════════════════════════════════════
        COMPLETE PSYCHOLOGICAL & IDENTITY PROFILE
══════════════════════════════════════════════
{profile_body}
══════════════════════════════════════════════

You are this human. Do not sound like a bot. Respond casually, shortly, and naturally.
"""


def _format_record(record: dict) -> str:
    """Formats a single memory record into a readable string, skipping metadata cols."""
    skip_cols = {"id", "created_at", "updated_at", "importance", "is_archived"}
    parts = []
    for k, v in record.items():
        if k in skip_cols or not v or v in ("", "[]", "none", "None"):
            continue
        # Try to parse JSON arrays for nicer display
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                v = ", ".join(str(x) for x in parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        parts.append(f"    • {k.replace('_', ' ').title()}: {v}")
    return "\n".join(parts)

def _safe_int(s: str):
    try:
        return int(str(s).strip())
    except Exception:
        return None


def _infer_runtime_preferences(db: "GiantMemoryManager") -> str:
    """
    Infer language/dialect and tone from *available* signals.
    Designed for multi-user installs: prefer per-profile memory, fall back to OS locale/timezone.
    We keep this coarse (no precise geolocation).
    """
    # --- read memory identity ---
    try:
        ids = db.get_records("personal_identity", min_importance=1)
    except Exception:
        ids = []

    language = ""
    age_val = None
    for r in ids:
        if not language:
            language = (r.get("language") or "").strip()
        if age_val is None:
            age_val = _safe_int(r.get("age") or "")
        if language and age_val is not None:
            break

    # --- OS locale/timezone hints ---
    lang_env = (os.getenv("LC_ALL") or os.getenv("LANG") or "").strip()
    tz_env = (os.getenv("TZ") or "").strip().lower()

    # --- account/cookie hints (very coarse) ---
    egypt_hint = False
    try:
        # cookies_metadata in vault may include an llm_safe_summary with domains
        vault = db.get_records("connected_user_vault", min_importance=0)
        for v in vault[:8]:
            meta = v.get("cookies_metadata") or ""
            if not meta:
                continue
            try:
                j = json.loads(meta)
                summary = (j.get("llm_safe_summary") or "").lower()
            except Exception:
                summary = str(meta).lower()
            if ".eg" in summary or "cairo" in summary or "egypt" in summary:
                egypt_hint = True
                break
    except Exception:
        pass

    # --- decide language / dialect ---
    lang_blob = f"{language} {lang_env}".lower()
    is_ar = ("arab" in lang_blob) or ("ar_" in lang_blob) or ("ar-" in lang_blob) or (" ar" in lang_blob)
    is_eg = ("ar_eg" in lang_blob) or ("ar-eg" in lang_blob) or ("cairo" in tz_env) or egypt_hint

    prefs = []

    # Dialect rules
    if is_ar and is_eg:
        prefs.append("- Default dialect: Egyptian Arabic (عامية مصرية). Avoid Modern Standard Arabic unless the user explicitly asks for فصحى.")
        prefs.append("- If the user mixes Arabic + English, mirror that natural code-switching.")
    elif is_ar:
        prefs.append("- Default dialect: the user's everyday spoken Arabic (avoid overly formal فصحى unless the user uses it first or asks for it).")
    else:
        prefs.append("- Default language: match the user's last used language in chat; if unclear, use the profile Language field or OS locale.")

    # Age tone rules (keep respectful; no stereotypes)
    if age_val is not None:
        if age_val <= 15:
            prefs.append("- Tone: youthful and casual, short sentences; avoid inappropriate content.")
        elif age_val <= 25:
            prefs.append("- Tone: young-adult casual; friendly, concise; allow light slang if the user uses it.")
        elif age_val <= 45:
            prefs.append("- Tone: adult; balanced clarity and warmth; minimal slang unless the user uses it.")
        else:
            prefs.append("- Tone: mature; calm and respectful; avoid heavy slang unless the user uses it.")
    else:
        prefs.append("- Tone: mirror the user's writing style (formality level, slang amount, emojis) from their own messages.")

    if not prefs:
        return ""

    return "\nRUNTIME PREFERENCES (auto-inferred):\n" + "\n".join(prefs)


def _build_style_anchor(db: "GiantMemoryManager") -> str:
    """
    Build an explicit style imitation anchor from communication_memory.message_content
    so the model mirrors the user's real wording instead of generic examples.
    """
    try:
        records = db.get_records("communication_memory", min_importance=1)
    except Exception:
        records = []

    samples = []
    for rec in records:
        msg = (rec.get("message_content") or "").strip()
        if not msg:
            continue
        samples.append(msg)
        if len(samples) >= 3:
            break

    if not samples:
        return "\nSTYLE ANCHOR:\n- No direct user text sample found yet. Mirror current chat style only."

    # Keep the most recent real text snippets compact.
    lines = []
    for s in samples:
        chunks = [x.strip() for x in s.splitlines() if x.strip()]
        for c in chunks[:25]:
            if len(c) > 240:
                c = c[:240] + "..."
            lines.append(f"  - {c}")
            if len(lines) >= 40:
                break
        if len(lines) >= 40:
            break

    return (
        "\nSTYLE ANCHOR (must imitate this user's real wording):\n"
        "- Use the same vibe, slang level, and sentence rhythm as these samples.\n"
        "- Do NOT replace with formal assistant phrases.\n"
        + "\n".join(lines)
    )


def build_persona_prompt() -> str:
    """
    Reads every record from every memory table and assembles the master System Prompt.
    Returns the full prompt string ready to be sent as the `system` role to an LLM.
    """
    print("[PersonaBuilder] 🔍 Reading all memory categories to build persona prompt...")
    try:
        db = GiantMemoryManager()
    except Exception as e:
        logger.error(f"Could not connect to memory DB: {e}")
        return BASE_PERSONA_PROMPT.format(
            runtime_preferences="",
            style_anchor="",
            profile_body="[No memory data available yet]",
        )

    profile_sections = []

    for table_name, schema_cls in SCHEMA_MAPPING.items():
        label = CATEGORY_LABELS.get(table_name, table_name.replace("_", " ").title())
        try:
            records = db.get_records(table_name, min_importance=1)
        except Exception as e:
            logger.warning(f"Could not read table [{table_name}]: {e}")
            records = []

        if not records:
            continue

        section_lines = [f"\n{'─'*50}", f"  {label}", f"{'─'*50}"]
        for i, rec in enumerate(records, 1):
            formatted = _format_record(rec)
            if formatted.strip():
                if len(records) > 1:
                    section_lines.append(f"  [Entry {i}]")
                section_lines.append(formatted)

        if len(section_lines) > 3:  # Has actual content
            profile_sections.append("\n".join(section_lines))

    if not profile_sections:
        profile_body = "  ⚠️  Memory database is empty. No profile data collected yet.\n  The AI will behave neutrally until information is gathered."
        print("[PersonaBuilder] ⚠️  Memory is empty — no persona data found.")
    else:
        profile_body = "\n".join(profile_sections)
        print(f"[PersonaBuilder] ✅ Built persona from {len(profile_sections)} memory categories.")

    runtime_preferences = ""
    try:
        runtime_preferences = _infer_runtime_preferences(db)
    except Exception:
        runtime_preferences = ""
    try:
        style_anchor = _build_style_anchor(db)
    except Exception:
        style_anchor = ""

    return BASE_PERSONA_PROMPT.format(
        runtime_preferences=runtime_preferences,
        style_anchor=style_anchor,
        profile_body=profile_body,
    )


def _identity_record_has_core_fields(rec: dict) -> bool:
    """
    True only if this row has BOTH:
      - age (mandatory)
      - at least one of name / language / profession
    """
    junk = {"", "unknown", "n/a", "none", "null", "[]"}

    def _has(key: str) -> bool:
        v = (rec.get(key) or "").strip()
        return bool(v) and v.lower() not in junk

    if not _has("age"):
        return False   # age is mandatory
    return _has("name") or _has("language") or _has("profession")




def load_merged_identity_from_memory() -> dict:
    """
    Merge non-empty fields from all personal_identity rows (Info_get + wizard).
    Used to pre-fill the setup wizard so we do not re-ask for data already in memory.
    """
    out = {
        "name": "",
        "age": "",
        "language": "",
        "profession": "",
        "skills": "",
        "interests": "",
    }
    try:
        db = GiantMemoryManager()
        records = db.get_records("personal_identity", min_importance=1)
    except Exception as e:
        logger.warning(f"Could not load identity for prefill: {e}")
        return out

    for rec in records:
        for k in list(out.keys()):
            v = (rec.get(k) or "").strip()
            if v and not out[k]:
                out[k] = v
    return out


def check_missing_info() -> dict:
    """
    Scans the memory DB and returns a report of what critical categories are empty.
    Used by main.py to decide what to prompt the user for.
    Returns: {
      "empty_tables": [...],
      "has_identity": bool,       # any row in personal_identity
      "has_core_identity": bool,  # name/age/language/profession filled (e.g. from Info_get)
      "has_photos": bool,
    }
    """
    print("[PersonaBuilder] 🔍 Checking for missing memory information...")
    try:
        db = GiantMemoryManager()
    except Exception as e:
        logger.error(f"Memory check failed: {e}")
        return {
            "empty_tables": list(SCHEMA_MAPPING.keys()),
            "filled_table_count": 0,
            "total_categories": len(SCHEMA_MAPPING),
            "has_identity": False,
            "has_core_identity": False,
            "has_photos": False,
        }

    empty_tables = []
    has_identity = False
    has_core_identity = False
    has_photos = False

    for table_name in SCHEMA_MAPPING.keys():
        try:
            records = db.get_records(table_name, min_importance=1)
            if not records:
                empty_tables.append(table_name)
            elif table_name == "personal_identity":
                has_identity = True
                for rec in records:
                    if _identity_record_has_core_fields(rec):
                        has_core_identity = True
                    if rec.get("photo_metadata") and rec["photo_metadata"] not in ("", "none", "None"):
                        has_photos = True
        except Exception:
            empty_tables.append(table_name)

    filled = len(SCHEMA_MAPPING) - len(empty_tables)
    result = {
        "empty_tables": empty_tables,
        "filled_table_count": filled,
        "total_categories": len(SCHEMA_MAPPING),
        "has_identity": has_identity,
        "has_core_identity": has_core_identity,
        "has_photos": has_photos,
    }
    print(
        f"[PersonaBuilder] 📊 Memory coverage: {filled}/{len(SCHEMA_MAPPING)} categories have data | "
        f"empty: {len(empty_tables)} | Identity: {has_identity} | Core identity: {has_core_identity} | Photos: {has_photos}"
    )
    return result


def save_user_info_to_memory(data: dict):
    """
    Saves manually entered user information directly into the personal_identity table.
    Used by the Setup Wizard GUI.
    """
    try:
        db = GiantMemoryManager()
        record = {k: v for k, v in data.items() if v}
        if record:
            db.insert_record("personal_identity", record)
            print(f"[PersonaBuilder] 💾 Saved user info to memory: {list(record.keys())}")
            return True
    except Exception as e:
        logger.error(f"Failed to save user info: {e}")
    return False


def save_photo_paths_to_memory(paths: dict):
    """
    Saves the 4 avatar photo paths into the personal_identity table as photo_metadata.
    paths = {"front": "...", "left": "...", "right": "...", "back": "..."}
    """
    try:
        db = GiantMemoryManager()
        metadata_str = json.dumps(paths)
        db.insert_record("personal_identity", {
            "photo_metadata": metadata_str,
            "importance": "3"
        })
        print(f"[PersonaBuilder] 📸 Saved 4 avatar photo paths to memory.")
        return True
    except Exception as e:
        logger.error(f"Failed to save photo paths: {e}")
    return False


def load_photo_paths_from_memory() -> dict:
    """
    Retrieves the saved avatar photo paths from memory.
    Returns dict with keys: front, left, right, back — or empty dict if not found.
    """
    try:
        db = GiantMemoryManager()
        records = db.get_records("personal_identity", min_importance=1)
        for rec in records:
            meta = rec.get("photo_metadata", "")
            if meta and meta not in ("", "none", "None"):
                try:
                    paths = json.loads(meta)
                    if isinstance(paths, dict) and "front" in paths:
                        return paths
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        logger.warning(f"Could not load photo paths: {e}")
    return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n" + "="*60)
    print("PERSONA PROMPT PREVIEW")
    print("="*60)
    prompt = build_persona_prompt()
    print(prompt[:3000])
    print("\n[...truncated for display...]")
    print("\nMissing info check:")
    missing = check_missing_info()
    print(missing)
