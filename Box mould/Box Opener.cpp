#include <Arduino.h>
#include <AccelStepper.h>
#include <Servo.h>

// ----- PIN DEFINITIONS -----
const int STEP1_PIN =  23;
const int DIR1_PIN  = 22;
const int STEP2_PIN = 18;
const int DIR2_PIN  = 17;
const int STEP3_PIN = 16;
const int DIR3_PIN  = 4;
const int Stepper_In = 33;
const int Servo_In = 32;
const int SERVO_PIN = 27;
const int End1 = 19;
const int End2 = 21;

const int microstep = 16;
const int gearRatio = 6;

float speed1 = 0.15 * 200 * microstep * gearRatio;
float accel1 = speed1 * 3;
float speed2 = 20 * 200 * microstep;

AccelStepper stepper1(AccelStepper::DRIVER, STEP1_PIN, DIR1_PIN); 
AccelStepper stepper2(AccelStepper::DRIVER, STEP2_PIN, DIR2_PIN);
AccelStepper stepper3(AccelStepper::DRIVER, STEP3_PIN, DIR3_PIN);
Servo myServo;

bool Homed1 = true; 
bool Homed2 = true;
bool Homing = false;

unsigned long lastServoUpdate = 0;
const unsigned long servoInterval = 50;
int servoAngle = 0;
static int smoothAngle = 0;

void Endstop1(){
  //Serial.println("Endstop 1 triggered");
  //if (Homing){
  stepper1.setCurrentPosition(-2000);
  //Serial.println("naar nul");
  stepper1.moveTo(0);
  Homed1 = true;
  
  //}
}
void Endstop2(){
    Serial.println("Endstop 2 triggered");
  if (Homing){
  stepper2.setCurrentPosition(-1000);
  stepper2.moveTo(0);
  Homed2 = true;
  }
}

void Home() {
  Homing = true;
  Homed1 = false;
  Serial.println("Homing!");
  if (!Homed1){
    Serial.println("naar oneindig");
    stepper1.moveTo(-100000);
    stepper1.setMaxSpeed(speed1*0.05);
    stepper1.setAcceleration(accel1);
    while (!Homed1){
      stepper1.run();
    }
    while (stepper1.distanceToGo() > 0){
      stepper1.run();
    }
  }
  if (!Homed2){
    stepper2.moveTo(-100000);
    stepper2.setMaxSpeed(speed2*0.05);
    stepper2.setAcceleration(speed2);
    while (!Homed2){
      stepper2.run();
    }
  }
  Homing = false;
}

void setup() {
  Serial.begin(115200);

  pinMode(Stepper_In, INPUT_PULLUP);
  pinMode(Servo_In, INPUT_PULLUP);
  pinMode(End1, INPUT_PULLUP);
  pinMode(End2, INPUT_PULLUP);
  
  attachInterrupt(End1, Endstop1, FALLING);
  attachInterrupt(End2, Endstop2, FALLING);
  
  stepper1.setMaxSpeed(speed1*15);
  stepper1.setAcceleration(accel1*10);
  stepper2.setMaxSpeed(speed2*0.75 );
  stepper2.setAcceleration(speed2*3);

  myServo.attach(SERVO_PIN);
}

void loop() {

  if(!Homed1 || !Homed2) {
    Home();
    delay(1000);
  } else {

    int Stepper_On  = analogRead(Stepper_In);
    int Servo_On  = analogRead(Servo_In);

    // ----- SERVO CODE -----
    unsigned long now = millis();
    if (now - lastServoUpdate >= servoInterval) {
      lastServoUpdate = now;

      servoAngle = map(Servo_On, 0, 4095, 0, 110); 
      smoothAngle = (smoothAngle * 0.8) + (servoAngle * 0.2);
      myServo.write(smoothAngle);

      //Serial.print("end1=");
      //Serial.print(digitalRead(End1));
      //Serial.print(" | end2=");
      //Serial.print(digitalRead(End2));
      //Serial.print(" | home=");
      //Serial.println(digitalRead(Button1));

      // ----- STEPPER CODE -----
      if (Stepper_On >= 340 && Stepper_On < 1020) { //680 = 0.55V
        stepper1.moveTo(0);
      }
      else if (Stepper_On >= 1020 && Stepper_On < 1700) { //1360 = 1.1V 
        stepper1.moveTo(5000);
      }
      else if (Stepper_On >= 1700 && Stepper_On < 2380) { //2040 = 1.65V
        stepper2.moveTo(0); 
      }
      else if (Stepper_On >= 2380 && Stepper_On < 3060) { //2720 = 2.2V
        stepper2.moveTo(0);
      }
      else if (Stepper_On >= 3060 && Stepper_On < 3740) { //3400 = 2.75V
        stepper2.moveTo(0);
      }
      else if (Stepper_On >= 3740) { //4095 = 3.3V
        stepper3.setSpeed(200);
      }
      else { 
        stepper3.setSpeed(0);
      }
    }
    stepper1.run();
    stepper2.run();
    stepper3.runSpeed();
  }
}
