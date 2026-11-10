# Bolo Bill - One-Page Pitch

**Voice ledger for shopkeepers. Speak in Hindi or Hinglish, the hisaab writes itself.**

Built by Shubh Mehta (solo) | Great Indian AI Internship Challenge by Gnani AI

## Problem
Millions of kirana and small-shop owners keep their hisaab in a notebook or in their head. Their hands are busy with customers, so typing in an app is slow. Most apps are in English. Udhaar (credit) is easy to forget, and forgotten udhaar is lost money.

## Solution
Bolo Bill lets a shopkeeper just say what happened:
- "Aaj paanch sau ka maal becha" -> saved as a sale
- "Teen sau ka saman kharida" -> saved as an expense
- "Ramesh ko do sau ka udhaar diya" -> saved as udhaar for Ramesh
- "Ramesh ne paanch sau wapas kiye" -> udhaar paid back
- "Ramesh ka kitna baaki hai?" -> the app answers out loud

The app also shows today's totals, who owes how much, a 7-day report with a chart (read aloud on request), and a CSV download for Excel.

## Who will use it
Kirana, medical, stationery and other small-shop owners who speak Hindi or Hinglish and want a faster way than a notebook.

## Gnani AI models used
| Model | API | Used for |
|---|---|---|
| Prisma v3.0 | Speech-to-text (REST) | Turns the shopkeeper's voice into text |
| Timbre v3.0 (voice Shivani) | Text-to-speech (REST) | Reads out answers, totals and the weekly report |

## How it works
Voice -> Prisma STT -> simple rule-based parser (type, amount, customer name) -> saved in ledger -> totals / balances -> Timbre speaks the answer.

## Why it matters
- Hindi-first and voice-first: no typing, no English needed
- Tracks udhaar by customer name, so nothing is forgotten
- Works as a free Streamlit web app on a phone browser

## What is next
- Phone-friendly installable app and WhatsApp reminders for udhaar
- More languages (Gnani supports many Indian languages)
- Per-shop login so each shopkeeper has a private ledger

## Links
- Code: https://github.com/shubbhmehta/bolo-bill
- Demo video and post: see the submission form
