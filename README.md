# Startup WhatsApp Monitor

A Python automation project that monitors public startup and founder
directories and sends notifications through WhatsApp using WasenderAPI.

## Features

- Monitors startup and founder profile pages
- Detects newly added profiles
- Prevents duplicate alerts
- Sends structured WhatsApp notifications
- Runs automatically using GitHub Actions
- Stores monitoring state in JSON
- Does not require a dedicated server

## Project structure

```text
startup-whatsapp-monitor/
├── .github/workflows/startup-monitor.yml
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── monitor.py
│   ├── state_manager.py
│   └── whatsapp.py
├── data/seen_items.json
├── .gitignore
├── README.md
├── requirements.txt
└── run.py
