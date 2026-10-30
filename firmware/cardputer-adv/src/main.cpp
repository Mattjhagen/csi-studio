// CSI Studio: Cardputer-Adv USB receiver. Credentials live in RAM only.
#include <Arduino.h>
#include <atomic>
#include <M5Cardputer.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <ping/ping_sock.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

struct Frame {
    uint16_t len;
    int8_t rssi;
    bool invalid;
    int8_t data[612];
};
QueueHandle_t samples;
esp_ping_handle_t pingSession = nullptr;
uint8_t apMac[6] = {};
uint32_t emitted = 0;
std::atomic<uint32_t> dropped{0};
String ssid, password, input;
enum Stage { SSID, PASSWORD, CONNECTING, STREAMING, FAILED };
Stage stage = SSID;
uint32_t connectStart = 0;

void screen(const String &title, const String &body) {
    auto &d = M5Cardputer.Display;
    d.fillScreen(TFT_BLACK);
    d.setTextColor(TFT_CYAN);
    d.setTextSize(2);
    d.setCursor(4, 4);
    d.println("CSI Studio v0.2");
    d.setTextSize(1);
    d.setTextColor(TFT_WHITE);
    d.setCursor(4, 34);
    d.println(title);
    d.setCursor(4, 52);
    d.println(body);
}
void drawInput() {
    String visible = input;
    if (stage == PASSWORD) {
        visible = "";
        for (unsigned i = 0; i < input.length(); ++i) visible += '*';
    }
    screen(stage == SSID ? "2.4 GHz Wi-Fi name:" : "Wi-Fi password:",
           visible + "\n\nEnter: next | Backspace: edit");
}
void onCSI(void *, wifi_csi_info_t *info) {
    static uint32_t last = 0;
    uint32_t now = micros();
    if (!info || !info->buf || memcmp(info->mac, apMac, 6) ||
        info->len > 612 || info->len < 4 || (info->len % 2) ||
        uint32_t(now - last) < 50000) return;
    last = now;
    Frame f;
    f.len = info->len;
    f.rssi = info->rx_ctrl.rssi;
    f.invalid = info->first_word_invalid;
    memcpy(f.data, info->buf, f.len);
    if (xQueueSend(samples, &f, 0) != pdTRUE) ++dropped;
}
bool startCSI() {
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK) return false;
    memcpy(apMac, ap.bssid, 6);
    wifi_csi_config_t cfg = {};
    cfg.lltf_en = true;
    cfg.htltf_en = false;
    cfg.stbc_htltf2_en = false;
    cfg.ltf_merge_en = true;
    cfg.channel_filter_en = true;
    cfg.manu_scale = false;
    if (esp_wifi_set_csi_config(&cfg) != ESP_OK ||
        esp_wifi_set_csi_rx_cb(onCSI, nullptr) != ESP_OK ||
        esp_wifi_set_csi(true) != ESP_OK) return false;
    esp_ping_config_t ping = ESP_PING_DEFAULT_CONFIG();
    ping.count = 0;
    ping.interval_ms = 50;
    ping.timeout_ms = 500;
    ping.data_size = 16;
    ping.target_addr.type = IPADDR_TYPE_V4;
    ping.target_addr.u_addr.ip4.addr = static_cast<uint32_t>(WiFi.gatewayIP());
    esp_ping_callbacks_t callbacks = {};
    return esp_ping_new_session(&ping, &callbacks, &pingSession) == ESP_OK &&
           esp_ping_start(pingSession) == ESP_OK;
}
void setup() {
    auto cfg = M5.config();
    M5Cardputer.begin(cfg, true);
    // A CSI JSON record is larger than the default 256-byte USB TX ring.
    Serial.setTxBufferSize(8192);
    Serial.setTxTimeoutMs(10);
    Serial.begin(115200);
    samples = xQueueCreate(16, sizeof(Frame));
    if (!samples) {
        screen("Error", "CSI queue allocation failed");
        while (true) delay(1000);
    }
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    drawInput();
}
void loop() {
    M5Cardputer.update();
    if ((stage == SSID || stage == PASSWORD) &&
        M5Cardputer.Keyboard.isChange() && M5Cardputer.Keyboard.isPressed()) {
        auto keys = M5Cardputer.Keyboard.keysState();
        if (keys.del && input.length()) input.remove(input.length()-1);
        for (char c : keys.word) {
            unsigned limit = stage == SSID ? 32 : 63;
            if (c >= 32 && c <= 126 && input.length() < limit) input += c;
        }
        if (keys.enter) {
            if (stage == SSID && input.length()) {
                ssid = input;
                input = "";
                stage = PASSWORD;
            } else if (stage == PASSWORD) {
                password = input;
                input = "";
                WiFi.begin(ssid.c_str(), password.c_str());
                password = "";
                stage = CONNECTING;
                connectStart = millis();
                screen("Connecting...", "2.4 GHz only\nUSB data goes to the Mac");
            }
        }
        if (stage == SSID || stage == PASSWORD) drawInput();
    }
    if (stage == CONNECTING) {
        if (WiFi.status() == WL_CONNECTED) {
            if (startCSI()) {
                stage = STREAMING;
            } else {
                stage = FAILED;
                screen("CSI setup failed", "Press reset to retry");
            }
        } else if (millis() - connectStart > 30000) {
            stage = FAILED;
            screen("Wi-Fi connection failed", "Check name/password and 2.4 GHz\nPress reset to retry");
        }
    }
    Frame f;
    if (xQueueReceive(samples, &f, 0) == pdTRUE) {
        // Build away from the Wi-Fi callback; never block the Wi-Fi task on USB.
        char line[4096];
        int n = snprintf(line, sizeof(line), "{\"rssi\":%d,\"first_word_invalid\":%s,\"data\":[",
                         f.rssi, f.invalid ? "true" : "false");
        for (unsigned i = 0; i < f.len; ++i)
            n += snprintf(line+n, sizeof(line)-n, "%s%d", i ? "," : "", f.data[i]);
        n += snprintf(line+n, sizeof(line)-n, "]}\n");
        if (Serial.write(reinterpret_cast<uint8_t *>(line), n) == size_t(n)) ++emitted;
        else ++dropped;
    }
    static uint32_t lastDraw = 0;
    if (stage == STREAMING && millis() - lastDraw >= 1000) {
        lastDraw = millis();
        if (WiFi.status() != WL_CONNECTED) {
            screen("Wi-Fi disconnected", "Waiting for reconnection...\nReset if it does not recover");
        } else {
            screen("LIVE CSI -> USB", "Channel: " + String(WiFi.channel()) +
                   "  RSSI: " + String(WiFi.RSSI()) + " dBm\nSent: " + String(emitted) +
                   "  Dropped: " + String(dropped.load()) + "\nOpen CSI Studio on your Mac\nReset: change network");
        }
    }
    delay(2);
}
