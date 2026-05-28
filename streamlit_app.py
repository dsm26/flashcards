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
# INDESTRUCTIBLE MOBILE GRID OVERRIDE (FORCES ALL COLUMNS SIDE-BY-SIDE ON IPHONES)
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
    if st.session_state.history_pointer > 0:
        st.session_state.history_pointer -= 1
        st.session_state.completed_sequential = False

def reset_deck_session():
    st.session_state.history_stack = [0]
    st.session_state.history_pointer = 0
    st.session_state.completed_sequential = False

# ==============================================================================
# 5. STREAMLINED UI DISPLAY (MOBILE OPTIMIZED)
# ==============================================================================
# Pull explicit column names directly from your Google Sheet headers
lang_1_header = str(df.columns[1]).strip()
lang_2_header = str(df.columns[2]).strip()

selected_first_lang = st.selectbox(
    "Show First:", 
    options=[lang_1_header, lang_2_header],
    index=0
)
display_mode = (selected_first_lang == lang_1_header)

if st.session_state.completed_sequential:
    st.warning("🎉 **End of Deck Reached!** You have walked sequentially through every single card in this list.")
    if st.button("🔄 Start This Deck Over Again", use_container_width=True):
        reset_deck_session()
        st.rerun()
else:
    active_row = df.iloc[current_row_idx]
    
    # Safe text conversions to protect against unexpected types
    card_chapter = str(active_row.iloc[0]) if pd.notna(active_row.iloc[0]) else "General"
    card_lang_1  = str(active_row.iloc[1]) if pd.notna(active_row.iloc[1]) else ""
    card_lang_2  = str(active_row.iloc[2]) if pd.notna(active_row.iloc[2]) else ""
    
    # 4th Column check: Phonetics/Pinyin (Index 3, Column D)
    has_phonetics_col = len(active_row) > 3
    card_phonetics = str(active_row.iloc[3]).strip() if (has_phonetics_col and pd.notna(active_row.iloc[3])) else ""
    
    # 5th Column check: Comments/Footnotes (Index 4, Column E)
    card_comment = str(active_row.iloc[4]).strip() if (len(active_row) > 4 and pd.notna(active_row.iloc[4])) else ""
    
    # Check if the phonetics column contains actual data anywhere across the dataset
    show_phonetics_option = False
    if has_phonetics_col:
        has_real_data = df.iloc[:, 3].dropna().astype(str).str.strip().str.len().gt(0).any()
        if has_real_data:
            show_phonetics_option = True

    # REORDERED High-density checkbox settings bar: [Answer] [Phonetics] [Random]
    col_ans, col_phon, col_rand = st.columns(3)
    with col_ans:
        reveal_answer = st.checkbox("Show Answer", value=False)
    with col_phon:
        if show_phonetics_option:
            st.checkbox("Phonetics", key="toggle_phonetics")
        else:
            # Render empty space placeholder to preserve grid mapping structure on devices
            st.write("")
    with col_rand:
        random_mode = st.checkbox("Random", value=False)

    # Determine deck type
    is_chinese_deck = "zh" in str(deck_config["id"]).lower()

    # Get user specified size for foreign string (defaults to 34 for clear Chinese viewing)
    try:
        user_foreign_size = int(deck_config.get("font_size_px", 34))
    except (ValueError, TypeError):
        user_foreign_size = 34

    # Assign text values and fonts dynamically based on selection orientation
    if display_mode:
        # Foreign (Lang 1) is at the top, Native (Lang 2) is at the bottom
        top_display_text = card_lang_1
        bottom_display_text = card_lang_2
        
        top_font_size = user_foreign_size if is_chinese_deck else 24
        bottom_font_size = 22 
    else:
        # Native (Lang 2) is at the top, Foreign (Lang 1) is at the bottom
        top_display_text = card_lang_2
        bottom_display_text = card_lang_1
        
        top_font_size = 22 
        bottom_font_size = user_foreign_size if is_chinese_deck else 24 

    # ==============================================================================
    # ASYMMETRICAL PHONETICS LOGIC MATRIX IMPLEMENTATION
    # ==============================================================================
    phonetics_visible = False
    if show_phonetics_option and st.session_state.get("toggle_phonetics", False) and card_phonetics:
        if display_mode:
            phonetics_visible = True
        else:
            if reveal_answer:
                phonetics_visible = True

    # Build layout fragments dynamically with calculated structural font sizes
    answer_html = f"<div style='color: #FF4B4B; font-size: {bottom_font_size}px; margin-top: 10px; font-weight: normal;'>{bottom_display_text}</div>" if reveal_answer else ""
    phonetics_html = f"<div style='color: #888888; font-size: 22px; margin-top: 10px; font-weight: normal;'>🗣️ {card_phonetics}</div>" if phonetics_visible else ""

    # Fixed-height canvas frame document utilizing native device color schemes
    card_content_html = f"""
    <style>
        .card-canvas {{
            background-color: #1E1E1E; /* Core Dark Theme */
            border: 2px solid #36393F;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overflow-y: auto;
            box-sizing: border-box;
        }}
        .main-text {{
            font-size: {top_font_size}px; 
            font-weight: normal; 
            color: #FFFFFF; 
            line-height: 1.2;
        }}
        @media (prefers-color-scheme: light) {{
            .card-canvas {{
                background-color: #F0F2F6; /* Core Light Theme */
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
    components.html(card_content_html, height=146)

    # 🔊 FIXED AUDIO PLAYER: Always reads card_lang_1 (Foreign String)
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

    # Pure, native Streamlit navigation buttons row (Forced side-by-side by CSS layout engine)
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        st.button("⬅️ Previous", use_container_width=True, on_click=run_prev_step, disabled=(current_pointer == 0))
    with nav_col2:
        st.button("Next ➡️", use_container_width=True, on_click=run_next_step, args=(random_mode,))

    # Native, centered bottom index string tracker
    st.caption(f"Card {current_pointer + 1} of {total_rows} &nbsp;|&nbsp; Group: {card_chapter}")
