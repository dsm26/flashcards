import streamlit as st
import pandas as pd
import random
import time
import toml
import urllib.parse

# Force layout optimization for mobile viewport frames
st.set_page_config(page_title="Language Flashcards", page_icon="🎴", layout="centered")

# ==============================================================================
# 1. READ PUBLIC CONFIGURATION (FROM CONFIG FILE)
# ==============================================================================
try:
    config_data = toml.load("decks.toml")
except Exception as e:
    st.error(f"❌ Error reading 'decks.toml' configuration file. Ensure the file exists in the same folder. Technical Details: {str(e)}")
    st.stop()

# ==============================================================================
# 2. PERFORMANCE TRACKED DATA INGESTION (VIA CSV EXPORT URL)
# ==============================================================================
@st.cache_data(ttl=3600)
def load_vocab_sheet(spreadsheet_id, worksheet_name):
    """Fetches public sheet data instantly by converting the link to a CSV export stream."""
    start_time = time.perf_counter()
    
    # URL encode the tab name to safely handle spaces and special characters
    parsed_sheet_name = urllib.parse.quote(worksheet_name)
    
    # Target the Google Visualisation API endpoint for a fast CSV export stream
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={parsed_sheet_name}"
    
    # Load raw stream directly into a Pandas DataFrame
    df = pd.read_csv(export_url)
    
    elapsed_time = time.perf_counter() - start_time
    return df, elapsed_time

# ==============================================================================
# 3. SIDEBAR INTERFACE & CONFIGURATION
# ==============================================================================
st.sidebar.title("App Settings")

# Build map from the configuration file arrays
deck_map = {deck["display_name"]: deck for deck in config_data["decks"]}
selected_deck_name = st.sidebar.selectbox("Choose Vocab List", options=list(deck_map.keys()))
deck_config = deck_map[selected_deck_name]

# Global cache purging hook
if st.sidebar.button("🔄 Force Reload From Google Sheets"):
    st.cache_data.clear()
    st.rerun()

# Run connection data pipeline with explicit error catching
try:
    df, load_duration = load_vocab_sheet(
        deck_config["spreadsheet_id"], 
        deck_config["worksheet_name"]
    )
    
    # Structural Validation Check (Requires Chapter, Lang 1, Lang 2)
    if df.shape[1] < 3:
        st.error(f"❌ Spreadsheet Schema Error: The selected tab '{deck_config['worksheet_name']}' contains only {df.shape[1]} columns. It requires at least 3 columns to operate.")
        st.stop()

except Exception as e:
    st.error(f"❌ Failed to load vocabulary list. Verify that 'Anyone with the link can view' is enabled on your Google Sheet, and check that your spreadsheet_id and worksheet_name match perfectly inside decks.toml.\n\nError details: {str(e)}")
    st.stop()

# Print diagnostics performance logs to sidebar drawer
st.sidebar.markdown("---")
st.sidebar.metric(label="Data Fetch Time", value=f"{load_duration:.4f}s")
st.sidebar.caption(f"Total entries loaded: {len(df)} rows")

# ==============================================================================
# 4. ROBUST TIME-TRAVELING NAVIGATION ENGINE
# ==============================================================================
# Reset tracking states cleanly if user switches vocabulary lists mid-flight
if "current_deck_id" not in st.session_state or st.session_state.current_deck_id != deck_config["id"]:
    st.session_state.current_deck_id = deck_config["id"]
    st.session_state.history_stack = [0]       # Tracks actual dataframe row indices viewed
    st.session_state.history_pointer = 0       # Track where the user is looking inside the history stack
    st.session_state.flipped = False
    st.session_state.completed_sequential = False

# Layout session operational controls
order_mode = st.radio("Card Ordering Strategy", ["Sequential Track", "Randomized Shuffle"], horizontal=True)
display_mode = st.toggle("Display Language 1 First", value=True)

total_rows = len(df)
current_pointer = st.session_state.history_pointer
current_row_idx = st.session_state.history_stack[current_pointer]

def run_next_step():
    st.session_state.flipped = False
    
    # Case A: User backed over cards via "Previous" and is stepping back forward through history
    if st.session_state.history_pointer < len(st.session_state.history_stack) - 1:
        st.session_state.history_pointer += 1
        
    # Case B: User is on the cutting edge of history and needs a brand new card generated
    else:
        if order_mode == "Sequential Track":
            next_row = current_row_idx + 1
            if next_row >= total_rows:
                st.session_state.completed_sequential = True
            else:
                st.session_state.history_stack.append(next_row)
                st.session_state.history_pointer += 1
        else:
            # Randomized generation appends a random row number to the stack
            next_row = random.randint(0, total_rows - 1)
            st.session_state.history_stack.append(next_row)
            st.session_state.history_pointer += 1

def run_prev_step():
    if st.session_state.history_pointer > 0:
        st.session_state.history_pointer -= 1
        st.session_state.flipped = False
        st.session_state.completed_sequential = False

def reset_deck_session():
    st.session_state.history_stack = [0]
    st.session_state.history_pointer = 0
    st.session_state.flipped = False
    st.session_state.completed_sequential = False

# ==============================================================================
# 5. MOBILE APP DISPLAY RENDERING (CSS TRICKS)
# ==============================================================================
st.write("---")
st.markdown(f"**Card Session Tracker:** Card #{current_pointer + 1} viewed | Mapped Row {current_row_idx + 1} of {total_rows}")

# Inject adaptive css styling based on configuration constraints for font sizing
card_font_size = deck_config.get("font_size_px", 28)
st.markdown(f"""
    <style>
    .flashcard-frame {{
        background-color: var(--background-secondary-color);
        border: 2px solid var(--primary-color);
        border-radius: 12px;
        padding: 35px 15px;
        text-align: center;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 15px;
    }}
    .main-term {{ 
        font-size: {card_font_size}px !important; 
        font-weight: bold; 
        line-height: 1.3; 
    }}
    </style>
""", unsafe_allowed_html=True)

if st.session_state.completed_sequential:
    st.warning("🎉 **End of Deck Reached!** You have walked sequentially through every single card in this list.")
    if st.button("🔄 Start This Deck Over Again", use_container_width=True):
        reset_deck_session()
        st.rerun()
else:
    # Read row parameters using strict numerical index assignments
    active_row = df.iloc[current_row_idx]
    
    card_chapter = active_row.iloc[0]  # Column 1 (Index 0)
    card_lang_1  = active_row.iloc[1]  # Column 2 (Index 1)
    card_lang_2  = active_row.iloc[2]  # Column 3 (Index 2)
    
    # Catch optional comments row block if it exists
    card_comment = active_row.iloc[3] if len(active_row) > 3 else ""

    st.caption(f"📂 Section / Grouping: **{card_chapter}**")
    
    # Interface toggle display state controller logic
    is_front = (display_mode and not st.session_state.flipped) or (not display_mode and st.session_state.flipped)
    display_heading = card_lang_1 if is_front else card_lang_2
    side_label = "Language 1" if is_front else "Language 2"

    # Render out custom mobile container card frame
    st.markdown(f"""
        <div class="flashcard-frame">
            <span style="font-size:11px; text-transform:uppercase; color:var(--primary-color); font-weight:bold; margin-bottom:10px;">{side_label}</span>
            <div class="main-term">{display_heading}</div>
        </div>
    """, unsafe_allowed_html=True)

    # Display target footnotes exclusively if flipped open and valid
    if st.session_state.flipped and pd.notna(card_comment) and str(card_comment).strip() != "":
        st.info(f"💡 **Note:** {card_comment}")

    if st.button("🔄 Flip Card", use_container_width=True, type="primary"):
        st.session_state.flipped = not st.session_state.flipped
        st.rerun()

    # Nav Control Array Matrix
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        st.button("⬅️ Previous", use_container_width=True, on_click=run_prev_step, disabled=(current_pointer == 0))
    with nav_col2:
        st.button("Next ➡️", use_container_width=True, on_click=run_next_step)

