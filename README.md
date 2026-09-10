# TesiMagistrale_NextQuerySuggestion

**Dynamic User Profile Injection: A Closed-Loop RAG Architecture for Context-Aware LLMs**

Master's thesis project (University of Verona) exploring how to give a stateless LLM a
persistent, evolving model of the student it is tutoring. Developed in the context of the
European **DataGEMS** project and the **MathE** e-learning platform.

## Idea

A standard AI tutor is *stateless*: it does not adapt to the student, does not remember
their gaps, and cannot reason about memory decay. This project wraps a Gemini model in a
**closed loop**:

1. **Hierarchical Router** — picks only the relevant slice of the student profile
   (topic → subtopic) instead of dumping the whole database into the prompt.
2. **Generator** — answers the student, using the retrieved profile slice plus web search,
   and adapts tone/difficulty via a recommendation matrix over Knowledge / Lapse / Interest.
3. **Asynchronous Evaluator** (LLM-as-a-Judge) — after each turn, silently scores the
   interaction and updates the profile database (EMA smoothing for knowledge/interest,
   Ebbinghaus-style exponential decay for lapse). A "semantic bypass" kill-switch skips
   updates for non-didactic requests.

The student profile is stored as descriptive categories (`High knowledge`,
`Extremely lapsed`, ...) rather than raw numbers, to reduce LLM misinterpretation.

## Repository layout

| Path | Contents |
|------|----------|
| `GeminiAPI_x_streamlit/` | Streamlit application and experiment code |
| `GeminiAPI_x_streamlit/naive_app.py` | Baseline: entire profile DB passed to the model every turn |
| `GeminiAPI_x_streamlit/appF.py` | Flat Router-Based (FRB) architecture |
| `GeminiAPI_x_streamlit/appH.py` | Hierarchical Router-Based (HRB) architecture — the proposed system |
| `GeminiAPI_x_streamlit/context_data.csv` | Per-student profile (topic, subtopic, knowledge/lapse/interest scores + categories) |
| `GeminiAPI_x_streamlit/context/` | Source assessment data used to build profiles |
| `GeminiAPI_x_streamlit/not_in_context/` | Auxiliary MathE datasets not fed to the model |
| `GeminiAPI_x_streamlit/analysis/`, `*_logs.csv`, `token_usage_*.ipynb` | Telemetry (tokens, latency) and analysis notebooks |
| `plots/` | Figures used in the thesis |
| `ms_thesis/` | Thesis PDF, slides, and acknowledgements |
| `slides.txt`, `to do.txt` | Working notes |

## Running the app

Requires Python 3.12+ and a Google Gemini API key.

```bash
cd GeminiAPI_x_streamlit
pip install -r requirements.txt

# provide your key
echo "GEMINI_API_KEY=your-key-here" > .env

# run one of the architectures
streamlit run appH.py      # Hierarchical Router-Based (proposed)
streamlit run appF.py      # Flat Router-Based
streamlit run naive_app.py # Naive full-DB baseline
```

In the sidebar, choose a **Student ID** (e.g. `80`) whose profile exists in
`context_data.csv`. As you chat, the Evaluator updates that student's rows in place.

Models used: `gemini-2.5-flash` (generator), `gemini-2.5-flash-lite` (router and evaluator).

## Key results

Comparing the three architectures on the same interaction set, the Hierarchical
Router-Based system cuts end-to-end token usage from ~59k (Naive) to ~12.5k while keeping
user-perceived latency effectively unchanged (profile updates happen asynchronously).

## Known limitations

- **Global profile query dilemma** — the router struggles with meta-questions
  ("what are my interests?") because routing happens before the interest scores are visible.
- **Task discriminator** is imperfect and occasionally updates the profile when it should not.
- **API dependency** — vendor lock-in and scaling cost. Future work: an upstream intent
  classifier and a move to dense retrieval / vector databases.

See `ms_thesis/ms_thesis.pdf` for full methodology and evaluation.
