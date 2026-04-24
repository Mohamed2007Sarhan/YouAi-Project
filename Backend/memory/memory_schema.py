from dataclasses import dataclass, fields
from typing import List, Optional

# Base class for all Memory Tables to ensure standard metadata
@dataclass
class MemoryBase:
    importance: int = 1  # 1: Low, 2: Medium, 3: High
    is_archived: bool = False

# 1. Personal Identity
@dataclass
class PersonalIdentity(MemoryBase):
    name: str = ""
    age: str = ""
    language: str = ""
    profession: str = ""
    skills: str = "" # JSON encoded list
    interests: str = "" # JSON encoded list
    photo_metadata: str = "" # Paths or identifiers for photos from all angles

# 2. Cognitive Profile
@dataclass
class CognitiveProfile(MemoryBase):
    thinking_style: str = "" # Logical / Emotional
    decision_making_style: str = ""
    reaction_speed: str = ""
    risk_level: str = ""

# 3. Communication Memory
@dataclass
class CommunicationMemory(MemoryBase):
    message_content: str = ""
    communication_style: str = ""
    important_people_mentioned: str = "" # JSON encoded list
    relationship_context: str = ""

# 4. Life Events & Timeline
@dataclass
class LifeEventsTimeline(MemoryBase):
    event_name: str = ""
    event_date: str = ""
    event_details: str = ""
    impact_level: str = ""

# 5. Work & Productivity
@dataclass
class WorkProductivity(MemoryBase):
    job_role: str = ""
    current_tasks: str = "" # JSON encoded list
    projects: str = "" # JSON encoded list
    past_decisions: str = ""
    productivity_patterns: str = ""

# 6. Financial Memory (Highly Sensitive)
@dataclass
class FinancialMemory(MemoryBase):
    income_level: str = ""
    expenses_log: str = "" # JSON encoded list
    transactions: str = "" # JSON encoded list
    financial_goals: str = ""

# 7. Relationships Graph
@dataclass
class RelationshipsGraph(MemoryBase):
    person_name: str = ""
    closeness_level: str = "" # e.g. 1-10
    relationship_nature: str = "" # Family, friend, enemy
    notes: str = ""

# 8. Knowledge & Learning
@dataclass
class KnowledgeLearning(MemoryBase):
    learned_topic: str = ""
    experience_level: str = ""
    past_mistakes: str = ""
    lessons_learned: str = ""

# 9. Goals & Intentions
@dataclass
class GoalsIntentions(MemoryBase):
    goal_name: str = ""
    action_plan: str = ""
    intentions: str = ""
    progress_status: str = ""

# 10. Decision History
@dataclass
class DecisionHistory(MemoryBase):
    decision_context: str = ""
    reasoning: str = ""
    was_it_correct: str = "" # Boolean represented as string
    lessons_learned: str = ""

# 11. Values & Principles
@dataclass
class ValuesPrinciples(MemoryBase):
    core_principles: str = ""
    red_lines: str = "" # Non-negotiable things
    acceptable_risks: str = ""

# 12. Biases & Weaknesses
@dataclass
class BiasesWeaknesses(MemoryBase):
    known_biases: str = ""
    weaknesses: str = ""
    manipulation_triggers: str = "" # Things that influence them quickly

# 13. Emotional Patterns
@dataclass
class EmotionalPatterns(MemoryBase):
    sadness_triggers: str = ""
    happiness_triggers: str = ""
    stress_triggers: str = ""
    pressure_reaction: str = ""

# 14. Habit System
@dataclass
class HabitSystem(MemoryBase):
    daily_habits: str = "" # JSON encoded list
    routine: str = ""
    active_hours: str = ""

# 15. Problem Solving Style
@dataclass
class ProblemSolvingStyle(MemoryBase):
    solving_approach: str = ""
    starting_point: str = ""
    is_step_by_step: str = ""

# 16. Risk Profile
@dataclass
class RiskProfile(MemoryBase):
    risk_appetite: str = "" # Safety vs Risk
    when_to_risk: str = ""
    when_to_withdraw: str = ""

# 17. Attention & Focus Model
@dataclass
class AttentionFocusModel(MemoryBase):
    focus_areas: str = ""
    distractions: str = ""
    focus_duration: str = ""

# 18. Personality Layers
@dataclass
class PersonalityLayers(MemoryBase):
    layer_name: str = "" # e.g. 'work_mode', 'friends_mode', 'family_mode'
    traits: str = ""
    activation_triggers: str = ""

# 19. Memory Importance System 
# (This acts as rules/configuration for the Forgetting model)
@dataclass
class MemoryImportanceConfig(MemoryBase):
    rule_name: str = ""
    retention_period_days: str = ""
    forgetting_action: str = "" # Archive vs Delete

# 20. Prediction Model
@dataclass
class PredictionModel(MemoryBase):
    scenario: str = ""
    expected_action: str = ""
    expected_reaction: str = ""
    future_decisions: str = ""

# 21. Evolution Tracking
@dataclass
class EvolutionTracking(MemoryBase):
    trait_changed: str = ""
    past_state: str = ""
    current_state: str = ""
    reason_for_change: str = ""

# 22. Language & Tone Engine
@dataclass
class LanguageToneEngine(MemoryBase):
    speaking_style: str = ""
    catchphrases: str = "" # JSON encoded list
    explanation_style: str = ""

# 23. Meta-Thinking
@dataclass
class MetaThinking(MemoryBase):
    self_reflection_level: str = ""
    self_doubt_frequency: str = ""
    opinion_flexibility: str = ""

# 24. Action Patterns
@dataclass
class ActionPatterns(MemoryBase):
    execution_speed: str = ""
    procrastination_tendency: str = ""
    execution_style: str = ""

# 25. Context Switching
@dataclass
class ContextSwitching(MemoryBase):
    work_life_balance_style: str = ""
    seriousness_to_humor_switch: str = ""
    switch_triggers: str = ""

# Mapping for generic DB generation
SCHEMA_MAPPING = {
    "personal_identity": PersonalIdentity,
    "cognitive_profile": CognitiveProfile,
    "communication_memory": CommunicationMemory,
    "life_events_timeline": LifeEventsTimeline,
    "work_productivity": WorkProductivity,
    "financial_memory": FinancialMemory,
    "relationships_graph": RelationshipsGraph,
    "knowledge_learning": KnowledgeLearning,
    "goals_intentions": GoalsIntentions,
    "decision_history": DecisionHistory,
    "values_principles": ValuesPrinciples,
    "biases_weaknesses": BiasesWeaknesses,
    "emotional_patterns": EmotionalPatterns,
    "habit_system": HabitSystem,
    "problem_solving_style": ProblemSolvingStyle,
    "risk_profile": RiskProfile,
    "attention_focus_model": AttentionFocusModel,
    "personality_layers": PersonalityLayers,
    "memory_importance_config": MemoryImportanceConfig,
    "prediction_model": PredictionModel,
    "evolution_tracking": EvolutionTracking,
    "language_tone_engine": LanguageToneEngine,
    "meta_thinking": MetaThinking,
    "action_patterns": ActionPatterns,
    "context_switching": ContextSwitching,
}
