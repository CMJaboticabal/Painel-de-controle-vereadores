# Configurações do Sistema de Controle de Tribuna

# Servidor Flask-SocketIO
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
SERVER_DEBUG = False

# Arduino
ARDUINO_BAUDRATE = 9600
ARDUINO_TIMEOUT = 1.0
ARDUINO_AUTO_RECONNECT = True
ARDUINO_RECONNECT_DELAY = 3  # segundos

# Lower Third
LOWER_THIRD_DELAY = 10  # segundos
LOWER_THIRD_WARNING_THRESHOLD = 30  # segundos

# Timer
TIMER_UPDATE_INTERVAL = 1000  # milissegundos

# Banco de Dados
VEREADORES_JSON_PATH = 'vereadores.json'

# Interface
WINDOW_MIN_WIDTH = 1400
WINDOW_MIN_HEIGHT = 800

# Segurança
AUDIO_DEFAULT_STATE = False  # False = cortado (seguro)
ARDUINO_TIMEOUT_SAFETY = 5000  # milissegundos

# Versão do Sistema
VERSION = "1.7.3"
GITHUB_REPO = "almeidasinop/Painel-de-controle-vereadores"
