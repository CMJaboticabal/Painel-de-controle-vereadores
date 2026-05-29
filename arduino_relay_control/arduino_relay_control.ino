/*
 * Sistema de Controle de Tribuna Parlamentar
 * Controle de Relé de 2 Canais para Corte de Áudio
 * 
 * LÓGICA FAIL-SAFE (Som aberto por padrão)
 * 
 * Hardware:
 * - Arduino Uno/Nano
 * - Módulo Relé 5V de 2 Canais
 * 
 * Conexões:
 * - Relé Canal 1 IN -> Pino Digital 7 (Microfone 1)
 * - Relé Canal 2 IN -> Pino Digital 8 (Microfone 2)
 * - Relé VCC -> 5V
 * - Relé GND -> GND
 * 
 * Ligação de Áudio (FAIL-SAFE):
 * - Sinal de Áudio IN -> COM (Comum)
 * - Sinal de Áudio OUT -> NC (Normalmente Fechado)
 * 
 * Comandos Serial:
 * '1' = Liberar áudio (relé DESLIGADO - contato NC fechado)
 * '0' = Cortar áudio (relé LIGADO - contato NC aberto)
 * 
 * Lógica de Segurança FAIL-SAFE:
 * - Estado natural (sem energia): Relé DESLIGADO = Contato NC FECHADO = SOM ATIVO ✅
 * - Sistema ligado em repouso: Relé LIGADO = Contato NC ABERTO = SOM CORTADO
 * - Falha de energia/USB: Relé DESLIGADO = SOM ATIVO (SEGURO) ✅
 */

// Configurações
const int RELAY_CH1_PIN = 7;       // Canal 1 - Microfone 1
const int RELAY_CH2_PIN = 8;       // Canal 2 - Microfone 2
const int LED_PIN = LED_BUILTIN;   // LED interno para feedback visual
const unsigned long TIMEOUT = 5000; // Timeout de 5 segundos sem comunicação

// Variáveis de controle
unsigned long lastCommandTime = 0;
bool audioMuted = true;  // Inicia com áudio cortado (relés ligados)

void setup() {
  // Configurar pinos
  pinMode(RELAY_CH1_PIN, OUTPUT);
  pinMode(RELAY_CH2_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  // Estado inicial: áudio cortado (relés LIGADOS para abrir contato NC)
  // Isso garante que ao ligar o sistema, o áudio esteja cortado até iniciar
  digitalWrite(RELAY_CH1_PIN, HIGH);
  digitalWrite(RELAY_CH2_PIN, HIGH);
  digitalWrite(LED_PIN, HIGH);
  audioMuted = true;
  
  // Iniciar comunicação serial
  Serial.begin(9600);
  
  // Aguardar estabilização
  delay(1000);
  
  // Sinal de inicialização
  blinkLED(3, 200);
  
  Serial.println("===========================================");
  Serial.println("Sistema de Controle de Audio - FAIL-SAFE");
  Serial.println("===========================================");
  Serial.println("Logica: NC (Normalmente Fechado)");
  Serial.println("Rele DESLIGADO = Som ATIVO (Fail-Safe)");
  Serial.println("Rele LIGADO = Som CORTADO");
  Serial.println("-------------------------------------------");
  Serial.println("Comandos:");
  Serial.println("'1' = Liberar Audio (Rele OFF)");
  Serial.println("'0' = Cortar Audio (Rele ON)");
  Serial.println("===========================================");
  Serial.println();
  Serial.println(">>> AUDIO CORTADO (Aguardando inicio) <<<");
}

void loop() {
  // Verificar se há dados disponíveis na serial
  if (Serial.available() > 0) {
    char command = Serial.read();
    lastCommandTime = millis();
    
    // Processar comando
    if (command == '1') {
      openAudio();
    } 
    else if (command == '0') {
      cutAudio();
    }
    else {
      Serial.print("Comando invalido: ");
      Serial.println(command);
    }
  }
  
  // Verificar timeout de comunicação
  // Se áudio está aberto e não recebe comando há 5s, corta por segurança
  if (!audioMuted && (millis() - lastCommandTime > TIMEOUT)) {
    Serial.println("TIMEOUT: Cortando audio por seguranca");
    cutAudio();
  }
  
  // Pequeno delay para estabilidade
  delay(10);
}

/**
 * Abre o áudio (DESLIGA os relés - contato NC fecha)
 * FAIL-SAFE: Este é o estado natural sem energia
 */
void openAudio() {
  if (audioMuted) {
    // DESLIGAR relés = Contato NC fecha = Som passa
    digitalWrite(RELAY_CH1_PIN, LOW);
    digitalWrite(RELAY_CH2_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    audioMuted = false;
    
    Serial.println("╔═══════════════════════════════════════╗");
    Serial.println("║   >>> AUDIO LIBERADO (2 CANAIS) <<<  ║");
    Serial.println("║   Reles: DESLIGADOS (NC fechado)     ║");
    Serial.println("╚═══════════════════════════════════════╝");
    blinkLED(1, 100);
  }
}

/**
 * Corta o áudio (LIGA os relés - contato NC abre)
 */
void cutAudio() {
  if (!audioMuted) {
    // LIGAR relés = Contato NC abre = Som cortado
    digitalWrite(RELAY_CH1_PIN, HIGH);
    digitalWrite(RELAY_CH2_PIN, HIGH);
    digitalWrite(LED_PIN, HIGH);
    audioMuted = true;
    
    Serial.println("╔═══════════════════════════════════════╗");
    Serial.println("║   >>> AUDIO CORTADO (2 CANAIS) <<<   ║");
    Serial.println("║   Reles: LIGADOS (NC aberto)         ║");
    Serial.println("╚═══════════════════════════════════════╝");
    blinkLED(2, 100);
  }
}

/**
 * Pisca o LED para feedback visual
 * @param times Número de piscadas
 * @param delayMs Delay entre piscadas em milissegundos
 */
void blinkLED(int times, int delayMs) {
  bool originalState = digitalRead(LED_PIN);
  
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_PIN, LOW);
    delay(delayMs);
  }
  
  digitalWrite(LED_PIN, originalState);
}

/**
 * Função de emergência - pode ser chamada por interrupção
 * se necessário adicionar um botão físico de emergência
 */
void emergencyCut() {
  digitalWrite(RELAY_CH1_PIN, HIGH);
  digitalWrite(RELAY_CH2_PIN, HIGH);
  digitalWrite(LED_PIN, HIGH);
  audioMuted = true;
  
  Serial.println("!!! CORTE DE EMERGENCIA !!!");
  
  // Piscar LED rapidamente
  for (int i = 0; i < 10; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    delay(50);
  }
}

/**
 * Função chamada ao resetar ou desligar
 * Garante que relés sejam desligados (som ativo)
 */
void shutdown() {
  // DESLIGAR relés = Som ATIVO (Fail-Safe)
  digitalWrite(RELAY_CH1_PIN, LOW);
  digitalWrite(RELAY_CH2_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  
  Serial.println("╔═══════════════════════════════════════╗");
  Serial.println("║   SISTEMA DESLIGANDO                  ║");
  Serial.println("║   Audio LIBERADO (Fail-Safe)          ║");
  Serial.println("╚═══════════════════════════════════════╝");
}