import os
import sys
import logging
import json
from typing import List, Dict

# Ensure paths
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
sys.path.append(os.path.dirname(_DIR))

try:
    from persona_builder import check_missing_info
    from memory_schema import SCHEMA_MAPPING
except ImportError:
    from .persona_builder import check_missing_info
    from .memory_schema import SCHEMA_MAPPING

logger = logging.getLogger("QuestionGenerator")

# ─────────────────────────────────────────────────────────────
# فقط أسئلة الهوية الأساسية — الباقي هيتملى من السوشيال ميديا
# ─────────────────────────────────────────────────────────────
CORE_IDENTITY_QUESTIONS = [
    {
        "id": "language_pref",
        "question": "ما هي اللغة التي تفضل التحدث بها؟ (عربي أو English)",
        "table": "personal_identity"
    },
    {
        "id": "name",
        "question": "ما اسمك الكامل؟",
        "table": "personal_identity"
    },
    {
        "id": "age",
        "question": "كم عمرك؟",
        "table": "personal_identity"
    },
    {
        "id": "profession",
        "question": "ما مجال عملك أو تخصصك؟",
        "table": "personal_identity"
    },
]


def get_setup_questions() -> List[Dict[str, str]]:
    """
    Returns ONLY the core identity questions if they are missing.
    The rest of the memory (24 categories) is filled automatically
    from social media accounts provided in the Setup window.
    This avoids overwhelming the user with 24+ voice questions.
    """
    logger.info("Checking if core identity questions are needed...")

    missing_info = check_missing_info()

    # If core identity (name/age/language/profession) already filled → no questions needed
    if missing_info.get("has_core_identity", False):
        logger.info("Core identity already in memory. No setup questions needed.")
        return []

    logger.info("Core identity missing. Will ask 4 basic questions only.")
    return CORE_IDENTITY_QUESTIONS
