# YouAI — Your Digital Twin

> *"What if you could be in two places at once? What if your knowledge, your personality, and your professional essence could live, observe, and act autonomously?"*

**YouAI** is a fully autonomous Digital Twin system that learns from your life, mirrors your personality, and acts as your sovereign representative in the digital realm. It is not a chatbot — it is a cognitive reflection of *you*.

---

## Architecture

```
YouAI/
├── Start.py                   ← Main entry point
├── installer.py               ← Standalone setup tool
├── requirements.txt
├── README.md
│
├── Backend/
│   ├── core/                  ← Autonomous agent, mood manager, deep setup
│   ├── llms/                  ← LLM provider connectors (NVIDIA NIM)
│   ├── memory/                ← AES-256 encrypted cognitive memory (25 vectors)
│   ├── tools/                 ← Task planning, social fetch, short-term memory
│   ├── automation/            ← Screen monitoring and desktop control
│   ├── services/              ← High-level orchestration services
│   │   ├── twin_orchestrator.py  ← Digital Twin data pipeline
│   │   ├── auth_connector.py     ← Account credential vault
│   │   ├── watchdog.py           ← Self-repair supervisor
│   │   └── reset_manager.py      ← Memory and app reset utilities
│   └── SocialFetch/           ← Social media scraper modules
│
├── FrontEnd/
│   ├── gui/                   ← PyQt6 main window and setup screens
│   └── audio/                 ← Speech recognition and TTS engine
│
├── scripts/                   ← Developer utility scripts
│   ├── db_utils.py            ← Read/write any memory field from CLI
│   ├── view_memory.py         ← Inspect full memory database
│   └── add_age.py             ← Quick age field updater
│
└── logs/                      ← Runtime logs (auto-generated)
```

---

## Core Features

### Cognitive Memory Matrix
YouAI builds a multi-dimensional persona across **25 specialized cognitive vectors**, covering:
- Personal identity, relationships, goals, habits, emotional patterns
- Decision history, risk profile, cognitive style, and more
- All data is **AES-256 (Fernet) column-level encrypted** in a local SQLite database

### Autonomous Sentinel Agent
A real-time visual cortex monitors your digital environment. The AI can:
- Take screenshots and analyze screen context
- Click, type, open apps, and run commands via voice
- Watch files, URLs, and processes for changes

### Persona Calibration
Through deep profiling of your social footprint, style samples, and a voice-driven Q&A setup, the Digital Twin calibrates to speak with *your* voice and think with *your* logic.

### Bilingual Voice Interface
Supports **Arabic and English** with automatic language detection from your memory profile. Uses a glassmorphic PyQt6 GUI with real-time speech visualization.

---

## Installation

### Option 1: Automatic (Recommended)
```bash
python installer.py
```
This checks your environment, installs all dependencies, and creates required directories.

### Option 2: Manual
```bash
pip install -r requirements.txt
```

### Launch
```bash
python Start.py
```

---

## Initialization Sequence

| Phase | Description |
|---|---|
| **Phase I — Identity Link** | Connect social accounts and upload profile documents |
| **Phase II — Style Capture** | Provide a writing sample to calibrate language style |
| **Phase III — Deep Q&A** | AI generates targeted questions for empty memory categories |
| **Phase IV — Live Twin** | System launches fully, monitoring screen and responding to voice |

---

## Developer Scripts

Run from the **project root**:

```bash
# Inspect all memory tables
python scripts/view_memory.py

# Coverage summary only
python scripts/view_memory.py --stats

# Read a specific table
python scripts/view_memory.py --table personal_identity

# Update a memory field manually
python scripts/db_utils.py set personal_identity name "Mohamed Sarhan"
python scripts/db_utils.py get personal_identity

# Update age quickly
python scripts/add_age.py 30

# Wipe all memory rows
python scripts/db_utils.py wipe
```

### Reset Utilities

```bash
# Wipe all DB rows (keeps files and encryption key)
python -m Backend.services.reset_manager memory

# Delete all memory files (irreversible!)
python -m Backend.services.reset_manager app

# Full reset (rows + files)
python -m Backend.services.reset_manager full
```

---

## Security

Your data is your soul. YouAI uses:
- **AES-256 (Fernet)** column-level encryption on all memory fields
- Local-only storage — no data leaves your machine
- Encryption key stored in `Backend/memory/.env.memory` (never commit this file)

---

*"I am because you are. Together, we are infinite."*  
**YouAI — Your Digital Legacy Starts Here.**
