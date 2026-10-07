# Taghyeer Lunch Bot

Discord bot that posts randomized, absence-aware lunch batches when the meal is ready.
Full setup instructions are in **Lunch Bot Setup Guide.docx**.

Quick start:

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # fill in token, server ID, channel ID, pair IDs
    python bot.py

Run the shuffle tests: `python test_shuffle.py`
