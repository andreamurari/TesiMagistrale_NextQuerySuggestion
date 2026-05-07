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
        
    result = pd.read_csv("context_data.csv")
    return result

def extract_relevant_topics(api_key: str, model: str, user_prompt: str, unique_topics: list, active_topics: list, topic_mapping_str: str) -> list:
    """Multi-label router with Hierarchical State Tracking."""
    if not unique_topics:
        return []
        
    client = genai.Client(api_key=api_key)
    active_str = ",".join(active_topics) if active_topics else "None"
    
    router_prompt = (
        f"Previous Active Topics: [{active_str}]\n\n"
        f"Current User Query: '{user_prompt}'\n\n"
        f"Available Database Knowledge (Topic -> Subtopics):\n{topic_mapping_str}\n\n"
        "Task: Analyze the user query IN CONTEXT of the Previous Active Topics.\n"
        "Apply these STRICT rules to output ONLY a JSON array of exact string matches representing the MAIN Topics (e.g., 'Physics', 'History'):\n"
        "1. IMPLICIT CONTINUATION & RESOURCES: If the query is ambiguous, asks for study resources (e.g., 'YouTube channels', 'books'), OR answers a question the AI just asked, output the EXACT 'Previous Active Topics'.\n"
        "2. META-QUERIES: If the user asks about their grades, status, progress, or situation, DO NOT invent topics. Output the 'Previous Active Topics'.\n"
        "3. HIERARCHICAL MAPPING: Look at the 'Available Database Knowledge'. If the user's query matches any of the specific Subtopics (e.g., 'Fluid Dynamics'), you MUST output its parent MAIN Topic (e.g., 'Physics').\n"
        "4. TOPIC SWITCH: If the query introduces a NEW subject not found in the Database Knowledge, intelligently select the closest MAIN Topic, or return an empty array [] if nothing is relevant.\n"
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
        log_token_usage("Router_RB", response.usage_metadata, latency)
        
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

def update_context_data(student_id: int, topic: str, subtopic: str, inter_k: float, inter_l: float, inter_i: float, file_path: str = "context_data.csv"):
    """Apply EMA to scores and recalculate categories."""
    ALPHA = 0.8 
    
    if not os.path.exists(file_path):
        cols = ['student_id', 'Topic', 'Subtopic', 'lapse_score', 'knowledge_score', 'interest_score', 'lapse_category', 'knowledge_category', 'interest_category']
        df = pd.DataFrame(columns=cols)
    else:
        df = pd.read_csv(file_path)
        for col in ['knowledge_score', 'lapse_score', 'interest_score']:
            if col in df.columns:
                df[col] = df[col].astype(float)
                
    # 1. Make sure student_id is int and topic/subtopic are stripped strings to avoid hidden mismatches
    df['student_id'] = df['student_id'].astype(int)
    student_id_clean = int(student_id)
    
    # 2. Remove leading/trailing whitespace from 'Topic' and 'Subtopic' columns in the DataFrame to ensure clean matching
    df['Topic'] = df['Topic'].astype(str).str.strip()
    df['Subtopic'] = df['Subtopic'].astype(str).str.strip()
    
    topic_clean = str(topic).strip()
    subtopic_clean = str(subtopic).strip()
    
    # 3. Use cleaned variables for matching
    mask = (df['student_id'] == student_id_clean) & (df['Topic'] == topic_clean) & (df['Subtopic'] == subtopic_clean)
    
    if df[mask].empty:
        new_row = pd.DataFrame([{
            'student_id': student_id_clean,
            'Topic': topic_clean,
            'Subtopic': subtopic_clean,
            'knowledge_score': float(inter_k),
            'lapse_score': float(inter_l),
            'interest_score': float(inter_i),
            'knowledge_category': 'Moderate knowledge',
            'lapse_category': 'Not lapsed',
            'interest_category': 'Moderate interest'
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        old_k = df.loc[mask, 'knowledge_score'].values[0]
        old_l = df.loc[mask, 'lapse_score'].values[0]
        old_i = df.loc[mask, 'interest_score'].values[0]
        
        df.loc[mask, 'knowledge_score'] = (old_k * ALPHA) + (inter_k * (1 - ALPHA))
        df.loc[mask, 'lapse_score']     = (old_l * ALPHA) + (inter_l * (1 - ALPHA))
        df.loc[mask, 'interest_score']  = (old_i * ALPHA) + (inter_i * (1 - ALPHA))

    try:
        df['lapse_category'] = pd.qcut(df['lapse_score'].rank(method='first'), q=5, 
                                       labels=['Extremely lapsed', 'Highly lapsed', 'Moderately lapsed', 'Slightly lapsed', 'Not lapsed'])
        df['knowledge_category'] = pd.qcut(df['knowledge_score'].rank(method='first'), q=5, 
                                           labels=['Extremely low knowledge', 'Low knowledge', 'Moderate knowledge', 'High knowledge', 'Extremely high knowledge'])
        df['interest_category'] = pd.qcut(df['interest_score'].rank(method='first'), q=5, 
                                          labels=['Extremely low interest', 'Low interest', 'Moderate interest', 'High interest', 'Extremely high interest'])
    except ValueError as e:
        print(f"Warning: Not enough diverse data to qcut yet. {e}")

    df.to_csv(file_path, index=False)
        
def evaluate_and_update_scores(api_key: str, student_id: int, context_text: str, user_query: str, tutor_response: str):
    """LLM-as-a-Judge to evaluate the interaction with a score 0-100."""
    client = genai.Client(api_key=api_key)
    
    judge_prompt = f"""
    You are an educational data analyst. Evaluate the student's performance in this specific interaction.
    Score them from 0 to 100 on three metrics.

    CURRENT STATE (Reference Data):
    {context_text if context_text else "No relevant previous data found for this interaction."}

    INTERACTION:
    User Query: "{user_query}"
    Tutor Response: "{tutor_response}"

    SCORING RULES (0 to 100):
    1. interaction_knowledge: 0 (completely failed/clueless) to 100 (perfect understanding/correct answer).
    2. interaction_lapse: 0 (completely forgot the basics) to 100 (fresh memory, no hesitation).
    3. interaction_interest: 0 (bored, minimum effort) to 100 (curious, enthusiastic, asking follow-ups).
    
    CRITICAL INSTRUCTIONS FOR TOPIC SELECTION:
    - Step 1 (STRICT MATCHING): Compare the INTERACTION subject directly to the 'Subtopic' column in the CURRENT STATE. "Medieval History" is NOT "The Roman Empire". 
    - Step 2 (KNOWN DOMAIN): If and ONLY if the interaction is explicitly about the exact same specific subtopic present in the table, set "is_new_topic" to false. EXACTLY COPY-PASTE the "Topic" and "Subtopic" strings from the table.
    - Step 3 (NEW DOMAIN): If the interaction explores a different specific subject (even if it belongs to the same broad category, e.g., both are 'History'), set "is_new_topic" to true.
    - Step 4 (CREATION): If "is_new_topic" is true, generate a broad academic "topic" (e.g., "History") and a specific subject-matter "subtopic" (e.g., "Medieval History"). Do NOT reuse the old subtopic from the table.
    - CRITICAL RULE: The subtopic MUST be a domain of knowledge. NEVER use meta-activities like "Test Preparation" or "Study Strategies".
    - CRITICAL RULE FOR NEW DOMAINS: The subtopic MUST represent a core subject matter, skill, or area of interest (e.g., "Navier-Stokes Equations", "Verona Tourism", "Personal Finance"). It must define WHAT the user is exploring, not HOW they are consuming it. NEVER use media formats, platforms, resources, or task-oriented actions as subtopics (STRICTLY FORBIDDEN: "YouTube Channels", "Books", "Test Preparation", "Itinerary Planning", "Study Strategies").
    """
    
    try:
        # PAUSA CRITICA: previene il 503 dopo la chiamata di generazione
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
                        "is_new_topic": {"type": "BOOLEAN"},
                        "topic": {"type": "STRING"},
                        "subtopic": {"type": "STRING"},
                        "interaction_knowledge": {"type": "NUMBER"},
                        "interaction_lapse": {"type": "NUMBER"},
                        "interaction_interest": {"type": "NUMBER"}
                    },
                    "required": ["is_new_topic", "topic", "subtopic", "interaction_knowledge", "interaction_lapse", "interaction_interest"]
                }
            )
        )
        
        latency = time.time() - start_time
        log_token_usage("Evaluator_RB", response.usage_metadata, latency)
        
        if not response.text:
             print("Background evaluation failed: Modello ha restituito un testo vuoto.")
             return
             
        result = json.loads(response.text)
        update_context_data(
            student_id=student_id,
            topic=result["topic"],
            subtopic=result["subtopic"],
            inter_k=result["interaction_knowledge"],
            inter_l=result["interaction_lapse"],
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
        # PAUSA CRITICA: Dà respiro all'API dopo la chiamata di Routing iniziale
        time.sleep(2.5) 
        
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                # CORREZIONE SINTASSI TOOL RICERCA
                tools=[{"google_search": {}}], 
            ),
        )
        
        latency = time.time() - start_time
        log_token_usage("Generator_RB", response.usage_metadata, latency)
        
        # CORREZIONE FILTRI SICUREZZA: previene l'errore strip() on None
        if not response.text:
            return "Errore: La risposta restituita è vuota. Potrebbe essere intervenuto un filtro di sicurezza."
            
        return response.text.strip()
        
    except Exception as e:
        # STAMPA L'ERRORE REALE NEL TERMINALE
        traceback.print_exc()
        return f"Errore durante la generazione: {str(e)}"
        
def main():
    st.set_page_config(page_title="Context-Aware Consultant", layout="wide")
    st.title("Intelligent RAG Consultant")

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
            mapping = full_df.groupby('Topic')['Subtopic'].apply(lambda x: ', '.join(x.unique())).to_dict()
            topic_mapping_str = "\n".join([f"- '{k}' (contains: {v})" for k, v in mapping.items()])
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
                # 1. Routing
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

                # 3. Generation
                reply = call_gemini(api_key, DEFAULT_MODEL_PRO, system_prompt, history_text, user_prompt, temperature)
                
            except Exception as e:
                reply = f"Error during processing: {e}"
                traceback.print_exc()

            # Mostra la risposta all'utente
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            
            if "Errore" not in reply and "Error" not in reply:
                topics_str = ", ".join(st.session_state.active_topics) if st.session_state.active_topics else "None"
                log_chat_interaction(
                    architecture="RB",
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