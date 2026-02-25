from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import uuid
import qrcode
import io
import base64
import os
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

app = Flask(__name__)
# Enable CORS for all domains, crucial since Vercel and Render will have different domains
CORS(app)

# Connect to MongoDB Atlas
# Default to localhost for local testing if MONGO_URI is not set
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/eventnexus")
client = MongoClient(MONGO_URI)

# Get the default database (or specify eventnexus if you want)
db = client.get_database() 
attendees_collection = db.attendees

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    student_id = data.get('student_id')
    event = data.get('event', 'Main Event')
    
    ticket_id = str(uuid.uuid4())
    
    attendee = {
        "id": ticket_id,
        "name": name,
        "email": email,
        "student_id": student_id,
        "event": event,
        "checked_in": 0
    }
    
    try:
        attendees_collection.insert_one(attendee)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
        
    # Generate QR logic
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(ticket_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({"success": True, "ticket_id": ticket_id, "qr_code": img_str})

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.json
    ticket_id = data.get('ticket_id')
    
    attendee = attendees_collection.find_one({"id": ticket_id})
    
    if not attendee:
        return jsonify({"success": False, "message": "Invalid QR"})
        
    if attendee.get('checked_in'):
        return jsonify({"success": False, "message": "Already Checked In"})
        
    attendees_collection.update_one({"id": ticket_id}, {"$set": {"checked_in": 1}})
    
    return jsonify({
        "success": True, 
        "message": f"Check-in successful for {attendee['name']}!",
        "attendee": {
            "name": attendee['name'],
            "email": attendee['email'],
            "student_id": attendee['student_id'],
            "event": attendee['event'],
            "checked_in": 1
        }
    })

@app.route('/api/stats')
def api_stats():
    total = attendees_collection.count_documents({})
    checked_in = attendees_collection.count_documents({"checked_in": 1})
    
    # Get 10 most recent (using _id which contains timestamp info)
    recent_cursor = attendees_collection.find().sort('_id', -1).limit(10)
    recent = []
    for row in recent_cursor:
        recent.append({
            "name": row.get('name'),
            "email": row.get('email'),
            "student_id": row.get('student_id'),
            "event": row.get('event'),
            "checked_in": row.get('checked_in')
        })
        
    return jsonify({
        "total": total,
        "checked_in": checked_in,
        "recent": recent
    })

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "EventNexus API"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
