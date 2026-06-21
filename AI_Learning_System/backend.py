from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from openai import OpenAI

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from datetime import datetime

from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy import func

import os
import json
import uvicorn

# =========================
# ENV SETUP
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env file")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# FASTAPI APP
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# DATABASE SETUP
# =========================
if not DATABASE_URL:
    raise ValueError("Missing DATABASE_URL in .env file")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# SECURITY
# =========================
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# =========================
# TABLES
# =========================
class UserTable(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="student")

class ScoreTable(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    topic = Column(String)
    score = Column(Integer)
    level = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class EngagementTable(Base):
    __tablename__ = "engagement"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    action = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class AnalyticsTable(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True)

    username = Column(String)
    topic = Column(String)

    time_spent = Column(Integer)
    quiz_attempt_number = Column(Integer)
    hints_used = Column(Integer)

    score = Column(Integer)

    date = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# =========================
# PYDANTIC MODELS
# =========================
class User(BaseModel):
    username: str
    password: str


class TopicRequest(BaseModel):
    topic: str
    level: str


class HintRequest(BaseModel):
    question: str


class ScoreRequest(BaseModel):
    username: str
    topic: str
    score: int
    level: str


class FeedbackRequest(BaseModel):
    topic: str
    score: int


class ChatRequest(BaseModel):
    message: str


class EngagementRequest(BaseModel):
    username: str
    action: str


class RecommendationRequest(BaseModel):
    username: str
    topic: str
    score: int

class AnalyticsRequest(BaseModel):
    username: str
    topic: str
    time_spent: int
    quiz_attempt_number: int
    hints_used: int
    score: int

# =========================
# AUTH
# =========================
@app.post("/register")
def register(user: User):
    db = SessionLocal()
    try:
        existing = db.query(UserTable).filter_by(username=user.username).first()
        if existing:
            return {"status": "error", "message": "User already exists"}

        hashed = pwd_context.hash(user.password)
        role = "admin" if user.username.lower() == "admin" else "student"
        db.add(UserTable(username=user.username, password=hashed,role=role))
        db.commit()

        return {"status": "success", "message": "Account created"}

    finally:
        db.close()


@app.post("/login")
def login(user: User):
    db = SessionLocal()
    try:
        existing = db.query(UserTable).filter_by(username=user.username).first()

        if not existing or not pwd_context.verify(user.password, existing.password):
            return {"status": "error", "message": "Invalid credentials"}

        return {"status": "success","role": existing.role}

    finally:
        db.close()

# =========================
# GENERATE NOTES
# =========================
@app.post("/generate")
def generate_notes(req: TopicRequest):
    prompt = f"""
    Create beginner learning notes.

    Topic: {req.topic}
    Level: {req.level}

    Include:
    - explanation
    - examples
    - key points
    - summary
    """

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return {"notes": res.choices[0].message.content}

# =========================
# QUIZ GENERATION
# =========================
@app.post("/quiz")
def generate_quiz(req: TopicRequest):
    prompt = f"""
    Generate 5 multiple-choice questions.

    Topic: {req.topic}
    Difficulty: {req.level}

    Return ONLY JSON:
    {{
      "quiz": [
        {{
          "question": "",
          "options": ["", "", "", ""],
          "answer": "",
          "explanation": ""
        }}
      ]
    }}
    """

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    data = json.loads(res.choices[0].message.content)

    return {"quiz": data.get("quiz", [])}

# =========================
# SAVE SCORE + AUTO LEVEL UPDATE (FIXED CORE LOGIC)
# =========================
@app.post("/save_score")
def save_score(data: ScoreRequest):
    db = SessionLocal()

    try:
        # Determine level
        if data.score >= 4:
            new_level = "advanced"
        elif data.score >= 2:
            new_level = "intermediate"
        else:
            new_level = "beginner"

        record = db.query(ScoreTable).filter_by(
            username=data.username,
            topic=data.topic
        ).first()

        if record:
            record.score = data.score
            record.level = new_level
        else:
            db.add(ScoreTable(
                username=data.username,
                topic=data.topic,
                score=data.score,
                level=new_level
            ))

        db.commit()

        return {
            "status": "success",
            "level": new_level
        }

    finally:
        db.close()

# =========================
# RECOMMENDATION (FIXED)
# =========================
@app.post("/recommend")
def recommend(req: RecommendationRequest):

    topic_paths = {
        "Python Programming": {
            "Beginner": ["Variables", "Data Types", "Control Flow"],
            "Intermediate": ["Functions", "OOP", "Modules"],
            "Advanced": ["Decorators", "Multithreading", "Async IO"]
        },
        "Machine Learning": {
            "Beginner": ["Data Preprocessing", "Pandas Basics"],
            "Intermediate": ["Regression Models", "Classification"],
            "Advanced": ["Deep Learning", "Transformers"]
        }
    }

    if req.score >= 4:
        level = "Advanced"
    elif req.score >= 2:
        level = "Intermediate"
    else:
        level = "Beginner"

    next_topics = topic_paths.get(req.topic, {}).get(level)

    # ✅ fallback if topic not found
    if not next_topics:
        next_topics = ["Continue current topic"]

    return {
        "recommended_topics": next_topics,
        "next_level": level
    }
# =========================
# HINT
# =========================
@app.post("/hint")
def hint(req: HintRequest):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Give a hint: {req.question}"}]
    )

    return {"hint": res.choices[0].message.content}

# =========================
# FEEDBACK
# =========================
@app.post("/feedback")
def feedback(req: FeedbackRequest):
    prompt = f"""
    Score: {req.score}/5
    Topic: {req.topic}

    Give:
    - strengths
    - weaknesses
    - improvements
    """

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return {"feedback": res.choices[0].message.content}

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(req: ChatRequest):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": req.message}]
    )

    return {"response": res.choices[0].message.content}

# =========================
# ENGAGEMENT TRACKING
# =========================
@app.post("/track")
def track(data: EngagementRequest):
    db = SessionLocal()
    try:
        db.add(EngagementTable(**data.dict()))
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

# =========================
# ANALYTICS
# =========================

@app.post("/analytics")
def save_analytics(data: AnalyticsRequest):

    db = SessionLocal()

    try:
        record = AnalyticsTable(
            username=data.username,
            topic=data.topic,
            time_spent=data.time_spent,
            quiz_attempt_number=data.quiz_attempt_number,
            hints_used=data.hints_used,
            score=data.score
        )

        db.add(record)
        db.commit()

        return {"status": "success"}

    finally:
        db.close()


@app.get("/analytics/{username}")
def get_analytics(username: str):

    db = SessionLocal()

    try:
        data = db.query(AnalyticsTable)\
                 .filter_by(username=username)\
                 .all()

        return [
            {
                "topic": x.topic,
                "time_spent": x.time_spent,
                "quiz_attempt_number": x.quiz_attempt_number,
                "hints_used": x.hints_used,
                "score": x.score,
                "date": x.date.strftime("%Y-%m-%d %H:%M:%S")
            }
            for x in data
        ]

    finally:
        db.close()
# =========================
# RUN SERVER
# =========================
@app.get("/admin_stats")
def admin_stats():

    db = SessionLocal()

    try:
        total_users = db.query(UserTable).count()

        total_quizzes = db.query(AnalyticsTable).count()

        avg_score = db.query(
            func.avg(AnalyticsTable.score)
        ).scalar()

        popular_topic = db.query(
            AnalyticsTable.topic,
            func.count(AnalyticsTable.topic)
        ).group_by(
            AnalyticsTable.topic
        ).order_by(
            func.count(AnalyticsTable.topic).desc()
        ).first()

        difficulty_distribution = db.query(
            ScoreTable.level,
            func.count(ScoreTable.level)
        ).group_by(
            ScoreTable.level
        ).all()

        return {
            "total_users": total_users,
            "total_quizzes": total_quizzes,
            "average_score": round(avg_score or 0, 2),
            "most_popular_topic": popular_topic[0] if popular_topic else "N/A",
            "difficulty_distribution": [
                {
                    "level": row[0],
                    "count": row[1]
                }
                for row in difficulty_distribution
            ]
        }

    finally:
        db.close()
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
