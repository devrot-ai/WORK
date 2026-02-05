# Playto Community Feed - Engineering Challenge

## Overview
A threaded discussion platform with gamification and a dynamic leaderboard built with Django REST Framework and React.

## Features
- **Threaded Comments**: Reddit-style nested comments on posts
- **Gamification**: Karma system (5 points per post like, 1 point per comment like)
- **Dynamic Leaderboard**: Top 5 users by karma earned in last 24 hours
- **Optimized Queries**: No N+1 problems, efficient comment tree loading
- **Concurrency Safe**: DB constraints prevent double-likes

## Tech Stack
- **Backend**: Django 5, Django REST Framework, SQLite
- **Frontend**: React 18, TypeScript, Tailwind CSS

## Quick Start

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install django djangorestframework django-cors-headers

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

Backend runs at `http://localhost:8000`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

## API Endpoints

- `GET /api/posts/` - List all posts with nested comments
- `POST /api/posts/` - Create a new post
- `POST /api/posts/{id}/like/` - Toggle like on a post
- `POST /api/comments/` - Create a comment
- `POST /api/comments/{id}/like/` - Toggle like on a comment
- `GET /api/leaderboard/` - Get top 5 users (last 24h karma)

## Project Structure

```
backend/
  community/
    models.py       # Data models with constraints
    serializers.py  # DRF serializers with tree building
    views.py        # API viewsets
    services.py     # Business logic (like toggles)
    urls.py         # URL routing
```

## Key Technical Decisions

1. **Comment Tree**: Self-referential FK on Comment model, built in-memory to avoid N+1
2. **Karma Ledger**: Separate KarmaTransaction model for auditable, time-based queries
3. **Like Constraints**: DB-level unique constraints + select_for_update for race conditions
4. **Leaderboard**: Dynamic aggregation over transactions, no cached integer field

See EXPLAINER.md for detailed technical explanations.
