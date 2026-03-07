# Accident Detection System

A WhatsApp-based system for reporting accidents, tracking locations, and suggesting alternative routes.

---

## Features
- Receive accident reports via WhatsApp (text or voice).
- Automatic location extraction (English & Urdu supported).
- Save accident reports in a SQLite database.
- Suggest alternative routes using Google Maps.

---

## Libraries & Tools
- **Flask** – Web server for handling WhatsApp requests.
- **Twilio** – WhatsApp messaging integration.
- **SQLite** – Local database for storing reports.
- **SpeechRecognition & Pydub** – Voice message processing.
- **Deep Translator** – English/Urdu translation.
- **Python-dotenv** – Manage environment variables.

---

## How It Works
1. User sends a WhatsApp message (text or voice).
2. The system extracts the accident location.
3. Accident details are saved in the database.
4. Users can request:
   
   - Alternative routes to destinations

---



## License
This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.
