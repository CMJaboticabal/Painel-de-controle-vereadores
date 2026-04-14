/*
 * Código-fonte completo para o Comunicador Wi-Fi (Walkie-Talkie) com ESP32
 * Atualizado com suporte ao Painel em Python (GET_CFG e CFG).
 */
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <driver/adc.h>
#include <Preferences.h>

// -------------------------------------------------------------------
// CONFIGURAÇÃO MEMÓRIA INTERNA
// -------------------------------------------------------------------
Preferences preferences;
String nomeDispositivo;
String ssidAtual;
String senhaAtual;

// Rede
IPAddress MULTICAST_ADDR(239, 0, 0, 1);
const int UDP_PORT = 1234;

// Áudio
const int SAMPLE_RATE = 8000;
const int SAMPLE_BITS = 16;

// Pinos (Configuração para Placa com Bateria/Lolin32)
const int PTT_PIN = 14;
const int VOL_POT_PIN = 34;   
const int MIC_ADC_PIN = 36;   

// Pinos I2S (Saída DAC PCM5102A)
const int I2S_LRC_PIN = 25;
const int I2S_BCK_PIN = 26;
const int I2S_DIN_PIN = 22;

const int PACKET_SAMPLES = 256;
const int BUFFER_SIZE = PACKET_SAMPLES * 2;

// Objetos e Variáveis Globais
WiFiUDP udp;
TaskHandle_t xTransmitTask;
TaskHandle_t xReceiveTask;
volatile float current_volume = 1.0;

// Variáveis de diagnóstico
unsigned long last_packet_time = 0;
bool receiving_signal = false;
const unsigned long SIGNAL_TIMEOUT = 500;

// =======================================================================
// 1. LEITURA DE COMANDOS USB (Extraído para não bloquear o Wi-Fi)
// =======================================================================
void verificar_comandos_usb() {
  while (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();
    
    // Ignora quebras de linha vazias ou ruído mínimo
    if (comando.length() < 3) continue;
    
    // Usamos indexOf para ignorar qualquer "lixo" que venha antes do comando
    if (comando.indexOf("GET_CFG") != -1) {
      Serial.printf("CFG_DATA:%s:%s:%s\n", nomeDispositivo.c_str(), ssidAtual.c_str(), senhaAtual.c_str());
    }
    else if (comando.indexOf("CFG:") != -1) {
      int start = comando.indexOf("CFG:");
      int s1 = comando.indexOf(':', start + 4);
      int s2 = comando.indexOf(':', s1 + 1);
      
      if (s1 > 0 && s2 > 0) {
        String nNome = comando.substring(start + 4, s1);
        String nSSID = comando.substring(s1 + 1, s2);
        String nSenha = comando.substring(s2 + 1);
        
        preferences.putString("nome", nNome);
        preferences.putString("ssid", nSSID);
        preferences.putString("pass", nSenha);
        
        Serial.println("\nOK_SALVO");
        delay(500);
        ESP.restart(); // Reinicia para aplicar o novo Wi-Fi
      }
    }
  }
}

// =======================================================================
// TAREFA DE RECEÇÃO (RX - Núcleo 0)
// =======================================================================
void receive_task(void *pvParameters) {
  uint8_t rx_buffer[BUFFER_SIZE];
  int16_t stereo_buffer[PACKET_SAMPLES * 2]; 
  size_t bytes_written;

  Serial.println(">> Tarefa RX (Ouvidos) iniciada no Núcleo 0");

  while (true) {
    int packetSize = udp.parsePacket();
    
    if (packetSize) {
      int len = udp.read(rx_buffer, BUFFER_SIZE);

      // Se o tamanho for exatamente um pacote de áudio (512 bytes)
      if (len == BUFFER_SIZE) {
        if (!receiving_signal) {
          receiving_signal = true;
          Serial.println("\n[SINAL] Recebendo áudio de outro rádio ou do PC...");
        }
        last_packet_time = millis();

        // Converte Mono para Estéreo e aplica o volume
        int16_t *mono_samples = (int16_t *)rx_buffer;
        for (int i = 0; i < PACKET_SAMPLES; i++) {
          int16_t sample = (int16_t)(mono_samples[i] * current_volume);
          stereo_buffer[i * 2]     = sample;
          stereo_buffer[i * 2 + 1] = sample;
        }

        i2s_write(I2S_NUM_0, stereo_buffer, BUFFER_SIZE * 2, &bytes_written, portMAX_DELAY);
      }
    }

    if (receiving_signal && (millis() - last_packet_time > SIGNAL_TIMEOUT)) {
      receiving_signal = false;
      Serial.println("[SINAL] Fim da transmissão.");
    }
    
    vTaskDelay(1 / portTICK_PERIOD_MS); 
  }
}

// =======================================================================
// TAREFA DE TRANSMISSÃO (TX - Núcleo 1)
// =======================================================================
void transmit_task(void *pvParameters) {
  uint8_t tx_buffer[BUFFER_SIZE];
  int16_t *samples = (int16_t *)tx_buffer;

  Serial.println(">> Tarefa TX (Boca) iniciada no Núcleo 1");

  while (true) {
    if (digitalRead(PTT_PIN) == LOW) {
      
      static bool was_transmitting = false;
      
      // Quando aperta o botão: Dá um BEEP de aviso
      if (!was_transmitting) {
        was_transmitting = true;
        Serial.println("[PTT] Gerando BEEP de sistema...");
        
        for(int b = 0; b < 3; b++) {
          for (int i = 0; i < PACKET_SAMPLES; i++) {
            if ((i / 4) % 2 == 0) samples[i] = 16000;
            else samples[i] = -16000;
          }
          udp.beginPacket(MULTICAST_ADDR, UDP_PORT);
          udp.write(tx_buffer, BUFFER_SIZE);
          udp.endPacket();
          vTaskDelay(15 / portTICK_PERIOD_MS);
        }
        Serial.println("[PTT] Lendo microfone analógico...");
      }

      // Loop de captura do Microfone
      for (int i = 0; i < PACKET_SAMPLES; i++) {
        int adc_val = adc1_get_raw(ADC1_CHANNEL_0);
        int32_t sample = (int32_t)adc_val - 2048; 
        sample = sample * 16; 

        if (sample > 32767) sample = 32767;
        if (sample < -32768) sample = -32768;

        samples[i] = (int16_t)sample;
        delayMicroseconds(125); 
      }

      udp.beginPacket(MULTICAST_ADDR, UDP_PORT);
      udp.write(tx_buffer, BUFFER_SIZE);
      udp.endPacket();
      
    } else {
      static bool was_transmitting = true;
      if (was_transmitting) {
        was_transmitting = false;
        Serial.println("[PTT] Botão solto. Modo Escuta.");
      }
      vTaskDelay(20 / portTICK_PERIOD_MS);
    }
  }
}

// =======================================================================
// SETUP: INICIALIZAÇÃO
// =======================================================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n--- Walkie-Talkie ESP32 Pro ---");

  pinMode(PTT_PIN, INPUT_PULLUP);

  // --- CARREGA DADOS DA MEMÓRIA FLASH ---
  preferences.begin("config", false);
  
  nomeDispositivo = preferences.getString("nome", "Radio-1");
  ssidAtual = preferences.getString("ssid", "comunicador");
  senhaAtual = preferences.getString("pass", "11050921");

  Serial.println("[SISTEMA] Dispositivo: " + nomeDispositivo);
  
  // Grita as configurações no boot para o Python ler facilmente
  Serial.printf("CFG_DATA:%s:%s:%s\n", nomeDispositivo.c_str(), ssidAtual.c_str(), senhaAtual.c_str());

  Serial.printf("[WIFI] Conectando na rede: %s \n", ssidAtual.c_str());
  WiFi.begin(ssidAtual.c_str(), senhaAtual.c_str());
  
  // Tenta conectar por 10 segundos
  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 20) {
    delay(500);
    // Alterado para println para não engasgar o buffer de leitura do Python
    Serial.println("[WIFI] Tentando conectar..."); 
    tentativas++;
    verificar_comandos_usb(); // Escuta o USB enquanto tenta conectar
  }

  if(WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Online!");
    Serial.print("[WIFI] IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[ERRO] Falha no Wi-Fi. Aguardando configuração via USB.");
  }

  // --- INICIA MÓDULOS DE ÁUDIO ---
  if (udp.beginMulticast(MULTICAST_ADDR, UDP_PORT)) {
    Serial.println("[UDP] Rádio aberto em Multicast.");
  }

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT, 
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false,
    .tx_desc_auto_clear = true
  };
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCK_PIN,
    .ws_io_num = I2S_LRC_PIN,
    .data_out_num = I2S_DIN_PIN,
    .data_in_num = I2S_PIN_NO_CHANGE 
  };
  i2s_set_pin(I2S_NUM_0, &pin_config);

  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(ADC1_CHANNEL_0, ADC_ATTEN_DB_11);
  adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_ATTEN_DB_11);

  xTaskCreatePinnedToCore(receive_task, "RX Task", 10000, NULL, 1, &xReceiveTask, 0);
  xTaskCreatePinnedToCore(transmit_task, "TX Task", 10000, NULL, 1, &xTransmitTask, 1);
}

// =======================================================================
// LOOP PRINCIPAL: SISTEMA E USB
// =======================================================================
void loop() {
  // 1. Atualiza o volume via potenciómetro
  current_volume = (float)adc1_get_raw(ADC1_CHANNEL_6) / 4095.0;

  // 2. Escuta comandos do PC via Cabo USB
  verificar_comandos_usb();

  // 3. Envia o sinal "Estou vivo" para o Painel do PC
  static unsigned long ultimoHeartbeat = 0;
  if (millis() - ultimoHeartbeat > 5000) { 
    ultimoHeartbeat = millis();
    
    if (WiFi.status() == WL_CONNECTED) {
      String statusMsg = "HEARTBEAT:" + nomeDispositivo + ":" + WiFi.localIP().toString();
      udp.beginPacket(MULTICAST_ADDR, UDP_PORT);
      udp.print(statusMsg);
      udp.endPacket();
    }
  }

  delay(100); 
}