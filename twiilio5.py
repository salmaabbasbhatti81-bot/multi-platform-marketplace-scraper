import re
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report, get_latest_incident_location, get_reports_by_location, get_reports_by_location_and_date
import requests
import speech_recognition as sr
from pydub import AudioSegment
from deep_translator import GoogleTranslator
import dateparser
import os
from dotenv import load_dotenv

# -----------------------------
# 🔐 Load Environment Variables
# -----------------------------
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# -----------------------------
# 🔹 Flask App
# -----------------------------
app = Flask(__name__)

# -----------------------------
# 🔹 Initialize Database
# -----------------------------
init_db()

# -----------------------------
# 🔹 Download File Helper
# -----------------------------
def download_file(url, filename):
    r = requests.get(
        url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        stream=True
    )
    r.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

# -----------------------------
# 🔹 Extract Location & Date
# -----------------------------
def extract_location_and_date(message):
    message = message.strip()

    # Translate Urdu → English for easier parsing
    message_en = GoogleTranslator(source='auto', target='en').translate(message)

    # English pattern: "accident in/at <location> on <date>"
    match = re.search(r'(?:accident|incident)\s*(?:in|at)\s*([a-zA-Z\s]+?)(?:\s+on\s+(.*?))?$', message_en, re.IGNORECASE)
    if match:
        location = match.group(1).strip().title()
        date_str = match.group(2).strip() if match.group(2) else None
    else:
        # Urdu pattern: "<location> میں حادثہ [date]"
        match_urdu = re.search(r'(.+?) میں حادثہ', message)
        if match_urdu:
            location = match_urdu.group(1).strip().title()
            date_match = re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|گزشتہ\s+\w+', message)
            date_str = date_match.group(0) if date_match else None
        else:
            location = message.title()
            date_str = None

    # Parse date string to YYYY-MM-DD
    if date_str:
        date_obj = dateparser.parse(date_str, languages=['en', 'ur'])
        if date_obj:
            date_str = date_obj.strftime("%Y-%m-%d")
        else:
            date_str = None

    return location, date_str

# -----------------------------
# 🔹 Extract Destinations
# -----------------------------
def extract_destinations(message):
    message = message.lower()
    if " to " in message:
        parts = message.split(" to ", 1)
        dest_part = parts[1].strip()
        destinations = [d.strip().title() for d in re.split(r',| and ', dest_part)]
        return destinations
    return []

# -----------------------------
# 🔹 Google Maps Route Link
# -----------------------------
def google_route_link(origin, destination):
    origin_param = origin.replace(" ", "+")
    dest_param = destination.replace(" ", "+")
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_param}&destination={dest_param}"

# -----------------------------
# 🔹 Speech → Text
# -----------------------------
def speech_to_text(audio_url):
    audio_file = "temp_audio.ogg"
    wav_file = "temp_audio.wav"
    try:
        download_file(audio_url, audio_file)
        sound = AudioSegment.from_file(audio_file, format="ogg")
        sound.export(wav_file, format="wav")
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        print("Recognized Text:", text)
    except Exception as e:
        print(f"Voice recognition error: {e}")
        text = ""
    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if os.path.exists(wav_file):
            os.remove(wav_file)
    return text

# -----------------------------
# 🔹 Translate Urdu → English
# -----------------------------
def translate_if_urdu(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

# -----------------------------
# 🔹 Translate English → Urdu
# -----------------------------
def translate_to_urdu(text):
    try:
        return GoogleTranslator(source='en', target='ur').translate(text)
    except:
        return text

# -----------------------------
# 🔹 WhatsApp Webhook
# -----------------------------
@app.route("/reply_whatsapp", methods=['POST'])
def reply_whatsapp():
    user_message = request.form.get('Body')
    user_number = request.form.get('From')
    num_media = int(request.form.get('NumMedia', 0))

    resp = MessagingResponse()

    # 🎤 Handle Voice Message
    if num_media > 0:
        media_url = request.form.get('MediaUrl0')
        user_message = speech_to_text(media_url)
        if not user_message:
            resp.message("❌ Could not understand voice message.")
            return Response(str(resp), mimetype="text/xml")

    print("Processed Message:", user_message)

    # 🚦 Alternative Route Query
    if "alternative" in user_message.lower() or "route" in user_message.lower():
        latest_location = get_latest_incident_location(user_number)
        if not latest_location:
            reply_en = "❌ No accident location found yet."
            resp.message(reply_en + "\n" + translate_to_urdu(reply_en))
            return Response(str(resp), mimetype="text/xml")

        destinations = extract_destinations(user_message)
        if not destinations:
            reply_en = "❌ Please specify destination(s). Example: Alternative to Saddar, DHA"
            resp.message(reply_en + "\n" + translate_to_urdu(reply_en))
            return Response(str(resp), mimetype="text/xml")

        reply_en = f"🛣 Alternative Routes from {latest_location}:"
        for dest in destinations:
            link = google_route_link(latest_location, dest)
            reply_en += f"\n📍 To {dest}: {link}"

        resp.message(reply_en + "\n\n" + translate_to_urdu(reply_en))
        return Response(str(resp), mimetype="text/xml")

    # 🚨 Accident History Query
    if any(word in user_message.lower() for word in ["history", "accident happened", "حادثہ ہوا", "کیا"]):
        location, date_str = extract_location_and_date(user_message)

        if date_str:
            reports = get_reports_by_location_and_date(location, date_str)
        else:
            reports = get_reports_by_location(location)

        if not reports:
            reply_en = f"❌ No accident history found for {location}."
            resp.message(reply_en + "\n" + translate_to_urdu(reply_en))
            return Response(str(resp), mimetype="text/xml")

        latest_report = reports[-1]  # last report
        maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
        reply_en = (
            f"🚨 Latest Accident at {location}:\n"
            f"Time: {latest_report['timestamp']}\n"
            f"📍 Map: {maps_link}"
        )
        resp.message(reply_en + "\n\n" + translate_to_urdu(reply_en))
        return Response(str(resp), mimetype="text/xml")

    # 🚨 Save New Accident Report
    location, _ = extract_location_and_date(user_message)
    save_report(user_number, "Accident", location)

    maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
    reply_en = (
        f"🚨 Accident Report Saved:\n"
        f"Location: {location}\n"
        f"📍 Map: {maps_link}"
    )
    resp.message(reply_en + "\n\n" + translate_to_urdu(reply_en))

    return Response(str(resp), mimetype='text/xml')

# -----------------------------
# 🔹 Run Flask App
# -----------------------------
if __name__ == "__main__":
    app.run(port=3000, debug=True)