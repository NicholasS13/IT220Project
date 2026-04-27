import serial
import time

PORT = "COM10"       # Change to your port, e.g. "/dev/ttyUSB0" on Linux or Mac
BAUD = 115200

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # give ESP32 time to reset after serial opens
        print(f"Connected to {PORT} at {BAUD}")

        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print(line)

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        try:
            ser.close()
        except:
            pass

if __name__ == "__main__":
    main()