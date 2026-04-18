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
        You are an expert tutor and data analyst for a master's thesis.
        Your goal is to answer the user's questions and proactively suggest what they should study next based on their learning data.

        STUDENT DATA (Filtered by current topic):
        {context_data if context_data else "No specific data for this topic."}

        SUGGESTION RULES (Next Query Suggestion):
        Always end your response with 2 or 3 suggested follow-up questions or exercises for the student. Use these rules based on the data above:
        - If 'knowledge_score' is low (< 1.0), suggest queries to learn the basics of that Subtopic.
        - If 'knowledge_score' is high but 'lapse_score' is also high (meaning they haven't practiced in a while), suggest a quick review or a challenge query to refresh their memory.
        - If they are doing great in both, suggest advancing to the next logical complex Subtopic.

        Response style:
        - Be encouraging, clear, and concise.
        - If you don't have data for a specific concept, answer based on your general knowledge but don't invent scores.
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


def extract_topic_from_query(api_key: str, model: str, user_prompt: str, unique_topics: list) -> str:
    client = genai.Client(api_key=api_key)
    topics_str = ", ".join(unique_topics)
    
    router_prompt = (
        f"Analyze this user query: '{user_prompt}'\n"
        f"Which of the following topics does it belong to? [{topics_str}]\n\n"
        "Reply ONLY with the exact Topic name from the list. "
        "If it doesn't match any specific topic, reply as if the user has zero knowledge of it."
    )
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=router_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0, # Temperatura a 0 per avere output deterministici
            ),
        )
        topic = (response.text or "General").strip()
        # Controllo di sicurezza: se l'LLM ha allucinato e generato testo extra, forziamo General
        if topic not in unique_topics:
            return "General"
        return topic
    except Exception as e:
        print(f"Router error: {e}")
        return "General"


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
    st.title("Tutor AI - Context-Aware")
    st.caption("Chiedimi spiegazioni. Ti suggerirò cosa ripassare in base ai tuoi voti!")
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

    # 1. Carica il dataset completo all'avvio (ma non lo passa ancora all'LLM)
    try:
        full_context_data = load_context_data(int(student_id))
        unique_topics = full_context_data['Topic'].unique().tolist() if not full_context_data.empty else []
    except Exception as exc:
        full_context_data = pd.DataFrame()
        unique_topics = []
        st.error(f"Impossibile caricare i dati: {exc}")

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

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # [NUOVO] STEP 1: L'LLM capisce l'argomento (Router)
                detected_topic = extract_topic_from_query(api_key, model, user_prompt, unique_topics)
                
                # [NUOVO] STEP 2: Filtriamo il dataframe
                if detected_topic != "General" and not full_context_data.empty:
                    filtered_df = full_context_data[full_context_data['Topic'] == detected_topic]
                    context_text = filtered_df.to_string(index=False)
                    st.info(f"🔍 Argomento individuato: **{detected_topic}**. Trovate {len(filtered_df)} metriche.")
                else:
                    context_text = "Nessuna metrica specifica trovata o domanda troppo generica."
                    st.info("🔍 Argomento generico. Rispondo usando la conoscenza di base.")

                # Costruiamo il prompt solo con i dati filtrati
                system_prompt = build_system_prompt(context_text)
                history_text = build_history_text(st.session_state.messages[:-1])

                # [NUOVO] STEP 3: Generiamo la risposta con le suggestion personalizzate
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


