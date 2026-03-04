from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from database import init_db, save_report, get_all_reports, get_latest_incident_location

app = Flask(__name__)

# ✅ CREATE DATABASE + TABLE
init_db()

def extract_location(message):
    """
    Extract accident location from message.
    Looks for 'in <location>' and returns the location.
    """
    message = message.lower()
    if " in " in message:
        parts = message.split(" in ", 1)
        location = parts[1].strip().title()  # Capitalize each word
        return location
    return "Unknown"

def extract_destinations(message):
    """
    Extract one or multiple destinations from message.
    Supports comma-separated destinations.
    Example: "Alternative from X to Saddar, Chungi No 22"
    """
    message = message.lower()
    if " to " in message:
        parts = message.split(" to ", 1)
        dest_part = parts[1].strip()
        # Split by comma if multiple destinations
        destinations = [d.strip().title() for d in dest_part.split(",")]
        return destinations
    return []

def google_route_link(origin, destination):
    """
    Generate Google Maps Directions link from origin to destination.
    """
    origin_param = origin.replace(" ", "+")
    dest_param = destination.replace(" ", "+")
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_param}&destination={dest_param}"

@app.route("/reply_whatsapp", methods=['POST'])
def reply_whatsapp():
    user_message = request.form.get('Body')
    user_number = request.form.get('From')

    print(f"Message from {user_number}: {user_message}")

    resp = MessagingResponse()

    # ✅ Detect if user is asking for alternative route
    if "alternative" in user_message.lower() or "route" in user_message.lower() or "to " in user_message.lower():
        latest_location = get_latest_incident_location()
        if not latest_location:
            resp.message("❌ No accident location found yet.")
            return Response(str(resp), mimetype="text/xml")

        # Extract destinations
        destinations = extract_destinations(user_message)
        if not destinations:
            resp.message("❌ Please specify destination(s).\nExample: Alternative from X to Saddar, Chungi No 22")
            return Response(str(resp), mimetype="text/xml")

        reply = f"🛣 Alternative Routes from {latest_location}:\n"
        for dest in destinations:
            link = google_route_link(latest_location, dest)
            reply += f"\n📍 To {dest}: {link}"

        resp.message(reply)
        return Response(str(resp), mimetype="text/xml")

    # ✅ Otherwise, treat as accident report
    location = extract_location(user_message)
    processed_info = (
        "Incident detected.\n"
        "Type: Accident\n"
        f"Location: {location}\n"
        "Severity: Unknown"
    )

    save_report(user_number, "Accident", location, "Unknown")

    # Generate Google Maps link for accident location
    maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
    resp.message(f"🚨 Accident Report Saved:\n{processed_info}\n📍 Location Map: {maps_link}")

    return Response(str(resp), mimetype='text/xml')

# ✅ SHOW REPORTS ON WEB PAGE WITH SEARCH BOX FOR ALTERNATIVE ROUTES
@app.route("/reports", methods=['GET', 'POST'])
def show_reports():
    reports = get_all_reports()
    routes_html = ""

    if request.method == "POST":
        destinations_input = request.form.get("destinations", "")
        if destinations_input.strip():
            destinations = [d.strip().title() for d in destinations_input.split(",")]
            routes_html += "<h3>Alternative Routes:</h3>"
            for report in reports:
                origin = report[3]  # Accident location
                if origin == "Unknown":
                    continue
                routes_html += f"<b>From {origin}:</b><br>"
                for dest in destinations:
                    link = google_route_link(origin, dest)
                    routes_html += f'📍 To {dest}: <a href="{link}" target="_blank">{link}</a><br>'
                routes_html += "<br>"

    html = """
    <html>
    <head>
        <title>Accident Reports</title>
    </head>
    <body>
        <h1>🚨 Accident Reports</h1>
        <form method="POST">
            <label>Enter destination(s) for alternative route (comma-separated):</label><br>
            <input type="text" name="destinations" style="width:300px" placeholder="Saddar, Chungi No 22">
            <input type="submit" value="Get Routes">
        </form>
        <br>
        <table border="1" cellpadding="10">
            <tr>
                <th>ID</th>
                <th>Phone Number</th>
                <th>Incident Type</th>
                <th>Location</th>
                <th>Time</th>
            </tr>
    """

    for r in reports:
        location = r[3]
        maps_link = f"https://www.google.com/maps/search/{location.replace(' ', '+')}"
        html += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
            <td><a href="{maps_link}" target="_blank">{location}</a></td>
            <td>{r[5]}</td>
        </tr>
        """

    html += """
        </table>
        <br>
        """ + routes_html + """
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    app.run(port=3000)
