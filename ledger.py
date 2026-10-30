"""
Bolo Bill - ledger logic (no API needed).

Turns a sentence like "aaj 500 ka maal becha" into an entry:
    type   = sale / expense / udhaar_diya / udhaar_wapas
    amount = 500

Works with text from Gnani Prisma in either style:
  - transcribe    -> digits ("500")            <- easiest, try this first
  - transliterate -> number words ("paanch sau") <- handled for common numbers
"""

import csv
import os
import re
from datetime import datetime, timedelta

LEDGER_FILE = "ledger.csv"
FIELDS = ["time", "type", "amount", "text", "customer"]

# ---------- Words that tell us what kind of entry it is ----------
# Add more words here if your tests show Prisma writes something different.
UDHAAR_WORDS = ["udhaar", "udhar", "udhari", "उधार", "उधारी", "credit"]
BACK_WORDS = ["wapas", "vapas", "vasool", "chukaya", "chuka", "lautaya", "mila",
              "वापस", "वसूल", "चुकाया", "लौटाया", "मिला"]
SALE_WORDS = ["becha", "beche", "bech", "bikri", "bika", "sold", "sale", "sell",
              "बेचा", "बेचे", "बिक्री", "बिका"]
EXPENSE_WORDS = ["kharida", "kharide", "kharcha", "kharch", "kharidi", "bought", "buy",
                 "expense", "खरीदा", "खरीदे", "खर्च", "खर्चा"]

TYPE_LABELS = {
    "sale": "Bikri (sale)",
    "expense": "Kharcha (expense)",
    "udhaar_diya": "Udhaar diya (credit given)",
    "udhaar_wapas": "Udhaar wapas (credit received back)",
}

# ---------- Hindi number words (Latin letters) ----------
# Only common numbers. Odd ones like 45 ("paintalis") are NOT included:
# for those, use the "transcribe" style which gives digits.
UNITS = {
    "ek": 1, "do": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4,
    "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6, "cheh": 6, "chah": 6,
    "saat": 7, "sat": 7, "aath": 8, "ath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
    "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19,
    "bees": 20, "tees": 30, "chalis": 40, "pachas": 50, "saath": 60,
    "sattar": 70, "assi": 80, "nabbe": 90,
}
MULTIPLIERS = {"sau": 100, "hazaar": 1000, "hazar": 1000, "lakh": 100000}
SPECIAL = {"dedh": 1.5, "dhai": 2.5, "adhai": 2.5}


def _words_to_number(text):
    """Find a number written in Hindi words (Latin letters). Returns int or None."""
    words = re.findall(r"[a-z]+", text.lower())
    total, current, found = 0, 0, False
    for w in words:
        if w in UNITS:
            current += UNITS[w]
            found = True
        elif w in SPECIAL:
            current += SPECIAL[w]
            found = True
        elif w in MULTIPLIERS:
            found = True
            current = (current or 1) * MULTIPLIERS[w]
            if MULTIPLIERS[w] >= 1000:      # close a big group (hazaar / lakh)
                total += current
                current = 0
        elif found and current:
            # a normal word after the number ends it (e.g. "ka")
            break
    total += current
    return int(total) if found and total > 0 else None


def find_amount(text):
    """Return the amount in the sentence, or None. Digits first, then number words."""
    cleaned = text.replace(",", "")                 # 1,500 -> 1500
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        value = float(match.group())
        return int(value) if value.is_integer() else value
    return _words_to_number(text)


def _has_any(text, words):
    lower = text.lower()
    return any(w.lower() in lower for w in words)


def find_type(text):
    """Return 'sale', 'expense', 'udhaar_diya', 'udhaar_wapas' or None."""
    if _has_any(text, UDHAAR_WORDS):
        return "udhaar_wapas" if _has_any(text, BACK_WORDS) else "udhaar_diya"
    # "Ramesh ne paanch sau wapas kiye": a name plus "wapas" means money came back
    if _has_any(text, ["wapas", "vapas", "वापस"]) and find_customer(text):
        return "udhaar_wapas"
    if _has_any(text, SALE_WORDS):
        return "sale"
    if _has_any(text, EXPENSE_WORDS):
        return "expense"
    return None


# ---------- Customer name (for udhaar) ----------
# "Ramesh ko do sau ka udhaar diya"  -> customer = Ramesh
# "Ramesh ne teen sau wapas kiye"    -> customer = Ramesh
NAME_MARKERS = {"ko", "ne", "को", "ने"}
NOT_A_NAME = {
    "aaj", "आज", "kal", "कल", "abhi", "अभी", "phir", "fir", "फिर", "bhi", "भी",
    "maine", "mene", "मैंने", "humne", "hamne", "ka", "ki", "ke", "का", "की", "के",
    "rupaye", "rupay", "rs", "रुपये", "रुपए", "udhaar", "udhar", "उधार",
    "saman", "samaan", "maal", "सामान", "माल", "diya", "kiya", "diye", "kiye",
    "दिया", "किया", "दिये", "किये", "sirf", "bas", "total", "aur", "और", "hai", "है",
}


_TYPE_WORDS = {w.lower() for w in UDHAAR_WORDS + BACK_WORDS + SALE_WORDS + EXPENSE_WORDS}


def find_customer(text):
    """Return the customer name before 'ko' / 'ne', or '' if there is none."""
    tokens = re.findall(r"[^\s,।.?!]+", text)
    for i, tok in enumerate(tokens):
        if tok.lower() in NAME_MARKERS:
            name_words = []
            j = i - 1
            while j >= 0 and len(name_words) < 2:
                w = tokens[j]
                lw = w.lower()
                if (lw in NOT_A_NAME or lw in _TYPE_WORDS or lw in UNITS or lw in MULTIPLIERS
                        or lw in SPECIAL or re.search(r"\d", w)
                        or lw in NAME_MARKERS):
                    break
                name_words.insert(0, w)
                j -= 1
            if name_words:
                name = " ".join(name_words)
                return name.title() if name.isascii() else name
            return ""
    return ""


# ---------- Questions ("Ramesh ka kitna baaki hai?") ----------
QUESTION_WORDS = ["kitna", "kitne", "kitni", "batao", "bataiye", "bataao", "sunao",
                  "hisaab", "hisab", "कितना", "कितने", "कितनी", "बताओ", "बताइए",
                  "सुनाओ", "हिसाब"]
BALANCE_WORDS = ["udhaar", "udhar", "baaki", "baki", "उधार", "बाकी"]
WEEK_WORDS = ["hafte", "hafta", "haphte", "week", "saptah", "हफ्ते", "हफ्ता", "सप्ताह", "हफ़्ते"]


def is_question(text):
    return _has_any(text or "", QUESTION_WORDS)


def parse_sentence(text):
    """
    Returns (entry, problem).
    entry   = dict with type, amount, text   (or None)
    problem = a short message explaining what was missing (or None)
    """
    text = (text or "").strip()
    if not text:
        return None, "No words heard. Please speak a full sentence."

    kind = find_type(text)
    amount = find_amount(text)

    if kind is None and amount is None:
        return None, "I could not find a type or an amount."
    if kind is None:
        return None, "I found the amount but not the type (becha / kharida / udhaar)."
    if amount is None:
        return None, "I found the type but not the amount."
    customer = find_customer(text) if kind in ("udhaar_diya", "udhaar_wapas") else ""
    return {"type": kind, "amount": amount, "text": text, "customer": customer}, None


# ---------- Saving and totals ----------
def _upgrade_old_file():
    """Old ledger.csv files have no 'customer' column. Add it once."""
    if not os.path.exists(LEDGER_FILE):
        return
    with open(LEDGER_FILE, newline="", encoding="utf-8") as f:
        header = f.readline()
    if "customer" not in header:
        rows = load_entries()
        with open(LEDGER_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


def add_entry(entry):
    """Save one entry to ledger.csv."""
    _upgrade_old_file()
    is_new = not os.path.exists(LEDGER_FILE)
    with open(LEDGER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": entry["type"],
            "amount": entry["amount"],
            "text": entry["text"],
            "customer": entry.get("customer", ""),
        })


def load_entries():
    """Read all entries (list of dicts). Empty list if no file yet."""
    if not os.path.exists(LEDGER_FILE):
        return []
    with open(LEDGER_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["amount"] = float(row["amount"])
        row["customer"] = row.get("customer") or ""
    return rows


def delete_last_entry():
    """Remove the most recent entry. Returns True if something was removed."""
    rows = load_entries()
    if not rows:
        return False
    rows = rows[:-1]
    with open(LEDGER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return True


def totals_for_today(entries=None):
    """Totals for today's date."""
    entries = load_entries() if entries is None else entries
    today = datetime.now().strftime("%Y-%m-%d")
    sums = {"sale": 0, "expense": 0, "udhaar_diya": 0, "udhaar_wapas": 0}
    for e in entries:
        if e["time"].startswith(today) and e["type"] in sums:
            sums[e["type"]] += e["amount"]
    sums["profit"] = sums["sale"] - sums["expense"]
    sums["udhaar_baaki"] = sums["udhaar_diya"] - sums["udhaar_wapas"]
    return sums


def summary_text(sums):
    """A short Hindi sentence (Devanagari) to read out with Timbre later."""
    def n(x):
        return int(x) if float(x).is_integer() else x
    return (f"आज की कुल बिक्री {n(sums['sale'])} रुपये, "
            f"खर्चा {n(sums['expense'])} रुपये, "
            f"और उधार बाकी {n(sums['udhaar_baaki'])} रुपये है।")


# ---------- Who owes how much ----------
def customer_balances(entries=None):
    """{name: amount still to receive}, only people who still owe money."""
    entries = load_entries() if entries is None else entries
    bal = {}
    for e in entries:
        name = (e.get("customer") or "").strip()
        if not name:
            continue
        if e["type"] == "udhaar_diya":
            bal[name] = bal.get(name, 0) + e["amount"]
        elif e["type"] == "udhaar_wapas":
            bal[name] = bal.get(name, 0) - e["amount"]
    return {k: v for k, v in bal.items() if v > 0}


def daily_totals(entries=None, days=7):
    """Totals for each of the last `days` days, oldest first."""
    entries = load_entries() if entries is None else entries
    today = datetime.now().date()
    rows = []
    for back in range(days - 1, -1, -1):
        day = (today - timedelta(days=back)).strftime("%Y-%m-%d")
        sums = {"sale": 0, "expense": 0, "udhaar_diya": 0, "udhaar_wapas": 0}
        for e in entries:
            if e["time"].startswith(day) and e["type"] in sums:
                sums[e["type"]] += e["amount"]
        rows.append({
            "date": day,
            "sale": sums["sale"],
            "expense": sums["expense"],
            "profit": sums["sale"] - sums["expense"],
            "udhaar_diya": sums["udhaar_diya"],
            "udhaar_wapas": sums["udhaar_wapas"],
        })
    return rows


def week_summary_text(rows):
    """Hindi sentence (Devanagari) for the last 7 days, to read out with Timbre."""
    def n(x):
        return int(x) if float(x).is_integer() else x
    sale = sum(r["sale"] for r in rows)
    expense = sum(r["expense"] for r in rows)
    return (f"पिछले {len(rows)} दिनों की कुल बिक्री {n(sale)} रुपये, "
            f"खर्चा {n(expense)} रुपये, और मुनाफा {n(sale - expense)} रुपये है।")


def answer_question(text, entries=None):
    """Answer a spoken question in Hindi (Devanagari) so Timbre can read it out."""
    entries = load_entries() if entries is None else entries

    def n(x):
        return int(x) if float(x).is_integer() else x

    if _has_any(text, WEEK_WORDS):
        return week_summary_text(daily_totals(entries))
    if _has_any(text, BALANCE_WORDS):
        balances = customer_balances(entries)
        for name in sorted(balances, key=len, reverse=True):   # longest name first
            if name.lower() in text.lower():                    # a customer was named
                return f"{name} के {n(balances[name])} रुपये बाकी हैं।"
        if not balances:
            return "किसी का भी उधार बाकी नहीं है।"
        parts = [f"{name} के {n(a)} रुपये" for name, a in balances.items()]
        return "उधार बाकी है: " + ", ".join(parts) + "।"
    return summary_text(totals_for_today(entries))
