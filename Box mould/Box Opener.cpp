#include <Arduino.h>
#include <AccelStepper.h>

// ----- PIN DEFINITIONS -----
const int STEP_PIN = 19;
const int DIR_PIN  = 27;
const int BTN_CW   = 33;
const int microstep  = 32;

// ----- CREATE STEPPER OBJECT -----
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

// Debug timing
unsigned long lastDebug = 0;
const unsigned long debugInterval = 200;   // ms between prints

void setup() {
  Serial.begin(115200);

  pinMode(BTN_CW, INPUT_PULLUP);

  stepper.setMaxSpeed(0.25 * 200 * microstep);
  stepper.setAcceleration(0.25 * 200 * microstep);
}

void loop() {

  // ----- Read buttons -----
  bool cwPressed  = !digitalRead(BTN_CW);

  // ----- Rate-Limited Debug Output -----
  unsigned long now = millis();
  if (now - lastDebug >= debugInterval) {
    lastDebug = now;

    Serial.print("CW=");
    Serial.println(cwPressed);
  }

  // ----- Motor Direction & Speed -----
  if (cwPressed) {
    stepper.moveTo(0.25 * 200 * microstep);
  }
  else {
    stepper.moveTo(0);
  }

  // Run motor smoothly (must be called constantly)
  stepper.runToPosition();
}
