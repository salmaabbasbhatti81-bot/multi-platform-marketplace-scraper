from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report, get_latest_incident_location
import requests
import speech_recognition as sr
from pydub import AudioSegment
from deep_translator import GoogleTranslator
import os

app = Flask(__name__)

# -----------------------------
# 🔹 Initialize DB
# -----------------------------
init_db()

# -----------------------------
# 🔹 Translate Urdu → English
# -----------------------------
def translate_to_english(text):
    """Detect Urdu and translate to English"""
    if not text:
        return ""
    if any(ord(c) > 127 for c in text):  # simple check for non-ASCII characters
        try:
            text = GoogleTranslator(source='auto', target='en').translate(text)
        except Exception as e:
            print(f"Translation Error: {e}")
    return text

# -----------------------------
# 🔹 Translate English → Urdu
# -----------------------------
def translate_to_urdu(text):
    if not text:
        return ""
    try:
        return GoogleTranslator(source='auto', target='ur').translate(text)
    except Exception as e:
        print(f"Translation Error: {e}")
        return text

# -----------------------------
# 🔹 Extract accident location
# -----------------------------
def extract_location(message):
    message = message.lower()
    if " in " in message:
        parts = message.split(" in ", 1)
        return parts[1].strip().title()
    return "Unknown"

# -----------------------------
# 🔹 Extract destinations
# -----------------------------
def extract_destinations(message):
    message = message.lower()
    if " to " in message:
        parts = message.split(" to ", 1)
        dest_part = parts[1].strip()
        return [d.strip().title() for d in dest_part.split(",")]
    return []

# -----------------------------
# 🔹 Generate Google Route Link
# -----------------------------
def google_route_link(origin, destination):
    origin_param = origin.replace(" ", "+")
    dest_param = destination.replace(" ", "+")
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_param}&destination={dest_param}"

# -----------------------------
# 🔹 Voice → Text
# -----------------------------
def speech_to_text(audio_url):
    """Download voice message from Twilio, convert, and recognize speech"""
    audio_file = "temp_audio.ogg"
    wav_file = "temp_audio.wav"

    try:
        r = requests.get(audio_url)
        with open(audio_file, "wb") as f:
            f.write(r.content)

        # Convert OGG → WAV
        sound = AudioSegment.from_file(audio_file)
        sound.export(wav_file, format="wav")

        # Recognize
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio = recognizer.record(source)

        text = recognizer.recognize_google(audio)
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

    # 🌍 Translate Urdu → English for processing
    message_en = translate_to_english(user_message)

    print(f"Processed Message (EN): {message_en}")

    # 🚦 Alternative Route Logic
    if "alternative" in message_en.lower() or "route" in message_en.lower():
        latest_location = get_latest_incident_location()
        if not latest_location:
            resp.message("❌ No accident location found yet.")
            return Response(str(resp), mimetype="text/xml")

        destinations = extract_destinations(message_en)
        if not destinations:
            resp.message("❌ Please specify destination(s). Example: Alternative to Saddar, DHA")
            return Response(str(resp), mimetype="text/xml")

        reply_en = f"🛣 Alternative Routes from {latest_location}:"
        for dest in destinations:
            link = google_route_link(latest_location, dest)
            reply_en += f"\n📍 To {dest}: {link}"

        reply_ur = translate_to_urdu(reply_en)
        resp.message(f"{reply_en}\n\n{reply_ur}")
        return Response(str(resp), mimetype="text/xml")

    # 🚨 Accident Report Logic
    location = extract_location(message_en)
    save_report(user_number, "Accident", location, "Unknown")

    maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"

    reply_en = (
        f"🚨 Accident Report Saved:\n"
        f"Type: Accident\n"
        f"Location: {location}\n"
        f"Severity: Unknown\n"
        f"📍 Map: {maps_link}"
    )
    reply_ur = translate_to_urdu(reply_en)

    resp.message(f"{reply_en}\n\n{reply_ur}")
    return Response(str(resp), mimetype='text/xml')

# -----------------------------
# 🔹 Run App
# -----------------------------
if __name__ == "__main__":
    app.run(port=3000, debug=True)