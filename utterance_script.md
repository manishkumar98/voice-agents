# Utterance Script — Advisor Appointment Scheduling Voice Agent

Demo phrases used during testing and recording.
All flows tested on: **9 April 2026** | Language: **English (en-IN)** | Mode: **Voice**

---

## Flow 1 — Happy Path Booking (used in demo recording)

| Turn | Speaker | Utterance |
|------|---------|-----------|
| 1 | Agent | "Hello! I'm the Advisor Scheduling assistant. I'll help you book a consultation in about two minutes." |
| 2 | User | **"Hi, I want to book an appointment."** |
| 3 | Agent | "Quick note: this service is for scheduling only. Our advisors provide informational guidance, not investment advice. Shall we continue?" |
| 4 | User | **"Yes, please continue."** |
| 5 | Agent | "Great. What topic would you like to discuss? KYC and onboarding, SIP and mandates, statements and tax documents, withdrawals, or account changes." |
| 6 | User | **"I need help with KYC and onboarding."** |
| 7 | Agent | "What day and time works best for you this week or next?" |
| 8 | User | **"Monday afternoon."** |
| 9 | Agent | "I found 2 slots on Monday afternoon. Option 1: Monday, 13 April at 2:00 PM IST. Option 2: Monday, 13 April at 4:00 PM IST. Which would you prefer?" |
| 10 | User | **"Option 1 please."** |
| 11 | Agent | "Perfect. Confirming: KYC and Onboarding consultation on Monday, 13/04/2026 at 02:00 PM IST. Is that correct?" |
| 12 | User | **"Yes, that's correct."** |
| 13 | Agent | "Your booking is confirmed. KYC and Onboarding on Monday, 13th April at 2 PM IST. Your booking code is N - L - A - 7 - 4 - 2. Please note it down. You'll receive a secure link to submit your contact details. Thank you for calling!" |

---

## Flow 2 — Hindi Happy Path

| Turn | Speaker | Utterance |
|------|---------|-----------|
| 1 | Agent | "नमस्ते! मैं Advisor Scheduling सहायक हूँ।" |
| 2 | User | **"हाँ, मुझे अपॉइंटमेंट बुक करनी है।"** |
| 3 | Agent | "एक छोटी सी जानकारी: यह सेवा केवल शेड्यूलिंग के लिए है। क्या हम आगे बढ़ें?" |
| 4 | User | **"हाँ।"** |
| 5 | Agent | "आप किस विषय पर चर्चा करना चाहते हैं? KYC, SIP, स्टेटमेंट, निकासी, या खाता बदलाव।" |
| 6 | User | **"SIP और मैंडेट।"** |
| 7 | Agent | "इस सप्ताह या अगले सप्ताह कौन सा दिन और समय आपके लिए सुविधाजनक है?" |
| 8 | User | **"शुक्रवार सुबह।"** |
| 9 | Agent | "शुक्रवार सुबह के लिए 2 स्लॉट मिले। विकल्प 1: शुक्रवार, 10 अप्रैल सुबह 10 बजे IST..." |
| 10 | User | **"पहला विकल्प।"** |
| 11 | User | **"हाँ, सही है।"** |
| 12 | Agent | "आपकी बुकिंग की पुष्टि हो गई है।..." |

---

## Flow 3 — "This Week" Range Query

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(greeting + disclaimer as above)* |
| 8 | User | **"This week."** |
| 9 | Agent | "Here are the available slots this week. The earliest is Thursday, 9 April. Option 1: Thursday, 9 April at 10:00 AM IST. Option 2: Thursday, 9 April at 2:00 PM IST. Which would you prefer?" |

---

## Flow 4 — Investment Advice Refusal + Educational Links

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(greeting + disclaimer)* |
| 4 | User | **"Should I invest in mutual funds right now?"** |
| 5 | Agent | "I'm not able to provide investment advice on this call. For investor education, you can visit SEBI's portal at investor.sebi.gov.in, or AMFI India at amfiindia.com/investor-corner. I can help you book a consultation with a human advisor. Would you like to do that?" |
| 6 | User | **"Yes, book an appointment."** |

---

## Flow 5 — No Slots → Waitlist

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(greeting + disclaimer + topic)* |
| 8 | User | **"Saturday morning."** |
| 9 | Agent | "I'm sorry, no slots are available for your requested time. Would you like to be added to our waitlist? We'll contact you as soon as a slot opens." |
| 10 | User | **"Yes, add me to the waitlist."** |
| 11 | Agent | "Done. I've added you to the waitlist for KYC and Onboarding on Saturday in the morning. Your waitlist code is N - L - W - 3 - 9 - 1. An advisor will reach out as soon as that slot opens. Thank you!" |

---

## Flow 6 — Reschedule

| Turn | Speaker | Utterance |
|------|---------|-----------|
| 1–4 | ... | *(greeting + disclaimer)* |
| 5 | User | **"I want to reschedule my appointment."** |
| 6 | Agent | "Please share your booking code so I can find your appointment." |
| 7 | User | **"NL-A742."** |
| 8 | Agent | "I've located your booking NL-A742. What new day and time works for you?" |

---

## Flow 7 — Cancel

| Turn | Speaker | Utterance |
|------|---------|-----------|
| 1–4 | ... | *(greeting + disclaimer)* |
| 5 | User | **"I want to cancel my booking."** |
| 6 | Agent | "Please share your booking code so I can find your appointment." |
| 7 | User | **"NL-A742."** |
| 8 | Agent | "Your booking NL-A742 has been cancelled. If you'd like to rebook in the future, feel free to call again. Goodbye!" |

---

## Flow 8 — What to Prepare

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(greeting + disclaimer)* |
| 5 | User | **"What should I prepare for my KYC appointment?"** |
| 6 | Agent | *(Provides preparation guidance for the selected topic)* |

---

## Flow 9 — PII Blocked

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(mid-flow)* |
| 8 | User | **"My phone number is 9876543210."** |
| 9 | Agent | "Please don't share personal details on this call. You'll receive a secure link after booking to submit your contact information." |

---

## Flow 10 — End Call Early

| Turn | Speaker | Utterance |
|------|---------|-----------|
| ... | ... | *(any state)* |
| N | User | **"I want to end the call."** |
| N+1 | Agent | "Thank you for reaching out. We'll be happy to help whenever you're ready. Have a wonderful day!" |

---

## Quick Reference — Key Phrases

```
Booking:      "I want to book an appointment"
Topic:        "KYC" / "SIP" / "statements" / "withdrawals" / "account changes"
Time:         "Monday afternoon" / "this week" / "10th April" / "next week morning"
Confirm slot: "Option 1" / "the first one" / "yes"
Confirm hold: "Yes, that's correct" / "confirmed"
Reschedule:   "I want to reschedule" + booking code
Cancel:       "Cancel my booking" + booking code
Advice:       "Should I invest in..." → triggers educational links
Waitlist:     "Yes, add me to the waitlist"
End:          "Goodbye" / "end the call" / "that's all"
```
