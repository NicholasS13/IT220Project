#include <ESP32Servo.h>

Servo motorR;
Servo motorL;

const int pinR = 18; // Right Motor Signal (White)
const int pinL = 17; // Left Motor Signal (White)

int curR = 90; // Current Angle Right
int curL = 90; // Current Angle Left

void setup() {
  Serial.begin(115200);
  
  // Allocate timers for S3
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);

  motorR.setPeriodHertz(50);
  motorL.setPeriodHertz(50);

  motorR.attach(pinR, 1000, 2000);
  motorL.attach(pinL, 1000, 2000);

  // Ensure both start stopped
  motorR.write(90);
  motorL.write(90);
  
  Serial.println("Dual VEX Motor Tester Ready...");
}

// Ramps both motors to their targets simultaneously
void dualRamp(int targetR, int targetL) {
  while (curR != targetR || curL != targetL) {
    // Increment/Decrement Right
    if (curR < targetR) curR++;
    else if (curR > targetR) curR--;
    
    // Increment/Decrement Left
    if (curL < targetL) curL++;
    else if (curL > targetL) curL--;

    motorR.write(curR);
    motorL.write(curL);
    
    delay(15); // Sync ramping speed
  }
}

void loop() {
  Serial.println("Both Motors: Full Forward");
  dualRamp(180, 180); 
  delay(3000);

  Serial.println("Both Motors: Stopping");
  dualRamp(90, 90); 
  delay(2000);

  Serial.println("Both Motors: Full Reverse");
  dualRamp(0, 0); 
  delay(3000);

  Serial.println("Both Motors: Stopping");
  dualRamp(90, 90); 
  delay(2000);
}
