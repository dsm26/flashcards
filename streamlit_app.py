import streamlit as st
import pandas as pd
import random
import time
import toml
import urllib.parse

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
    st.session_state.flipped = False
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
    st.session_state.flipped = False
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
# 5. STREAMLINED UI RENDERING (COMPACT MOBILE VIEW)
# ==============================================================================
display_mode = st.toggle("Display Language 1 First", value=True)

if st.session_state.completed_sequential:
    st.warning("🎉 **End of Deck Reached!** You have walked sequentially through every single card in this list.")
    if st.button("🔄 Start This Deck Over Again", use_container_width=True):
        reset_deck_session()
        st.rerun()
else:
    active_row = df.iloc[current_row_idx]
    
    # Core variables mapping safely
    card_chapter = str(active_row.iloc[0]) if pd.notna(active_row.iloc[0]) else "General"
    card_lang_1  = str(active_row.iloc[1]) if pd.notna(active_row.iloc[1]) else ""
    card_lang_2  = str(active_row.iloc[2]) if pd.notna(active_row.iloc[2]) else ""
    
    # 4th Column check: Phonetics/Pinyin (Index 3, Column D)
    has_phonetics_col = len(active_row) > 3
    card_phonetics = str(active_row.iloc[3]).strip() if (has_phonetics_col and pd.notna(active_row.iloc[3])) else ""
    
    # 5th Column check: Comments/Footnotes (Index 4, Column E)
    card_comment = str(active_row.iloc[4]).strip() if (len(active_row) > 4 and pd.notna(active_row.iloc[4])) else ""
    
    # Evaluate global availability of data inside the Phonetics column across the entire sheet
    # Only displays the checkbox if the column exists and has actual data somewhere in it
    show_phonetics_option = False
    if has_phonetics_col:
        # Check if column 3 has any valid non-null entries anywhere
        has_real_data = df.iloc[:, 3].dropna().astype(str).str.strip().str.len().gt(0).any()
        if has_real_data:
            show_phonetics_option = True

    is_front = (display_mode and not st.session_state.flipped) or (not display_mode and st.session_state.flipped)
    display_heading = card_lang_1 if is_front else card_lang_2

    # Clean, bordered card canvas
    with st.container(border=True):
        try:
            user_font_size = int(deck_config.get("font_size_px", 28))
        except (ValueError, TypeError):
            user_font_size = 28
        
        # Render the primary text
        if user_font_size >= 36:
            st.title(f"{display_heading}")
        else:
            st.subheader(f"{display_heading}")
            
        # Render the optional phonetics layer if conditions match
        # It displays only on the "Native/Language 1" side of the card, and only when toggled on
        if is_front and show_phonetics_option and st.session_state.get("toggle_phonetics", False) and card_phonetics:
            st.caption(f"🗣️ {card_phonetics}")

    # Display optional footnotes safely
    if st.session_state.flipped and card_comment != "":
        st.info(f"💡 **Note:** {card_comment}")

    if st.button("🔄 Flip Card", use_container_width=True, type="primary"):
        st.session_state.flipped = not st.session_state.flipped
        st.rerun()

    # Layout multi-control flags beneath card tightly
    col_rand, col_phon = st.columns(2)
    with col_rand:
        random_mode = st.checkbox("Randomized Shuffle", value=False)
    with col_phon:
        if show_phonetics_option:
            # Save toggle choice to session state so it persists across cards smoothly
            st.checkbox("Show Phonetics", key="toggle_phonetics")

    # Clean layout controls grid
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        st.button("⬅️ Previous", use_container_width=True, on_click=run_prev_step, disabled=(current_pointer == 0))
    with nav_col2:
        st.button("Next ➡️", use_container_width=True, on_click=run_next_step, args=(random_mode,))

    # Native, centered text tracker at the absolute bottom
    st.caption(f"Card {current_pointer + 1} of {total_rows} &nbsp;|&nbsp; Group: {card_chapter}")
