// FlexML → ESP32 over Wi-Fi (UDP).
//
// 1. Set your Wi-Fi below and upload to an ESP32 (Arduino core 2.x or 3.x).
// 2. Open the Serial Monitor (115200) and note the IP address it prints.
// 3. In FlexML: Network Setup › Microcontrollers › turn on "Send over Wi-Fi (UDP)",
//    enter that IP, port 5005.
//
// Each datagram is one frame of compact lines (see docs/robot-integration.md):
//   F <frame> <time_ms> <objects>
//   O <track_id> <label> <conf_pct> <cx> <cy> <w> <h> <dist_cm>   (cx, cy, w, h in 0–1000)
//   P <x_cm> <y_cm> <z_cm> <heading_deg>
//
// The example steers toward the most confident "person": it prints LEFT / RIGHT / AHEAD and
// lights the built-in LED when one is closer than 1 m. Replace steer() with your motor code.

#include <WiFi.h>
#include <WiFiUdp.h>

const char* WIFI_SSID = "your-wifi";
const char* WIFI_PASSWORD = "your-password";
const uint16_t UDP_PORT = 5005;
const char* TARGET_LABEL = "person";
const int LED_PIN = 2;

WiFiUDP udp;
char packet[1500];

struct Target {
  bool found = false;
  int conf = 0, cx = 500, distanceCm = -1;
};

void steer(const Target& t) {
  if (!t.found) { Serial.println("searching…"); return; }
  const char* direction = t.cx < 400 ? "LEFT" : (t.cx > 600 ? "RIGHT" : "AHEAD");
  Serial.printf("%s %s conf=%d%% dist=%dcm\n", TARGET_LABEL, direction, t.conf, t.distanceCm);
  digitalWrite(LED_PIN, (t.distanceCm > 0 && t.distanceCm < 100) ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print("."); }
  Serial.printf("\nReady. In FlexML enter %s port %u\n", WiFi.localIP().toString().c_str(), UDP_PORT);
  udp.begin(UDP_PORT);
}

void loop() {
  int size = udp.parsePacket();
  if (size <= 0) return;
  int len = udp.read(packet, sizeof(packet) - 1);
  packet[len] = '\0';

  Target best;
  for (char* line = strtok(packet, "\n"); line; line = strtok(nullptr, "\n")) {
    if (line[0] != 'O') continue;
    int id, conf, cx, cy, w, h, dist;
    char label[32];
    if (sscanf(line, "O %d %31s %d %d %d %d %d %d", &id, label, &conf, &cx, &cy, &w, &h, &dist) == 8
        && strcmp(label, TARGET_LABEL) == 0 && conf > best.conf) {
      best.found = true; best.conf = conf; best.cx = cx; best.distanceCm = dist;
    }
  }
  steer(best);
}
