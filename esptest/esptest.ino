void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32 ready");
}

void loop() {
  static unsigned long counter = 0;
  counter++;

  Serial.print("Count: ");
  Serial.print(counter);
  Serial.print(", millis: ");
  Serial.println(millis());

  delay(1000);
}