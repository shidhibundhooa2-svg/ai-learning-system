import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time

# =========================
# CONFIG
# =========================
BASE_URL = "https://ai-learning-system-backend.onrender.com"

st.set_page_config(
    page_title="Adaptive AI Learning Platform",
    layout="wide"
)

# =========================
# SESSION STATE INIT
# =========================
def init_state():
    defaults = {
        "quiz_start_time": None,
        "hints_used": 0,
        "role": "",
        "quiz_attempt_number": 0,
        "page": "login",
        "quiz": [],
        "q_index": 0,
        "score": 0,
        "hint": "",
        "username": "",
        "topic": "",
        "recommended_topic": "",
        "level": "Beginner",
        "history": []
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================
# API CALL HELPER
# =========================
def api_post(endpoint, data):
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", json=data)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =========================
# LOGIN PAGE
# =========================
def login_page():
    st.title("🔐 Adaptive AI Learning Platform")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            res = api_post("/login", {"username": username, "password": password})

            if res.get("status") == "success":
                st.session_state.username = username
                st.session_state.role = res.get("role")
                if st.session_state.role == "admin":
                   st.session_state.page = "admin"
                else:
                     st.session_state.page = "dashboard"

                     st.rerun()
            else:
                st.error(res.get("message", "Login failed"))

    with col2:
        if st.button("Register"):
            res = api_post("/register", {"username": username, "password": password})

            if res.get("status") == "success":
                st.success("Account created")
            else:
                st.error(res.get("message", "Registration failed"))

# =========================
# DASHBOARD PAGE
# =========================
def dashboard_page():
    if st.session_state.role == "admin":
        st.session_state.page = "admin"
        st.rerun()

    st.title("📚 Personalized Learning Dashboard")
    st.success(f"Welcome {st.session_state.username}")
    topics = [
    "Python Programming",
    "Machine Learning",
    "Data Science",
    "Artificial Intelligence",
    "Database Systems",
    "Cybersecurity"
    ]

    if (
      "recommended_topic" in st.session_state
      and st.session_state.recommended_topic
     ):
       topics.insert(
           0,
           f"⭐ {st.session_state.recommended_topic}"
    )

    topic = st.selectbox(
     "Select Topic",
     topics
   )    
    # ========================= 
    # LOGOUT 
    # ========================= 
    if st.button("Logout"): 
       st.session_state.page = "login"
       st.session_state.username = "" 
       st.session_state.role = ""
       st.rerun()

    # =========================
    # ADAPTIVE LEVEL
    # =========================
    if st.session_state.history:
        avg = sum(st.session_state.history) / len(st.session_state.history)

        if avg >= 4:
            level = "Advanced"
        elif avg >= 2:
            level = "Intermediate"
        else:
            level = "Beginner"
    else:
        level = "Beginner"

    st.info(f"Adaptive Level: {level}")

    st.session_state.topic = topic
    st.session_state.level = level

    col1, col2 = st.columns(2)

    # =========================
    # NOTES
    # =========================
    with col1:
        if st.button("📖 Generate Notes"):
            res = api_post("/generate", {
                "topic": topic,
                "level": level
            })

            st.markdown("## 📘 Notes")
            st.markdown(res.get("notes", "No notes"))

    # =========================
    # QUIZ
    # =========================
    with col2:
     if st.button("🧠 Generate Quiz"):
        res = api_post(
            "/quiz",
            {
                "topic": topic,
                "level": level
            }
        )

        quiz = res.get("quiz", [])

        if quiz:

            st.session_state.quiz_start_time = time.time()

            st.session_state.hints_used = 0

            st.session_state.quiz_attempt_number += 1

            st.session_state.quiz = quiz
            st.session_state.q_index = 0
            st.session_state.score = 0
            st.session_state.page = "quiz"

            st.rerun()

        else:
            st.error("Quiz failed")
    # =========================
    # CHATBOT
    # =========================
    st.markdown("---")
    st.subheader("🤖 AI Tutor")

    question = st.text_input("Ask something")

    if st.button("Ask"):
        res = api_post("/chat", {"message": question})
        st.success(res.get("response", ""))

    # =========================
    # PROGRESS GRAPH
    # =========================
    st.markdown("---")
    st.subheader("📊 Progress")
    try:
        analytics = requests.get(
            f"{BASE_URL}/analytics/{st.session_state.username}"
        ).json()
        

        if analytics:

            df = pd.DataFrame(analytics)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Quizzes", len(df))

            with col2:
                st.metric(
                    "Hints Used",
                    int(df["hints_used"].sum())
                )

            with col3:
                st.metric(
                    "Average Score",
                    round(df["score"].mean(), 2)
                )

            with col4:
                st.metric(
                    "Time (mins)",
                    round(df["time_spent"].sum() / 60, 2)
                )

            fig = px.line(
                df,
                x="date",
                y="score",
                title="Performance Trend"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Analytics Error: {e}")
# =========================
# Admin PAGE
# =========================
def admin_page():

    if st.session_state.role != "admin":
        st.error("⛔ Access Denied")
        return

    # Logout button
    if st.button("🚪 Logout"):

        st.session_state.page = "login"
        st.session_state.username = ""
        st.session_state.role = ""

        st.rerun()

    st.title("📊 Platform Analytics Dashboard")

    try:
        stats = requests.get(
            f"{BASE_URL}/admin_stats"
        ).json()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Users",
                stats["total_users"]
            )

        with col2:
            st.metric(
                "Total Quizzes",
                stats["total_quizzes"]
            )

        with col3:
            st.metric(
                "Average Score",
                stats["average_score"]
            )

        with col4:
            st.metric(
                "Most Popular Topic",
                stats["most_popular_topic"]
            )

        st.markdown("---")

        st.subheader("Difficulty Distribution")

        df = pd.DataFrame(
            stats["difficulty_distribution"]
        )

        if not df.empty:

            fig = px.pie(
                df,
                names="level",
                values="count",
                title="Difficulty Distribution"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    except Exception as e:
        st.error(str(e))
# =========================
# QUIZ PAGE
# =========================
def quiz_page():

    quiz = st.session_state.quiz
    i = st.session_state.q_index

    st.title("🧠 Quiz")

    # =========================
    # END QUIZ
    # =========================
    if i >= len(quiz):
        score = st.session_state.score

        st.success(f"Final Score: {score}/{len(quiz)}")

        st.session_state.history.append(score)

        api_post(
            "/save_score",
            {
                "username": st.session_state.username,
                "topic": st.session_state.topic,
                "score": score,
                "level": st.session_state.level
            }
        )

        time_spent = int(
            time.time()
            - st.session_state.quiz_start_time
        )

        api_post(
            "/analytics",
            {
                "username": st.session_state.username,
                "topic": st.session_state.topic,
                "time_spent": time_spent,
                "quiz_attempt_number":
                    st.session_state.quiz_attempt_number,
                "hints_used":
                    st.session_state.hints_used,
                "score": score
            }
        )

        feedback = api_post("/feedback", {
            "topic": st.session_state.topic,
            "score": score
        })

        recommend = api_post(
            "/recommend",
            {
                "username": st.session_state.username,
                "topic": st.session_state.topic,
                "score": score
            }
        )

        recommended_topics = recommend.get(
            "recommended_topics",
            []
        )

        if recommended_topics:

            st.session_state.recommended_topic = (
                recommended_topics[0]
            )

            st.markdown("## 📚 Recommended Topics")

            selected_topic = st.selectbox(
                "Choose your next topic",
                 options=recommended_topics
               )

            st.success(
                f"Next: {selected_topic}"
            )
        st.markdown("## 🧠 Feedback")
        st.markdown(feedback.get("feedback", ""))

        st.markdown("## 📚 Recommendation")
        st.markdown(recommend.get("recommendation", ""))

        if st.button("🏠 Back"):
            st.session_state.page = "dashboard"
            st.session_state.q_index = 0
            st.session_state.score = 0
            st.rerun()

        return

    q = quiz[i]

    st.subheader(f"Q{i+1}")
    st.write(q["question"])

    answer = st.radio("Select", q["options"], key=f"q_{i}")

    # =========================
    # HINT
    # =========================
    if st.button("💡 Hint", key=f"h_{i}"):

        st.session_state.hints_used += 1

        res = api_post(
            "/hint",
            {
                "question": q["question"]
            }
        )

        st.session_state.hint = res.get(
            "hint",
            ""
        )

    if st.session_state.hint:
        st.info(st.session_state.hint)

    # =========================
    # SUBMIT
    # =========================
    if st.button("Submit", key=f"s_{i}"):

        if answer == q["answer"]:
            st.success("Correct ✅")
            st.session_state.score += 1
        else:
            st.error("Wrong ❌")
            st.warning(f"Answer: {q['answer']}")

        if "explanation" in q:
            st.info(q["explanation"])

        st.session_state.q_index += 1
        st.session_state.hint = ""
        time.sleep(0.5)
        st.rerun()

    # =========================
    # SIDEBAR
    # =========================
    st.sidebar.title("Progress")
    st.sidebar.write(f"{i+1}/{len(quiz)}")
    st.sidebar.write(f"Score: {st.session_state.score}")

# =========================
# ROUTER
# =========================
if st.session_state.page == "login":
    login_page()

elif st.session_state.page == "dashboard":
    dashboard_page()

elif st.session_state.page == "quiz":
    quiz_page()

elif st.session_state.page == "admin":
    admin_page()
