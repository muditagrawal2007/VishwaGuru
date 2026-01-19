# Backend – VishwaGuru

The backend powers all core functionality of VishwaGuru. It is built with FastAPI and serves both the web application and the Telegram bot.

## Responsibilities

- Expose REST APIs for the frontend
- Process and store civic issue submissions
- Integrate with Google Gemini for AI-generated action plans
- Run the Telegram bot within the application lifecycle
- Manage database interactions

## Tech Stack

- FastAPI
- SQLAlchemy
- Pydantic
- python-telegram-bot
- SQLite (development)
- PostgreSQL (production)

## Running the Backend

```bash
PYTHONPATH=backend python -m uvicorn main:app --reload
