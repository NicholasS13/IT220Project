const int sensorPin = 34; 
const int buttonPin = 14; // Connect button between Pin 14 and GND

void setup() {
  Serial.begin(115200);
  pinMode(sensorPin, INPUT);
  pinMode(buttonPin, INPUT_PULLUP); // LOW when pressed
  Serial.println("Service C: Sensor & Button Node Ready");
}

void loop() {
  int sensorValue = analogRead(sensorPin);
  int buttonState = digitalRead(buttonPin);

  // Send as a single line for Python to parse or two separate lines
  // Let's send a simple format Python can easily catch
  Serial.print("Analog: ");
  Serial.print(sensorValue);
  Serial.print(" | Button: ");
  Serial.println(buttonState == LOW ? "PRESSED" : "RELEASED");

  delay(200); // Faster update for button responsiveness
}