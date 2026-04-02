import fitz  # PyMuPDF
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# Configurazione
CHROMA_PATH = "./chroma_db"
PDF_PATH = r"G:\Il mio Drive\PC\UNIVERSITA'\MAGISTRALE\tesi_magistrale\GeminiAPI_x_streamlit\MathE_db_documentation.pdf"

def ingest_documentation():
    # 1. Inizializza Chroma
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    
    # Crea o recupera la collezione per la documentazione
    docs_col = client.get_or_create_collection(name="documentation_base", embedding_function=ef)

    # 2. Estrai testo dal PDF
    doc = fitz.open(PDF_PATH)
    for page_num, page in enumerate(doc):
        text = page.get_text()
        # Pulizia base e inserimento (una pagina per blocco o dividi per sezioni)
        docs_col.add(
            documents=[text],
            ids=[f"page_{page_num}"],
            metadatas=[{"source": "pdf_documentation", "page": page_num}]
        )
    print(f"✅ Documentazione caricata: {len(doc)} pagine elaborate.")

if __name__ == "__main__":
    ingest_documentation()