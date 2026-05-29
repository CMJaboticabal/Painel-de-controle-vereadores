"""
Sistema de Controle de Tribuna Parlamentar
Servidor Flask-SocketIO para comunicação com Lower Third Web
"""

from flask import Flask, render_template, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
import os
from datetime import datetime
import sys

# Adicionar diretório atual ao path para importar módulos locais
sys.path.append(os.path.dirname(__file__))
import logger_setup
logger_setup.setup_logger("server")

from session_config import SessionConfig

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tribuna-parlamentar-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Estado global do sistema
system_state = {
    'timer': {
        'total_seconds': 0,
        'remaining_seconds': 0,
        'is_running': False,
        'is_paused': False
    },
    'speaker': None,
    'audio_muted': True,
    'delay_seconds': 10,
    'connections': {
        'arduino': False,
        'clients': 0
    }
}

# ===================================
# Rotas HTTP
# ===================================

@app.route('/api/session/logo')
def get_session_logo():
    """Servir a logo configurada na sessão"""
    try:
        config = SessionConfig()
        logo_path = config.get_logo()
        
        if logo_path:
            # Se for caminho relativo, converter para absoluto nos dados do usuário
            if not os.path.isabs(logo_path):
                abs_path = config.get_data_path(logo_path)
                if os.path.exists(abs_path):
                    return send_file(abs_path)
                # Tentar bundle se não estiver em dados
                abs_path = config.get_bundle_path(logo_path)
                if os.path.exists(abs_path):
                    return send_file(abs_path)
            elif os.path.exists(logo_path):
                return send_file(logo_path)
                
            return "Logo não encontrada", 404
        else:
            return "Logo não definida", 404
    except Exception as e:
        return str(e), 500

@app.route('/api/session/info')
def get_session_info():
    """Obter informações da sessão"""
    config = SessionConfig()
    return jsonify({
        'session_name': config.get_session_name(),
        'session_number': config.get_session_name(), # Fallback de compatibilidade
        'website_url': config.get_website_url()
    })

@app.route('/api/session/colors')
def get_session_colors():
    """Obter cores do tema"""
    config = SessionConfig()
    return jsonify(config.get_colors())

def load_vereadores():
    """Carrega lista de vereadores do JSON (usa AppData)"""
    config = SessionConfig()
    active_list = config.get_active_list()
    json_path = config.get_data_path(active_list)
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        # Tentar bundle como fallback
        json_path = config.get_bundle_path(active_list)
        if os.path.exists(json_path):
             with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception:
        return []

@app.route('/')
def index():
    """Página principal - Lower Third"""
    return render_template('lower_third.html')

@app.route('/api/vereadores')
def get_vereadores():
    """API para obter lista de vereadores"""
    return jsonify(load_vereadores())

@app.route('/api/state')
def get_state():
    """API para obter estado atual do sistema"""
    return jsonify(system_state)

@app.route('/api/config')
def get_config():
    """API para obter configurações"""
    return jsonify({
        'delay_seconds': system_state['delay_seconds']
    })

from flask import request

# ===================================
# Rotas de Controle HTTP (API para o Desktop)
# ===================================

@app.route('/api/action/timer', methods=['POST'])
def action_timer():
    """Receber comando do timer via HTTP"""
    data = request.json
    action = data.get('action') # start, pause, stop, update
    
    if action == 'start':
        server_update_timer(True, False, data.get('remaining'), data.get('total'))
    elif action == 'pause':
        server_update_timer(False, True, data.get('remaining'))
    elif action == 'stop':
        server_update_timer(False, False, data.get('total'), data.get('total'))
    elif action == 'update':
        server_update_timer(True, False, data.get('remaining'))
        
    return jsonify({'status': 'ok'})

@app.route('/api/action/speaker', methods=['POST'])
def action_speaker():
    """Receber orador via HTTP"""
    data = request.json
    speaker = data.get('speaker')
    server_update_speaker(speaker)
    return jsonify({'status': 'ok'})

@app.route('/api/action/audio', methods=['POST'])
def action_audio():
    """Controle de áudio via HTTP"""
    data = request.json
    server_update_audio(data.get('muted'))
    return jsonify({'status': 'ok'})

@app.route('/api/action/arduino', methods=['POST'])
def action_arduino():
    """Status arduino via HTTP"""
    data = request.json
    server_update_arduino(data.get('connected'))
    return jsonify({'status': 'ok'})

@app.route('/api/action/config_update', methods=['POST'])
def action_config_update():
    """Notificar atualização de configuração"""
    socketio.emit('config_updated')
    return jsonify({'status': 'ok'})

# ===================================
# Funções Internas de Atualização
# ===================================

def server_update_timer(is_running, is_paused, remaining, total=None):
    """Atualiza estado do timer e emite evento"""
    system_state['timer']['is_running'] = is_running
    system_state['timer']['is_paused'] = is_paused
    system_state['timer']['remaining_seconds'] = remaining
    if total is not None:
        system_state['timer']['total_seconds'] = total
    
    event = 'timer_update'
    if is_running: event = 'timer_start'
    elif is_paused: event = 'timer_pause'
    elif not is_running and not is_paused and remaining == system_state['timer']['total_seconds']: event = 'timer_stop'
    
    socketio.emit(event, system_state['timer'])
    # socketio.emit('state_update', system_state) # Opcional, mas carrega network

def server_update_speaker(speaker_data):
    """Atualiza orador e emite evento"""
    system_state['speaker'] = speaker_data
    if speaker_data:
        socketio.emit('speaker_selected', {'speaker': speaker_data, 'nome': speaker_data.get('nome')})
    else:
        socketio.emit('speaker_selected', {'speaker': None}) # Front espera speaker: null
        # Ou speaker_cleared
        socketio.emit('speaker_cleared')

def server_update_audio(muted):
    """Atualiza áudio e emite evento"""
    system_state['audio_muted'] = muted
    socketio.emit('audio_toggle', {'muted': muted})

def server_update_arduino(connected):
    """Atualiza status arduino"""
    system_state['connections']['arduino'] = connected
    socketio.emit('arduino_status', {'connected': connected})

# ===================================
# WebSocket Events (Client-Side)
# ===================================

@socketio.on('connect')
def handle_connect():
    system_state['connections']['clients'] += 1
    print(f"✅ Cliente conectado. Total: {system_state['connections']['clients']}")
    emit('state_update', system_state)

@socketio.on('disconnect')
def handle_disconnect():
    system_state['connections']['clients'] -= 1
    print(f"❌ Cliente desconectado. Total: {system_state['connections']['clients']}")

# Mantemos os handlers antigos para compatibilidade caso algum cliente tente enviar
@socketio.on('timer_start')
def handle_timer_start(data):
    server_update_timer(True, False, data.get('remaining_seconds'), data.get('total_seconds'))

@socketio.on('timer_stop')
def handle_timer_stop():
    server_update_timer(False, False, system_state['timer']['total_seconds'])

def run_server(host='0.0.0.0', port=5000, debug=False):
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🏛️  Sistema de Controle de Tribuna Parlamentar             ║
║                                                              ║
║  Servidor Flask-SocketIO iniciado                           ║
║  URL: http://{host}:{port}                            ║
║  Lower Third: http://{host}:{port}/                   ║
║                                                              ║
║  Pressione Ctrl+C para encerrar                             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    run_server(debug=True)
