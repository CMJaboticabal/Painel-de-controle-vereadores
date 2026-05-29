# Especificação Técnica - Sistema de Controle de Tribuna Parlamentar

## 1. Visão Geral do Sistema

### 1.1 Objetivo
Sistema integrado para controle de tempo de fala em sessões parlamentares, com corte físico de áudio via hardware e transmissão ao vivo com Lower Third.

### 1.2 Componentes Principais
1. **Interface Desktop** (PyQt6) - Painel do Presidente
2. **Servidor Web** (Flask-SocketIO) - Comunicação em tempo real
3. **Lower Third Web** (HTML/CSS/JS) - Overlay para OBS/vMix
4. **Controlador Arduino** (C++) - Corte físico de áudio
5. **Banco de Dados** (JSON) - Armazenamento de vereadores

## 2. Arquitetura do Sistema

### 2.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                      CAMADA DE APRESENTAÇÃO                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐              ┌──────────────────────┐│
│  │  Painel Presidente   │              │   Lower Third Web    ││
│  │     (PyQt6 GUI)      │              │   (HTML/CSS/JS)      ││
│  │                      │              │                      ││
│  │  - Cronômetro        │              │  - Delay 10s         ││
│  │  - Vereadores        │              │  - Animações         ││
│  │  - Controles         │              │  - Socket.io Client  ││
│  └──────────────────────┘              └──────────────────────┘│
│           │                                      │              │
└───────────┼──────────────────────────────────────┼──────────────┘
            │                                      │
            │                                      │
┌───────────┼──────────────────────────────────────┼──────────────┐
│           │         CAMADA DE NEGÓCIOS           │              │
├───────────┼──────────────────────────────────────┼──────────────┤
│           │                                      │              │
│  ┌────────▼──────────┐              ┌───────────▼────────────┐ │
│  │  Arduino          │              │  Flask-SocketIO        │ │
│  │  Controller       │              │  Server                │ │
│  │  (Python)         │              │                        │ │
│  │                   │              │  - WebSocket Events    │ │
│  │  - Serial Comm    │              │  - State Management    │ │
│  │  - Auto Reconnect │              │  - Broadcasting        │ │
│  └────────┬──────────┘              └────────────────────────┘ │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
            │
┌───────────┼─────────────────────────────────────────────────────┐
│           │           CAMADA DE HARDWARE                        │
├───────────┼─────────────────────────────────────────────────────┤
│           │                                                     │
│  ┌────────▼──────────┐              ┌────────────────────────┐ │
│  │  Arduino Uno/Nano │──────────────│  Módulo Relé 5V        │ │
│  │                   │              │                        │ │
│  │  - Firmware C++   │              │  - NO/COM/NC           │ │
│  │  - Serial 9600    │              │  - Corte Físico        │ │
│  │  - Timeout 5s     │              │                        │ │
│  └───────────────────┘              └────────┬───────────────┘ │
│                                               │                 │
│                                      ┌────────▼───────────────┐ │
│                                      │  Sinal de Áudio        │ │
│                                      │  (Microfone XLR/P10)   │ │
│                                      └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Fluxo de Dados

```
[Usuário] 
    │
    ├─> Seleciona Vereador
    │       │
    │       └─> [PyQt6] → [WebSocket] → [Lower Third] (delay 10s)
    │
    ├─> Define Tempo
    │       │
    │       └─> [PyQt6] → Estado Local
    │
    └─> Clica "Iniciar"
            │
            ├─> [PyQt6] → [Arduino Controller] → [Serial USB] → [Arduino]
            │                                                        │
            │                                                        └─> Relé ON
            │
            └─> [PyQt6] → [WebSocket] → [Lower Third]
                                            │
                                            └─> setTimeout(10000) → Exibe
```

## 3. Especificação dos Módulos

### 3.1 Interface Desktop (main.py)

**Tecnologia:** PyQt6

**Responsabilidades:**
- Gerenciar interface gráfica do usuário
- Controlar cronômetro local
- Comunicar com Arduino via Serial
- Enviar eventos para WebSocket
- Gerenciar estado do sistema

**Classes Principais:**

```python
class PainelPresidente(QMainWindow):
    """Janela principal do sistema"""
    
    # Atributos
    - vereadores: List[Dict]
    - selected_vereador: Optional[Dict]
    - total_seconds: int
    - remaining_seconds: int
    - is_running: bool
    - is_paused: bool
    - arduino: ArduinoController
    - websocket_thread: WebSocketThread
    - timer: QTimer
    
    # Métodos Principais
    + init_ui() -> None
    + load_vereadores() -> None
    + select_vereador(item: QListWidgetItem) -> None
    + set_time(seconds: int) -> None
    + start_timer() -> None
    + pause_timer() -> None
    + stop_timer() -> None
    + update_timer() -> None
    + on_time_up() -> None

class WebSocketThread(QThread):
    """Thread para comunicação WebSocket"""
    
    # Sinais
    connection_changed = pyqtSignal(bool)
    
    # Métodos
    + run() -> None
    + emit(event: str, data: Dict) -> None
    + disconnect() -> None
```

**Estados do Timer:**
- `AGUARDANDO`: Timer parado, aguardando início
- `EM_EXECUÇÃO`: Timer rodando
- `PAUSADO`: Timer pausado temporariamente

### 3.2 Servidor Web (server.py)

**Tecnologia:** Flask + Flask-SocketIO

**Responsabilidades:**
- Servir página Lower Third
- Gerenciar conexões WebSocket
- Broadcast de eventos
- Manter estado sincronizado

**Endpoints HTTP:**

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Página Lower Third |
| `/api/vereadores` | GET | Lista de vereadores |
| `/api/state` | GET | Estado atual do sistema |
| `/api/config` | GET | Configurações |

**Eventos WebSocket:**

| Evento | Direção | Payload | Descrição |
|--------|---------|---------|-----------|
| `connect` | Client → Server | - | Cliente conectado |
| `disconnect` | Client → Server | - | Cliente desconectado |
| `timer_start` | Server → Clients | `{total_seconds, remaining_seconds}` | Timer iniciado |
| `timer_pause` | Server → Clients | `{remaining_seconds}` | Timer pausado |
| `timer_stop` | Server → Clients | - | Timer parado |
| `timer_update` | Server → Clients | `{remaining_seconds}` | Atualização de tempo |
| `speaker_selected` | Server → Clients | `{speaker: {id, nome, partido, foto}}` | Vereador selecionado |
| `speaker_cleared` | Server → Clients | - | Vereador removido |
| `audio_toggle` | Server → Clients | `{muted: bool}` | Toggle de áudio |
| `arduino_status` | Server → Clients | `{connected: bool}` | Status Arduino |
| `request_state` | Client → Server | - | Solicitar estado |
| `state_update` | Server → Client | `{timer, speaker, audio_muted, ...}` | Estado completo |

**Estado Global:**

```python
system_state = {
    'timer': {
        'total_seconds': int,
        'remaining_seconds': int,
        'is_running': bool,
        'is_paused': bool
    },
    'speaker': {
        'id': int,
        'nome': str,
        'partido': str,
        'foto': Optional[str]
    } | None,
    'audio_muted': bool,
    'delay_seconds': int,
    'connections': {
        'arduino': bool,
        'clients': int
    }
}
```

### 3.3 Controlador Arduino (arduino_controller.py)

**Tecnologia:** Python + pyserial

**Responsabilidades:**
- Detectar porta COM do Arduino
- Estabelecer comunicação serial
- Enviar comandos de controle
- Reconexão automática
- Callback de status

**API Pública:**

```python
class ArduinoController:
    """Controlador de comunicação com Arduino"""
    
    # Métodos Públicos
    + __init__(baudrate: int = 9600, timeout: float = 1.0)
    + list_available_ports() -> List[Dict]
    + connect(port_name: Optional[str] = None) -> bool
    + disconnect() -> None
    + send_command(command: str) -> bool
    + open_audio() -> bool
    + cut_audio() -> bool
    + check_connection() -> bool
    
    # Atributos
    + is_connected: bool
    + port_name: Optional[str]
    + on_connection_change: Optional[Callable[[bool], None]]
```

**Comandos Serial:**
- `'1'` → Abrir áudio (relé ativo)
- `'0'` → Cortar áudio (relé desativo)

**Lógica de Reconexão:**
1. Detectar desconexão (SerialException)
2. Aguardar 3 segundos
3. Tentar reconectar
4. Repetir até sucesso ou `auto_reconnect = False`

### 3.4 Firmware Arduino (arduino_relay_control.ino)

**Tecnologia:** C++ (Arduino)

**Responsabilidades:**
- Controlar relé
- Receber comandos serial
- Timeout de segurança
- Feedback visual (LED)

**Especificação:**

```cpp
// Configurações
const int RELAY_PIN = 7;
const int LED_PIN = LED_BUILTIN;
const unsigned long TIMEOUT = 5000; // 5 segundos

// Comandos
'1' → digitalWrite(RELAY_PIN, HIGH)  // Abrir áudio
'0' → digitalWrite(RELAY_PIN, LOW)   // Cortar áudio

// Lógica de Segurança
if (millis() - lastCommandTime > TIMEOUT && audioOpen) {
    cutAudio();  // Cortar por segurança
}
```

**Estados:**
- `audioOpen = false` → Relé LOW → Áudio cortado (padrão)
- `audioOpen = true` → Relé HIGH → Áudio ativo

**Feedback Visual:**
- Inicialização: 3 piscadas rápidas
- Abrir áudio: 1 piscada
- Cortar áudio: 2 piscadas

### 3.5 Lower Third Web (templates/lower_third.html)

**Tecnologia:** HTML5 + CSS3 + JavaScript + Socket.io

**Responsabilidades:**
- Exibir informações do vereador
- Mostrar cronômetro
- Aplicar delay de 10 segundos
- Animações de entrada/saída
- Sincronizar via WebSocket

**Estrutura:**

```html
<body>
    <!-- Lower Third -->
    <div class="lower-third-container">
        <div class="photo-container">
            <!-- Foto ou inicial -->
        </div>
        <div class="info-container">
            <div class="speaker-name">Nome</div>
            <div class="speaker-party">Partido</div>
        </div>
    </div>
    
    <!-- Timer -->
    <div class="timer-container">
        <div class="timer-display">00:00</div>
        <div class="timer-label">TEMPO RESTANTE</div>
    </div>
</body>
```

**Lógica de Delay:**

```javascript
socket.on('timer_start', (data) => {
    // Aguardar 10 segundos antes de exibir
    setTimeout(() => {
        showLowerThird();
        startLocalTimer();
    }, DELAY_SECONDS * 1000);
});
```

**Animações CSS:**

```css
.lower-third-container {
    transform: translateX(-100%);
    opacity: 0;
    transition: all 0.8s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.lower-third-container.visible {
    transform: translateX(0);
    opacity: 1;
}
```

**Sincronização:**
- Timer local sincronizado com servidor
- Atualização a cada segundo
- Aviso visual quando faltam 30 segundos

## 4. Banco de Dados

### 4.1 Estrutura JSON (vereadores.json)

```json
[
    {
        "id": 1,
        "nome": "Nome Completo",
        "partido": "SIGLA",
        "foto": "caminho/para/foto.jpg" | null
    }
]
```

**Campos:**
- `id` (int): Identificador único
- `nome` (string): Nome completo do vereador
- `partido` (string): Sigla do partido
- `foto` (string|null): Caminho para foto ou null

### 4.2 Operações

- **Leitura:** Ao iniciar aplicação
- **Busca:** Filtro por nome ou partido
- **Seleção:** Por clique na lista

## 5. Hardware

### 5.1 Especificação do Relé

**Tipo:** Módulo Relé 5V de 1 Canal

**Características:**
- Tensão de controle: 5V DC
- Corrente de controle: ~70mA
- Contatos: NO (Normalmente Aberto), COM (Comum), NC (Normalmente Fechado)
- Capacidade: 10A @ 250V AC / 10A @ 30V DC

**Conexão:**
```
Arduino D7 → IN (Sinal de controle)
Arduino 5V → VCC (Alimentação)
Arduino GND → GND (Terra)

Microfone Sinal+ → COM (Comum)
Mesa de Som ← → NO (Normalmente Aberto)
```

**Lógica:**
- Sinal LOW (0V) → Relé desligado → Circuito aberto → Áudio cortado
- Sinal HIGH (5V) → Relé ligado → Circuito fechado → Áudio ativo

### 5.2 Esquema de Corte de Áudio

```
[Microfone] ──┬── Sinal+ ──┐
              │             │
              └── GND ──────┼─────→ [Mesa de Som]
                            │
                       ┌────┴────┐
                       │  Relé   │
                       │ NO  COM │
                       └─────────┘
                            │
                       [Arduino D7]
```

## 6. Segurança

### 6.1 Áudio Cortado por Padrão

**Princípio:** Fail-safe

- Ao ligar sistema: áudio cortado
- Ao desconectar Arduino: áudio cortado
- Ao fechar aplicação: áudio cortado
- Timeout sem comando: áudio cortado

### 6.2 Timeout de Segurança

- Arduino: 5 segundos sem comando → cortar áudio
- Reconexão automática em caso de falha

### 6.3 Validações

- Verificar conexão Arduino antes de iniciar
- Confirmar se vereador está selecionado
- Validar tempo antes de iniciar

## 7. Performance

### 7.1 Requisitos

- **Latência WebSocket:** < 100ms
- **Atualização Timer:** 1 segundo (preciso)
- **Delay Lower Third:** 10 segundos (configurável)
- **Resposta Arduino:** < 50ms

### 7.2 Otimizações

- Timer local no cliente (evita latência de rede)
- Broadcast apenas de mudanças de estado
- Reconexão em background (não bloqueia UI)

## 8. Testes

### 8.1 Testes Unitários

```python
# Testar Arduino Controller
python arduino_controller.py

# Testar Servidor
python server.py
```

### 8.2 Testes de Integração

1. **Teste de Fluxo Completo:**
   - Selecionar vereador
   - Definir tempo
   - Iniciar timer
   - Verificar áudio aberto
   - Verificar Lower Third (após 10s)
   - Pausar
   - Verificar áudio cortado
   - Retomar
   - Parar
   - Verificar Lower Third oculto

2. **Teste de Reconexão:**
   - Desconectar Arduino
   - Verificar reconexão automática
   - Verificar áudio cortado durante desconexão

3. **Teste de Sincronização:**
   - Abrir múltiplos clientes Lower Third
   - Verificar sincronização perfeita

## 9. Deployment

### 9.1 Instalação

```bash
# 1. Instalar Python 3.11+
# 2. Clonar repositório
# 3. Executar install.bat
# 4. Carregar firmware no Arduino
# 5. Executar run.bat
```

### 9.2 Configuração OBS

```
Fonte: Browser
URL: http://127.0.0.1:5000/
Largura: 1920
Altura: 1080
FPS: 30
CSS: body { background-color: rgba(0, 0, 0, 0); }
```

## 10. Manutenção

### 10.1 Logs

- Servidor: Console output
- Arduino: Serial Monitor (9600 baud)
- Lower Third: Browser Console (F12)

### 10.2 Backup

- `vereadores.json` → Backup regular
- Fotos dos vereadores → Backup em nuvem

### 10.3 Atualizações

1. Atualizar código
2. Executar `pip install -r requirements.txt`
3. Reiniciar sistema

---

**Versão:** 1.0.0  
**Data:** 2024-12-19  
**Autor:** Sistema de Controle de Tribuna Parlamentar
