import pandas as pd
import time
import os
from dotenv import load_dotenv

from app import (
    extract_relevant_topics, 
    call_gemini, 
    build_system_prompt, 
    evaluate_tutor_response, 
    load_context_data
)

def get_token_usage_for_query(log_file: str, query_start_row: int) -> dict:
    """Read token usage log and sum tokens added after the specified row."""
    if not os.path.exists(log_file):
        return {"Input_Tokens": 0, "Output_Tokens": 0, "Total_Tokens": 0}
    
    try:
        df_log = pd.read_csv(log_file)
        if len(df_log) <= query_start_row:
            return {"Input_Tokens": 0, "Output_Tokens": 0, "Total_Tokens": 0}
        
        # Sum tokens from new rows added during this query
        query_logs = df_log.iloc[query_start_row:]
        return {
            "Input_Tokens": int(query_logs["Input Tokens (Prompt)"].sum()),
            "Output_Tokens": int(query_logs["Output Tokens (Risposta)"].sum()),
            "Total_Tokens": int(query_logs["Total Tokens"].sum())
        }
    except Exception as e:
        print(f"Error reading token usage: {e}")
        return {"Input_Tokens": 0, "Output_Tokens": 0, "Total_Tokens": 0}

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

def run_automated_test():
    # 1. Define the Test Dataset (Strategic queries)
    test_queries = [
        {"id": 1, "query": "What's the best way to learn about Biological Bases of Consciousness?"},
        {"id": 2, "query": "Explain Fungi and Mycelial Networks (Wood Wide Web) to me, I used to know them but I forgot."},
        {"id": 3, "query": "I have a Cultural Anthropology test tomorrow, I'm panicking!"},
        {"id": 4, "query": "I'm confused about the difference between Collaborative Robotics (Cobots) and other parts of Artificial Intelligence (AI)."},
        {"id": 5, "query": "How does Orienteering and Navigation with Map and Compass work exactly?"},
        {"id": 6, "query": "I'm confused about the difference between Relationship between Observer and Observed and other parts of Philosophy of Science (Epistemology)."},
        {"id": 7, "query": "Is Nomadic Cultures and Sedentarism actually useful in real life?"},
        {"id": 8, "query": "Is Social Organization in Ant Colonies actually useful in real life?"},
        {"id": 9, "query": "Explain The Roman Empire: Rise and Fall to me, I used to know them but I forgot."},
        {"id": 10, "query": "What's the best way to learn about Evolution of Latin Scripts (Capital, Uncial, Gothic)?"},
        {"id": 11, "query": "I have a Religions and Spirituality test tomorrow, I'm panicking!"},
        {"id": 12, "query": "Tell me a fun fact about Emerging Markets (BRICS+)."},
        {"id": 13, "query": "Give me some advanced problems on Japanese Anime and Their Global Impact."},
        {"id": 14, "query": "I'm confused about the difference between Aesthetics and the Concept of Beauty and other parts of Philosophy and Critical Thinking."},
        {"id": 15, "query": "Tell me a fun fact about Parkour and Movement in the Urban Environment."},
        {"id": 16, "query": "I have a Publishing and Media test tomorrow, I'm panicking!"},
        {"id": 17, "query": "Is Geotechnical Engineering and Soil Stability actually useful in real life?"},
        {"id": 18, "query": "Explain Last-mile Delivery Logistics to me, I used to know them but I forgot."},
        {"id": 19, "query": "Explain Emotional Branding and Corporate Storytelling to me, I used to know them but I forgot."},
        {"id": 20, "query": "Explain Topology of the Internet and the Web to me, I used to know them but I forgot."},
        {"id": 21, "query": "Tell me a fun fact about Utilitarian vs. Deontological Ethics."},
        {"id": 22, "query": "I would like to do some exercises on Conversational Interfaces and Chatbots."},
        {"id": 23, "query": "I would like to do some exercises on Astrochemistry: Organic Molecules in Space."},
        {"id": 24, "query": "What are the main theories in Seafloor Geology and Plate Tectonics?"},
        {"id": 25, "query": "Explain Neurodegenerative Diseases (Alzheimer's, Parkinson's) to me, I used to know them but I forgot."},
        {"id": 26, "query": "What's the best way to learn about Lahars and Pyroclastic Flows: The Greatest Dangers?"},
        {"id": 27, "query": "I would like to do some exercises on Bonsai: The Art of Miniature Trees."},
        {"id": 28, "query": "Explain Sign Language and Visual Communication to me, I used to know them but I forgot."},
        {"id": 29, "query": "Give me some advanced problems on The Transition from Water to Land."},
        {"id": 30, "query": "Is Transboundary Pollution of Air Masses actually useful in real life?"},
        {"id": 31, "query": "I have a Applied Ethics test tomorrow, I'm panicking!"},
        {"id": 32, "query": "Give me some advanced problems on Seismic and Geochemical Monitoring of Craters."},
        {"id": 33, "query": "I would like to do some exercises on Color in Hospital and School Architecture."},
        {"id": 34, "query": "Can you help me understand Great Human Migrations in Prehistory?"},
        {"id": 35, "query": "I'm looking for a deep dive into Data Analysis and Sales Funnels."},
        {"id": 36, "query": "I need to prep for a Languages and Linguistics quiz on Semantics and Pragmatics of Communication."},
        {"id": 37, "query": "Explain Mental Training and Visualization to me, I used to know them but I forgot."},
        {"id": 38, "query": "Explain Forensic Anthropology: Identification from Skeletal Remains to me, I used to know them but I forgot."},
        {"id": 39, "query": "What's the best way to learn about Smart Ports and Customs Digitalization?"},
        {"id": 40, "query": "Is Thermodynamics and the Arrow of Time actually useful in real life?"},
        {"id": 41, "query": "I would like to do some exercises on Omnichannel Integration (Physical and Digital)."},
        {"id": 42, "query": "I'm writing an essay on Human Genome Sequencing and Big Data, any tips?"},
        {"id": 43, "query": "What's the best way to learn about Nanofiltration for Water Purification?"},
        {"id": 44, "query": "Tell me a fun fact about The Role of Models and Simulations."},
        {"id": 45, "query": "I'm confused about the difference between Organizational Psychology and other parts of Sociology of Work and Organization."},
        {"id": 46, "query": "I would like to do some exercises on Plate Tectonics and Continental Drift."},
        {"id": 47, "query": "I'm writing an essay on Capacity of Understanding and Will, any tips?"},
        {"id": 48, "query": "I'm writing an essay on Digital Tribalism and Echo Chambers, any tips?"},
        {"id": 49, "query": "What's the best way to learn about Academic and Scientific Integrity?"},
        {"id": 50, "query": "Explain Machine Translation and Neural Limits to me, I used to know them but I forgot."},
        {"id": 51, "query": "I need to prep for a Computational Linguistics quiz on Sentiment Analysis on Social Media."},
        {"id": 52, "query": "What's the best way to learn about Mystery Shopping and Quality Control?"},
        {"id": 53, "query": "Can you help me understand Psychedelic-Assisted Therapy?"},
        {"id": 54, "query": "I'm confused about the difference between Incentive Plans and Corporate Benefits and other parts of Human Resources (HR) Management."},
        {"id": 55, "query": "Tell me a fun fact about Energy Management vs Time Management."},
        {"id": 56, "query": "I would like to do some exercises on Elementary Geometry."},
        {"id": 57, "query": "I'm confused about the difference between Lighting Design and Circadian Wellness and other parts of Design and Interior Architecture."},
        {"id": 58, "query": "Explain Sunken Treasures and Ancient Trade Routes to me, I used to know them but I forgot."},
        {"id": 59, "query": "Explain Nanotechnologies for Water-repellent or Fireproof Fabrics to me, I used to know them but I forgot."},
        {"id": 60, "query": "I'm writing an essay on Longevity and Anti-aging Medicine, any tips?"},
        {"id": 61, "query": "Is Atmospheric Electricity and the Genesis of Lightning actually useful in real life?"},
        {"id": 62, "query": "I'm writing an essay on Ketogenic Diet and Intermittent Fasting, any tips?"},
        {"id": 63, "query": "I need to prep for a Chemistry and Biochemistry quiz on Radioactivity and Nuclear Chemistry."},
        {"id": 64, "query": "Can you help me understand Nature Spirits: Fairies, Gnomes, and Nymphs?"},
        {"id": 65, "query": "I'm writing an essay on Neuroscience of Learning, any tips?"},
        {"id": 66, "query": "Explain AI in Medicine and Diagnostics to me, I used to know them but I forgot."},
        {"id": 67, "query": "I'm writing an essay on Economy of Italian Industrial Districts, any tips?"},
        {"id": 68, "query": "I would like to do some exercises on Types of Volcanoes: Shield, Stratovolcanoes, Calderas."},
        {"id": 69, "query": "Give me some advanced problems on Neuroplasticity and Habits."},
        {"id": 70, "query": "How does Statistics work exactly?"},
        {"id": 71, "query": "I'm confused about the difference between Pulsars and Magnetars and other parts of Astronomy and Astrophysics."},
        {"id": 72, "query": "I'm confused about the difference between Ethnobotany: The Relationship between Humans and Plants and other parts of Cultural Anthropology."},
        {"id": 73, "query": "Explain Derivatives to me, I used to know them but I forgot."},
        {"id": 74, "query": "Explain Glass Art (Murano and beyond) to me, I used to know them but I forgot."},
        {"id": 75, "query": "I'm looking for a deep dive into Prediction and Prevention of Natural Risks."},
        {"id": 76, "query": "Is History of the Phoenician Alphabet and Its Derivations actually useful in real life?"},
        {"id": 77, "query": "Is Earth and Straw Constructions actually useful in real life?"},
        {"id": 78, "query": "I'm confused about the difference between Lithium-ion Batteries and Alternatives (Solid State, Sodium) and other parts of Energy Engineering and Storage."},
        {"id": 79, "query": "Is Structure and Dynamics of Cell Membranes actually useful in real life?"},
        {"id": 80, "query": "Give me some advanced problems on Supercapacitors for Ultra-fast Charging."},
        {"id": 81, "query": "I would like to do some exercises on Dams and Water Resources Management."},
        {"id": 82, "query": "I'm confused about the difference between Paleoecology: Reconstructing Past Ecosystems and other parts of Paleontology and Prehistoric Life."},
        {"id": 83, "query": "Can you help me understand Democracy and Manipulation via Micro-targeting?"},
        {"id": 84, "query": "I need to prep for a Fashion and Costume quiz on The Influence of Pop Icons on Fashion."},
        {"id": 85, "query": "Explain Road Safety and Vision Zero to me, I used to know them but I forgot."},
        {"id": 86, "query": "Explain Lifelong Learning to me, I used to know them but I forgot."},
        {"id": 87, "query": "Explain Pollination and Co-evolution with Angiosperms to me, I used to know them but I forgot."},
        {"id": 88, "query": "What's the best way to learn about Marine Archaeology and Shipwrecks?"},
        {"id": 89, "query": "I'm looking for a deep dive into Commedia dell'Arte and Masks."},
        {"id": 90, "query": "I need to prep for a Aerospace and Aeronautical Engineering quiz on Aerodynamics and Flight Dynamics."},
        {"id": 91, "query": "Explain Biodiversity Conservation to me, I used to know them but I forgot."},
        {"id": 92, "query": "I'm confused about the difference between Minimally Invasive Robotic Surgery and other parts of Robotics and Automation."},
        {"id": 93, "query": "Explain Bloodstain Pattern Analysis (BPA) to me, I used to know them but I forgot."},
        {"id": 94, "query": "I need to prep for a Archaeology and Mysteries of the Past quiz on Construction Techniques of the Ancients."},
        {"id": 95, "query": "I'm looking for a deep dive into Museology and Exhibition Curating."},
        {"id": 96, "query": "I'm writing an essay on ESG Investments (Environmental, Social, Governance), any tips?"},
        {"id": 97, "query": "Can you help me understand Recommendation Algorithms and Filter Bubbles?"},
        {"id": 98, "query": "Tell me a fun fact about Inflation and Monetary Policies."},
        {"id": 99, "query": "I need to prep for a Sociology of Work and Organization quiz on Automation and Job Displacement."},
        {"id": 100, "query": "I have a Marine Sciences (Oceanography) test tomorrow, I'm panicking!"},
    ]
    
    # 2. Load the actual user data
    student_id = 80
    try:
        full_df = load_context_data(student_id)
        unique_topics = full_df['Topic'].unique().tolist() if not full_df.empty else []
    except Exception as e:
        print(f"Error loading context data: {e}")
        return

    results = []
    log_file = "bot_token_usage_log.csv"

    print(f"Starting automated test on {len(test_queries)} queries...\n")

    # 3. The Evaluation Loop
    for query_item in test_queries:
        query_id = query_item["id"]
        query = query_item["query"]
        print(f"[{query_id}/{len(test_queries)}] Testing: '{query}'")
        
        # Track token usage: get current log size before processing
        query_start_row = len(pd.read_csv(log_file)) if os.path.exists(log_file) else 0
        
        try:
            # --- PHASE A: The App's standard flow ---
            
            # Step A1: Router extracts topics
            # (Note: Assuming extract_relevant_topics internally calls log_token_usage)
            target_topics = extract_relevant_topics(API_KEY, MODEL, query, unique_topics)
            
            # Step A2: Filter real data and build context (NO MOCKS)
            if target_topics and not full_df.empty:
                filtered_df = full_df[full_df['Topic'].isin(target_topics)]
                
                # Token optimization: drop the redundant 'Topic' column and keep only essentials
                # Checking if you implemented the labels, otherwise fallback to raw scores
                columns_to_keep = ['Subtopic']
                if 'knowledge_label' in filtered_df.columns:
                    columns_to_keep.extend(['knowledge_label', 'lapse_label'])
                else:
                    columns_to_keep.extend(['lapse_score', 'knowledge_score'])
                    
                df_slim = filtered_df[columns_to_keep]
                real_context_text = df_slim.to_csv(index=False)
            else:
                real_context_text = "No specific data found for these topics."
            
            # Step A3: Build prompt and generate response
            system_prompt = build_system_prompt(real_context_text)
            
            # (Note: Assuming call_gemini internally calls log_token_usage)
            tutor_reply = call_gemini(API_KEY, MODEL, system_prompt, "", query, 0.2)
            
            # --- PHASE B: The Judge evaluates ---
            # (Note: If you want to track the Judge's tokens too, make sure evaluate_tutor_response 
            # implements log_token_usage internally!)
            evaluation = evaluate_tutor_response(API_KEY, query, target_topics, tutor_reply)
            
            # Get token usage for this query
            token_usage = get_token_usage_for_query(log_file, query_start_row)
            
            # 4. Save results for the Excel report
            results.append({
                "Query_ID": query_id,
                #"Query": query,
                #"Extracted_Topics": ", ".join(target_topics) if target_topics else "None",
                #"Tutor_Reply": tutor_reply,
                "Router_Score (1-10)": evaluation.get("router_score"),
                "Proactivity_Score (1-10)": evaluation.get("proactivity_score"),
                "Tone_Score (1-10)": evaluation.get("tone_score"),
                "Input_Tokens": token_usage["Input_Tokens"],
                "Output_Tokens": token_usage["Output_Tokens"],
                "Total_Tokens": token_usage["Total_Tokens"],
                #"Judge_Feedback": evaluation.get("feedback_notes")
            })
            
            # CRITICAL: Sleep to avoid API Rate Limit errors on free tiers
            time.sleep(60) 
            
        except Exception as e:
            print(f"Error during testing query '{query}': {e}")

    # 5. Data Export
    if results:
        df_results = pd.DataFrame(results)
        output_file = "ai_evaluation_report.csv"
        df_results.to_csv(output_file, index=False)
        print(f"\n✅ Test completed! Open '{output_file}' with Excel to see the LLM's grades.")
    else:
        print("\n❌ Test failed to generate any results.")

if __name__ == "__main__":
    run_automated_test()