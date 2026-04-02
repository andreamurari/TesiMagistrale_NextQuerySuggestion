import os
import streamlit as st
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv
from google import genai
from google.genai import types
import re # Per intercettare gli ID nel testo

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="GemBot RAG & Analytics", layout="wide", page_icon="🤖")

# --- CONNESSIONE AL DATABASE RAG LOCALE ---
@st.cache_resource
def init_db():
    try:
        # Usiamo un modello multilingua per gestire bene i dati italiani/inglesi
        local_ef = SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        return chroma_client.get_collection(name="knowledge_base", embedding_function=local_ef)
    except Exception as e:
        st.error(f"Errore caricamento Database RAG. Dettaglio: {e}")
        return None

collection = init_db()

# --- FUNZIONE DI RICERCA NEL DATABASE ---
def get_rag_context(query, n_results=20):
    """
    Cerca nel database. 
    Se la query contiene un ID numerico, potremmo voler aumentare n_results 
    per catturare tutta la storia dello studente.
    """
    if not collection: return "Nessun database trovato."
    
    # Se la query sembra un ID (es. solo numeri), facciamo una ricerca specifica
    # Nota: ChromaDB eccelle nella ricerca semantica, ma qui la usiamo per 'pescare' i record correlati
    risultati = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    if not risultati['documents'] or not risultati['documents'][0]:
        return "Nessuna informazione pertinente trovata."

    return "\n\n--- RECORD TROVATO ---\n".join(risultati['documents'][0])

# --- APP PRINCIPALE ---
if not api_key:
    st.error("Chiave API mancante. Configura il file .env.")
else:
    client = genai.Client(api_key=api_key)
    model_name = 'gemini-2.5-flash'
    
    st.title("🤖 GemBot RAG: Studenti & Didattica")
    
    with st.sidebar:
        st.success("✅ Database Vettoriale Attivo")
        st.info("💡 Consiglio: Se cerchi uno studente, inserisci il suo ID specifico.")
        if st.button("Pulisci Cronologia Chat"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            types.Content(role="model", parts=[types.Part(text="Ciao! Inserisci un argomento di studio o uno Student ID. Estrarrò i dati dal database e genererò un resoconto strutturato.")])
        ]

    for message in st.session_state.messages:
        with st.chat_message(message.role):
            text_parts = [part.text for part in message.parts if hasattr(part, 'text')]
            st.markdown("".join(text_parts))

    if prompt := st.chat_input("Inserisci ID studente o domanda didattica..."):
        st.session_state.messages.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("Estrazione dati in corso..."):
                # Aumentiamo i risultati a 40 se sospettiamo sia un'analisi di uno studente (molti record)
                num_records = 40 if any(char.isdigit() for char in prompt) else 20
                contesto_estratto = get_rag_context(prompt, n_results=num_records)
            
            # --- LOGICA DI SYSTEM INSTRUCTION ADATTABILE ---
            # Qui implementiamo il suggerimento del prof: 
            # l'LLM deve agire come un sommarizzatore statistico/descrittivo dei dati RA.
            rag_instruction = (
                "Sei 'GemBot', un analista didattico esperto. Il tuo compito è analizzare i dati estratti dal database.\n\n"
                "CASO A: ANALISI STUDENTE (Se i dati contengono record di uno Student ID):\n"
                "1. Esegui una sommarizzazione quantitativa (media voti, numero test fatti, frequenza).\n"
                "2. Esegui una sommarizzazione qualitativa (commenti, lacune ricorrenti, punti di forza).\n"
                "3. Concludi con un 'PROFILO SINTETICO' e suggerisci su quali materiali MathE o ESCO dovrebbe concentrarsi.\n\n"
                "CASO B: DOMANDA DIDATTICA:\n"
                "1. Spiega l'argomento usando ESCLUSIVAMENTE i materiali didattici trovati.\n"
                "2. Proponi esercizi o quiz estratti dai record 'Questions_Information'.\n\n"
                "IMPORTANTE: Se i dati estratti sono insufficienti o non coerenti con l'ID, dichiaralo apertamente.\n"
                f"--- CONTESTO ESTRATTO DAL DATABASE ---\n{contesto_estratto}"
            )

            config = types.GenerateContentConfig(
                system_instruction=rag_instruction,
                temperature=0.2, # Molto basso per essere precisi sui dati dello studente
            )

            response = client.models.generate_content(
                model=model_name,
                contents=st.session_state.messages,
                config=config
            )

            with st.chat_message("model"):
                st.markdown(response.text)
                with st.expander("🔍 Analisi del Recupero (Retrieval)"):
                    st.write(f"Record recuperati: {num_records}")
                    st.text(contesto_estratto)

            st.session_state.messages.append(response.candidates[0].content)

        except Exception as e:
            st.error(f"Errore nella generazione del resoconto: {e}")