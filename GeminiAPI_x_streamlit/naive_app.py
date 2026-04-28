import os
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

# DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MODEL = "gemini-2.5-flash"

def log_token_usage(step_name: str, usage_metadata, latency_seconds: float = 0.0):
    """Save token usage and latency data to a CSV file."""
    if not usage_metadata:
        return
        
    log_file = "token_usage_log.csv"
    
    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Step": step_name,
        "Input Tokens (Prompt)": usage_metadata.prompt_token_count,
        "Output Tokens (Answer)": usage_metadata.candidates_token_count,
        "Total Tokens": usage_metadata.total_token_count,
        "Latency (s)": round(latency_seconds, 2)
    }])
    
    if not os.path.exists(log_file):
        new_data.to_csv(log_file, index=False)
    else:
        new_data.to_csv(log_file, mode='a', header=False, index=False)

def build_system_prompt(context_data: str) -> str:
    return f"""
You are an expert consultant and advisor.
Your goal is to answer the user's questions and proactively suggest what they should study next based on their learning data.

ENTIRE STUDENT DATABASE:
{context_data if context_data else "No data available."}

CONVERSATION & PROACTIVITY RULES:
1. Identify the relevant topic from the database above based on the user's prompt.
2. Answer the user's specific request FIRST.
3. PROACTIVITY: Guide the user naturally based on their data. NEVER copy-paste recommendations.
4. RECOMMENDATION MATRIX:
   - 'Extremely low' / 'Low knowledge': Suggest foundational basics.
   - 'Extremely lapsed' / 'Highly lapsed' (with moderate knowledge): Suggest quick memory refreshers.
   - 'High' / 'Extremely high knowledge': Suggest advanced problems/applications.
   - 'Not lapsed' / 'Slightly lapsed' (with low knowledge): Focus on practice.
5. INTEREST SCORE: 
    - If the user has a 'High interest' score, suggest engaging, real-world applications. If 'Low interest', suggest ways to spark curiosity.
    - If the user asks for suggestions, keep in mind to provide suggestions that are in line with their interest level.
    - If you have to use general knowledge due to lack of data, use the interest score to guide your suggestions.

Response style:
- Be encouraging, conversational, and concise.
- Avoid robotic "Next Steps" headers. Integrate naturally.
""".strip()

def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []

def get_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")

def build_history_text(messages, max_turns: int = 1) -> str:
    if not messages:
        return ""
    selected = messages[-(max_turns * 2) :]
    lines = []
    for msg in selected:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)

def load_context_data(student_id: int) -> pd.DataFrame:
    if not os.path.exists("context_data.csv"):
        return pd.DataFrame()
    return pd.read_csv("context_data.csv")
        
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

    try:
        start_time = time.time()
            
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        
        latency = time.time() - start_time
        log_token_usage("Generator (NAIVE RAG - Full DB)", response.usage_metadata, latency)
        
        return (response.text or "").strip()
    except Exception as e:
        print(f"Generation error: {e}")
        return f"Error: {e}"

def main():
    st.set_page_config(page_title="Naive Consultant (No Router)", layout="wide")
    st.title("Naive RAG (Full DB Test)")
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
    except Exception as e:
        full_df = pd.DataFrame()
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
        with st.spinner("Processing entire database..."):
            try:
                # DUMP DELL'INTERO DATAFRAME
                if not full_df.empty:
                    # Includiamo 'Topic' perché il modello naive deve capire le categorie da solo,
                    # e passiamo le Category semantiche al posto degli score crudi.
                    df_slim = full_df[['Topic', 'Subtopic', 'knowledge_category', 'lapse_category', 'interest_category']]
                    context_text = df_slim.to_csv(index=False)
                else:
                    context_text = ""

                system_prompt = build_system_prompt(context_text)
                history_text = build_history_text(st.session_state.messages[:-1], max_turns=1)

                # Chiamata diretta senza routing
                reply = call_gemini(api_key, model, system_prompt, history_text, user_prompt, temperature)
                
            except Exception as e:
                reply = f"Error during generation: {e}"

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()