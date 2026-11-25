// FlexML → ESP32 over Bluetooth LE (no Wi-Fi needed).
//
// FlexML advertises as "FlexML" with the Nordic UART Service:
//   TX 6E400003-… (notify): one compact line per notification, e.g. "O 3 person 87 512 430 210 380 145"
//   RX 6E400002-… (write):  text commands, e.g. "set_threshold 0.5"; replies arrive on TX as "OK …" / "ERR …"
//
// 1. Upload to an ESP32 (Arduino core 2.x or 3.x, built-in BLE library).
// 2. In FlexML: Network Setup › Microcontrollers › turn on "Send over Bluetooth LE", then open the camera.
// 3. Serial Monitor (115200) shows the detections. Type a command there (e.g. "set_threshold 0.6")
//    to send it to the phone.

#include <BLEDevice.h>

static BLEUUID SERVICE_UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
static BLEUUID RX_UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E");  // write: ESP32 → phone
static BLEUUID TX_UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E");  // notify: phone → ESP32

static BLEAdvertisedDevice* flexml = nullptr;
static BLERemoteCharacteristic* rx = nullptr;
static bool connected = false;

// Called for every line from FlexML.
void onLine(const char* line) {
  int id, conf, cx, cy, w, h, dist;
  char label[32];
  if (sscanf(line, "O %d %31s %d %d %d %d %d %d", &id, label, &conf, &cx, &cy, &w, &h, &dist) == 8) {
    Serial.printf("#%d %s %d%% at x=%d dist=%dcm\n", id, label, conf, cx, dist);
  } else if (line[0] == 'O' && line[1] == 'K') {
    Serial.printf("phone: %s\n", line);       // command accepted
  } else if (strncmp(line, "ERR", 3) == 0) {
    Serial.printf("phone error: %s\n", line);
  }
}

void onNotify(BLERemoteCharacteristic*, uint8_t* data, size_t length, bool) {
  char line[256];
  size_t n = length < sizeof(line) - 1 ? length : sizeof(line) - 1;
  memcpy(line, data, n);
  line[n] = '\0';
  onLine(line);
}

class Finder : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice device) override {
    if (device.haveServiceUUID() && device.isAdvertisingService(SERVICE_UUID)) {
      BLEDevice::getScan()->stop();
      flexml = new BLEAdvertisedDevice(device);
    }
  }
};

bool connectToFlexML() {
  BLEClient* client = BLEDevice::createClient();
  if (!client->connect(flexml)) return false;
  client->setMTU(185);
  BLERemoteService* service = client->getService(SERVICE_UUID);
  if (!service) { client->disconnect(); return false; }
  BLERemoteCharacteristic* tx = service->getCharacteristic(TX_UUID);
  rx = service->getCharacteristic(RX_UUID);
  if (!tx || !rx) { client->disconnect(); return false; }
  tx->registerForNotify(onNotify);
  Serial.println("Connected to FlexML. Type a command, e.g. get_status");
  return true;
}

void sendCommand(const String& text) {
  if (connected && rx) rx->writeValue((uint8_t*)text.c_str(), text.length(), true);
}

void setup() {
  Serial.begin(115200);
  BLEDevice::init("FlexML-ESP32");
  BLEScan* scan = BLEDevice::getScan();
  scan->setAdvertisedDeviceCallbacks(new Finder());
  scan->setActiveScan(true);
  Serial.println("Scanning for FlexML…");
  scan->start(10, false);
}

void loop() {
  if (!connected && flexml) {
    connected = connectToFlexML();
    if (!connected) { delete flexml; flexml = nullptr; }
  }
  if (!connected && !flexml) BLEDevice::getScan()->start(5, false);

  if (Serial.available()) {
    String text = Serial.readStringUntil('\n');
    text.trim();
    if (text.length()) sendCommand(text);
  }
  delay(20);
}
