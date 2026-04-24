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

#DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_MODEL = "gemini-2.5-flash"

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
1. Answer the user's specific request FIRST.
2. PROACTIVITY: Guide the user naturally based on their data. NEVER copy-paste recommendations.
3. RECOMMENDATION MATRIX:
   - 'Extremely low' / 'Low knowledge': Suggest foundational basics.
   - 'Extremely lapsed' / 'Highly lapsed' (with moderate knowledge): Suggest quick memory refreshers.
   - 'High' / 'Extremely high knowledge': Suggest advanced problems/applications.
   - 'Not lapsed' / 'Slightly lapsed' (with low knowledge): Focus on practice.
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
            "Task: Analyze the user query IN CONTEXT of the Previous Active Topics.\n"
            "Apply these STRICT rules to output ONLY a JSON array of exact string matches from Available Topics:\n"
            "1. IMPLICIT CONTINUATION: If the query is ambiguous ('give me an exercise', 'tell me more') OR answers a question the AI just asked, output the 'Previous Active Topics'.\n"
            "2. META-QUERIES: If the user asks about their grades, status, progress, or situation (e.g., 'how am I doing?', 'what is my situation?'), DO NOT invent topics. Output the 'Previous Active Topics' so the system can evaluate their data.\n"
            "3. FUZZY MAPPING (BROAD CATEGORIES & EVERYDAY TERMS): If the user mentions a general interest, a broad domain, or a casual topic (e.g., 'math', 'fitness', 'the future', 'art', 'cooking', 'business') WITHOUT specifying the exact subtopic, intelligently select 2 to 4 of the closest matching foundational topics from the 'Available Topics' list (e.g., map 'fitness' to 'Sport and Human Performance', or 'the future' to 'Futurology and Tomorrow's Scenarios').\n"
            "4. TOPIC SWITCH: If the query explicitly introduces a NEW specific subject, ignore previous topics and select the new relevant topics from 'Available Topics'.\n"
            "Return ONLY a JSON array of strings."
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
        
        log_token_usage("Router (Topic Extraction)", response.usage_metadata)
        
        extracted_topics = json.loads(response.text)
        valid_topics = [t for t in extracted_topics if t in unique_topics]
        return valid_topics
        
    except Exception as e:
        print(f"Routing error: {e}")
        return []

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
        "Output Tokens (Answer)": usage_metadata.candidates_token_count,
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

def update_context_data(student_id: int, topic: str, subtopic: str, new_k_score: str, new_l_score: str, file_path: str = "context_data.csv"):
    """Aggiorna il file CSV con le nuove etichette di punteggio."""
    if not os.path.exists(file_path):
        return
        
    df = pd.read_csv(file_path)
    
    # Cerca la riga esatta
    mask = (df['student_id'] == student_id) & (df['Topic'] == topic) & (df['Subtopic'] == subtopic)
    
    if df[mask].empty:
        # Se non esiste, crea una nuova riga
        new_row = pd.DataFrame([{
            'student_id': student_id,
            'Topic': topic,
            'Subtopic': subtopic,
            'knowledge_score': new_k_score,
            'lapse_score': new_l_score
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        # Aggiorna i valori esistenti
        df.loc[mask, 'knowledge_score'] = new_k_score
        df.loc[mask, 'lapse_score'] = new_l_score
        
    df.to_csv(file_path, index=False)

def evaluate_and_update_scores(api_key: str, student_id: int, context_text: str, user_query: str, tutor_response: str):
    """L'LLM-as-a-Judge che valuta l'apprendimento e aggiorna il CSV."""
    if not context_text:
        return # Non facciamo aggiornamenti se non stiamo parlando di un topic noto
        
    client = genai.Client(api_key=api_key)
    
    judge_prompt = f"""
    You are an educational data analyst. Analyze this interaction and update the student's semantic scores based on their performance.

    CURRENT DATA (Subtopics and scores):
    {context_data}

    User Query: "{user_query}"
    Tutor Response: "{tutor_response}"

    TASK:
    1. Identify which 'Topic' and 'Subtopic' was discussed.
    2. If the user successfully learned/answered, output a higher knowledge label and 'Not lapsed'.
    3. If they struggled, lower knowledge and increase lapse.
    
    Valid Knowledge Labels: 'Extremely low knowledge', 'Low knowledge', 'Moderate knowledge', 'High knowledge', 'Extremely high knowledge'
    Valid Lapse Labels: 'Not lapsed', 'Slightly lapsed', 'Moderately lapsed', 'Highly lapsed', 'Extremely lapsed'
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite", # Usiamo il modello ultra-veloce e leggero
            contents=judge_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "topic": {"type": "STRING"},
                        "subtopic": {"type": "STRING"},
                        "new_knowledge_score": {"type": "STRING"},
                        "new_lapse_score": {"type": "STRING"},
                        "reasoning": {"type": "STRING"}
                    },
                    "required": ["topic", "subtopic", "new_knowledge_score", "new_lapse_score"]
                }
            )
        )
        
        # Registra i token anche del giudice
        log_token_usage("Evaluator (Post-Interaction)", response.usage_metadata)
        
        result = json.loads(response.text)
        update_context_data(
            student_id=student_id,
            topic=result["topic"],
            subtopic=result["subtopic"],
            new_k_score=result["new_knowledge_score"],
            new_l_score=result["new_lapse_score"]
        )
        print(f"Update Success: {result.get('reasoning', 'Scores updated')}")
        
    except Exception as e:
        print(f"Background evaluation failed: {e}")
                
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

    # Assicurati che ensure_state() inizializzi sia 'messages' che 'active_topics'
    ensure_state()

    with st.sidebar:
        st.header("Configuration")
        student_id = st.number_input("Student ID", min_value=1, value=80, step=1)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.4, 0.1)
        if st.button("Reset Chat"):
            st.session_state.messages = []
            st.session_state.active_topics = [] # Resetta anche la memoria dei topic!
            st.rerun()

    api_key = get_api_key()

    # Caricamento dati utente
    try:
        full_df = load_context_data(int(student_id))
        unique_topics = full_df['Topic'].unique().tolist() if not full_df.empty else []
    except Exception as e:
        full_df = pd.DataFrame()
        unique_topics = []
        st.error(f"Data loading failed: {e}")

    # Renderizza la cronologia della chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input dell'utente
    user_prompt = st.chat_input("Ask a question...")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not api_key:
        st.error("API Key missing.")
        return

    # Risposta dell'Assistente
    with st.chat_message("assistant"):
        with st.spinner("Analyzing intent..."):
            try:
                # 1. ROUTING: Chiama il router passando i Topic attivi della sessione precedente
                target_topics = extract_relevant_topics(
                    api_key, 
                    model, 
                    user_prompt, 
                    unique_topics, 
                    st.session_state.active_topics
                )
                
                # 2. STATE TRACKING & TOKEN OPTIMIZATION
                if target_topics and not full_df.empty:
                    # SALVA IN MEMORIA: aggancia i nuovi topic per la prossima domanda
                    st.session_state.active_topics = target_topics 
                    
                    # Filtra le righe del dataframe
                    filtered_df = full_df[full_df['Topic'].isin(target_topics)]

                    # OTTIMIZZAZIONE TOKEN: Elimina la colonna ridondante 'Topic' e usa il CSV
                    df_slim = filtered_df[['Subtopic', 'knowledge_score', 'lapse_score']]
                    context_text = df_slim.to_csv(index=False)
                    
                    st.info(f"🎯 Found {len(filtered_df)} records for topics: {', '.join(target_topics)}")
                else:
                    # SVUOTA LA MEMORIA: l'utente ha cambiato discorso senza un topic noto
                    st.session_state.active_topics = [] 
                    context_text = ""
                    st.info("🌐 No relevant topics found. Using general knowledge.")

                # Costruisce il prompt finale
                system_prompt = build_system_prompt(context_text)
                
                # 3. SLIDING WINDOW: Passa solo l'ultimo scambio (max_turns=1) per evitare il memory leak dei token!
                history_text = build_history_text(st.session_state.messages[:-1])

                # 4. GENERATION: Chiama il modello principale
                # ... [Il tuo codice esistente per routing e generazione] ...

                # 4. GENERATION: Chiama il modello principale
                reply = call_gemini(api_key, model, system_prompt, history_text, user_prompt, temperature)
                
            except Exception as e:
                reply = f"Error during generation: {e}"

            # Mostra la risposta all'utente
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            
            # --- NUOVO: CLOSED-LOOP UPDATE ---
            # Valuta e aggiorna il CSV in background senza bloccare la chat visiva
            if context_text and "Error" not in reply:
                evaluate_and_update_scores(
                    api_key=api_key,
                    student_id=int(student_id),
                    context_text=context_text,
                    user_query=user_prompt,
                    tutor_response=reply
                )
                
if __name__ == "__main__":
    main()