import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONTEXT_DIR = BASE_DIR / "context"


def _safe_read_text(file_path: Path, max_chars: int = 12000) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            text = file_path.read_text(encoding=enc, errors="replace")
            return text[:max_chars]
        except Exception:
            continue
    return ""


def _format_table_preview(df: pd.DataFrame, max_rows: int) -> str:
    preview = df.head(max_rows)
    if preview.empty:
        return "(empty table)"
    return preview.to_string(index=False)


@st.cache_data(show_spinner=False)
def load_context_folder(folder_path: str, max_rows: int = 120, max_chars_per_file: int = 12000):
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return "", [], [f"Folder not found: {folder_path}"]

    loaded_files = []
    errors = []
    chunks = []

    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        rel_name = str(file_path.relative_to(folder))
        content = ""

        try:
            if ext in {".xlsx", ".xls"}:
                excel_book = pd.read_excel(file_path, sheet_name=None)
                sheet_chunks = []
                for sheet_name, df in excel_book.items():
                    sheet_chunks.append(f"\n[SHEET: {sheet_name}]\n{_format_table_preview(df, max_rows)}")
                content = "\n".join(sheet_chunks)

            elif ext == ".csv":
                try:
                    df = pd.read_csv(file_path, sep=";")
                    if len(df.columns) < 2:
                        df = pd.read_csv(file_path, sep=",")
                except Exception:
                    df = pd.read_csv(file_path, encoding="latin1")
                content = _format_table_preview(df, max_rows)

            elif ext == ".json":
                data = json.loads(_safe_read_text(file_path, max_chars=max_chars_per_file))
                content = json.dumps(data, indent=2, ensure_ascii=False)

            elif ext in {".txt", ".md", ".sql"}:
                content = _safe_read_text(file_path, max_chars=max_chars_per_file)

            else:
                continue

            if not content.strip():
                continue

            content = content[:max_chars_per_file]
            block = (
                f"\n--- INIZIO FILE: {rel_name} ---\n"
                f"{content}\n"
                f"--- FINE FILE: {rel_name} ---\n"
            )
            chunks.append(block)
            loaded_files.append(rel_name)

        except Exception as exc:
            errors.append(f"{rel_name}: {exc}")

    return "\n".join(chunks), loaded_files, errors


def build_system_prompt(context_data: str) -> str:
    return f"""
You are an expert data analyst for a master's thesis.
You have access to the tables and documents loaded below.

AVAILABLE DATA:
{context_data}

JOIN RULES:
1. Files are linked through common keys (for example STUDENT_ID, COURSE_CODE).
2. If information is missing in one table, look for it in the others using the keys.
3. If you find naming differences (for example Student vs User), treat them as the same entity.

Response style:
- Be clear and concise.
- If data is missing, say so explicitly.
""".strip()


def ensure_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []


def get_api_key() -> str:
    env_key = os.getenv("GEMINI_API_KEY", "")
    return st.session_state.get("gemini_api_key", env_key)


def build_history_text(messages, max_turns: int = 8) -> str:
    if not messages:
        return ""
    selected = messages[-(max_turns * 2) :]
    lines = []
    for msg in selected:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def ask_gemini(model_name: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return (response.text or "").strip()


def main():
    if load_dotenv is not None:
        load_dotenv()

    st.set_page_config(page_title="Gemini Data Assistant", page_icon="\U0001F4DA", layout="wide")
    st.title("Gemini Interface for Your Thesis")
    st.caption("Chat with Gemini using the files available in the context folder")

    ensure_state()

    with st.sidebar:
        st.header("Configuration")
        model_name = st.selectbox(
            "Model",
            options=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
            index=0,
        )

        st.subheader("Context")
        context_folder = st.text_input("Context folder", value=str(DEFAULT_CONTEXT_DIR))
        max_rows = st.slider("Max rows per table", min_value=20, max_value=500, value=120, step=20)
        max_chars = st.slider("Max characters per file", min_value=2000, max_value=30000, value=12000, step=1000)

        if st.button("Clear chat"):
            st.session_state.messages = []
            st.rerun()

    with st.spinner("Loading context..."):
        context_data, loaded_files, load_errors = load_context_folder(
            context_folder,
            max_rows=max_rows,
            max_chars_per_file=max_chars,
        )

    st.info(f"Loaded context files: {len(loaded_files)}")
    if load_errors:
        with st.expander("Loading error details"):
            for err in load_errors:
                st.write(f"- {err}")

    with st.expander("Loaded files preview"):
        for name in loaded_files:
            st.write(f"- {name}")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Write your question...")

    if user_input:
        api_key = get_api_key()
        if not api_key:
            st.error("Enter the Gemini API Key in the sidebar before continuing.")
            return
        if not context_data:
            st.error("No context available. Check the context folder path.")
            return

        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        history_text = build_history_text(st.session_state.messages)
        system_prompt = build_system_prompt(context_data)
        prompt = (
            "RECENT CONVERSATION:\n"
            f"{history_text}\n\n"
            "CURRENT QUESTION:\n"
            f"{user_input}"
        )

        with st.chat_message("assistant"):
            with st.spinner("Gemini is thinking..."):
                try:
                    answer = ask_gemini(
                        model_name=model_name,
                        api_key=api_key,
                        system_prompt=system_prompt,
                        user_prompt=prompt,
                    )
                    if not answer:
                        answer = "I did not receive a valid response from the model."
                except Exception as exc:
                    answer = f"Error while calling Gemini: {exc}"
                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()