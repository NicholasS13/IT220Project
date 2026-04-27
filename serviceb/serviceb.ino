#include <ESP32Servo.h>

Servo motorR; Servo motorL;
const int pinR = 18; const int pinL = 17;
int curR = 90; int curL = 90;

void setup() {
  Serial.begin(115200);
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  motorR.setPeriodHertz(50);
  motorL.setPeriodHertz(50);
  motorR.attach(pinR, 1000, 2000);
  motorL.attach(pinL, 1000, 2000);
  motorR.write(90);
  motorL.write(90);
  Serial.println("Service B: Dual Motor Ready");
}

void dualRamp(int targetR, int targetL) {
  while (curR != targetR || curL != targetL) {
    if (curR < targetR) curR++; else if (curR > targetR) curR--;
    if (curL < targetL) curL++; else if (curL > targetL) curL--;
    motorR.write(curR);
    motorL.write(curL);
    delay(15); 
  }
}

void loop() {
  //Serial.print("loop running");
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.startsWith("MOTOR,START")) {
      int lastComma = input.lastIndexOf(',');
      int speedVal = (lastComma != -1) ? input.substring(lastComma + 1).toInt() : 255;
      
      // Map 0-255 to 0-180 degrees
      int target = map(speedVal, 0, 255, 0, 180);
      Serial.print("ACK: Ramping to "); Serial.println(speedVal);
      dualRamp(target, target);
    } 
    else if (input.startsWith("MOTOR,STOP")) {
      Serial.println("ACK: Stopping");
      dualRamp(90, 90);
    }
  }
}