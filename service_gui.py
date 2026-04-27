
from flask import Flask, request, jsonify, render_template_string, render_template
from flask_cors import CORS
import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()
SERVICE_GUI_IP = os.getenv('SERVICE_GUI_IP', '127.0.0.1')
SERVICE_B_IP = os.getenv('SERVICE_B_IP', '127.0.0.1')
SERVICE_C_IP = os.getenv('SERVICE_C_IP', '127.0.0.1')

app = Flask(__name__)
# Enable CORS globally so JS can call /forward and /receive without preflight blocking
CORS(app)


latest_received_data = {"msg": "Waiting for data..."}

@app.route('/')
def index():
  return render_template('index.html', gui_ip=SERVICE_GUI_IP, b_ip=SERVICE_B_IP, c_ip=SERVICE_C_IP)

@app.route('/get_latest')
def get_latest():
    global latest_received_data
    print("Get LATEST WAS RUNNED")
    return jsonify(latest_received_data)

@app.route('/receive', methods=['POST'])
def receive():
  global latest_received_data
  data = request.get_json(silent=True)
  # Log received payload to terminal for visibility
  print('Received POST on GUI /receive:', data)
  latest_received_data = data
    
  return jsonify({"status": "ok"})


@app.route('/forward', methods=['POST'])
def forward():
  data = request.get_json(silent=True) or {}
  target = data.get('target')
  recipient = data.get('recipient')
  payload = data.get('payload')
  if recipient is None or payload is None:
    return jsonify({'error': 'missing recipient or payload'}), 400

  print('Forward envelope received on GUI:', {'recipient': recipient, 'payload': payload, 'target': target})

  # If intended for GUI process locally
  if str(recipient).lower() in ('gui', 'servicegui', 'service_gui'):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    processed = {'service': 'GUI', 'timestamp': now, 'received': payload}
    print('GUI processing payload locally:', payload)
    return jsonify({'processed': processed}), 200

  # Otherwise forward to target
  if not target:
    return jsonify({'error': 'no target provided to forward to'}), 400
  try:
    r = requests.post(target, json=payload, timeout=5)
    try:
      resp_json = r.json()
    except Exception:
      resp_json = {'text': r.text}
    return jsonify({'forwarded_to': target, 'status': r.status_code, 'response': resp_json})
  except Exception as e:
    return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
  app.run(host=SERVICE_GUI_IP, port=5000, debug=True)
