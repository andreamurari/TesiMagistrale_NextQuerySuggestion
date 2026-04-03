import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

selected_student = 3538

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONTEXT_DIR = BASE_DIR / "context"

context = pd.read_excel('context/Assesment_Information.xlsx')
context = context[context['student_id'] == selected_student]

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


def _extract_retry_delay_seconds(error_text: str) -> float | None:
    match = re.search(r"retry(?:\s*in)?\s*([0-9]+(?:\.[0-9]+)?)s", error_text, flags=re.IGNORECASE)
    if match:
        return max(1.0, float(match.group(1)))
    match = re.search(r"'retryDelay':\s*'([0-9]+)s'", error_text)
    if match:
        return max(1.0, float(match.group(1)))
    return None


def _is_hard_quota_error(error_text: str) -> bool:
    lowered = error_text.lower()
    return (
        "resource_exhausted" in lowered
        or "quota exceeded" in lowered
        or "free_tier" in lowered
        or "limit: 0" in lowered
    )


def ask_gemini(model_name: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    last_error = None

    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            return (response.text or "").strip()
        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            if _is_hard_quota_error(error_text):
                raise RuntimeError(
                    "Gemini quota is exhausted for the selected model. "
                    "This usually means the free-tier limit is unavailable for this project or model. "
                    "Enable billing, switch to a project with quota, or use a different API key."
                ) from exc

            retry_delay = _extract_retry_delay_seconds(error_text)
            if retry_delay is None or attempt == 3:
                raise RuntimeError(f"Gemini request failed after {attempt} attempt(s): {exc}") from exc

            time.sleep(retry_delay)

    raise RuntimeError(f"Gemini request failed: {last_error}")


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
        sel_student = st.number_input("Student ID", min_value=0, value=3538, step=1)
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
            sel_student=int(sel_student),
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