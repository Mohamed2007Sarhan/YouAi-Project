"""
deep_setup.py  —  Batch-mode self-simulation
=============================================
Sends ALL questions in ONE LLM call to save tokens (was 14-42 calls → now 1).
Results are stored in ShortMemory as a formatted table + individual entries.
"""

import os
import sys
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger("DeepSetup")

_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_DIR)
for p in [_BACKEND, os.path.join(_BACKEND, "memory"),
          os.path.join(_BACKEND, "llms"), os.path.join(_BACKEND, "tools")]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from nvidia_llm import NvidiaLLM
    from persona_builder import build_persona_prompt
    from short_memory import ShortMemory
except ImportError:
    from Backend.llms.nvidia_llm import NvidiaLLM
    from Backend.memory.persona_builder import build_persona_prompt
    from Backend.tools.short_memory import ShortMemory

SHORT_MEM_PATH = os.path.join(_BACKEND, "..", "logs", "short_memory.json")

DEEP_SETUP_QUESTIONS = [
    "ما اسمك الكامل وكم عمرك؟",
    "ما مجال عملك أو تخصصك الأكاديمي؟",
    "ما هي لغتك الأساسية في التواصل؟",
    "كيف تصف أسلوب تفكيرك: منطقي وتحليلي أم عاطفي وانطباعي؟",
    "ما أكبر هدف تسعى إليه في حياتك الآن؟",
    "كيف تتعامل مع الضغط والمواقف الصعبة؟",
    "ما الأشياء التي تجعلك سعيداً أو تضايقك بشدة؟",
    "كيف تتخذ قراراتك: بسرعة وبديهياً، أم تأخذ وقتك في التفكير؟",
    "ما أهم قيمة تحكم تصرفاتك في الحياة؟",
    "كيف يصفك أقرب الناس إليك في 3 كلمات؟",
    "ما روتينك اليومي المعتاد؟",
    "ما المجالات التي تحب التعلم فيها؟",
    "ما نقطة ضعفك التي تعترف بها بصدق؟",
    "كيف أسلوبك في الكلام: رسمي، عامي، بتستخدم نكات؟",
]


class DeepSetup:
    """
    Batch self-simulation: ONE LLM call answers all questions as the user.
    Token-efficient compared to 14 separate calls.
    Stores results in ShortMemory as Q&A + summary table.
    """

    def __init__(self, progress_callback=None):
        self.llm = NvidiaLLM()
        self.short_mem = ShortMemory(file_path=SHORT_MEM_PATH, max_items=120)
        self.progress_cb = progress_callback

    def _prog(self, pct: int, msg: str):
        logger.info(f"[DeepSetup] {pct}% — {msg}")
        if self.progress_cb:
            try:
                self.progress_cb(pct, msg)
            except Exception:
                pass

    def run(self) -> Dict:
        self._prog(5, "تحميل بيانات الشخصية من الذاكرة...")
        try:
            persona = build_persona_prompt()
        except Exception as e:
            logger.error(f"[DeepSetup] Failed to load persona: {e}")
            persona = "بيانات الشخصية غير متاحة بعد."

        # ── Load writing style from short memory ──────────────────────────────
        style_sample = ""
        try:
            sm_items = list(self.short_mem.buffer)
            for item in reversed(sm_items):
                if item.get("role") == "user_style_sample":
                    style_sample = item.get("content", "")
                    break
        except Exception:
            pass

        style_note = ""
        if style_sample:
            style_note = (
                f"\n\nعيّنة كتابة المستخدم (استخدم نفس أسلوبه تماماً):\n"
                f"\"{style_sample[:500]}\""
            )

        self._prog(15, "إرسال كل الأسئلة دفعة واحدة للـ AI...")

        # Build the numbered question list
        q_block = "\n".join(
            f"{i+1}. {q}" for i, q in enumerate(DEEP_SETUP_QUESTIONS)
        )

        system_prompt = (
            "أنت تمثّل شخصاً حقيقياً بناءً على بيانات ذاكرته."
            " أجِب على كل سؤال أدناه بضمير المتكلم كأنك هو فعلاً.\n"
            "CRITICAL RULES:\n"
            "- لا تخترع معلومات غير موجودة في بيانات الشخصية — إذا كانت المعلومة غير متاحة قل 'لا أعلم بالضبط'.\n"
            "- استخدم أسلوب المستخدم الكتابي إذا كان متاحاً.\n"
            "- كل إجابة يجب أن تكون قصيرة (جملة أو جملتان) وطبيعية.\n"
            "- أعد **JSON فقط** بدون أي كلام خارج الـ JSON:\n"
            "  {\"answers\": [{\"q\": \"نص السؤال\", \"a\": \"الإجابة\"}, ...]}\n\n"
            f"بيانات الشخصية:\n{persona[:5000]}"
            f"{style_note}"
        )

        user_msg = f"أجب على هذه الأسئلة الـ {len(DEEP_SETUP_QUESTIONS)} كأنك المستخدم:\n\n{q_block}"

        qa_pairs = []
        confidence = 0.0
        raw = ""

        try:
            raw = self.llm.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.35,
                use_reviser=False,
            )
            self._prog(70, "تحليل إجابات المحاكاة...")

            # ── Robust JSON parsing (multi-strategy) ───────────────────
            raw_clean = raw.strip()

            # Strategy 1: strip markdown fences
            if raw_clean.startswith("```"):
                lines_r = raw_clean.split("\n")
                raw_clean = "\n".join(
                    l for l in lines_r if not l.startswith("```")
                ).strip()

            # Strategy 2: extract JSON block between first { and last }
            import re as _re
            m = _re.search(r'\{.*\}', raw_clean, _re.DOTALL)
            if m:
                raw_clean = m.group(0)

            # Strategy 3: try to fix trailing comma / missing bracket issues
            def _try_parse(s: str):
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    # Fix common: last item ends with }] instead of }]}
                    # or has trailing comma before ]
                    s2 = _re.sub(r',\s*]', ']', s)   # trailing comma in array
                    s2 = _re.sub(r',\s*}', '}', s2)  # trailing comma in object
                    # Ensure answers array closes properly
                    if '"answers"' in s2 and not s2.rstrip().endswith(']}'):
                        # Try to close the structure
                        s2 = s2.rstrip().rstrip('}').rstrip().rstrip(']')
                        s2 += ']}'
                    try:
                        return json.loads(s2)
                    except Exception:
                        return None

            data = _try_parse(raw_clean)
            if data is None and m:
                data = _try_parse(m.group(0))

            if data:
                answers_list = data.get("answers", [])
                for item in answers_list:
                    q = item.get("q", "")
                    a = item.get("a", "")
                    if q and a:
                        qa_pairs.append({"question": q, "answer": a})
                confidence = round(len(qa_pairs) / len(DEEP_SETUP_QUESTIONS) * 100, 1)
                logger.info(f"[DeepSetup] Parsed {len(qa_pairs)}/{len(DEEP_SETUP_QUESTIONS)} Q&A. Confidence={confidence}%")
            else:
                logger.warning("[DeepSetup] JSON parse failed with all strategies. Storing raw.")
                self.short_mem.add("deep_setup_raw", raw[:3000])

        except Exception as e:
            logger.error(f"[DeepSetup] Batch LLM call failed: {e}")
            if raw:
                self.short_mem.add("deep_setup_raw", raw[:3000])

        # ── Store in ShortMemory ──────────────────────────────────────────────
        self._prog(80, "تخزين نتائج المحاكاة في الذاكرة القصيرة...")

        self.short_mem.add(
            "system",
            f"[DEEP_SETUP_START] بدء التحقق من الشخصية بالمحاكاة الذاتية | confidence={confidence}%"
        )

        # Individual Q&A entries
        for qa in qa_pairs:
            self.short_mem.add("twin_question", qa["question"])
            self.short_mem.add("twin_answer",   qa["answer"])

        # ── Summary table in ShortMemory ─────────────────────────────────────
        if qa_pairs:
            table_lines = ["=" * 55, "  جدول محاكاة الشخصية — Deep Setup Summary", "=" * 55]
            for i, qa in enumerate(qa_pairs, 1):
                table_lines.append(f"[{i:02d}] Q: {qa['question']}")
                table_lines.append(f"     A: {qa['answer']}")
                table_lines.append("")
            table_lines.append(f"Confidence: {confidence}%  |  Answered: {len(qa_pairs)}/{len(DEEP_SETUP_QUESTIONS)}")
            table_lines.append("=" * 55)
            self.short_mem.add("deep_setup_table", "\n".join(table_lines))

        self.short_mem.add(
            "system",
            f"[DEEP_SETUP_END] اكتملت المحاكاة | ثقة: {confidence}% | {len(qa_pairs)}/{len(DEEP_SETUP_QUESTIONS)}"
        )

        self._prog(95, f"اكتملت المحاكاة — ثقة: {confidence}%")

        result = {
            "qa_pairs":        qa_pairs,
            "total_questions": len(DEEP_SETUP_QUESTIONS),
            "converged_count": len(qa_pairs),
            "confidence_pct":  confidence,
            "short_memory_path": SHORT_MEM_PATH,
        }
        logger.info(f"[DeepSetup] Complete. Confidence={confidence}%")
        return result


def run_deep_setup(progress_callback=None) -> Dict:
    """Convenience wrapper called from Start.py / Info_get.py."""
    return DeepSetup(progress_callback=progress_callback).run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s: %(message)s")
    result = run_deep_setup()
    print(f"\nConfidence: {result['confidence_pct']}%")
    print(f"Answered:   {result['converged_count']}/{result['total_questions']}")
    if result['qa_pairs']:
        print("\nSample Q&A:")
        for qa in result['qa_pairs'][:3]:
            print(f"  Q: {qa['question']}")
            print(f"  A: {qa['answer']}\n")
