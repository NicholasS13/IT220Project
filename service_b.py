import argparse
import threading
import queue
import datetime
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
try:
    import serial
except ImportError:
    serial = None

app = Flask(__name__)
CORS(app)

# Global holder for the serial worker
serial_controller = None

class SerialController:
    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = int(baud)
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        if serial is None: return
        try:
            # 1. Open the port
            ser = serial.Serial(self.port, self.baud, timeout=1)
            # 2. CRITICAL: Give the ESP32 2 seconds to reboot after opening the port
            print(f'--- Motor Serial Port Opened: {self.port}. Waiting for ESP32 reset... ---')
            time.sleep(2) 
            print('--- Ready to send commands! ---')
        except Exception as e:
            print(f'--- Failed to open serial port {self.port}: {e} ---')
            return

        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.2)
                if item is None: break
                
                # 3. Write and print to confirm it actually left the computer
                ser.write(item.encode('utf-8'))
                ser.flush()
                print(f'>>> PHYSICALLY SENT TO SERIAL: {item.strip()}') # Look for this in terminal
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f'Serial Write Error: {e}')
                break # Exit loop on hardware failure
                
        ser.close()
        print("--- Serial Port Closed ---")
    def send(self, text):
        self._q.put(text)

    def stop(self):
        self._stop.set()
        self._q.put(None)
        self._thread.join(timeout=1)

def process_motor_logic(data):
    """Helper to extract motor commands from incoming JSON"""
    global serial_controller
    if not serial_controller:
        return
    
    # Support multiple formats: {"motor": "on"} or {"cmd": "motor", "action": "on"}
    action = data.get('motor') or data.get('action')
    if not action and data.get('cmd') == 'motor':
        action = data.get('action')

    if action:
        speed = data.get('speed', 255)
        if str(action).lower() in ('start', 'on', 'run'):
            cmd_text = f"MOTOR,START,{speed}\n"
        else:
            cmd_text = "MOTOR,STOP\n"
        
        serial_controller.send(cmd_text)
        print(f"Local Processing: {cmd_text.strip()}")

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json(silent=True) or {}
    print('Received POST on Service B /receive:', data)
    
    # Check for motor commands in the direct payload
    process_motor_logic(data)
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return jsonify({'service': 'B', 'timestamp': now, 'received': data})

@app.route('/forward', methods=['POST'])
def forward():
    data = request.get_json(silent=True) or {}
    target = data.get('target')
    recipient = data.get('recipient')
    payload = data.get('payload')

    if recipient is None or payload is None:
        return jsonify({'error': 'missing recipient or payload'}), 400

    print(f'Forward envelope received on B for: {recipient}')

    # If this message is intended for B, process locally
    if str(recipient).lower() in ('b', 'serviceb', 'service_b'):
        process_motor_logic(payload)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return jsonify({'processed': {'service': 'B', 'timestamp': now, 'received': payload}}), 200

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
    parser.add_argument('--serve', action='store_true', help='Start Service B server')
    parser.add_argument('--serial-port', help='Serial port for Motor ESP32 (e.g. COM11)')
    parser.add_argument('--baud', default=115200, help='Baud rate')
    args = parser.parse_args()

    if args.serve:
        if args.serial_port:
            serial_controller = SerialController(args.serial_port, args.baud)
        else:
            print("Warning: No serial port provided. Motor commands will be logged but not sent.")
            
        print("Starting Service B on Port 5001...")
        # host='0.0.0.0' allows other machines on the network to connect
        app.run(host='0.0.0.0', port=5001, debug=False) 

if __name__ == '__main__':
    main()
