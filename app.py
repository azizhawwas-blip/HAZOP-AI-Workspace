import streamlit as st
import pandas as pd
import json
import google.genai as genai
from PIL import Image
import io

# Set up clean app viewport layout
st.set_page_config(page_title="AI Process Safety Workspace", page_icon="🛡️", layout="centered")

st.title("🛡️ AI Process Safety Workspace")
st.write("Leverage advanced AI to generate structured risk assessments or consult the interactive safety assistant.")

# --- 1. Fetch Key Behind the Scenes Dynamically ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("🔑 API Key missing! Please add GEMINI_API_KEY to your local `.streamlit/secrets.toml` file.")
    st.stop()

# Initialize clean GenAI client
client = genai.Client(api_key=api_key)

# --- 2. Define App Tabs Layout ---
tab1, tab2 = st.tabs(["🚀 Automated HAZOP Generator", "💬 Safety Assistant Chat"])

# =========================================================================
# TAB 1: AUTOMATED HAZOP ENGINE
# =========================================================================
with tab1:
    st.header("P&ID HAZOP Automation")
    st.write("Upload a P&ID sheet to run a multi-stage automated safety loop analysis.")

    uploaded_file = st.file_uploader("Upload P&ID Diagram (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="hazop_uploader")

    # Strict engineering prompts inside the automation logic
    PROMPT_1 = """
    You are an expert Principal Process Safety Engineer and a certified HAZOP Leader. Analyze this P&ID drawing and divide it into logical HAZOP nodes.
    Follow these rules for node separation:
    1. Divide nodes based on lines with similar design intent, process parameters, or piping specifications.
    2. Create new nodes at major equipment boundaries (e.g., suction side of a pump is one node; discharge side is another).
    3. Identify distinct changes in process variables (Flow, Pressure, Temperature, Composition).

    You must return your output ONLY as a valid JSON object. Do not include any conversational text or markdown blocks (like ```json).
    Structure:
    {
      "study_metadata": {"system_name": "Extracted System Title from P&ID"},
      "nodes": [
        {
          "node_number": 1,
          "node_name": "Descriptive tag/line name",
          "design_intent": "Purpose of line/equipment segment",
          "process_conditions": {
            "fluid_phase": "Liquid/Gas",
            "operating_pressure": "Extracted or estimated operating limits",
            "pipe_specification": "Visible pipe spec/pressure rating"
          }
        }
      ]
    }
    """

    PROMPT_2 = """
    You are a Principal Process Safety Specialist. Take this JSON input detailing a P&ID node layout and perform a formal, rigorous Hazard and Operability (HAZOP) study. Loop through the nodes and evaluate standard deviations: More Flow, Less Flow, More Pressure, Less Pressure.

    For every deviation, determine:
    1. Credible Causes: Equipment failures (e.g., control valve fails, pump trips) or line configurations visible in the diagram data.
    2. Consequences: Direct operational impacts, safety hazards, or overpressurization risks.
    3. Engineered Safeguards: Hardware-based controls (e.g., PSVs, high-pressure alarms, check valves). Avoid administrative controls like "Follow SOP".
    4. Recommendations: Actionable engineering advice if design parameters are challenged.

    You must return your output ONLY as a valid JSON array of objects. Do not include any conversational text or markdown formatting.
    Structure:
    [
      {
        "Node Number": 1,
        "Node Name": "Name from input JSON",
        "Deviation": "More Pressure",
        "Credible Causes": "1. Specific cause text based on node conditions",
        "Consequences": "1. Specific safety impact text matching specifications",
        "Safeguards": "1. Expected physical hardware controls",
        "Recommendations": "1. Targeted engineering action item"
      }
    ]
    """

    if uploaded_file:
        # Prevent old test data bleed if user shifts drawings mid-session
        if "current_file" not in st.session_state or st.session_state["current_file"] != uploaded_file.name:
            st.session_state["current_file"] = uploaded_file.name
            if "final_df" in st.session_state:
                del st.session_state["final_df"]

        if st.button("🚀 Run Live HAZOP Analysis", type="primary"):
            try:
                image_bytes = uploaded_file.read()
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                with st.status("Processing Live HAZOP Pipeline...", expanded=True) as status:
                    status.update(label="🔍 Analyzing P&ID layout and compiling custom nodes...", state="running")
                    
                    try:
                        response_1 = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[pil_image, PROMPT_1]
                        )
                    except Exception as e:
                        if "503" in str(e) or "UNAVAILABLE" in str(e):
                            response_1 = client.models.generate_content(
                                model='gemini-2.5-flash-lite',
                                contents=[pil_image, PROMPT_1]
                            )
                        else:
                            raise e

                    raw_json_1 = response_1.text.replace("```json", "").replace("```", "").strip()
                    hidden_nodes_data = json.loads(raw_json_1)
                    
                    status.update(label="🛡️ Applying matrix logic and generating credible risk deviations...", state="running")
                    
                    try:
                        response_2 = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[f"Data:\n{json.dumps(hidden_nodes_data)}\n\nInstructions:\n{PROMPT_2}"]
                        )
                    except Exception as e:
                        if "503" in str(e) or "UNAVAILABLE" in str(e):
                            response_2 = client.models.generate_content(
                                model='gemini-2.5-flash-lite',
                                contents=[f"Data:\n{json.dumps(hidden_nodes_data)}\n\nInstructions:\n{PROMPT_2}"]
                            )
                        else:
                            raise e

                    raw_json_2 = response_2.text.replace("```json", "").replace("```", "").strip()
                    final_hazop_rows = json.loads(raw_json_2)
                    
                    status.update(label="🎉 Assessment complete! Preparing download files...", state="complete")

                st.session_state["final_df"] = pd.DataFrame(final_hazop_rows)
                st.balloons()

            except json.JSONDecodeError:
                st.error("🛑 The AI model output did not form a clean data object structure. Please try running the study again.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")

        # Present structured data outputs explicitly isolated to this current run file name
        if "final_df" in st.session_state:
            df = st.session_state["final_df"]
            st.success("📝 Report Generated Successfully from P&ID Data!")
            
            st.subheader("Preview Generated Worksheet")
            st.dataframe(df)
            
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            st.download_button(
                label="📥 Download Real Excel HAZOP Sheet",
                data=excel_buffer,
                file_name=f"HAZOP_Report_{st.session_state['current_file']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# =========================================================================
# TAB 2: PROCESS SAFETY CHAT CO-PILOT
# =========================================================================
with tab2:
    st.header("💬 Process Safety Co-Pilot")
    st.write("Consult the assistant regarding process standards, SIL targets, risk scenarios, or methodology structures.")

    # Initialize separate chronological history storage array for the chatbot interface
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Hello! I am your process safety assistant. Ask me anything about risk assessment methodologies, international engineering guidelines, or hazard scenarios."}
        ]

    # Render previous historical message dialogue boxes dynamically inside viewports
    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Collect conversational typed prompt input text lines
    if user_query := st.chat_input("Ask a safety engineering question..."):
        # Display the user message locally right away
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state["chat_history"].append({"role": "user", "content": user_query})

        # Submit request directly down to live engine stream pipeline
        try:
            with st.spinner("Analyzing safety context..."):
                # System configuration injected into the baseline interaction text block
                system_context = "You are a professional, highly analytical Process Safety Engineer and technical advisor. Provide expert, clear engineering guidance."
                
                try:
                    # Attempt standard Flash model first
                    chat_response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[f"System Context: {system_context}\n\nUser Query: {user_query}"]
                    )
                except Exception as e:
                    # Fallback to high-availability Flash-Lite model if 503 server overload occurs
                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                        chat_response = client.models.generate_content(
                            model='gemini-2.5-flash-lite',
                            contents=[f"System Context: {system_context}\n\nUser Query: {user_query}"]
                        )
                    else:
                        raise e
                
                assistant_reply = chat_response.text
                
            # Display response output elements
            with st.chat_message("assistant"):
                st.write(assistant_reply)
            st.session_state["chat_history"].append({"role": "assistant", "content": assistant_reply})
            
        except Exception as e:
            st.error(f"Chat connection encountered an issue: {str(e)}")
