import streamlit as st
import pandas as pd
import random
import time
import toml
import urllib.parse
import streamlit.components.v1 as components

# Force layout optimization for mobile viewports
st.set_page_config(page_title="Language Flashcards", page_icon="🎴", layout="centered")

# ==============================================================================
# 1. READ CONFIGURATION FILE (FROM GITHUB)
# ==============================================================================
try:
    config_data = toml.load("decks.toml")
except Exception as e:
    st.error(f"❌ Error reading 'decks.toml' configuration file. Technical Details: {str(e)}")
    st.stop()

# ==============================================================================
# 2. DATA INGESTION (VIA CSV EXPORT URL)
# ==============================================================================
@st.cache_data(ttl=3600)
def load_vocab_sheet(spreadsheet_id, worksheet_name):
    """Fetches public sheet data instantly by converting the link to a CSV export stream."""
    start_time = time.perf_counter()
    parsed_sheet_name = urllib.parse.quote(worksheet_name)
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={parsed_sheet_name}"
    df = pd.read_csv(export_url)
    elapsed_time = time.perf_counter() - start_time
    return df, elapsed_time

# ==============================================================================
# 3. SIDEBAR INTERFACE & CONFIGURATION
# ==============================================================================
st.sidebar.title("App Settings")

deck_map = {deck["display_name"]: deck for deck in config_data["decks"]}
selected_deck_name = st.sidebar.selectbox("Choose Vocab List", options=list(deck_map.keys()))
deck_config = deck_map[selected_deck_name]

if st.sidebar.button("🔄 Force Reload From Google Sheets"):
    st.cache_data.clear()
    st.rerun()

try:
    df, load_duration = load_vocab_sheet(
        deck_config["spreadsheet_id"], 
        deck_config["worksheet_name"]
    )
    
    if df is None or df.empty:
        st.error(f"❌ Data Error: The tab '{deck_config['worksheet_name']}' is empty.")
        st.stop()
        
    if df.shape[1] < 3:
        st.error(f"❌ Spreadsheet Schema Error: Requires at least 3 columns (Chapter, Lang 1, Lang 2).")
        st.stop()

except Exception as e:
    st.error(f"❌ Failed to load vocabulary list. Error details: {str(e)}")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.metric(label="Data Fetch Time", value=f"{load_duration:.4f}s")
st.sidebar.caption(f"Total entries loaded: {len(df)} rows")

# ==============================================================================
# 4. NAVIGATION ENGINE
# ==============================================================================
if "current_deck_id" not in st.session_state or st.session_state.current_deck_id != deck_config["id"]:
    st.session_state.current_deck_id = deck_config["id"]
    st.session_state.history_stack = [0]       
    st.session_state.history_pointer = 0       
    st.session_state.completed_sequential = False

total_rows = len(df)
current_pointer = st.session_state.history_pointer

if current_pointer >= len(st.session_state.history_stack):
    st.session_state.history_pointer = len(st.session_state.history_stack) - 1
    current_pointer = st.session_state.history_pointer

current_row_idx = st.session_state.history_stack[current_pointer]

if current_row_idx >= total_rows:
    st.session_state.history_stack = [0]
    st.session_state.history_pointer = 0
    current_row_idx = 0

def run_next_step(is_randomized):
    if st.session_state.history_pointer < len(st.session_state.history_stack) - 1:
        st.session_state.history_pointer += 1
    else:
        if not is_randomized:
            next_row = current_row_idx + 1
            if next_row >= total_rows:
                st.session_state.completed_sequential = True
            else:
                st.session_state.history_stack.append(next_row)
                st.session_state.history_pointer += 1
        else:
            next_row = random.randint(0, total_rows - 1)
            st.session_state.history_stack.append(next_row)
            st.session_state.history_pointer += 1

def run_prev_step():
    if st.session_state.history
