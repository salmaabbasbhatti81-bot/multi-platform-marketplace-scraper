from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report, get_latest_incident_location  # no get_all_reports needed
import requests
import speech_recognition as sr
from pydub import AudioSegment
from deep_translator import GoogleTranslator
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
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),  # 🔥 Fixes 401 error
        stream=True
    )
    r.raise_for_status()
    with open(filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

# -----------------------------
# 🔹 Extract Accident Location
# -----------------------------
def extract_location(message):
    message = message.lower()
    if " in " in message:
        parts = message.split(" in ", 1)
        return parts[1].strip().title()
    return "Unknown"

# -----------------------------
# 🔹 Extract Destinations
# -----------------------------
def extract_destinations(message):
    message = message.lower()
    if " to " in message:
        parts = message.split(" to ", 1)
        dest_part = parts[1].strip()
        destinations = [d.strip().title() for d in dest_part.split(",")]
        return destinations
    return []

# -----------------------------
# 🔹 Generate Google Route Link
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

    # 🌍 Translate Urdu → English
    user_message_en = translate_if_urdu(user_message)
    print("Processed Message:", user_message_en)

    # 🚦 Alternative Route
    if "alternative" in user_message_en.lower() or "route" in user_message_en.lower():
        latest_location = get_latest_incident_location(user_number)  # ✅ Pass user_number
        if not latest_location:
            reply_en = "❌ No accident location found yet."
            resp.message(reply_en + "\n" + translate_to_urdu(reply_en))
            return Response(str(resp), mimetype="text/xml")

        destinations = extract_destinations(user_message_en)
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

    # 🚨 Accident Report
    location = extract_location(user_message_en)
    save_report(user_number, "Accident", location, "Unknown")

    maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
    reply_en = (
        f"🚨 Accident Report Saved:\n"
        f"Location: {location}\n"
        f"📍 Map: {maps_link}"
    )
    resp.message(reply_en + "\n\n" + translate_to_urdu(reply_en))

    return Response(str(resp), mimetype='text/xml')

# -----------------------------
# 🔹 Run App
# -----------------------------
if __name__ == "__main__":
    app.run(port=3000, debug=True)