"""
Bolo Bill - Streamlit page.

Run:
    pip install streamlit requests
    streamlit run app.py

Needs ledger.py and bolo_stt.py in the same folder.
The voice part needs GNANI_API_KEY. The typed part works without it.
"""

import os
import tempfile
import uuid

import pandas as pd
import streamlit as st

import ledger

st.set_page_config(page_title="Bolo Bill", page_icon="🧾", layout="centered")
st.title("🧾 Bolo Bill")
st.caption("Boliye, hisaab apne aap likh jayega.  Speak or type your sale, kharcha or udhaar.")

# ---------------- Online (public) mode ----------------
# Set BOLO_PUBLIC=1 in the online app's Secrets. Then:
#   - every visitor gets a private ledger (nobody sees anybody else's entries)
#   - voice calls are limited, so strangers cannot use up the Gnani credits
PUBLIC = os.getenv("BOLO_PUBLIC") == "1"
DAILY_CAP = int(os.getenv("BOLO_DAILY_API_CAP", "150"))     # voice calls per day, all visitors
SESSION_CAP = int(os.getenv("BOLO_SESSION_API_CAP", "20"))  # voice calls per visitor

if PUBLIC:
    if "visitor_id" not in st.session_state:
        st.session_state.visitor_id = uuid.uuid4().hex[:12]
    ledger.use_file(os.path.join(tempfile.gettempdir(), f"bolo_{st.session_state.visitor_id}.csv"))
    st.info("Demo: your entries are private to you and are cleared when you close the page. "
            "Voice calls are limited per visitor, typing is unlimited.")


@st.cache_resource
def _usage():
    return {"day": "", "count": 0}


def api_allowed():
    """True if a Gnani voice call may be made now (only limited in online mode)."""
    if not PUBLIC:
        return True
    usage = _usage()
    today = ledger.now().strftime("%Y-%m-%d")
    if usage["day"] != today:
        usage["day"], usage["count"] = today, 0
    if usage["count"] >= DAILY_CAP:
        st.warning("Today's voice limit for this demo is finished. Typing still works - try again tomorrow.")
        return False
    if st.session_state.get("api_used", 0) >= SESSION_CAP:
        st.warning("You have used the voice calls allowed for this demo session. Typing still works.")
        return False
    usage["count"] += 1
    st.session_state["api_used"] = st.session_state.get("api_used", 0) + 1
    return True



def speak(text):
    """Read text out loud with Gnani Timbre (only if the API key is set)."""
    if not os.getenv("GNANI_API_KEY") or not api_allowed():
        return
    import bolo_tts  # imported here so the page works without the API file

    try:
        with st.spinner("Timbre is speaking..."):
            wav = bolo_tts.text_to_speech(text, language="auto")
        st.audio(wav, format="audio/wav", autoplay=True)
    except SystemExit as e:        # bolo_tts reports errors with sys.exit(message)
        st.error(str(e))


def save_if_ok(text):
    """A question gets an answer. A sale / kharcha / udhaar sentence gets saved."""
    if ledger.is_question(text):
        answer = ledger.answer_question(text)
        st.info(f"You asked: “{text}”")
        st.success(answer)
        speak(answer)
        return

    entry, problem = ledger.parse_sentence(text)
    if entry is None:
        st.warning(f"Heard: “{text}”\n\n{problem}")
        return
    ledger.add_entry(entry)
    who = f" - {entry['customer']}" if entry["customer"] else ""
    st.success(f"Saved: {ledger.TYPE_LABELS[entry['type']]}{who} - ₹{entry['amount']:g}")
    if entry["type"] in ("udhaar_diya", "udhaar_wapas") and not entry["customer"]:
        st.caption("Tip: say the name too, like “Ramesh ko do sau ka udhaar diya”.")


# ---------------- Input ----------------
tab_voice, tab_text = st.tabs(["🎤 Voice", "⌨️ Type"])

with tab_voice:
    if not os.getenv("GNANI_API_KEY"):
        st.info("Voice needs your Gnani API key (GNANI_API_KEY). Use the Type tab until it is ready.")
    else:
        style = st.radio(
            "Text style from Prisma",
            ["transcribe", "transliterate"],
            horizontal=True,
            help="transcribe = numbers as digits.  transliterate = English letters, numbers as words.",
        )
        audio = st.audio_input("Press the mic and say one sentence (under 30 seconds)")
        uploaded = st.file_uploader(
            "Or upload a recording (wav, mp3, m4a, ogg, flac, aac, mp4)",
            type=["wav", "mp3", "m4a", "ogg", "flac", "aac", "mp4"],
        )
        source = uploaded if uploaded is not None else audio
        if source is not None and st.button("Add to ledger", key="voice_add"):
            import bolo_stt  # imported here so the Type tab works without the API file

            if uploaded is not None:
                ext = os.path.splitext(uploaded.name)[1].lower()
                if ext == ".mp4":      # WhatsApp audio: Gnani wants .m4a for this
                    ext = ".m4a"
            else:
                ext = ".wav"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(source.getvalue())
                path = tmp.name
            try:
                heard = None
                if api_allowed():
                    with st.spinner("Listening..."):
                        heard = bolo_stt.speech_to_text(path, style)
                    if not heard:
                        st.warning("No speech heard. Please try again, closer to the mic.")
                if heard:
                    save_if_ok(heard)
            except SystemExit as e:        # bolo_stt reports errors with sys.exit(message)
                st.error(str(e))
            finally:
                os.remove(path)

with tab_text:
    with st.form("type_form", clear_on_submit=True):
        typed = st.text_input("Example: aaj 500 ka maal becha")
        submitted = st.form_submit_button("Add to ledger")
    if submitted and typed:
        save_if_ok(typed)

# ---------------- Today's totals ----------------
st.divider()
entries = ledger.load_entries()
if not entries:
    st.caption("No entries yet. Add one above, or try ready-made sample entries:")
    if st.button("Load sample entries"):
        for sample in ["aaj paanch sau ka maal becha", "do hazaar ka maal becha",
                       "teen sau ka saman kharida", "Ramesh ko do sau ka udhaar diya",
                       "Suresh ko paanch sau ka udhaar diya"]:
            sample_entry, _ = ledger.parse_sentence(sample)
            ledger.add_entry(sample_entry)
        st.rerun()
sums = ledger.totals_for_today(entries)

st.subheader("Aaj ka hisaab")
c1, c2, c3 = st.columns(3)
c1.metric("Bikri (sales)", f"₹{sums['sale']:g}")
c2.metric("Kharcha (expense)", f"₹{sums['expense']:g}")
c3.metric("Udhaar baaki", f"₹{sums['udhaar_baaki']:g}")
st.metric("Munafa (sales - kharcha)", f"₹{sums['profit']:g}")

# ---------------- Who owes how much ----------------
st.subheader("Kis ka kitna udhaar baaki hai")
balances = ledger.customer_balances(entries)
if balances:
    st.dataframe(
        [{"Naam": name, "Baaki (₹)": amount} for name, amount in
         sorted(balances.items(), key=lambda kv: -kv[1])],
        width="stretch",
        hide_index=True,
    )
else:
    st.write("Nobody owes anything. Say a name, like “Ramesh ko do sau ka udhaar diya”.")
st.caption("Tip: ask by voice or typing - “Ramesh ka kitna baaki hai?” or “aaj ka hisaab batao”.")

# ---------------- Table ----------------
st.subheader("Saari entries")
if entries:
    rows = [
        {
            "Time": e["time"],
            "Type": ledger.TYPE_LABELS.get(e["type"], e["type"]),
            "Naam": e["customer"],
            "Amount (₹)": e["amount"],
            "What was said": e["text"],
        }
        for e in reversed(entries)
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    if st.button("Undo last entry"):
        ledger.delete_last_entry()
        st.rerun()
else:
    st.write("No entries yet.")

# ---------------- Weekly report ----------------
st.subheader("Pichhle 7 din ka report")
week = ledger.daily_totals(entries, days=7)
table = pd.DataFrame(
    {
        "Date": [r["date"] for r in week],
        "Bikri": [r["sale"] for r in week],
        "Kharcha": [r["expense"] for r in week],
        "Munafa": [r["profit"] for r in week],
    }
)
st.bar_chart(table.set_index("Date")[["Bikri", "Kharcha"]])
st.dataframe(table, width="stretch", hide_index=True)

week_text = ledger.week_summary_text(week)
st.write(week_text)
r1, r2 = st.columns(2)
with r1:
    if os.getenv("GNANI_API_KEY") and st.button("🔊 Hafte ka hisaab sunao"):
        speak(week_text)
with r2:
    if os.path.exists(ledger.current_file()):
        with open(ledger.current_file(), encoding="utf-8") as f:
            csv_for_excel = f.read().encode("utf-8-sig")   # so Excel shows Hindi correctly
        st.download_button(
            "⬇️ Download ledger (Excel / CSV)",
            data=csv_for_excel,
            file_name="bolo_bill_ledger.csv",
            mime="text/csv",
        )

# ---------------- Spoken summary ----------------
st.subheader("Summary")
summary = ledger.summary_text(sums)
st.write(summary)

if not os.getenv("GNANI_API_KEY"):
    st.caption("Reading out loud needs your Gnani API key (GNANI_API_KEY).")
elif st.button("🔊 Suno hisaab (read it out)"):
    speak(summary)

# ---------------- Start fresh ----------------
with st.expander("⚙️ Settings"):
    st.write("Delete **all** entries and start with an empty ledger (for a fresh demo).")
    sure = st.checkbox("Yes, I want to delete everything")
    if st.button("🗑️ Start fresh", disabled=not sure):
        ledger.clear_all_entries()
        st.rerun()
