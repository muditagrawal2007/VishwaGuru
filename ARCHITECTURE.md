# VishwaGuru Deployment Architecture

```
                                 ┌─────────────────────────────────┐
                                 │         User's Browser          │
                                 │  https://your-app.netlify.app   │
                                 └─────────────────────────────────┘
                                             │
                                             │
                    ┌────────────────────────┴────────────────────────┐
                    │                                                  │
                    ▼                                                  ▼
        ┌──────────────────────┐                        ┌───────────────────────┐
        │   Netlify (Frontend) │                        │   Telegram Bot Users  │
        │   ─────────────────  │                        │                       │
        │   • React App        │                        └───────────┬───────────┘
        │   • Vite Build       │                                    │
        │   • Static Files     │                                    │
        │   • CDN Distributed  │                                    │
        └──────────┬───────────┘                                    │
                   │                                                 │
                   │ API Requests                                   │
                   │ (CORS Protected)                               │
                   │                                                 │
                   ▼                                                 ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │              Render Web Service (Backend)                       │
        │              ───────────────────────────────                     │
        │                                                                  │
        │  ┌──────────────────────────────────────────────────────────┐  │
        │  │  FastAPI Application (main.py)                           │  │
        │  │  • REST API Endpoints                                    │  │
        │  │  • CORS Middleware                                       │  │
        │  │  • Health Check (/health)                                │  │
        │  │  • File Upload Handling                                  │  │
        │  │  • AI Integration                                        │  │
        │  └──────────────┬───────────────────────────────┬───────────┘  │
        │                 │                               │              │
        │                 ▼                               ▼              │
        │  ┌─────────────────────────┐    ┌──────────────────────────┐  │
        │  │  Telegram Bot (bot.py)  │    │  AI Service (Gemini)     │  │
        │  │  • Conversation Handler │    │  • Action Plan Generator │  │
        │  │  • Photo Reception      │    │  • WhatsApp/Email Drafts │  │
        │  │  • Issue Submission     │    └──────────────────────────┘  │
        │  └─────────────┬───────────┘                                   │
        │                │                                               │
        │                ▼                                               │
        │  ┌──────────────────────────────────────────────────────────┐  │
        │  │  Database Layer (database.py, models.py)                 │  │
        │  │  • SQLAlchemy ORM                                        │  │
        │  │  • Issue Model                                           │  │
        │  │  • Session Management                                    │  │
        │  └──────────────────────────────────────────────────────────┘  │
        │                                │                                │
        └────────────────────────────────┼────────────────────────────────┘
                                         │
                                         ▼
                              ┌────────────────────┐
                              │  Neon PostgreSQL   │
                              │  ───────────────   │
                              │  • Serverless DB   │
                              │  • Auto-suspend    │
                              │  • Issues Table    │
                              │  • 0.5GB Free      │
                              └────────────────────┘


═══════════════════════════════════════════════════════════════════════════

Environment Variables Setup:

┌─────────────────────────────────────────────────────────────────────────┐
│  NETLIFY (Frontend)                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  VITE_API_URL=https://vishwaguru-backend.onrender.com                  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  RENDER (Backend)                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz            │
│  GEMINI_API_KEY=AIzaSyABcDEfGhIjKlMnOpQrStUvWxYz                       │
│  FRONTEND_URL=https://your-app.netlify.app                             │
│  DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/db?sslmode=req  │
│  PORT=10000 (auto-set)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  NEON (Database)                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  No configuration needed - just create project and copy connection str │
└─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════

Data Flow Examples:

1. Web User Reports Issue:
   Browser → Netlify (static) → Render API → PostgreSQL
                                  ↓
                            Gemini AI (action plan)

2. Telegram User Reports Issue:
   Telegram → Render Bot Handler → PostgreSQL
                     ↓
               Photo Storage

3. Responsibility Map Query:
   Browser → Netlify (static) → Render API → JSON File → Browser

═══════════════════════════════════════════════════════════════════════════

Deployment Commands:

BACKEND (Render):
  Build:  pip install -r backend/requirements.txt
  Start:  python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT

FRONTEND (Netlify):
  Build:  npm run build
  Publish: frontend/dist
  Base:   frontend/

═══════════════════════════════════════════════════════════════════════════
```
