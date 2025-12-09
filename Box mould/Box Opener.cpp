#include <Arduino.h>
#include <AccelStepper.h>
#include <Servo.h>

// ----- PIN DEFINITIONS -----
const int STEP_PIN = 33;
const int DIR_PIN  = 32;
const int Stepper_In = 26;
const int Servo_In = 25;
const int SERVO_PIN = 27;

const int microstep = 32;
const int gearRatio = 6;

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
Servo myServo;

unsigned long lastServoUpdate = 0;
const unsigned long servoInterval = 50;
int servoAngle = 0;
static int smoothAngle = 0;

void setup() {
  Serial.begin(115200);

  pinMode(Stepper_In, INPUT_PULLUP);
  pinMode(Servo_In, INPUT_PULLUP);

  float speed = 0.25 * 500 * microstep * gearRatio;
  stepper.setMaxSpeed(speed);
  stepper.setAcceleration(speed);

  myServo.attach(SERVO_PIN);
}

void loop() {

  bool Stepper_On  = digitalRead(Stepper_In);
  int Servo_On  = analogRead(Servo_In);

  // ----- SERVO CODE -----
  unsigned long now = millis();
  if (now - lastServoUpdate >= servoInterval) {
    lastServoUpdate = now;

    servoAngle = map(Servo_On, 0, 4095, 0, 110); 
    smoothAngle = (smoothAngle * 0.8) + (servoAngle * 0.2);
    myServo.write(smoothAngle);

    Serial.print("Stepper on=");
    Serial.print(Stepper_On);
    Serial.print("Servo on=");
    Serial.print(Servo_On);
    Serial.print(" | Servo Angle=");
    Serial.print(servoAngle);
    Serial.print(" | smooth Angle=");
    Serial.println(smoothAngle);

    // ----- STEPPER CODE -----
    if (Stepper_On == true) {
      stepper.moveTo(0.3 * 200 * microstep * gearRatio);
    }
    else {
      stepper.moveTo(0);
    }
  }
  stepper.run();
}
