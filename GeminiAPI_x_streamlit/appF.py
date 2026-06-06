import os
import json
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time
from datetime import datetime
import traceback
import math

load_dotenv()
DEFAULT_MODEL_LITE = "gemini-2.5-flash-lite"
DEFAULT_MODEL_PRO = "gemini-2.5-flash"

def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "active_topics" not in st.session_state:
        st.session_state.active_topics = []

def get_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")

def build_system_prompt(context_data: str, verbosity: str = "concise") -> str:
    length_rules = {
        "short": "Keep your answer extremely brief. Maximum 2 sentences.",
        "concise": "Provide a balanced, concise response. Use short paragraphs and bullets.",
        "detailed": "Provide a comprehensive explanation with multiple paragraphs and headers."
    }
    
    selected_rule = length_rules.get(verbosity, length_rules["concise"])

    return f"""
You are an expert consultant and advisor.
                
STUDENT DATA:
{context_data if context_data else "No specific data for the current concepts."}
                
LENGTH AND STYLE CONSTRAINT:
- {selected_rule}
- Be encouraging, conversational, and avoid robotic headers like "Next Steps".

CONVERSATION & PROACTIVITY RULES:
1. Answer the user's specific request FIRST, using your general knowledge to provide a DEEP and HELPFUL answer if the provided STUDENT DATA does not strictly match the user's current topic.
2. CONDITIONAL PROACTIVITY: Do NOT force a pivot to the profile data in every single turn. If the user is introducing a completely new topic or has an urgent request (e.g., "I have a test", "Help me understand X"), dedicate 100% of your response to helping them with that specific subject. Only pivot to proactive recommendations (e.g., "By the way, looking at your profile...") if the user's primary problem is fully resolved or they are just chatting generally.
3. RECOMMENDATION MATRIX:
   - 'Extremely low' / 'Low knowledge': Suggest foundational basics.
   - 'Extremely lapsed' / 'Highly lapsed' (with moderate knowledge): Suggest quick memory refreshers.
   - 'High' / 'Extremely high knowledge': Suggest advanced problems/applications.
   - 'Not lapsed' / 'Slightly lapsed' (with low knowledge): Focus on practice.
4. If the user asks for advice on how to improve, ALWAYS provide 2-3 specific, actionable suggestions based on their scores.
5. INTEREST SCORE: 
    - If the user has a 'High interest' score, suggest engaging, real-world applications. If 'Low interest', suggest ways to spark curiosity.
    - If the user asks for suggestions, keep in mind to provide suggestions that are in line with their interest level.
    - If you have to use general knowledge due to lack of data, use the interest score to guide your suggestions.
""".strip()

def build_history_text(messages, max_turns: int = 3) -> str:
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
        
    df = pd.read_csv("context_data.csv")
    now = datetime.now()
    
    if 'last_interaction_date' in df.columns:
        df['last_interaction_date'] = pd.to_datetime(df['last_interaction_date'], format='mixed', errors='coerce')
        
        def calculate_lapse(row):
            delta_days = (now - row['last_interaction_date']).days
            S = 30 + (row.get('knowledge_score', 50) / 2.0)
            decay = 100 * math.exp(-max(delta_days, 0) / S)
            return decay

        df['lapse_score'] = df.apply(calculate_lapse, axis=1)
        
        bins = [0, 20, 40, 60, 80, 100]
        lapse_labels = ['Extremely lapsed', 'Highly lapsed', 'Moderately lapsed', 'Slightly lapsed', 'Not lapsed']
        df['lapse_category'] = pd.cut(df['lapse_score'], bins=bins, labels=lapse_labels, include_lowest=True)
        
    return df

def extract_relevant_topics(api_key: str, model: str, user_prompt: str, unique_topics: list, active_topics: list, topic_mapping_str: str) -> list:
    """FLAT Multi-label router: uses only macro-topics without hierarchical dict."""
    if not unique_topics:
        return []
        
    client = genai.Client(api_key=api_key)
    active_str = ",".join(active_topics) if active_topics else "None"
    
    router_prompt = (
        f"Previous Active Topics: [{active_str}]\n\n"
        f"Current User Query: '{user_prompt}'\n\n"
        f"Available Database Topics:\n[{topic_mapping_str}]\n\n"
        "Task: Analyze the user query IN CONTEXT of the Previous Active Topics.\n"
        "Apply these STRICT rules to output ONLY a JSON array of exact string matches representing the MAIN Topics:\n"
        "1. IMPLICIT CONTINUATION & RESOURCES: If the query asks for study resources, OR answers an AI question, output the EXACT 'Previous Active Topics'.\n"
        "2. FUZZY MAPPING: Look at the 'Available Database Topics'. Select the closest conceptual match to the user's query. If nothing is relevant, return an empty array [].\n"
        "Return ONLY a JSON array of strings containing MAIN Topics."
    )

    try:
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=router_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={"type": "ARRAY", "items": {"type": "STRING"}},
            ),
        )
        latency = time.time() - start_time
        log_token_usage("Router_Flat", response.usage_metadata, latency)
        
        extracted_topics = json.loads(response.text)
        return [t for t in extracted_topics if t in unique_topics]
        
    except Exception as e:
        print(f"Routing error: {e}")
        return []
    
def log_token_usage(step_name: str, usage_metadata, latency_seconds: float = 0.0):
    """Save token usage and latency data to a CSV file."""
    if not usage_metadata:
        return
        
    log_file = "token_usage_log.csv"
    
    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Step": step_name,
        "Input Tokens": usage_metadata.prompt_token_count,
        "Output Tokens": usage_metadata.candidates_token_count,
        "Total Tokens": usage_metadata.total_token_count,
        "Latency (s)": round(latency_seconds, 2)
    }])
    
    if not os.path.exists(log_file):
        new_data.to_csv(log_file, index=False)
    else:
        new_data.to_csv(log_file, mode='a', header=False, index=False)

def log_chat_interaction(architecture: str, user_query: str, ai_response: str, active_topics: str = "All (Naive)"):
    """Save chat interaction logs to a CSV file for thesis case study analysis."""
    log_file = "chat_logs.csv"
    
    safe_query = user_query.replace('\n', ' ').replace('\r', '')
    safe_response = ai_response.replace('\n', ' \\n ')
    
    new_data = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Architecture": architecture,
        "Active_Topics": active_topics,
        "User_Query": safe_query,
        "AI_Response": safe_response
    }])
    
    if not os.path.exists(log_file):
        new_data.to_csv(log_file, index=False)
    else:
        new_data.to_csv(log_file, mode='a', header=False, index=False)

def update_context_data(student_id: int, topic: str, subtopic: str, inter_k: float, inter_i: float, file_path: str = "context_data.csv"):
    """Apply EMA to scores and recalculate categories."""
    ALPHA = 0.8 
    
    if not os.path.exists(file_path):
        cols = ['student_id', 'Topic', 'Subtopic', 'lapse_score', 'knowledge_score', 'interest_score', 'lapse_category', 'knowledge_category', 'interest_category', 'last_interaction_date']
        df = pd.DataFrame(columns=cols)
    else:
        df = pd.read_csv(file_path)
        for col in ['knowledge_score', 'lapse_score', 'interest_score']:
            if col in df.columns:
                df[col] = df[col].astype(float)
                
    df['student_id'] = df['student_id'].astype(int)
    student_id_clean = int(student_id)
    
    df['Topic'] = df['Topic'].astype(str).str.strip()
    df['Subtopic'] = df['Subtopic'].astype(str).str.strip()
    
    topic_clean = str(topic).strip()
    subtopic_clean = str(subtopic).strip()
    
    mask = (df['student_id'] == student_id_clean) & (df['Topic'] == topic_clean) & (df['Subtopic'] == subtopic_clean)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if df[mask].empty:
        new_row = pd.DataFrame([{
            'student_id': student_id_clean,
            'Topic': topic_clean,
            'Subtopic': subtopic_clean,
            'knowledge_score': float(inter_k),
            'lapse_score': 100.0,
            'interest_score': float(inter_i),
            'knowledge_category': 'Moderate knowledge',
            'lapse_category': 'Not lapsed',
            'interest_category': 'Moderate interest',
            'last_interaction_date': now_str
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        old_k = df.loc[mask, 'knowledge_score'].values[0]
        old_i = df.loc[mask, 'interest_score'].values[0]
        
        df.loc[mask, 'knowledge_score'] = (old_k * ALPHA) + (inter_k * (1 - ALPHA))
        df.loc[mask, 'lapse_score']     = 100.0
        df.loc[mask, 'interest_score']  = (old_i * ALPHA) + (inter_i * (1 - ALPHA))
        df.loc[mask, 'last_interaction_date'] = now_str
    
    bins = [0, 20, 40, 60, 80, 100]
    
    lapse_labels = ['Extremely lapsed', 'Highly lapsed', 'Moderately lapsed', 'Slightly lapsed', 'Not lapsed']
    know_labels = ['Extremely low knowledge', 'Low knowledge', 'Moderate knowledge', 'High knowledge', 'Extremely high knowledge']
    int_labels = ['Extremely low interest', 'Low interest', 'Moderate interest', 'High interest', 'Extremely high interest']

    df['lapse_category'] = pd.cut(df['lapse_score'], bins=bins, labels=lapse_labels, include_lowest=True)
    df['knowledge_category'] = pd.cut(df['knowledge_score'], bins=bins, labels=know_labels, include_lowest=True)
    df['interest_category'] = pd.cut(df['interest_score'], bins=bins, labels=int_labels, include_lowest=True)
    
    df.to_csv(file_path, index=False)
        
def evaluate_and_update_scores(api_key: str, student_id: int, context_text: str, user_query: str, tutor_response: str):
    """LLM-as-a-Judge to evaluate the interaction with a score 0-100."""
    client = genai.Client(api_key=api_key)
    
    judge_prompt = f"""
    You are an educational data analyst. Evaluate the student's performance in this specific interaction.
    
    CURRENT STATE (Reference Data):
    {context_text if context_text else "No relevant previous data found for this interaction."}

    INTERACTION:
    User Query: "{user_query}"
    Tutor Response: "{tutor_response}"
    
    CRITICAL DECISION (THE BYPASS RULE):
    Determine if this interaction is a "Learning/Exploration Event" (discussing concepts, theories, facts, academic subjects) OR a "Task/Execution Event" (asking the AI to plan a trip, give career advice, generate a quiz, summarize a text).
    If it is a Task/Execution Event, set "is_valid_tracking_event" to FALSE and set all other fields to null/empty/0. Do not track tasks.

    SCORING RULES (Only if is_valid_tracking_event is TRUE):
    1. interaction_knowledge: 0 to 100.
    2. interaction_interest: 0 to 100.
    
    CRITICAL INSTRUCTIONS FOR TOPIC SELECTION (Only if is_valid_tracking_event is TRUE):
    - Step 1 (GREEDY MATCHING): Review the CURRENT STATE. Can the core subject of this interaction be reasonably grouped under an existing Subtopic? If yes, reuse it.
    - Step 2: If a match is found, set "is_new_topic" to false. EXACTLY COPY-PASTE the "Topic" and "Subtopic" strings.
    - Step 3: Set "is_new_topic" to true ONLY IF the interaction represents a complete paradigm shift to a drastically different academic subject.
    - Step 4: If creating a new topic, it MUST be a pure knowledge domain. 
    """
    
    try:
        time.sleep(2.5)
        
        start_time = time.time()
        response = client.models.generate_content(
            model=DEFAULT_MODEL_LITE, 
            contents=judge_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "is_valid_tracking_event": {"type": "BOOLEAN"},
                        "is_new_topic": {"type": "BOOLEAN"},
                        "topic": {"type": "STRING"},
                        "subtopic": {"type": "STRING"},
                        "interaction_knowledge": {"type": "NUMBER"},
                        "interaction_interest": {"type": "NUMBER"}
                    },
                    "required": ["is_valid_tracking_event"] # Gli altri non sono più strettamente required se facciamo bypass
                }
            )
        )
        
        latency = time.time() - start_time
        log_token_usage("Evaluator_Flat", response.usage_metadata, latency)
        
        if not response.text:
             print("Background evaluation failed.")
             return
             
        result = json.loads(response.text)
        
        if not result.get("is_valid_tracking_event", True):
             print("Task Execution detected: Bypass database update. No state tracked.")
             return
         
        update_context_data(
            student_id=student_id,
            topic=result["topic"],
            subtopic=result["subtopic"],
            inter_k=result["interaction_knowledge"],
            inter_i=result["interaction_interest"]
        )
        print(f"EMA Update Success for: {result['subtopic']}")
        
    except Exception as e:
        print(f"Background evaluation failed: {e}")
        traceback.print_exc()

def call_gemini(api_key: str, model: str, system_prompt: str, history_text: str, user_prompt: str, temperature: float) -> str:
    client = genai.Client(api_key=api_key)
    full_prompt = (
        f"{system_prompt}\n\n"
        "You can search the web when up-to-date information is needed.\n\n"
        f"Conversation history:\n{history_text if history_text else 'No previous messages.'}\n\n"
        f"User question:\n{user_prompt}"
    )
    
    try:
        time.sleep(2.5) 
        
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                tools=[{"google_search": {}}], 
            ),
        )
        
        latency = time.time() - start_time
        log_token_usage("Generator_Flat", response.usage_metadata, latency)
        
        if not response.text:
            return "Errore: La risposta restituita è vuota. Potrebbe essere intervenuto un filtro di sicurezza."
            
        return response.text.strip()
        
    except Exception as e:
        traceback.print_exc()
        return f"Errore durante la generazione: {str(e)}"
        
def main():
    st.set_page_config(page_title="Context-Aware Consultant", layout="wide")
    st.title("Intelligent RAG Consultant (FLAT)")

    ensure_state()

    with st.sidebar:
        st.header("Configuration")
        student_id = st.number_input("Student ID", min_value=1, value=80, step=1)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.4, 0.1)
        if st.button("Reset Chat"):
            st.session_state.messages = []
            st.session_state.active_topics = []
            st.rerun()

    api_key = get_api_key()

    try:
        full_df = load_context_data(int(student_id))
        if not full_df.empty:
            unique_topics = full_df['Topic'].unique().tolist()
            topic_mapping_str = ", ".join(unique_topics)
        else:
            unique_topics = []
            topic_mapping_str = "None"
    except Exception as e:
        full_df = pd.DataFrame()
        unique_topics = []
        topic_mapping_str = "None"
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
                # 1. Routing (FLAT)
                target_topics = extract_relevant_topics(
                    api_key, 
                    DEFAULT_MODEL_LITE, 
                    user_prompt, 
                    unique_topics, 
                    st.session_state.active_topics,
                    topic_mapping_str
                )
                
                # 2. Context Extraction
                if target_topics and not full_df.empty:
                    st.session_state.active_topics = target_topics 
                    filtered_df = full_df[full_df['Topic'].isin(target_topics)]
                    df_slim = filtered_df[['Topic', 'Subtopic', 'knowledge_category', 'lapse_category', 'interest_category']]
                    context_text = df_slim.to_csv(index=False)
                    st.info(f"🎯 Found {len(filtered_df)} records for topics: {', '.join(target_topics)}")
                else:
                    st.session_state.active_topics = [] 
                    context_text = ""
                    st.info("🌐 No relevant topics found. Using general knowledge.")

                system_prompt = build_system_prompt(context_text)
                history_text = build_history_text(st.session_state.messages[:-1], max_turns=3)

                reply = call_gemini(api_key, DEFAULT_MODEL_PRO, system_prompt, history_text, user_prompt, temperature)
                
            except Exception as e:
                reply = f"Error during processing: {e}"
                traceback.print_exc()

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            
            if "Errore" not in reply and "Error" not in reply:
                topics_str = ", ".join(st.session_state.active_topics) if st.session_state.active_topics else "None"
                log_chat_interaction(
                    architecture="FRB",
                    user_query=user_prompt,
                    ai_response=reply,
                    active_topics=topics_str
                )
            
            # 4. Closed-Loop Update (Background)
            if "Errore" not in reply and "Error" not in reply:
                evaluate_and_update_scores(
                    api_key=api_key,
                    student_id=int(student_id),
                    context_text=context_text,
                    user_query=user_prompt,
                    tutor_response=reply
                )
                
if __name__ == "__main__":
    main()