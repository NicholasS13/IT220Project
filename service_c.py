
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
SERVICE_B_IP = os.getenv('SERVICE_B_IP', '127.0.0.1')
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
        self.edgeToggles = {'gui_c': True, 'gui_b': True, 'b_c': True}  # Default: all enabled
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_edge_toggles(self, edgeToggles):
        self.edgeToggles = edgeToggles

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

                        # Route sensor data according to edge toggles
                        self.route_sensor_data(payload)
                except Exception as e:
                    print(f"Serial Read Error: {e}")
            time.sleep(0.01) # Prevent CPU hogging
        ser.close()

    def route_sensor_data(self, payload):
        # Always treat C as the origin, GUI as the target
        edgeToggles = self.edgeToggles
        SERVICE_GUI_IP = os.getenv('SERVICE_GUI_IP', '127.0.0.1')
        SERVICE_B_IP = os.getenv('SERVICE_B_IP', '127.0.0.1')
        SERVICE_C_IP = os.getenv('SERVICE_C_IP', '127.0.0.1')
        node_map = {
            'GUI': f'http://{SERVICE_GUI_IP}:5000',
            'B': f'http://{SERVICE_B_IP}:5001',
            'C': f'http://{SERVICE_C_IP}:5002',
        }
        origin_name = 'C'
        target_name = 'GUI'
        # Determine if direct edge is enabled
        direct_edge = edgeToggles.get('gui_c', True)
        if not direct_edge:
            # Route via B
            intermediary_url = node_map['B'] + '/forward'
            try:
                requests.post(intermediary_url, json={
                    'target': node_map['GUI'] + '/receive',
                    'recipient': 'GUI',
                    'payload': payload,
                    'edgeToggles': edgeToggles
                }, timeout=0.5)
            except Exception as e:
                print(f"Sensor Routing Error (via B): {e}")
        else:
            # Direct to GUI
            try:
                requests.post(node_map['GUI'] + '/receive', json=payload, timeout=0.5)
            except Exception as e:
                print(f"Sensor Routing Error (direct): {e}")

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
    edgeToggles = data.get('edgeToggles', {'gui_c': True, 'gui_b': True, 'b_c': True})

    # Update edge toggles for sensor routing
    global serial_controller
    if serial_controller:
        serial_controller.set_edge_toggles(edgeToggles)

    if recipient is None or payload is None:
        return jsonify({'error': 'missing recipient or payload'}), 400

    print(f'Forward envelope received on C for: {recipient}, edgeToggles: {edgeToggles}')

    # Process locally if C is the recipient
    if str(recipient).lower() in ('c', 'servicec', 'service_c'):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return jsonify({'processed': {'service': 'C', 'timestamp': now, 'received': payload}}), 200

    # Routing logic for all comms
    node_map = {
        'GUI': f'http://{SERVICE_GUI_IP}:5000',
        'B': f'http://{SERVICE_B_IP}:5001',
        'C': f'http://{SERVICE_C_IP}:5002',
    }
    def get_node_name_from_url(url):
        if url and SERVICE_B_IP in url:
            return 'B'
        if url and SERVICE_C_IP in url:
            return 'C'
        return 'GUI'
    origin_name = 'C'
    target_name = get_node_name_from_url(target)
    # Determine if direct edge is enabled
    direct_edge = None
    if (origin_name, target_name) in [('GUI', 'B'), ('B', 'GUI')]:
        direct_edge = edgeToggles.get('gui_b', True)
    elif (origin_name, target_name) in [('GUI', 'C'), ('C', 'GUI')]:
        direct_edge = edgeToggles.get('gui_c', True)
    elif (origin_name, target_name) in [('B', 'C'), ('C', 'B')]:
        direct_edge = edgeToggles.get('b_c', True)
    else:
        direct_edge = True
    # If direct edge is disabled, route via the third node
    if not direct_edge:
        nodes = {'GUI', 'B', 'C'}
        intermediary = list(nodes - {origin_name, target_name})[0]
        intermediary_url = node_map[intermediary] + '/forward'
        print(f"Routing via intermediary: {intermediary}")
        try:
            r = requests.post(intermediary_url, json={
                'target': target,
                'recipient': recipient,
                'payload': payload,
                'edgeToggles': edgeToggles
            }, timeout=5)
            return jsonify({'forwarded_to': intermediary_url, 'status': r.status_code, 'response': r.json()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    # Otherwise, forward directly (always include edgeToggles for next hop)
    if not target:
        return jsonify({'error': 'no target provided to forward to'}), 400
    try:
        r = requests.post(target, json={
            'target': None,
            'recipient': recipient,
            'payload': payload,
            'edgeToggles': edgeToggles
        }, timeout=5)
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
