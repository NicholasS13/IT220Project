
import argparse
import threading
import queue
import datetime
import requests
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

try:
    import serial
except ImportError:
    serial = None


load_dotenv()
SERVICE_C_IP = os.getenv('SERVICE_C_IP', '127.0.0.1')
SERVICE_GUI_IP = os.getenv('SERVICE_GUI_IP', '127.0.0.1')
app = Flask(__name__)
CORS(app)

# Global holder for the serial worker
serial_controller = None

class SerialController:
    def __init__(self, port, baud=115200, gui_url=None):
        self.port = port
        self.baud = int(baud)
        if gui_url is None:
            self.gui_url = f"http://{SERVICE_GUI_IP}:5000/receive"
        else:
            self.gui_url = gui_url
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        if serial is None:
            print('Error: pyserial not installed.')
            return
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.1)
            print(f'--- Sensor Serial Port Opened: {self.port} @ {self.baud} ---')
        except Exception as e:
            print(f'--- Failed to open serial port {self.port}: {e} ---')
            return

        while not self._stop.is_set():
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        # Basic parsing logic
                        payload = {"source": "Service C", "raw": line}
                        print(f"[LIVE HARDWARE] {line}")
                        if "Button: PRESSED" in line:
                            payload["button"] = "ON"
                        elif "Button: RELEASED" in line:
                            payload["button"] = "OFF"
                        
                        # Push everything to GUI
                        requests.post(self.gui_url, json=payload, timeout=0.5)
                except Exception as e:
                    print(f"Serial Read Error: {e}")
            
            time.sleep(0.01) # Prevent CPU hogging
        ser.close()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1)

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json(silent=True) or {}
    print('Received POST on Service C /receive:', data)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return jsonify({'service': 'C', 'timestamp': now, 'received': data})

@app.route('/forward', methods=['POST'])
def forward():
    data = request.get_json(silent=True) or {}
    target = data.get('target')
    recipient = data.get('recipient')
    payload = data.get('payload')

    if recipient is None or payload is None:
        return jsonify({'error': 'missing recipient or payload'}), 400

    print(f'Forward envelope received on C for: {recipient}')

    # Process locally if C is the recipient
    if str(recipient).lower() in ('c', 'servicec', 'service_c'):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return jsonify({'processed': {'service': 'C', 'timestamp': now, 'received': payload}}), 200

    # Otherwise, forward to target
    if not target:
        return jsonify({'error': 'no target provided to forward to'}), 400

    try:
        r = requests.post(target, json=payload, timeout=5)
        return jsonify({'forwarded_to': target, 'status': r.status_code, 'response': r.json()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def main():
    global serial_controller
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true', help='Start Service C server')
    parser.add_argument('--serial-port', help='Serial port for Sensor ESP32 (e.g. COM10)')
    parser.add_argument('--baud', default=115200, help='Baud rate')
    parser.add_argument('--gui-url', default=None, help='URL of the GUI receiver (overrides .env)')
    args = parser.parse_args()

    if args.serve:
        if args.serial_port:
            serial_controller = SerialController(args.serial_port, args.baud, args.gui_url)
        else:
            print("Running in Network-Only mode (No Serial).")
        print(f"Starting Service C on {SERVICE_C_IP}:5002...")
        app.run(host=SERVICE_C_IP, port=5002, debug=False)

if __name__ == '__main__':
    main()
