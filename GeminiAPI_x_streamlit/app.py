import os
import json
import pandas as pd
import numpy as np
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash-lite"

def log_token_usage(step_name: str, usage_metadata):
    """Save token usage data to a CSV file for later analysis."""
    if not usage_metadata:
        return
        
    log_file = "token_usage_log.csv"
    
    # Prepariamo la riga con i dati
    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Step": step_name,
        "Input Tokens (Prompt)": usage_metadata.prompt_token_count,
        "Output Tokens (Risposta)": usage_metadata.candidates_token_count,
        "Total Tokens": usage_metadata.total_token_count
    }])
    
    if not os.path.exists(log_file):
        new_data.to_csv(log_file, index=False)
    else:
        new_data.to_csv(log_file, mode='a', header=False, index=False)

def evaluate_tutor_response(api_key: str, question: str, target_topics: list, tutor_reply: str) -> dict:
    """An LLM judge that evaluates the consultant's response."""
    
    client = genai.Client(api_key=api_key)
    
    judge_prompt = f"""
    You are an LLM judge that evaluates the consultant's response.
    
    Interaction data:
    - User's question: "{question}"
    - Topics identified by the Router: {target_topics}
    - Consultant's response: "{tutor_reply}"
    
    EVALUATION CRITERIA:
    1. Router Accuracy: Did the consultant use the correct topic information?
    2. Proactivity: Did the consultant provide 2-3 follow-up suggestions as requested?
    3. Tone: Is the tone encouraging and teacher-like?
    
    Evaluate the response by assigning a score from 1 to 10 for each criterion.
    """
    
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=judge_prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "router_score": {"type": "INTEGER"},
                    "proactivity_score": {"type": "INTEGER"},
                    "tone_score": {"type": "INTEGER"},
                    "feedback_notes": {"type": "STRING"}
                },
                "required": ["router_score", "proactivity_score", "tone_score", "feedback_notes"]
            }
        )
    )
    
    return json.loads(response.text)

def build_system_prompt(context_data: str) -> str:
    return f"""
You are an expert consultant and advisor for every task of the user.
Your goal is to answer the user's questions and proactively suggest what they should study next based on their learning data.

STUDENT DATA (Filtered by relevant topics):
{context_data if context_data else "No specific data for the current concepts."}

CONVERSATION & PROACTIVITY RULES:
1. Answer the user's specific request FIRST.
2. PROACTIVITY (Next Query Suggestion): You must guide the user's learning, BUT do it naturally. 
   - Suggest next steps ONLY when the user has completed a task, solved an exercise, or is asking for direction.
   - NEVER copy-paste or repeat the same exact recommendations across multiple messages. 
3. When you DO suggest next steps, use the scores:
   - low 'knowledge_score' -> suggest foundational basics.
   - high 'knowledge_score' & high 'lapse_score' -> suggest quick memory refreshers.
   - optimal scores -> suggest complex/advanced subtopics.

Response style:
- Be encouraging, conversational, and concise.
- Avoid robotic, repetitive "Next Steps" headers. Integrate your suggestions naturally into the dialogue.
""".strip()

def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "active_topics" not in st.session_state:
        st.session_state.active_topics = []

def get_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")

def build_history_text(messages, max_turns: int = 2) -> str:
    if not messages:
        return ""
    selected = messages[-(max_turns * 2) :]
    lines = []
    for msg in selected:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)

def load_context_data(student_id: int) -> pd.DataFrame:
    # Simulated loading process
    if not os.path.exists("context_data.csv"):
        return pd.DataFrame()
        
    result = pd.read_csv("context_data.csv")
    
    return result

def extract_relevant_topics(api_key: str, model: str, user_prompt: str, unique_topics: list, active_topics: list) -> list:
    """
    Multi-label router with State Tracking.
    """
    if not unique_topics:
        return []
        
    client = genai.Client(api_key=api_key)
    topics_str = ",".join(unique_topics)
    
    # Handle the first turn where active_topics might be empty
    active_str = ",".join(active_topics) if active_topics else "None"
    
    router_prompt = (
        f"Previous Active Topics: [{active_str}]\n\n"
        f"Current User Query: '{user_prompt}'\n\n"
        f"Available Topics: [{topics_str}]\n\n"
        "Task: Analyze the user query.\n"
        "1. If the query is ambiguous (e.g., 'give me an exercise', 'tell me more', 'let's continue') and implicitly refers to the ongoing conversation, output the 'Previous Active Topics'.\n"
        "2. If the query introduces a explicitly NEW subject (e.g., 'let's talk about History now'), ignore the previous topics and select the new relevant topics from the 'Available Topics'.\n"
        "Return ONLY a JSON array of exact string matches."
    )
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=router_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={"type": "ARRAY", "items": {"type": "STRING"}},
            ),
        )
        
        # log_token_usage("Router (Topic Extraction)", response.usage_metadata)
        
        extracted_topics = json.loads(response.text)
        valid_topics = [t for t in extracted_topics if t in unique_topics]
        return valid_topics
        
    except Exception as e:
        print(f"Routing error: {e}")
        return []
        
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
        "You can search the web when up-to-date information is needed.\n\n"
        f"Conversation history:\n{history_text if history_text else 'No previous messages.'}\n\n"
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
    
    log_token_usage("Generator (Main RAG)", response.usage_metadata)
    
    return (response.text or "").strip()

def main():
    st.set_page_config(page_title="Context-Aware Consultant", layout="wide")
    st.title("Intelligent RAG Consultant")
    model = DEFAULT_MODEL

    ensure_state()

    with st.sidebar:
        st.header("Configuration")
        student_id = st.number_input("Student ID", min_value=1, value=80, step=1)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.4, 0.1)
        if st.button("Reset Chat"):
            st.session_state.messages = []
            st.rerun()

    api_key = get_api_key()

    try:
        full_df = load_context_data(int(student_id))
        unique_topics = full_df['Topic'].unique().tolist() if not full_df.empty else []
    except Exception as e:
        full_df = pd.DataFrame()
        unique_topics = []
        st.error(f"Data loading failed: {e}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_prompt = st.chat_input("Ask a question...")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not api_key:
        st.error("API Key missing.")
        return

    with st.chat_message("assistant"):
        with st.spinner("Analyzing intent..."):
            try:
                # 1. Chiama il router passando i Topic attivi della sessione precedente
                target_topics = extract_relevant_topics(
                    api_key, 
                    model, 
                    user_prompt, 
                    unique_topics, 
                    st.session_state.active_topics
                )
                
                # 2. Aggiorna immediatamente la memoria per il prossimo turno!
                if target_topics and not full_df.empty:
                    filtered_df = full_df[full_df['Topic'].isin(target_topics)]
                    
                    # Selezioniamo solo 3 colonne, ignorando 'Topic' e i punteggi numerici grezzi
                    df_slim = filtered_df[['Subtopic', 'knowledge_label', 'lapse_label']]
                    context_text = df_slim.to_csv(index=False)
                    st.info(f"🎯 Found {len(filtered_df)} records for topics: {', '.join(target_topics)}")
                else:
                    context_text = ""
                    st.info("🌐 No relevant topics found.")

                system_prompt = build_system_prompt(context_text)
                history_text = build_history_text(st.session_state.messages[:-1])

                # 3. Generation
                reply = call_gemini(api_key, model, system_prompt, history_text, user_prompt, temperature)
                
            except Exception as e:
                reply = f"Error during generation: {e}"

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()