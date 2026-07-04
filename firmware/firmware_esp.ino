#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_SSD1306.h>
#include <LiquidCrystal_I2C.h>

Adafruit_BMP280 bmp;
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
LiquidCrystal_I2C lcd(0x27, 16, 2);

const int RELAY_PIN = 2; // Signal on D2 (Internal LED + Relay)
const int POT_PIN = 34;
int sampleCount = 0;
String lastAiMsg = "Initializing...";

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Start with everything OFF

  Wire.begin();
  lcd.init(); lcd.backlight();
  bmp.begin(0x76); 

  if(!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) Serial.println("OLED Error");
  oled.clearDisplay();
  oled.setTextWrap(true);
  oled.display();

  // --- HARDWARE BOOT TEST ---
  for(int i=0; i<3; i++) {
    digitalWrite(RELAY_PIN, HIGH); delay(300); // Blue Light & Relay ON
    digitalWrite(RELAY_PIN, LOW);  delay(300); // Blue Light & Relay OFF
  }
}

void loop() {
  float t = bmp.readTemperature();
  float p = bmp.readPressure() / 100.0F;
  int w = map(analogRead(POT_PIN), 0, 4095, 0, 100);

  // Send packet to Python: T, P, W, Z
  Serial.print(t); Serial.print(","); 
  Serial.print(p); Serial.print(",");
  Serial.print(w); Serial.print(","); 
  Serial.println(10); 

  // LCD Telemetry
  lcd.setCursor(0,0);
  lcd.print("T:"); lcd.print(t,1); lcd.print("C P:"); lcd.print((int)p);
  lcd.setCursor(0,1);
  lcd.print("B:"); lcd.print(sampleCount); lcd.print("/10  ");
  lcd.print(p < 970 ? "STORM" : "CLEAR");

  // --- AI DECISION LISTENER ---
  if (Serial.available() > 0) {
    lastAiMsg = Serial.readStringUntil('\n');
    lastAiMsg.toUpperCase();
    sampleCount = 0; 
    
    // Check for 'W' in the end of the AI string
    String commandZone = lastAiMsg.substring(max(0, (int)lastAiMsg.length() - 10));
    
    if (commandZone.indexOf('W') != -1) {
      digitalWrite(RELAY_PIN, HIGH); // WATER -> PUMP ON & BLUE LED ON
    } else {
      digitalWrite(RELAY_PIN, LOW);  // STOP -> PUMP OFF & BLUE LED OFF
    }
  }

  // --- OLED DASHBOARD ---
  oled.clearDisplay();
  oled.setTextColor(WHITE);
  oled.drawRect(0, 0, 128, 14, WHITE);
  oled.setCursor(35, 3); oled.print("AI BRAIN");
  
  oled.setCursor(0, 20);
  oled.print(lastAiMsg); 

  oled.setCursor(0, 54);
  oled.print("PUMP: "); 
  oled.print(digitalRead(RELAY_PIN) == HIGH ? "ACTIVE [ON]" : "OFF");
  oled.display();

  if (sampleCount < 10) sampleCount++;
  delay(2000); 
}
