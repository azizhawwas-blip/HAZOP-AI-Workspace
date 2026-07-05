import streamlit as st
import pandas as pd
import json
import google.genai as genai
from PIL import Image
import io

# Set up clean app viewport layout for Electrical Workspace
st.set_page_config(page_title="AI Electrical Safety Workspace", page_icon="⚡", layout="centered")

st.title("⚡ AI Electrical Safety & Substation Workspace")
st.write("Leverage advanced multi-modal AI to parse Single-Line Diagrams (SLDs), run automated hazard analyses, or consult the electrical code assistant.")

# --- 1. Fetch Key Behind the Scenes Dynamically ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("🔑 API Key missing! Please add GEMINI_API_KEY to your local `.streamlit/secrets.toml` file.")
    st.stop()

# Initialize clean GenAI client
client = genai.Client(api_key=api_key)

# --- 2. Define App Tabs Layout ---
tab1, tab2 = st.tabs(["🚀 Automated Substation Analysis", "💬 Electrical Code Copilot"])

# =========================================================================
# TAB 1: AUTOMATED SUBSTATION HAZARD ENGINE
# =========================================================================
with tab1:
    st.header("SLD Safety & Hazard Automation")
    st.write("Upload an Electrical Single-Line Diagram (SLD) to run a structured electrical failure mode and protection study.")

    uploaded_file = st.file_uploader("Upload Single-Line Diagram (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="sld_uploader")

    # Strict Electrical Engineering prompts inside the automation logic
    PROMPT_1 = """
    You are an expert Principal Electrical Safety Engineer and Substation Design Specialist. Analyze this Electrical Single-Line Diagram (SLD) or Substation layout and divide it into logical zones/nodes.
    Follow these rules for node separation:
    1. Divide nodes based on distinct voltage levels (e.g., High Voltage incoming, Medium Voltage distribution, Low Voltage auxiliary).
    2. Create new nodes at major equipment boundaries (e.g., Transformer primary side vs. secondary side; Switchgear busbars).
    3. Identify critical protection zones bounded by Circuit Breakers, Fuses, and Protective Relays (e.g., 50/51 overcurrent, 87 differential, 51N ground fault).

    You must return your output ONLY as a valid JSON object. Do not include any conversational text or markdown blocks (like ```json).
    Structure:
    {
      "study_metadata": {"substation_name": "Extracted Substation/Facility Name from SLD"},
      "nodes": [
        {
          "node_number": 1,
          "node_name": "Descriptive Bus/Equipment Tag (e.g., 13.8kV Switchgear Bus A)",
          "design_intent": "Purpose of this electrical segment or power path",
          "electrical_specs": {
            "voltage_level": "e.g., 13.8 kV / 480 V",
            "rated_current": "Visible bus continuous current rating (Amps) or Estimated rating",
            "grounding_system": "Solidly Grounded / Resistance Grounded / Ungrounded"
          }
        }
      ]
    }
    """

PROMPT_2 = """
    You are a strict, highly conservative Principal Electrical Protection Auditor. Your job is to validate the provided Single-Line Diagram (SLD) layout against standard power distribution design principles (IEEE / NFPA 70E / IEC). 
    
    CRITICAL INSTRUCTION: Do not exaggerate or create hypothetical risks. If a zone has appropriate visible or logically implied engineered safeguards (such as standard overcurrent relays, fuses, or surge arresters for its voltage level), you must explicitly mark it as compliant. Only flag a row as a 'Risk/Finding' if there is a clear protection gap, missing critical hardware safeguard, or a severe operational hazard.

    Evaluate each zone for these exact conditions:
    1. Short Circuit / Overcurrent Protection
    2. Overvoltage / Lightning Surge Protection
    3. Loss of Protection Coordination (e.g., a critical bus lacking any downstream isolation)

    You must return your output ONLY as a valid JSON array of objects. Do not include any conversational text or markdown formatting.
    
    Structure the JSON output exactly like this:
    [
      {
        "Zone Number": 1,
        "Equipment Zone": "Name from input JSON",
        "Audit Status": "COMPLIANT / RISK DETECTED",
        "Identified Gap": "Specify the exact engineering gap if status is RISK DETECTED. If status is COMPLIANT, write 'No risk detected. Standard protective elements are sufficient.'",
        "Credible Consequence": "None (if Compliant) OR the specific physical damage/arc flash hazard if a gap exists",
        "Required Engineered Safeguard": "The specific physical hardware component required to close the gap",
        "Targeted Action Item": "Clear, concise engineering recommendation"
      }
    ]
    """

    if uploaded_file:
        # Prevent old test data bleed if user shifts drawings mid-session
        if "current_file" not in st.session_state or st.session_state["current_file"] != uploaded_file.name:
            st.session_state["current_file"] = uploaded_file.name
            if "final_df" in st.session_state:
                del st.session_state["final_df"]

        if st.button("🚀 Run Substation Risk Analysis", type="primary"):
            try:
                image_bytes = uploaded_file.read()
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                with st.status("Processing Electrical Fault Pipeline...", expanded=True) as status:
                    status.update(label="🔍 Analyzing SLD layout and zoning voltage paths...", state="running")
                    
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
                    
                    status.update(label="🛡️ Evaluating protection settings and fault consequences...", state="running")
                    
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
                    
                    status.update(label="🎉 Analysis complete! Generating electrical safety sheets...", state="complete")

                st.session_state["final_df"] = pd.DataFrame(final_hazop_rows)
                st.balloons()

            except json.JSONDecodeError:
                st.error("🛑 The AI model output did not form a clean electrical data structure. Please try running the study again.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {str(e)}")

        # Present structured data outputs explicitly isolated to this current run file name
        if "final_df" in st.session_state:
            df = st.session_state["final_df"]
            st.success("📝 Report Generated Successfully from SLD Diagram!")
            
            st.subheader("Preview Substation Hazard Analysis")
            st.dataframe(df)
            
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            st.download_button(
                label="📥 Download Excel Electrical Hazard Sheet",
                data=excel_buffer,
                file_name=f"Electrical_Hazard_Report_{st.session_state['current_file']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# =========================================================================
# TAB 2: ELECTRICAL CODE COPILOT
# =========================================================================
with tab2:
    st.header("💬 Electrical Code Copilot")
    st.write("Consult the assistant regarding IEEE power guidelines, NFPA 70E arc flash boundaries, substation grounding, or breaker sizing.")

    # Initialize separate chronological history storage array for the chatbot interface
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Hello! I am your power distribution safety assistant. Ask me anything about substation design safety, protection relay coordination, grounding calculations, or electrical codes (IEEE, NEC, IEC)."}
        ]

    # Render previous historical message dialogue boxes dynamically inside viewports
    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Collect conversational typed prompt input text lines
    if user_query := st.chat_input("Ask an electrical safety question..."):
        # Display the user message locally right away
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state["chat_history"].append({"role": "user", "content": user_query})

        # Submit request directly down to live engine stream pipeline
        try:
            with st.spinner("Analyzing electrical context..."):
                # System configuration injected into the baseline interaction text block
                system_context = "You are a professional, highly analytical Principal Electrical Safety Engineer and power distribution expert. Provide expert technical guidance based on IEEE, NFPA 70E, NEC, and IEC standards."
                
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
