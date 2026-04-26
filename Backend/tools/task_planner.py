"""
Task Planner Module
===================
لو المهمة طويلة، الـ AI هيعمل خطة في ملف task_plan.md،
يمشي عليها خطوة بخطوة، ويبلغ المستخدم لما يخلص.
"""

import os
import json
import logging
import re
from datetime import datetime

logger = logging.getLogger("TaskPlanner")

TASK_PLAN_DIR = "logs/task_plans"


class TaskPlanner:
    """
    يحدد لو المهمة طويلة ويعمل خطة مكتوبة ويتابع تنفيذها.
    """

    # كلمات ترشح إن المهمة معقدة / متعددة الخطوات
    COMPLEXITY_KEYWORDS = [
        "خطوات", "مراحل", "ترتيب", "اولاً", "ثانياً", "ثالثاً",
        "وبعدين", "ثم", "بعد كده", "ابدأ", "انهي", "اعمل", "جهز",
        "steps", "then", "after that", "first", "second", "third",
        "plan", "organize", "setup", "configure", "install", "and then",
        "finally", "lastly", "next", "followed by",
        "مهمة", "خطة", "خطه", "نفذ", "تابع", "راقب",
        "task", "workflow", "monitor", "autopilot", "execute",
    ]

    # حد أدنى لعدد الخطوات يعتبر المهمة "طويلة"
    MIN_STEPS_FOR_PLAN = 2

    def __init__(self):
        os.makedirs(TASK_PLAN_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. هل المهمة طويلة؟
    # ------------------------------------------------------------------
    def is_long_task(self, user_text: str, ai_response: str) -> bool:
        """
        يحدد لو المهمة تستاهل خطة:
        - لو الـ response يحتوي على قايمة خطوات واضحة (أرقام / نقاط)
        - أو النص الأصلي فيه مؤشرات تعقيد
        """
        # 0. المستخدم طلب خطة صراحة
        user_lower = user_text.lower()
        explicit_plan_terms = ["خطة", "خطه", "رتب", "step by step", "plan", "workflow"]
        if any(term in user_lower for term in explicit_plan_terms):
            return True

        # 1. عد الخطوات المرقمة في رد الـ AI
        numbered = re.findall(r'(?:^|\n)\s*(?:\d+[\.\-\):]|\-|\*|•)', ai_response)
        if len(numbered) >= self.MIN_STEPS_FOR_PLAN:
            return True

        # 2. كلمات دلالة التعقيد في طلب المستخدم
        matched = sum(1 for kw in self.COMPLEXITY_KEYWORDS if kw.lower() in user_lower)
        if matched >= 2:
            return True

        return False

    def generate_plan_from_task(self, task_description: str) -> list[dict]:
        """
        توليد خطة احتياطية من وصف المهمة نفسه لو رد الـ AI ماطلعش خطوات كفاية.
        """
        chunks = re.split(r'(?:\bثم\b|\bوبعدين\b|\bبعدها\b|,|،|;|؛|\band then\b|\bthen\b|\bnext\b)', task_description)
        steps = []
        step_id = 1
        for raw in chunks:
            s = raw.strip(" .:-")
            if len(s) >= 6:
                steps.append({"id": step_id, "title": s, "status": "pending"})
                step_id += 1
            if step_id > 8:
                break

        if len(steps) < self.MIN_STEPS_FOR_PLAN:
            steps = [
                {"id": 1, "title": "Analyze the task requirements and constraints", "status": "pending"},
                {"id": 2, "title": "Execute the required actions in order", "status": "pending"},
                {"id": 3, "title": "Validate the final outcome and report status", "status": "pending"},
            ]
        return steps

    # ------------------------------------------------------------------
    # 2. توليد الخطة من رد الـ AI أو طلب المستخدم
    # ------------------------------------------------------------------
    def generate_plan_from_response(self, task_description: str, ai_response: str) -> list[dict]:
        """
        يحول رد الـ AI لقائمة خطوات منظمة.
        كل خطوة: {"id": N, "title": "...", "status": "pending"}
        """
        steps = []

        # حاول تستخلص خطوات مرقمة أو بنقاط
        lines = ai_response.split("\n")
        step_id = 1
        for line in lines:
            line = line.strip()
            # خطوات مرقمة: 1. أو 1- أو 1) أو - أو *
            match = re.match(r'^(?:\d+[\.\-\):]|\-|\*|•)\s*(.+)', line)
            if match:
                title = match.group(1).strip()
                if len(title) > 3:  # تجاهل الفارغة
                    steps.append({"id": step_id, "title": title, "status": "pending"})
                    step_id += 1

        # لو مفيش خطوات واضحة، قسّم على الجمل الطويلة
        if len(steps) < self.MIN_STEPS_FOR_PLAN:
            sentences = re.split(r'[.،؛\n]+', ai_response)
            steps = []
            step_id = 1
            for s in sentences:
                s = s.strip()
                if len(s) > 20:
                    steps.append({"id": step_id, "title": s, "status": "pending"})
                    step_id += 1
                    if step_id > 10:  # حد أقصى 10 خطوات
                        break

        return steps

    # ------------------------------------------------------------------
    # 3. كتابة ملف الخطة
    # ------------------------------------------------------------------
    def save_plan(self, task_description: str, steps: list[dict]) -> str:
        """
        يحفظ الخطة في ملف .md ويرجع المسار.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plan_path = os.path.join(TASK_PLAN_DIR, f"task_{timestamp}.md")

        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(f"# 📋 خطة المهمة\n")
            f.write(f"**المهمة:** {task_description}\n")
            f.write(f"**بدأت في:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**الحالة:** جارٍ التنفيذ ⏳\n\n")
            f.write("---\n\n")
            f.write("## الخطوات\n\n")
            for step in steps:
                f.write(f"- [ ] **الخطوة {step['id']}:** {step['title']}\n")

        logger.info(f"[TaskPlanner] Plan saved: {plan_path}")
        return plan_path

    # ------------------------------------------------------------------
    # 4. تحديث حالة خطوة
    # ------------------------------------------------------------------
    def update_step(self, plan_path: str, step_id: int, status: str):
        """
        status: 'done' | 'failed' | 'in_progress'
        يحدث ملف الخطة ليعكس الحالة الجديدة.
        """
        if not os.path.exists(plan_path):
            return

        icons = {"done": "✅", "failed": "❌", "in_progress": "🔄", "pending": "⬜"}
        icon = icons.get(status, "⬜")

        with open(plan_path, "r", encoding="utf-8") as f:
            content = f.read()

        # استبدل السطر الخاص بهذه الخطوة
        old_pattern = re.compile(
            rf'(- \[.?\] \*\*الخطوة {step_id}:\*\* .+)', re.MULTILINE
        )
        new_line = old_pattern.sub(
            lambda m: m.group(0).replace("[ ]", "[x]" if status == "done" else "[-]")
                      + f" {icon}",
            content
        )

        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(new_line)

    # ------------------------------------------------------------------
    # 5. إنهاء الخطة وتسجيل الوقت
    # ------------------------------------------------------------------
    def finalize_plan(self, plan_path: str, success: bool = True):
        """
        يكتب في الملف إن المهمة خلصت وبالتاريخ.
        """
        if not os.path.exists(plan_path):
            return

        with open(plan_path, "r", encoding="utf-8") as f:
            content = f.read()

        status_line = "✅ مكتملة" if success else "❌ فشلت"
        content = content.replace(
            "**الحالة:** جارٍ التنفيذ ⏳",
            f"**الحالة:** {status_line}\n**انتهت في:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"[TaskPlanner] Plan finalized: {plan_path} | success={success}")

    # ------------------------------------------------------------------
    # 6. رسالة الإكمال للمستخدم
    # ------------------------------------------------------------------
    def get_completion_message(self, task_description: str, steps: list[dict], lang: str = "ar") -> str:
        """
        يولّد رسالة تبلّغ المستخدم إن المهمة خلصت.
        """
        done_count = sum(1 for s in steps if s["status"] == "done")
        total = len(steps)

        if "ar" in lang.lower():
            return (
                f"✅ خلصت المهمة!\n"
                f"المهمة: {task_description}\n"
                f"تم تنفيذ {done_count} من {total} خطوة بنجاح."
            )
        else:
            return (
                f"✅ Task Completed!\n"
                f"Task: {task_description}\n"
                f"Executed {done_count} of {total} steps successfully."
            )
