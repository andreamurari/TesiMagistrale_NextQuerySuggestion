import os
import json
import pandas as pd
import numpy as np
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def build_system_prompt(context_data: str) -> str:
    return f"""
You are an expert consultant and advisor for every task of the user.
Your goal is to answer the user's questions and proactively suggest what they should study next based on their learning data.

STUDENT DATA (Filtered by relevant topics):
{context_data if context_data else "No specific data for the current concepts."}

SUGGESTION RULES (Next Query Suggestion):
Always end your response with 2 or 3 suggested follow-up questions or exercises. 
- If 'knowledge_score' is low (< 1.0), suggest foundational queries.
- If 'knowledge_score' is high but 'lapse_score' is high, suggest quick review queries.
- If both are optimal, suggest advancing to complex subtopics.

Response style:
- Be encouraging, clear, and concise.
- If data is missing, rely on general knowledge but do not invent scores.
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
    # Simulated loading process
    if not os.path.exists("context_data.csv"):
        return pd.DataFrame()
        
    result = pd.read_csv("context_data.csv")
    if result.empty:
        return result
        
    max_lapse = result['lapse_score'].max()
    min_lapse = result['lapse_score'].min()
    result['lapse_score'] = np.random.uniform(min_lapse, max_lapse, len(result)).round(3)
    
    max_knowledge = result['knowledge_score'].max()
    min_knowledge = result['knowledge_score'].min()
    result['knowledge_score'] = np.random.uniform(min_knowledge, max_knowledge, len(result)).round(3)
    
    result["lapse_score"] = 1 / (result["lapse_score"] + 0.001) # Added epsilon to avoid division by zero
    return result

def extract_relevant_topics(api_key: str, model: str, user_prompt: str, unique_topics: list) -> list:
    """
    Multi-label router that returns an array of the most relevant topics.
    Uses Structured Outputs to guarantee a JSON array response.
    """
    if not unique_topics:
        return []
        
    client = genai.Client(api_key=api_key)
    topics_str = ", ".join(unique_topics)
    
    router_prompt = (
        f"User query: '{user_prompt}'\n\n"
        f"Available topics: [{topics_str}]\n\n"
        "Analyze the user query. Identify all relevant topics from the list. "
        "If the query is a broad category (like 'math', 'cooking', or 'art'), select 3 to 5 of the most appropriate foundational sub-disciplines from the available topics. "
        "Return ONLY an array of exact string matches from the provided list. Do not invent topics."
    )
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=router_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                # Enforce JSON array of strings output
                response_schema={
                    "type": "ARRAY", 
                    "items": {"type": "STRING"}
                },
            ),
        )
        
        # Parse the guaranteed JSON array
        extracted_topics = json.loads(response.text)
        
        # Security/Sanity check: keep only valid topics
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
    return (response.text or "").strip()

def main():
    st.set_page_config(page_title="Context-Aware Consultant", layout="wide")
    st.title("Intelligent RAG Consultant")
    model = "gemini-2.5-flash"

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
                # 1. Multi-label routing
                target_topics = extract_relevant_topics(api_key, model, user_prompt, unique_topics)
                
                # 2. DataFrame filtering using .isin() for multiple topics
                if target_topics and not full_df.empty:
                    filtered_df = full_df[full_df['Topic'].isin(target_topics)]
                    context_text = filtered_df.to_string(index=False)
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