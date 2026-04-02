import os
import sys
import shutil
import uuid
import csv
import re
import time
import chromadb
from openpyxl import load_workbook
from google import genai
from dotenv import load_dotenv

# Forza l'output immediato nel terminale
def logger(msg):
    text = f">>> {msg}"
    try:
        print(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Fallback per terminali Windows con encoding non UTF-8.
        safe = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
        print(safe)
        sys.stdout.flush()

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Percorsi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDER_PATH = os.path.join(BASE_DIR, "context")
# DB locale al progetto (evita lock/sync esterni).
DB_PATH = os.path.join(BASE_DIR, "chroma_db")
MAX_ROWS_ENV = os.getenv("MAX_ROWS", "").strip()
MAX_ROWS = int(MAX_ROWS_ENV) if MAX_ROWS_ENV.isdigit() else None
RESET_DB = os.getenv("RESET_DB", "1").strip().lower() in {"1", "true", "yes", "y"}
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "tesi_db").strip() or "tesi_db"
EMBEDDING_DIM_ENV = os.getenv("EMBEDDING_DIM", "768").strip()
EMBEDDING_DIM = int(EMBEDDING_DIM_ENV) if EMBEDDING_DIM_ENV.isdigit() else 768

logger("AVVIO SCRIPT DI EMERGENZA")

# --- CLASSE EMBEDDING ---
class SimpleGoogleEF:
    def __init__(self, key):
        self.client = genai.Client(api_key=key)

    @staticmethod
    def _retry_delay_seconds(error_text):
        m = re.search(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, flags=re.IGNORECASE)
        if m:
            return max(1.0, float(m.group(1)))
        m = re.search(r"'retryDelay':\s*'([0-9]+)s'", error_text)
        if m:
            return max(1.0, float(m.group(1)))
        return 10.0

    def embed(self, texts):
        last_error = None
        for attempt in range(1, 6):
            try:
                res = self.client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=texts,
                    config={"output_dimensionality": EMBEDDING_DIM},
                )
                vectors = [list(item.values) for item in res.embeddings]
                if len(vectors) != len(texts):
                    raise ValueError(f"Numero embedding non coerente: attesi={len(texts)} ottenuti={len(vectors)}")
                return vectors
            except Exception as e:
                last_error = e
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait_s = self._retry_delay_seconds(msg)
                    logger(f"Rate limit embedding (tentativo {attempt}/5). Attendo {wait_s:.1f}s...")
                    time.sleep(wait_s)
                    continue
                raise

        raise RuntimeError(f"Embedding fallito dopo retry: {last_error}")


SUPPORTED_EXT = {".xlsx", ".xls", ".csv"}


def find_tabular_files(root_path):
    found = []
    for root, _, files in os.walk(root_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXT:
                found.append(os.path.join(root, filename))
    found.sort()
    return found


def load_tables(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        def csv_rows():
            with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    yield idx, row
        return [("csv", csv_rows())]

    workbook = load_workbook(file_path, read_only=True, data_only=True)
    tables = []
    for sheet_name in workbook.sheetnames:
        ws = workbook[sheet_name]

        def sheet_rows(worksheet=ws):
            iterator = worksheet.iter_rows(values_only=True)
            try:
                headers_raw = next(iterator)
            except StopIteration:
                return
            headers = [str(h).strip() if h is not None else "" for h in headers_raw]
            for idx, row in enumerate(iterator):
                row_dict = {}
                for h, value in zip(headers, row):
                    if not h:
                        continue
                    row_dict[h] = value
                yield idx, row_dict

        tables.append((sheet_name, sheet_rows()))
    return tables


def row_to_text(row):
    pairs = []
    for key, value in row.items():
        if value is None:
            continue
        pairs.append(f"{key}:{value}")
    return " ".join(pairs)


def add_batch(collection, embedder, docs, metas, ids):
    vectors = embedder.embed(docs)
    collection.add(documents=docs, embeddings=vectors, metadatas=metas, ids=ids)

def run():
    if not api_key:
        logger("ERRORE: Manca la GEMINI_API_KEY nel file .env")
        return

    logger(f"1. Inizializzo ChromaDB in: {DB_PATH}")
    logger(f"Embedding dimension: {EMBEDDING_DIM}")
    try:
        if RESET_DB and os.path.exists(DB_PATH):
            logger("Reset DB attivo: elimino il vecchio database")
            shutil.rmtree(DB_PATH, ignore_errors=True)

        # Usiamo un client che non crasha se la cartella è bloccata
        client = chromadb.PersistentClient(path=DB_PATH)
        embedder = SimpleGoogleEF(api_key)
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
    except Exception as e:
        logger(f"ERRORE INIZIALIZZAZIONE CHROMA: {e}")
        return

    logger("2. Ricerca tabelle nella cartella context...")
    files = find_tabular_files(FOLDER_PATH)
    if not files:
        logger("ERRORE: Nessun file tabellare trovato in context (.xlsx/.xls/.csv)")
        return
    logger(f"Trovati {len(files)} file tabellari")

    logger("3. Inizio caricamento in Chroma...")
    loaded = 0
    failed = 0
    batch_size = 50

    for file_path in files:
        rel = os.path.relpath(file_path, FOLDER_PATH)
        logger(f"File: {rel}")
        try:
            tables = load_tables(file_path)
        except Exception as e:
            failed += 1
            logger(f"ERRORE LETTURA FILE {rel}: {e}")
            continue

        for table_name, row_iter in tables:
            if MAX_ROWS is not None:
                logger(f"  Tabella '{table_name}' - righe limitate da MAX_ROWS={MAX_ROWS}")
            else:
                logger(f"  Tabella '{table_name}' - scansione completa")
            docs_batch = []
            metas_batch = []
            ids_batch = []
            rows_seen = 0

            def flush_batch():
                nonlocal loaded, failed, docs_batch, metas_batch, ids_batch
                if not docs_batch:
                    return
                try:
                    add_batch(collection, embedder, docs_batch, metas_batch, ids_batch)
                    loaded += len(docs_batch)
                    if loaded % 250 == 0:
                        logger(f"  Progress: {loaded} record caricati")
                except Exception as batch_err:
                    # Fallback: isoliamo eventuali righe problematiche.
                    for d, m, _id in zip(docs_batch, metas_batch, ids_batch):
                        try:
                            vec = embedder.embed([d])[0]
                            collection.add(documents=[d], embeddings=[vec], metadatas=[m], ids=[_id])
                            loaded += 1
                        except Exception as row_err:
                            msg = str(row_err)
                            if "already exists" in msg.lower() or "duplicate" in msg.lower():
                                continue
                            failed += 1
                            logger(f"ERRORE RIGA file={m.get('file')} tabella={m.get('table')} riga={m.get('row_index')}: {row_err}")
                    logger(f"Batch parzialmente fallito su '{table_name}': {batch_err}")
                finally:
                    docs_batch = []
                    metas_batch = []
                    ids_batch = []

            for i, row in row_iter:
                rows_seen += 1
                if MAX_ROWS is not None and rows_seen > MAX_ROWS:
                    break

                testo = row_to_text(row)
                if not testo.strip():
                    continue

                # ID stabile per evitare collisioni e permettere rerun con upsert.
                stable_key = f"{rel}|{table_name}|{i}"
                doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))
                metadata = {
                    "file": rel,
                    "table": str(table_name),
                    "row_index": int(i),
                }

                docs_batch.append(testo)
                metas_batch.append(metadata)
                ids_batch.append(doc_id)

                if len(docs_batch) >= batch_size:
                    flush_batch()

            flush_batch()

            if rows_seen == 0:
                logger(f"  Tabella '{table_name}' vuota: skip")

    logger(f"FINITO! Nuovi/aggiornati: {loaded} | Errori: {failed} | Totali nel DB: {collection.count()}")

if __name__ == "__main__":
    run()