from multiprocessing import context
import os
from datetime import timedelta

import pandas as pd
import numpy as np
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()



def build_system_prompt(context_data: str) -> str:
    return f"""
You are an expert data analyst for a master's thesis.
You have access to the tables and documents loaded below.

AVAILABLE DATA:
{context_data}

JOIN RULES:
1. Files are linked through common keys (for example STUDENT_ID, COURSE_CODE).
2. If information is missing in one table, look for it in the others using the keys.
3. If you find naming differences (for example Student vs User), treat them as the same entity.

Response style:
- Be clear and concise.
- If data is missing, say so explicitly.
""".strip()


def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []


def get_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")


def build_history_text(messages, max_turns: int = 8) -> str:
    if not messages:
        return ""
    selected = messages[-(max_turns * 2) :]
    lines = []
    for msg in selected:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def load_context_data(student_id: int) -> pd.DataFrame:
    """path = "context/Assessment_Information.xlsx"
    df = pd.read_excel(path)
    required_cols = {"student_id", "date", "Algorithm_level", "answer", "Topic", "Subtopic"}
    missing = required_cols.difference(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")

    filtered = df[df["student_id"] == student_id].copy()
    filtered['answer'] = filtered['answer'].replace(-1, 0)
    if filtered.empty:
        return pd.DataFrame(columns=["Topic", "Subtopic", "knowledge_score"])

    filtered["date"] = pd.to_datetime(filtered["date"])
    last_interaction = filtered["date"].max()
    filtered["days_since_last_interaction"] = (last_interaction - filtered["date"]).dt.days

    step_1 = timedelta(days=15)
    step_2 = timedelta(days=30)
    step_3 = timedelta(days=60)

    filtered["lapse_score"] = pd.cut(
        filtered["days_since_last_interaction"],
        bins=[-1, step_1.days, step_2.days, step_3.days, float("inf")],
        labels=["1", "0.6", "0.3", "0.1"],
    )

    filtered["lapse_score"] = filtered["lapse_score"].astype(float)
    
    filtered["knowledge_score"] = (
        filtered["Algorithm_level"] * filtered["lapse_score"] * filtered["answer"]
    )
    
    filtered["Subtopic"] = filtered["Subtopic"].fillna(filtered["Topic"])
    
    result = (
        filtered[["Topic", "Subtopic", "lapse_score", "knowledge_score"]]
        .groupby(["Topic", "Subtopic"], as_index=False)
        .agg({"lapse_score": "sum", "knowledge_score": "sum"})
    )
    
    result["lapse_score"] = 1/result["lapse_score"]
    """
    
    result = pd.read_csv("context_data.csv")
    max_lapse = result['lapse_score'].max()
    min_lapse = result['lapse_score'].min()
    result['lapse_score'] = np.random.uniform(min_lapse, max_lapse, len(result)).round(3)
    
    max_knowledge = result['knowledge_score'].max()
    min_knowledge = result['knowledge_score'].min()
    result['knowledge_score'] = np.random.uniform(min_knowledge, max_knowledge, len(result)).round(3)
    
    result["lapse_score"] = 1/result["lapse_score"]

    return result


def call_gemini(
    api_key: str,
    model: str,
    system_prompt: str,
    history_text: str,
    user_prompt: str,
    temperature: float,
) -> str:
    client = genai.Client(api_key=api_key)
    full_prompt = (
        f"{system_prompt}\n\n"
        "You can search the web when the question needs up-to-date or external information.\n\n"
        f"Conversation so far:\n{history_text if history_text else 'No previous messages.'}\n\n"
        f"User question:\n{user_prompt}"
    )
    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return (response.text or "").strip()


def main():
    st.set_page_config(page_title="Gemini Assistant", page_icon="AI", layout="wide")
    st.title("Gemini API - Simple Interface")
    st.caption("Ask questions with a small context-aware assistant.")
    model = "gemini-2.5-flash"

    ensure_state()

    with st.sidebar:
        st.header("Settings")
        student_id = st.number_input("Student ID", min_value=1, value=80, step=1)
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.1)
        st.caption(f"Model: {model}")
        if st.button("Clear chat"):
            st.session_state.messages = []
            st.rerun()

    api_key = get_api_key()

    try:
        context_data = load_context_data(int(student_id))
        context_text = context_data.to_string(index=False) if not context_data.empty else "No rows for this student."
    except Exception as exc:
        context_text = f"Context unavailable: {exc}"

    with st.expander("Preview context", expanded=False):
        st.text(context_text)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_prompt = st.chat_input("Write your question...")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not api_key:
        warning = "Missing GEMINI_API_KEY in .env file."
        st.session_state.messages.append({"role": "assistant", "content": warning})
        with st.chat_message("assistant"):
            st.warning(warning)
        return

    system_prompt = build_system_prompt(context_text)
    history_text = build_history_text(st.session_state.messages[:-1])

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply = call_gemini(
                    api_key,
                    model,
                    system_prompt,
                    history_text,
                    user_prompt,
                    temperature,
                )
                if not reply:
                    reply = "No response text returned by Gemini."
            except Exception as exc:
                reply = f"Gemini request failed: {exc}"

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()


