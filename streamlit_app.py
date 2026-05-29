import streamlit as st
import pandas as pd
import random
import time
import toml
import urllib.parse
import re
import streamlit.components.v1 as components

# Force layout optimization for mobile viewports
st.set_page_config(page_title="Language Flashcards", page_icon="🎴", layout="centered")

# ==============================================================================
# INDESTRUCTIBLE MOBILE GRID & TARGETED SIDEBAR KEYBOARD BLOCKERS
# ==============================================================================
st.markdown(
    """
    <style>
    /* Target all variations of Streamlit horizontal column layouts */
    div[data-testid="stHorizontalBlock"], 
    .stHorizontalBlock, 
    div[data-fieldname="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 10px !important;
    }
    
    /* Force column items to evenly split the row instead of snapping to full width */
    div[data-testid="stHorizontalBlock"] > div,
    .stHorizontalBlock > div {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        width: 100% !important;
    }

    /* Target ONLY the main body selectbox (excludes stSidebar entirely) */
    div[data-testid="stMainBlockContainer"] div[data-testid="stSelectbox"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        gap: 15px !important;
        width: 100% !important;
    }

    /* Prevent the main body label from wrapping or breaking text alignments */
    div[data-testid="stMainBlockContainer"] div[data-testid="stSelectbox"] label {
        margin-bottom: 0 !important;
        white-space: nowrap !important;
        min-width: fit-content !important;
    }

    /* Ensure the structural inner select wrapper takes up the remaining row space */
    div[data-testid="stMainBlockContainer"] div[data-testid="stSelectbox"] > div:nth-child(2) {
        flex-grow: 1 !important;
        width: auto !important;
    }

    /* BULLETPROOF MOBILE KEYBOARD DISABLEMENT */
    div[data-testid="stSidebar"] div[role="combobox"] input,
    div[data-testid="stSidebar"] input[role="combobox"] {
        pointer-events: none !important;
        inputmode: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

if st.sidebar.button("Reload GoogleSheet"):
    st.cache_data.clear()
    st.rerun()

try:
    df_raw, load_duration = load_vocab_sheet(
        deck_config["spreadsheet_id"], 
        deck_config["worksheet_name"]
    )
    
    if df_raw is None or df_raw.empty:
        st.error(f"❌ Data Error: The tab '{deck_config['worksheet_name']}' is empty.")
        st.stop()
        
    if df_raw.shape[1] < 3:
        st.error(f"❌ Spreadsheet Schema Error: Requires at least 3 columns (Chapter, Lang 1, Lang 2).")
        st.stop()

except Exception as e:
    st.error(f"❌ Failed to load vocabulary list. Error details: {str(e)}")
    st.stop()

st.sidebar.markdown("---")

# ------------------------------------------------------------------------------
# HYBRID FLEXIBLE SORTING ALGORITHM FOR ANY CHAPTER STYLE
# ------------------------------------------------------------------------------
def flexible_sort_key(text):
    """Breaks text into chunks of strings and numbers for natural sorting."""
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r'(\d+)', str(text))]

raw_chapters = df_raw.iloc[:, 0].dropna().astype(str).str.strip().unique()
sorted_chapters = sorted(list(raw_chapters), key=flexible_sort_key)
chapter_options = ["All Chapters"] + sorted_chapters

selected_chapter = st.sidebar.selectbox("Filter by Chapter", options=chapter_options)

if selected_chapter == "All Chapters":
    df = df_raw.copy()
else:
    df = df_raw[df_raw.iloc[:, 0].astype(str).str.strip() == selected_chapter].copy()

total_rows = len(df)

# ==============================================================================
# 4. FIXED CORE NAVIGATION ENGINE & SLIDER JUMP INTELLIGENCE
# ==============================================================================
session_key_deck = f"deck_{deck_config['id']}"
session_key_chap = f"chap_{selected_chapter}"
current_track_id = session_key_deck + "_" + session_key_chap

# FIRST: Ensure state variables exist to prevent baseline AttributeError
if "current_index_pointer" not in st.session_state:
    st.session_state.current_index_pointer = 0

if "completed_sequential" not in st.session_state:
    st.session_state.completed_sequential = False

if "shuffled_order" not in st.session_state:
    st.session_state.shuffled_order = []

# Track if user swapped active list configurations or chapters entirely
if "current_deck_track" not in st.session_state or st.session_state.current_deck_track != current_track_id:
    st.session_state.current_deck_track = current_track_id
    st.session_state.current_index_pointer = 0
    st.session_state.completed_sequential = False
    st.session_state.shuffled_order = []

# Boundary check safety verification execution step
if st.session_state.current_index_pointer >= total_rows and total_rows > 0:
    st.session_state.current_index_pointer = 0

# Generate discrete step points (0, 20, 40...)
jump_indices = list(range(0, total_rows, 20)) if total_rows > 0 else [0]

# Determine the closest matching step lower boundary
current_idx = st.session_state.current_index_pointer
closest_base = max([i for i in jump_indices if i <= current_idx]) if jump_indices else 0

def on_slider_move():
    # Force updating target frame base accurately
    st.session_state.current_index_pointer = st.session_state.jump_slider_widget
    st.session_state.completed_sequential = False

# Render the mobile friendly slider selector
st.sidebar.select_slider(
    "Jump to section:",
    options=jump_indices,
    value=closest_base,
    format_func=lambda x: f"Card {x + 1}",
    key="jump_slider_widget",
    on_change=on_slider_move,
    disabled=(total_rows == 0)
)

st.sidebar.markdown("---")
st.sidebar.metric(label="Data Fetch Time", value=f"{load_duration:.4f}s")
st.sidebar.caption(f"Loaded {len(df_raw)} total entries from sheet.")

# Navigation Step Handlers
def run_next_step(is_randomized):
    if not is_randomized:
        next_row = st.session_state.current_index_pointer + 1
        if next_row >= total_rows:
            st.session_state.completed_sequential = True
        else:
            st.session_state.current_index_pointer = next_row
    else:
        # If random mode is on, ensure we have a valid shuffle sequence matching total rows
        if not st.session_state.shuffled_order or len(st.session_state.shuffled_order) != total_rows:
            st.session_state.shuffled_order = list(range(total_rows))
            random.shuffle(st.session_state.shuffled_order)
            
        try:
            current_shuff_pos = st.session_state.shuffled_order.index(st.session_state.current_index_pointer)
            next_shuff_pos = current_shuff_pos + 1
            
            # CHANGED: Instead of stopping the deck, infinite random mode generates a clean new rotation loop
            if next_shuff_pos >= total_rows:
                new_rotation = list(range(total_rows))
                random.shuffle(new_rotation)
                # Avoid immediately displaying the same card twice on rotation cutoff
                if total_rows > 1 and new_rotation[0] == st.session_state.current_index_pointer:
                    new_rotation[0], new_rotation[-1] = new_rotation[-1], new_rotation[0]
                st.session_state.shuffled_order = new_rotation
                st.session_state.current_index_pointer = st.session_state.shuffled_order[0]
            else:
                st.session_state.current_index_pointer = st.session_state.shuffled_order[next_shuff_pos]
        except ValueError:
            st.session_state.current_index_pointer = random.choice(st.session_state.shuffled_order)

def run_prev_step(is_randomized):
    if not is_randomized:
        if st.session_state.current_index_pointer > 0:
            st.session_state.current_index_pointer -= 1
            st.session_state.completed_sequential = False
    else:
        # Move back one step cleanly using the current active random sequence history
        if st.session_state.shuffled_order:
            try:
                current_shuff_pos = st.session_state.shuffled_order.index(st.session_state.current_index_pointer)
                if current_shuff_pos > 0:
                    st.session_state.current_index_pointer = st.session_state.shuffled_order[current_shuff_pos - 1]
                    st.session_state.completed_sequential = False
            except ValueError:
                pass

def reset_deck_session():
    st.session_state.current_index_pointer = 0
    st.session_state.completed_sequential = False
    st.session_state.shuffled_order = []

# ==============================================================================
# 5. STREAMLINED UI DISPLAY (MOBILE OPTIMIZED)
# ==============================================================================
lang_1_header = str(df.columns[1]).strip()
lang_2_header = str(df.columns[2]).strip()

selected_first_lang = st.selectbox(
    "Show First:", 
    options=[lang_1_header, lang_2_header],
    index=0
)
display_mode = (selected_first_lang == lang_1_header)

# Note: st.session_state.completed_sequential only triggers now during true sequential (Non-Random) mode paths
if total_rows == 0:
    st.warning("⚠️ No vocabulary items found matching your current search parameters or chapter selection criteria.")
elif st.session_state.completed_sequential and not st.session_state.get("toggle_random_widget", False):
    st.warning("🎉 **End of Deck Reached!** You have walked sequentially through every single card in this filtered view.")
    if st.button("🔄 Start This Filtered Deck Over", use_container_width=True):
        reset_deck_session()
        st.rerun()
else:
    current_row_idx = st.session_state.current_index_pointer
    active_row = df.iloc[current_row_idx]
    
    card_chapter = str(active_row.iloc[0]) if pd.notna(active_row.iloc[0]) else "General"
    card_lang_1  = str(active_row.iloc[1]) if pd.notna(active_row.iloc[1]) else ""
    card_lang_2  = str(active_row.iloc[2]) if pd.notna(active_row.iloc[2]) else ""
    
    has_phonetics_col = len(active_row) > 3
    card_phonetics = str(active_row.iloc[3]).strip() if (has_phonetics_col and pd.notna(active_row.iloc[3])) else ""
    card_comment = str(active_row.iloc[4]).strip() if (len(active_row) > 4 and pd.notna(active_row.iloc[4])) else ""
    
    show_phonetics_option = False
    if has_phonetics_col:
        has_real_data = df.iloc[:, 3].dropna().astype(str).str.strip().str.len().gt(0).any()
        if has_real_data:
            show_phonetics_option = True

    col_ans, col_phon, col_rand = st.columns(3)
    with col_ans:
        reveal_answer = st.checkbox("Show Answer", value=False)
    with col_phon:
        if show_phonetics_option:
            st.checkbox("Phonetics", key="toggle_phonetics")
        else:
            st.write("")
    with col_rand:
        # Added tracking key to safeguard dynamic interactive mode transitions cleanly
        random_mode = st.checkbox("Random", value=False, key="toggle_random_widget")
        if not random_mode and st.session_state.shuffled_order:
            st.session_state.shuffled_order = []

    is_chinese_deck = "zh" in str(deck_config["id"]).lower()

    try:
        user_foreign_size = int(deck_config.get("font_size_px", 34))
    except (ValueError, TypeError):
        user_foreign_size = 34

    if display_mode:
        top_display_text = card_lang_1
        bottom_display_text = card_lang_2
        top_font_size = user_foreign_size if is_chinese_deck else 24
        bottom_font_size = 22 
    else:
        top_display_text = card_lang_2
        bottom_display_text = card_lang_1
        top_font_size = 22 
        bottom_font_size = user_foreign_size if is_chinese_deck else 24 

    phonetics_visible = False
    if show_phonetics_option and st.session_state.get("toggle_phonetics", False) and card_phonetics:
        if display_mode:
            phonetics_visible = True
        else:
            if reveal_answer:
                phonetics_visible = True

    answer_html = f"<div style='color: #FF4B4B; font-size: {bottom_font_size}px; margin-top: 10px; font-weight: normal;'>{bottom_display_text}</div>" if reveal_answer else ""
    phonetics_html = f"<div style='color: #888888; font-size: 22px; margin-top: 10px; font-weight: normal;'>🗣️ {card_phonetics}</div>" if phonetics_visible else ""

    card_content_html = f"""
    <style>
        .card-canvas {{
            background-color: #1E1E1E; 
            border: 2px solid #36393F;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            height: 180px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overflow-y: auto;
            box-sizing: border-box;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }}
        .card-canvas::-webkit-scrollbar {{
            display: none !important;
            width: 0 !important;
            height: 0 !important;
        }}
        .main-text {{
            font-size: {top_font_size}px; 
            font-weight: normal; 
            color: #FFFFFF; 
            line-height: 1.2;
        }}
        @media (prefers-color-scheme: light) {{
            .card-canvas {{
                background-color: #F0F2F6; 
                border-color: #E0E2E6;
            }}
            .main-text {{
                color: #111111;
            }}
        }}
    </style>

    <div class="card-canvas">
        <div class="main-text">{top_display_text}</div>
        {answer_html}
        {phonetics_html}
    </div>
    """
    components.html(card_content_html, height=186)

    lang_code = "it-IT" if "it" in str(deck_config["id"]).lower() else "zh-CN" if "zh" in str(deck_config["id"]).lower() else "en-US"
    safe_speech_text = card_lang_1.replace("'", "\\'")
    
    tts_html = f"""
    <div style="text-align: center; margin-bottom: 5px;">
        <button onclick="speakText()" style="background: none; border: none; font-size: 28px; cursor: pointer; padding: 5px; touch-action: manipulation;">🔊</button>
    </div>
    <script>
    function speakText() {{
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            var utterance = new SpeechSynthesisUtterance('{safe_speech_text}');
            utterance.lang = '{lang_code}';
            utterance.rate = 0.85;
            window.speechSynthesis.speak(utterance);
        }}
    }}
    </script>
    """
    components.html(tts_html, height=44)

    if reveal_answer and card_comment != "":
        st.info(f"💡 **Note:** {card_comment}")

    # Render navigational controls using the auto-rotation arguments
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        is_at_start = False
        if random_mode and st.session_state.shuffled_order:
            try:
                is_at_start = (st.session_state.shuffled_order.index(st.session_state.current_index_pointer) == 0)
            except ValueError:
                pass
        else:
            is_at_start = (st.session_state.current_index_pointer == 0)

        st.button("⬅️ Previous", use_container_width=True, on_click=run_prev_step, args=(random_mode,), disabled=is_at_start)
    with nav_col2:
        st.button("Next ➡️", use_container_width=True, on_click=run_next_step, args=(random_mode,))

    if selected_chapter == "All Chapters":
        footer_string = f"Card {st.session_state.current_index_pointer + 1} of {total_rows} &nbsp;|&nbsp; Group: {card_chapter}"
    else:
        footer_string = f"Card {st.session_state.current_index_pointer + 1} of {total_rows} in {selected_chapter} &nbsp;|&nbsp; Total Deck: {len(df_raw)}"
        
    st.caption(f"<div style='text-align: center;'>{footer_string}</div>", unsafe_allow_html=True)
