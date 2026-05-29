"""
Sistema de Controle de Tribuna Parlamentar
Interface Desktop Principal - Painel do Presidente
Desenvolvido com PyQt6
"""

import sys
import json
import os
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit,
    QSpinBox, QGroupBox, QGridLayout, QMessageBox, QComboBox,
    QFrame, QSizePolicy, QStackedWidget, QMenu, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap, QTransform
import socket
import urllib.request
import urllib.error
import threading
import server
import multiprocessing
import logger_setup
import ctypes
from arduino_controller import ArduinoController
from admin_vereadores import VereadoresAdminDialog
from tela_plenario import TelaPlenario
from tela_plenario_lateral import TelaPlenarioLateral
from session_config import SessionConfig


# Mutex para detecção pelo instalador
MUTEX_NAME = "PainelControleTribunaMutex"

# Tolerância de aparte: tempo usado no aparte que NÃO é descontado do orador original
APARTE_TOLERANCE_SECONDS = 60  # 1 minuto
_mutex_handle = None

def create_app_mutex():
    global _mutex_handle
    try:
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        # Se GetLastError retornar 183 (ERROR_ALREADY_EXISTS), o mutex já existe
        if kernel32.GetLastError() == 183:
            return False
        return True
    except Exception:
        return True # Fallback se falhar por algum motivo

# Inicializar LOG
# Deve ser chamado antes de qlqr outra coisa
logger_setup.setup_logger("painel")

def api_post(endpoint, data):
    """Envia comando HTTP POST para o servidor Flask em background"""
    def run():
        try:
            url = f"http://127.0.0.1:5000/api/action/{endpoint}"
            req = urllib.request.Request(url)
            req.add_header('Content-Type', 'application/json')
            jsondata = json.dumps(data).encode('utf-8')
            req.add_header('Content-Length', len(jsondata))
            with urllib.request.urlopen(req, jsondata, timeout=1) as response:
                pass # Sucesso
        except Exception as e:
            # Silencioso em caso de erro de conexão (server offline)
            # print(f"Erro API ({endpoint}): {e}")
            pass
    
    threading.Thread(target=run, daemon=True).start()



class ArduinoConnectionThread(QThread):
    """Thread para conectar ao Arduino sem travar a GUI"""
    finished = Signal(bool)
    
    def __init__(self, arduino_controller, preferred_port=None):
        super().__init__()
        self.arduino = arduino_controller
        self.preferred_port = preferred_port
        
    def run(self):
        connected = False
        # Tentar porta preferida primeiro
        if self.preferred_port:
             print(f"DEBUG: Tentando conectar Arduino na porta salva: {self.preferred_port}")
             connected = self.arduino.connect(self.preferred_port)
        
        # Se falhou ou não tinha preferida, auto-discovery
        if not connected:
            if self.preferred_port:
                print("DEBUG: Conexão na porta salva falhou. Tentando auto-conexão...")
            connected = self.arduino.connect()
            
        self.finished.emit(connected)

class PainelPresidente(QMainWindow):
    """Janela principal do Painel do Presidente"""
    
    def __init__(self):
        super().__init__()
        
        # Estado do sistema
        self.vereadores = []
        self.selected_vereador = None
        self.total_seconds = 0
        self.remaining_seconds = 0
        self.staged_seconds = 0 # Tempo preparado para o próximo ato (aparte)
        self.saved_main_seconds = 0 # Tempo salvo de quem sofreu aparte
        self.aparte_initial_seconds = 0 # Tempo inicial do aparte (para calculo de uso)
        self.is_running = False
        self.is_paused = False
        
        # Estado Aparte
        self.is_active_aparte = False
        self.is_parte_mode = False # CORREÇÃO: Atributo faltante causava crash!
        self.is_preparing_aparte = False # Aguardando seleção de tempo
        self.live_vereador = None  # Quem está realmente falando (na tela)
        self.main_speaker = None   # Orador principal (se houver aparte)
        self.aparte_speaker = None # Quem pediu aparte
        
        # UI Elements
        self.preset_buttons = [] # Lista de (btn, seconds)
        
        # Controladores
        self.arduino = ArduinoController()
        self.arduino.on_connection_change = self.on_arduino_connection_change
        
        self.websocket_thread = None
        
        # Tela do Plenário (Monitor 2)
        self.tela_plenario = None
        self.tela_plenario_lateral = None  # Layout alternativo: foto à lateral
        
        # Dialog de administração
        self.admin_dialog = None
        
        # Timer Qt
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        
        # Configuração da Sessão
        self.session_config = SessionConfig()
        
        # Configurar UI primeiro
        self.init_ui()
        
        # Timer de verificação de conexão e Keep-Alive
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connections)
        self.connection_timer.start(2000) # Checar a cada 2 segundos (previne timeout de 5s do Arduino)
        

    
    # Agendar inicialização pesada para depois que a janela aparecer
        print("DEBUG: Agendando inicialização...")
        QTimer.singleShot(100, self.delayed_init)
    
    def delayed_init(self):
        """Inicialização atrasada para evitar travamento da UI"""
        print("DEBUG: Executando delayed_init...")
        
        # Carregar dados
        self.load_vereadores()
        
        # Iniciar conexão com Arduino em Thread separada
        print("DEBUG: Iniciando thread de conexão Arduino...")
        
        # Recuperar última porta usada
        last_port = self.session_config.get_arduino_port()
        
        self.arduino_worker = ArduinoConnectionThread(self.arduino, preferred_port=last_port)
        self.arduino_worker.finished.connect(self.on_arduino_connection_finished)
        self.arduino_worker.start()
        
        # Iniciar servidor WebSocket (apenas atualização de status visual)
        self.start_websocket()

        # Abrir Tela do Plenário automaticamente (agora, em paralelo)
        print("DEBUG: Abrindo tela do plenário...")
        self._open_secondary_configured_with_layout_fallback()
        print("DEBUG: Inicialização completa!")

    def on_arduino_connection_finished(self, connected):
        """Chamado quando a thread de conexão do Arduino termina"""
        print(f"DEBUG: Conexão Arduino finalizada. Conectado: {connected}")
        self.update_arduino_status(connected)
        
        if connected:
            # Forçar corte de áudio inicial (Inicia sistema -> silêncio)
            # Necessário para lógica NF onde repouso = com som
            self.arduino.cut_audio()




    
    def init_ui(self):
        """Inicializar interface do usuário"""
        self.setWindowTitle("Painel do Presidente - Controle de Tribuna")
        self.setMinimumSize(1400, 800)
        
        # Icone da Janela
        icon_path = self.session_config.get_data_path(os.path.join("fotos", "logo.png"))
        if os.path.exists(icon_path):
             self.setWindowIcon(QIcon(icon_path))
        else:
            # Tentar bundle se não estiver em dados (primeira execução)
            bundle_icon = self.session_config.get_bundle_path(os.path.join("fotos", "logo.png"))
            if os.path.exists(bundle_icon):
                self.setWindowIcon(QIcon(bundle_icon))
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Coluna esquerda - Cronômetro e Controles
        left_column = self.create_timer_section()
        main_layout.addWidget(left_column, 2)
        
        # Coluna direita - Vereadores
        right_column = self.create_vereadores_section()
        main_layout.addWidget(right_column, 3)
        
        # Aplicar estilo
        self.apply_styles()
        
        # Abrir em fullscreen
        self.showFullScreen()

    def resizeEvent(self, event):
        """Ajustar altura dos cards de vereadores no redimensionamento"""
        super().resizeEvent(event)
        # O QGridLayout de 5 colunas se ajusta automaticamente.
        # Aqui apenas atualizamos a altura dos cards para preencher 3 linhas.
        QTimer.singleShot(50, self._update_card_sizes)

    def _update_card_sizes(self):
        """Calcula e aplica altura = scroll_area_height / 3 em todos os cards"""
        if not hasattr(self, 'vereadores_scroll_area') or not hasattr(self, 'vereador_card_widgets'):
            return
        spacing = self.vereadores_grid.spacing()
        available_h = self.vereadores_scroll_area.viewport().height()
        # 4 linhas e 3 espaçamentos internos entre elas
        card_h = max(80, (available_h - spacing * 3) // 4)
        for card, foto_label, pixmap_orig in self.vereador_card_widgets:
            card.setFixedHeight(card_h)
            # Recalcular largura real do card
            available_w = self.vereadores_scroll_area.viewport().width()
            spacing_h = self.vereadores_grid.spacing()
            card_w = max(80, (available_w - spacing_h * 4) // 5)
            # Foto com crop para preencher exatamente a área disponível
            foto_h = max(60, card_h - 55)  # reservar 55px para nome/partido
            foto_w = card_w - 16  # margens do card_layout
            if pixmap_orig and not pixmap_orig.isNull():
                # Expandir e recortar centralizado
                scaled = pixmap_orig.scaled(
                    foto_w, foto_h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = (scaled.width() - foto_w) // 2
                # O recorte (crop) começa no topo da imagem (y=0) para não cortar a cabeça do orador
                y = 0
                cropped = scaled.copy(x, y, foto_w, foto_h)
                foto_label.setPixmap(cropped)
                foto_label.setFixedSize(foto_w, foto_h)
            else:
                foto_label.setFixedSize(foto_w, foto_h)

    
    def create_timer_section(self):
        """Criar seção do cronômetro"""
        group = QGroupBox("Cronômetro")
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Ocupar todo espaço
        layout = QVBoxLayout()
        layout.setSpacing(20) # Mais espaçamento
        
        # Display do timer
        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet("""
            QLabel {
                font-size: 60px;
                font-weight: bold;
                color: #4facfe;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(102, 126, 234, 0.1),
                    stop:1 rgba(118, 75, 162, 0.1));
                border-radius: 15px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.timer_label, 2) # Peso 2 para crescer
        
        # Status
        self.status_label = QLabel("⏸️ Aguardando")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Controles Principais
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # INICIAR
        self.play_btn = QPushButton("▶️ INICIAR")
        self.play_btn.clicked.connect(self.start_timer)
        self.play_btn.setMinimumHeight(90) 
        self.play_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #11998e, stop:1 #38ef7d);
                color: white;
                font-size: 28px; 
                font-weight: 900;
                border: none;
                border-radius: 10px;
                text-transform: uppercase;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f877d, stop:1 #32d670);
                margin-top: 1px;
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.1);
                color: #555;
            }
        """)
        controls_layout.addWidget(self.play_btn)
        
        # AJUSTE DE TEMPO (Adicionar/Remover)
        adjust_time_layout = QHBoxLayout()
        adjust_time_layout.setSpacing(10)
        
        # Botão (-)
        self.btn_sub_time = QPushButton("-")
        self.btn_sub_time.setMinimumHeight(80) 
        self.btn_sub_time.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.btn_sub_time.clicked.connect(self.sub_time)
        self.btn_sub_time.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sub_time.setStyleSheet("""
            QPushButton {
                background: #c0392b;
                color: white;
                font-size: 36px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover { background: #e74c3c; }
        """)
        adjust_time_layout.addWidget(self.btn_sub_time)

        # Botão (+)
        self.btn_add_time = QPushButton("+")
        self.btn_add_time.setMinimumHeight(80) 
        self.btn_add_time.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.btn_add_time.clicked.connect(self.add_time)
        self.btn_add_time.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_time.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                font-size: 36px;
                font-weight: bold;
                border-radius: 10px;
            }
            QPushButton:hover { background: #2ecc71; }
        """)
        adjust_time_layout.addWidget(self.btn_add_time)
        
        controls_layout.addLayout(adjust_time_layout)
        
        # Botões Pausar e Parar lado a lado
        sub_controls = QHBoxLayout()
        sub_controls.setSpacing(10)
        
        # PAUSAR
        self.pause_btn = QPushButton("⏸️ PAUSAR")
        self.pause_btn.clicked.connect(self.pause_timer)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setMinimumHeight(80) 
        self.pause_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f2994a, stop:1 #f2c94c);
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e08e43, stop:1 #e0ba45);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.1);
                color: #555;
            }
        """)
        sub_controls.addWidget(self.pause_btn)
        
        # PARAR
        self.stop_btn = QPushButton("⏹️ PARAR")
        self.stop_btn.clicked.connect(self.stop_timer)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(80) 
        self.stop_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #cb2d3e, stop:1 #ef473a);
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b52837, stop:1 #d64034);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.1);
                color: #555;
            }
        """)
        sub_controls.addWidget(self.stop_btn)
        
        controls_layout.addLayout(sub_controls)
        
        # Botão de Aparte
        self.btn_aparte = QPushButton("🗣️ CONCEDER APARTE")
        self.btn_aparte.clicked.connect(self.conceder_aparte)
        self.btn_aparte.setMinimumHeight(80) 
        self.btn_aparte.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.btn_aparte.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e67e22, stop:1 #f39c12);
                color: white;
                font-weight: bold;
                font-size: 24px;
                border-radius: 8px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #d35400, stop:1 #e67e22);
            }
            QPushButton:pressed {
                 background: #c0392b;
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: #666;
            }
        """)
        self.btn_aparte.setCheckable(False)
        self.btn_aparte.setEnabled(False)
        controls_layout.addWidget(self.btn_aparte)
        
        layout.addLayout(controls_layout)
        
        layout.addSpacing(20)
        
        # Tempos pré-definidos (Grid menor)
        self.presets_group = QGroupBox("Definir Tempo")
        self.presets_layout = QGridLayout()
        self.presets_layout.setSpacing(10)
        
        self.rebuild_preset_buttons()
            
        self.presets_group.setLayout(self.presets_layout)
        layout.addWidget(self.presets_group)
        
        # Botão Admin no final
        layout.addStretch()
        self.btn_admin = QPushButton("⚙️ ADMINISTRAR VEREADORES")
        self.btn_admin.clicked.connect(self.open_admin)
        self.btn_admin.setMinimumHeight(45)
        self.btn_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_admin.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)
        layout.addWidget(self.btn_admin)

        layout.addStretch()
        
        layout.addStretch()
        group.setLayout(layout)
        return group


    def create_status_section(self):
        """Criar indicadores de status de conexão"""
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(10)
        
        # Arduino Status
        self.arduino_status_label = QLabel("❌ Arduino: Desconectado")
        self.arduino_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arduino_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                background-color: rgba(250, 112, 154, 0.4);
                border: 1px solid #fa709a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.arduino_status_label)
        
        # Server Status
        self.server_status_label = QLabel("❌ Servidor: Desconectado")
        self.server_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.server_status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                background-color: rgba(250, 112, 154, 0.4);
                border: 1px solid #fa709a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.server_status_label)
        
        container.setLayout(layout)
        return container

    
        group.setLayout(layout)
        return group

    def _make_circular_pixmap(self, pixmap, size):
        """Retorna um QPixmap recortado em círculo de 'size' x 'size'."""
        from PySide6.QtGui import QPainter, QPainterPath
        result = QPixmap(size, size)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        scaled = pixmap.scaled(size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        ox = (scaled.width()  - size) // 2
        oy = (scaled.height() - size) // 2
        painter.drawPixmap(0, 0, scaled, ox, oy, size, size)
        painter.end()
        return result

    def create_speaker_section_content(self, parent_layout):
        """Painel 'Orador em Tribuna' — design premium e compacto"""
        self.speaker_stack = QStackedWidget()

        # ── PÁGINA 0: MODO NORMAL ──────────────────────────────────
        page_normal = QWidget()
        page_normal.setStyleSheet("background: transparent;")
        lay_n = QHBoxLayout(page_normal)
        lay_n.setContentsMargins(16, 8, 16, 8)
        lay_n.setSpacing(18)

        self.normal_photo = QLabel("\U0001f464")
        self.normal_photo.setFixedSize(100, 100)
        self.normal_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.normal_photo.setStyleSheet("""
            QLabel {
                border: 3px solid rgba(102,126,234,0.7);
                border-radius: 50px;
                background: rgba(102,126,234,0.12);
                font-size: 42px;
                color: rgba(102,126,234,0.6);
            }
        """)

        info_w = QWidget()
        info_w.setStyleSheet("background: transparent;")
        info_l = QVBoxLayout(info_w)
        info_l.setContentsMargins(0, 0, 0, 0)
        info_l.setSpacing(2)

        lbl_tag = QLabel("\U0001f3a4  EM TRIBUNA")
        lbl_tag.setStyleSheet("font-size: 9px; font-weight: bold; color: rgba(102,200,255,0.75); letter-spacing: 2px; border: none; background: transparent;")

        self.normal_label = QLabel("Selecione um Vereador")
        self.normal_label.setWordWrap(True)
        self.normal_label.setStyleSheet("font-size: 19px; font-weight: bold; color: #fff; border: none; background: transparent;")

        self.normal_partido_label = QLabel("")
        self.normal_partido_label.setStyleSheet("font-size: 12px; color: rgba(180,190,255,0.7); border: none; background: transparent;")

        info_l.addStretch()
        info_l.addWidget(lbl_tag)
        info_l.addWidget(self.normal_label)
        info_l.addWidget(self.normal_partido_label)
        info_l.addStretch()

        lay_n.addWidget(self.normal_photo)
        lay_n.addWidget(info_w, 1)
        self.speaker_stack.addWidget(page_normal)

        # ── PÁGINA 1: MODO APARTE ──────────────────────────────────
        page_aparte = QWidget()
        page_aparte.setStyleSheet("background: transparent;")
        lay_a = QHBoxLayout(page_aparte)
        lay_a.setContentsMargins(16, 6, 16, 6)
        lay_a.setSpacing(12)

        def _person_block(accent_color, bg_color):
            """Bloco horizontal [foto circular | role + nome + partido]"""
            container = QWidget()
            # Fundo sutil apenas no container, não propaga
            container.setStyleSheet(
                f"QWidget#{container.objectName()} {{ background: {bg_color}; border-radius: 10px; }}"
            )
            container.setStyleSheet(f"background: {bg_color}; border-radius: 10px;")
            hl = QHBoxLayout(container)
            hl.setContentsMargins(10, 8, 10, 8)
            hl.setSpacing(12)

            photo_lbl = QLabel("\U0001f464")
            photo_lbl.setFixedSize(80, 80)
            photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Sem border-radius no label — o círculo é feito no pixmap mesmo
            photo_lbl.setStyleSheet(
                f"border: 2px solid {accent_color}; border-radius: 40px; "
                "background: rgba(255,255,255,0.05); font-size: 32px; "
                f"color: {accent_color};"
            )

            text_col = QWidget()
            text_col.setStyleSheet("background: transparent;")
            tl = QVBoxLayout(text_col)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)

            role_lbl = QLabel()
            role_lbl.setStyleSheet(
                f"font-size: 9px; font-weight: bold; color: {accent_color}; "
                "letter-spacing: 1px; border: none; background: transparent;"
            )
            nome_lbl = QLabel("---")
            nome_lbl.setWordWrap(True)
            nome_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #fff; border: none; background: transparent;")

            partido_lbl = QLabel("")
            partido_lbl.setStyleSheet("font-size: 11px; color: rgba(180,190,255,0.7); border: none; background: transparent;")

            tl.addStretch()
            tl.addWidget(role_lbl)
            tl.addWidget(nome_lbl)
            tl.addWidget(partido_lbl)
            tl.addStretch()

            hl.addWidget(photo_lbl)
            hl.addWidget(text_col, 1)
            return container, photo_lbl, nome_lbl, partido_lbl, role_lbl

        w_conc, self.aparte_concedente_photo, self._conc_nome, self._conc_partido, self._conc_role = \
            _person_block("#667eea", "rgba(102,126,234,0.10)")
        self._conc_role.setText("CONCEDENTE")

        arrow_lbl = QLabel("\u27a1")
        arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_lbl.setStyleSheet("font-size: 22px; color: rgba(255,255,255,0.4); border: none; background: transparent;")
        arrow_lbl.setFixedWidth(40)

        w_rec, self.aparte_receptor_photo, self._rec_nome, self._rec_partido, self._rec_role = \
            _person_block("#f39c12", "rgba(243,156,18,0.10)")
        self._rec_role.setText("EM TRIBUNA")

        lay_a.addWidget(w_conc, 1)
        lay_a.addWidget(arrow_lbl)
        lay_a.addWidget(w_rec, 1)
        self.speaker_stack.addWidget(page_aparte)

        # ── GroupBox wrapper ────────────────────────────────────────
        current_group = QGroupBox("\U0001f3a4 Orador em Tribuna")
        grp_lay = QVBoxLayout()
        grp_lay.setContentsMargins(4, 2, 4, 4)
        grp_lay.addWidget(self.speaker_stack)
        current_group.setLayout(grp_lay)
        current_group.setMaximumHeight(175)
        current_group.setMinimumHeight(120)
        parent_layout.addWidget(current_group)

    def create_vereadores_section(self):
        """Criar seção de vereadores - grid fixo de 5 colunas"""
        group = QGroupBox("👥 Vereadores")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        # --- Área de scroll que contém o grid ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.05);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(102,126,234,0.6);
                border-radius: 4px;
            }
        """)

        # Widget interno que recebe o grid
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.vereadores_grid = QGridLayout(self.grid_container)
        self.vereadores_grid.setContentsMargins(0, 0, 0, 0)
        self.vereadores_grid.setSpacing(12)
        # Tornar as 5 colunas igualmente esticadas
        for col in range(5):
            self.vereadores_grid.setColumnStretch(col, 1)

        self.vereadores_scroll_area = scroll_area
        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area, 3)  # stretch=3 → grid ocupa 75%, speaker 25%

        # Seção do orador
        self.create_speaker_section_content(layout)

        group.setLayout(layout)
        return group

    
    def apply_styles(self):
        """Aplicar estilos globais"""
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0f23, stop:1 #1a1a2e);
            }
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                border: 2px solid rgba(102, 126, 234, 0.3);
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background: rgba(255, 255, 255, 0.05);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(102, 126, 234, 0.3);
                border-color: #667eea;
            }
            QPushButton:pressed {
                background: rgba(102, 126, 234, 0.5);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: #666;
            }
            QLineEdit, QSpinBox {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #667eea;
            }
            QListWidget {
                background: rgba(255, 255, 255, 0.05);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 0px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background: rgba(102, 126, 234, 0.2);
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
            }
        """)
    
    def load_vereadores(self):
        """Carregar vereadores do JSON"""
        try:
            # Carregar configuração da sessão para saber qual lista usar
            from session_config import SessionConfig
            session_config = SessionConfig()
            active_list = session_config.get_active_list()
            
            json_path = session_config.get_data_path(active_list)
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.vereadores = json.load(f)
            else:
                self.vereadores = []
            
            self.populate_vereadores_list()
        except Exception as e:
            print(f"Erro ao carregar vereadores: {e}")
            self.vereadores = []
            self.populate_vereadores_list()
    
    def populate_vereadores_list(self, filter_text=''):
        """Preencher grid de vereadores (5 colunas fixas)"""
        # Limpar grid anterior
        while self.vereadores_grid.count():
            item = self.vereadores_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.vereador_cards = {}  # mapa nome -> card para highlight de seleção
        self.vereador_card_widgets = []  # lista (card, foto_label, pixmap_orig) para resize
        row, col = 0, 0
        COLS = 5

        for vereador in self.vereadores:
            nome = vereador['nome']
            partido = vereador['partido']

            if filter_text.lower() not in nome.lower() and filter_text.lower() not in partido.lower():
                continue

            # --- Card ---
            card = QFrame()
            card.setObjectName("vereador_card")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet("""
                QFrame#vereador_card {
                    background: rgba(255,255,255,0.08);
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 12px;
                }
                QFrame#vereador_card:hover {
                    background: rgba(102,126,234,0.25);
                    border: 1px solid #667eea;
                }
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 8, 8, 8)
            card_layout.setSpacing(6)
            card_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

            # Foto — o recorte dinâmico será feito em _update_card_sizes
            foto_label = QLabel()
            foto_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            foto_label.setStyleSheet("border: none; background: transparent;")
            foto_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            pixmap_orig = None  # Guardar original para recorte dinâmico
            if vereador.get('foto'):
                foto_path_data   = self.session_config.get_data_path(vereador['foto'])
                foto_path_bundle = self.session_config.get_bundle_path(vereador['foto'])
                foto_path = foto_path_data if os.path.exists(foto_path_data) else foto_path_bundle
                if os.path.exists(foto_path):
                    pixmap_orig = QPixmap(foto_path)
                    if pixmap_orig.isNull():
                        print(f'[AVISO] Foto inacessível: {foto_path}')
                        pixmap_orig = None
                        foto_label.setText('👤')
                        foto_label.setStyleSheet('font-size: 60px; border: none; background: transparent;')
                    else:
                        foto_label.setPixmap(pixmap_orig.scaled(200, 200,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation))
                else:
                    print(f'[AVISO] Foto nao encontrada: {vereador["foto"]}')
                    print(f'  data  : {foto_path_data}')
                    print(f'  bundle: {foto_path_bundle}')
                    foto_label.setText('👤')
                    foto_label.setStyleSheet('font-size: 60px; border: none; background: transparent;')
            else:
                foto_label.setText('👤')
                foto_label.setStyleSheet('font-size: 60px; border: none; background: transparent;')

            card_layout.addWidget(foto_label, 1)  # stretch=1 para crescer

            # Nome
            nome_label = QLabel(nome)
            nome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nome_label.setWordWrap(True)
            nome_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold; border: none; background: transparent;")
            card_layout.addWidget(nome_label)

            # Partido
            partido_label = QLabel(partido)
            partido_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            partido_label.setStyleSheet("color: rgba(200,200,255,0.7); font-size: 12px; border: none; background: transparent;")
            card_layout.addWidget(partido_label)

            # Guardar dados no frame para recuperar no clique
            card.setProperty('vereador_data', vereador)

            # Conectar clique no card
            card.mousePressEvent = lambda e, v=vereador: self._on_card_click(v)

            self.vereadores_grid.addWidget(card, row, col)
            self.vereador_cards[nome] = card
            self.vereador_card_widgets.append((card, foto_label, pixmap_orig))

            col += 1
            if col >= COLS:
                col = 0
                row += 1

        # Preencher espaços vazios na última linha com widgets transparentes
        if col > 0:
            for c in range(col, COLS):
                spacer = QWidget()
                spacer.setStyleSheet("background: transparent;")
                self.vereadores_grid.addWidget(spacer, row, c)

        # Iniciar redimensionamento dinâmico após a construção
        QTimer.singleShot(100, self._update_card_sizes)

    def sync_list_selection(self):
        """Sincronizar seleção visual dos cards com o vereador atual"""
        if not self.selected_vereador:
            return
        nome_alvo = self.selected_vereador.get('nome')
        cards = getattr(self, 'vereador_cards', {})
        for nome, card in cards.items():
            if nome == nome_alvo:
                card.setStyleSheet("""
                    QFrame#vereador_card {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #667eea, stop:1 #764ba2);
                        border: 2px solid #00f2fe;
                        border-radius: 12px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame#vereador_card {
                        background: rgba(255,255,255,0.08);
                        border: 1px solid rgba(255,255,255,0.12);
                        border-radius: 12px;
                    }
                    QFrame#vereador_card:hover {
                        background: rgba(102,126,234,0.25);
                        border: 1px solid #667eea;
                    }
                """)

    def filter_vereadores(self):
        """Filtrar vereadores (barra de busca removida, mantido por compatibilidade)"""
        fi = getattr(self, 'search_input', None)
        self.populate_vereadores_list(fi.text() if fi else '')
    
    def _on_card_click(self, vereador):
        """Chamado quando um card de vereador é clicado"""
        self.selected_vereador = vereador
        self.sync_list_selection()

        if not getattr(self, 'is_parte_mode', False):
            self.update_speaker_panel()

        self.update_aparte_button_state()
        self.update_presets_state()

        api_post('speaker', {'speaker': self.selected_vereador})

        if not self.is_running:
            self.live_vereador = self.selected_vereador
            self.sync_tela_plenario()

    def select_vereador(self, item=None, vereador=None):
        """Selecionar vereador — mantido por compatibilidade"""
        if item is not None:
            vereador = item.data(Qt.ItemDataRole.UserRole)
        elif vereador is None:
            return
        self._on_card_click(vereador)

    def update_speaker_panel(self):
        """Atualiza a UI do orador com base no modo (Normal ou Aparte)"""
        is_aparte = getattr(self, 'is_parte_mode', False)

        if is_aparte and hasattr(self, 'concedente') and hasattr(self, 'receptor'):
            self.speaker_stack.setCurrentIndex(1)

            # Concedente
            self._conc_nome.setText(self.concedente.get('nome', '---'))
            self._conc_partido.setText(self.concedente.get('partido', ''))
            self._load_photo_into(self.concedente.get('foto'), self.aparte_concedente_photo)

            # Receptor
            self._rec_nome.setText(self.receptor.get('nome', '---'))
            self._rec_partido.setText(self.receptor.get('partido', ''))
            self._load_photo_into(self.receptor.get('foto'), self.aparte_receptor_photo)

        else:
            self.speaker_stack.setCurrentIndex(0)

            if self.selected_vereador:
                self.normal_label.setText(self.selected_vereador['nome'])
                self.normal_partido_label.setText(self.selected_vereador.get('partido', ''))
                self._load_photo_into(self.selected_vereador.get('foto'), self.normal_photo)
            else:
                self.normal_label.setText("Selecione um Vereador")
                self.normal_partido_label.setText("")
                self.normal_photo.setText("\U0001f464")

    def _load_photo_into(self, foto_filename, label_widget):
        """Carrega foto no label como circulo recortado via QPainter"""
        if foto_filename:
            foto_path_data   = self.session_config.get_data_path(foto_filename)
            foto_path_bundle = self.session_config.get_bundle_path(foto_filename)
            foto_path = foto_path_data if os.path.exists(foto_path_data) else foto_path_bundle
            if os.path.exists(foto_path):
                pixmap = QPixmap(foto_path)
                if not pixmap.isNull():
                    size = label_widget.width() or label_widget.minimumWidth() or 80
                    circular = self._make_circular_pixmap(pixmap, size)
                    label_widget.setPixmap(circular)
                    return
                else:
                    print(f'[AVISO] Speaker foto invalida: {foto_path}')
            else:
                print(f'[AVISO] Speaker foto nao encontrada: {foto_filename}')
        label_widget.setText('👤')

    def update_aparte_button_state(self):
        """Atualizar estado do botão de aparte com base na lógica de orador"""
        if self.is_parte_mode:
            # MODO ENCERRAR
            self.btn_aparte.setText("🛑 ENCERRAR APARTE")
            self.btn_aparte.setEnabled(True)
            self.btn_aparte.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 24px; min-height: 80px;")
            
            # Bloquear botão PARAR geral durante o aparte
            self.stop_btn.setEnabled(False)
        elif self.is_preparing_aparte:
            # MODO CANCELAR SELEÇÃO
            self.btn_aparte.setText("❌ CANCELAR APARTE")
            self.btn_aparte.setEnabled(True)
            self.btn_aparte.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 24px; min-height: 80px;")
        elif self.is_running and self.selected_vereador and self.live_vereador:
            # Só permite aparte se o selecionado for diferente do que está falando ao vivo
            if self.selected_vereador['nome'] != self.live_vereador['nome']:
                self.btn_aparte.setText("🗣️ CONCEDER APARTE")
                self.btn_aparte.setEnabled(True)
                self.btn_aparte.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; font-size: 24px; min-height: 80px;")
            else:
                self.btn_aparte.setText("🗣️ CONCEDER APARTE")
                self.btn_aparte.setEnabled(False)
                self.btn_aparte.setStyleSheet("background-color: #3e3e3e; color: #888; font-weight: bold; font-size: 24px; min-height: 80px;")
        else:
            self.btn_aparte.setText("🗣️ CONCEDER APARTE")
            self.btn_aparte.setEnabled(False)
            self.btn_aparte.setStyleSheet("background-color: #3e3e3e; color: #888; font-weight: bold; font-size: 24px; min-height: 80px;")
    
    def set_time(self, seconds):
        """Definir tempo (Normal ou Aparte)"""
        if self.is_preparing_aparte:
            # Lógica de Aparte: Iniciar imediatamente com o tempo selecionado
            self.is_preparing_aparte = False
            self.executar_conceder_aparte(seconds)
            self.update_presets_state() # Volta ao normal
            return

        if self.is_running:
            # Se estiver rodando, apenas prepara o tempo para usar depois
            self.staged_seconds = seconds
            self.status_label.setText(f"⏱️ Tempo {seconds//60}min preparado")
        else:
            self.total_seconds = seconds
            self.remaining_seconds = seconds
            self.staged_seconds = seconds # Sincroniza
            self.update_display()

    def update_presets_state(self):
        """Habilitar/Desabilitar botões de tempo com base no contexto"""
        if self.is_preparing_aparte:
            # Modo Preparação de Aparte: Desabilita tempos maiores que o restante do orador
            for btn, seconds in self.preset_buttons:
                if seconds > self.remaining_seconds:
                    btn.setEnabled(False)
                else:
                    btn.setEnabled(True)
        elif self.is_running and not self.is_parte_mode:
             # Se está rodando normal, pode clicar para "preparar" próximo tempo (staged)
             for btn, seconds in self.preset_buttons:
                 btn.setEnabled(True)
        elif self.is_parte_mode:
             # Em aparte não pode mudar o tempo do aparte no meio dele via preset
             for btn, seconds in self.preset_buttons:
                 btn.setEnabled(False)
        else:
            # Repouso: Tudo liberado
            for btn, seconds in self.preset_buttons:
                btn.setEnabled(True)
    
    def set_custom_time(self):
        """Definir tempo customizado"""
        minutes = self.custom_minutes.value()
        self.set_time(minutes * 60)
        
    def add_time(self):
        """Adicionar tempo ao cronômetro"""
        # Usar o tempo preparado (staged) ou padrão 1 min
        seconds_to_use = self.staged_seconds if self.staged_seconds > 0 else 60
        minutes = seconds_to_use // 60
        
        self.remaining_seconds += seconds_to_use
        self.update_display()
        
        # Se não estiver rodando, também atualiza o total para consistência visual
        if not self.is_running:
            self.total_seconds = self.remaining_seconds
        else:
             # Se estiver rodando, aumenta o total para manter a barra de progresso coerente?
             # Normalmente adiciona-se ao tempo extra.
             self.total_seconds += seconds_to_use
            
        self.sync_tela_plenario()
        
        # Feedback visual rápido
        self.status_label.setText(f"+ {minutes} min")
        QTimer.singleShot(2000, lambda: self.status_label.setText("▶️ Em Execução" if self.is_running else "⏸️ Aguardando"))

    def sub_time(self):
        """Remover tempo do cronômetro"""
        # Usar o tempo preparado (staged) ou padrão 1 min
        seconds_to_use = self.staged_seconds if self.staged_seconds > 0 else 60
        minutes = seconds_to_use // 60
        
        self.remaining_seconds -= seconds_to_use
        if self.remaining_seconds < 0:
            self.remaining_seconds = 0
            
        self.update_display()
        
        # Se não estiver rodando, também atualiza o total
        if not self.is_running:
             self.total_seconds = self.remaining_seconds
        
        self.sync_tela_plenario()
        
        # Feedback visual rápido
        self.status_label.setText(f"- {minutes} min")
        QTimer.singleShot(2000, lambda: self.status_label.setText("▶️ Em Execução" if self.is_running else "⏸️ Aguardando"))
    
    def _run_arduino_async(self, func):
        """Executar comando Arduino em thread separada"""
        threading.Thread(target=func, daemon=True).start()
    
    def start_timer(self):
        """Iniciar cronômetro"""
        print("DEBUG: start_timer chamado")
        if self.remaining_seconds == 0:
            self.show_warning("Aviso", "Defina um tempo antes de iniciar!")
            return
        
        if not self.selected_vereador:
            reply = QMessageBox.question(
                self, "Confirmação",
                "Nenhum vereador selecionado. Deseja continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Definir Orador Vivo
        self.live_vereador = self.selected_vereador
        
        self.is_running = True
        self.is_paused = False
        self.timer.start(1000)
        
        # Abrir áudio (Async)
        print("DEBUG: Abrindo áudio...")
        self._run_arduino_async(self.arduino.open_audio)
        
        # Atualizar UI
        self.status_label.setText("▶️ Em Execução")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #00f2fe;
                background: rgba(0, 242, 254, 0.2);
                border-radius: 20px;
                padding: 10px 20px;
                margin: 5px;
            }
        """)
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        # Botão Parar só é habilitado se NÃO estiver em modo aparte
        self.stop_btn.setEnabled(not self.is_parte_mode)
        
        # Atualizar estado do botão de aparte e presets
        self.update_aparte_button_state()
        self.update_presets_state()
        
        # Enviar para Servidor (API)
        api_post('timer', {'action': 'start', 'remaining': self.remaining_seconds, 'total': self.total_seconds})

        # Sincronizar com tela do plenário
        # FORÇAR VISUAL DE ORADOR AGORA (Garante transição imediata)
        for tela in [self.tela_plenario, self.tela_plenario_lateral]:
            if tela:
                tela.show_vereador_info()

        self.sync_tela_plenario()
    
    def show_warning(self, title, message):
        """Mostrar aviso customizado com estilo"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Icon.Warning)
        
        # Estilo customizado
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #1a1a2e; /* Fundo escuro */
            }
            QLabel {
                color: #ffffff;
                font-size: 20px; /* Fonte maior */
                font-weight: bold;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #067b42, stop:1 #ff5e62);
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 120px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff5e62, stop:1 #067b42);
            }
        """)
        msg.exec()

    def conceder_aparte(self):
        """Alternar modo de preparação de aparte (Sinaliza para usar os presets)"""
        # Se já estiver em modo aparte, o botão serve para ENCERRAR
        if self.is_parte_mode:
            self.encerrar_aparte()
            return

        if not self.selected_vereador:
             return

        if not self.live_vereador or self.remaining_seconds <= 0:
             QMessageBox.warning(self, "Aparte não permitido", "O orador principal não possui tempo disponível para conceder aparte.")
             return

        # Toggle no modo de preparação
        self.is_preparing_aparte = not self.is_preparing_aparte
        
        # Atualizar Visual
        self.update_aparte_button_state()
        self.update_presets_state()
        
        if self.is_preparing_aparte:
             # Pequeno aviso sonoro ou visual de instrução poderia ir aqui
             self.status_label.setText("🗣️ SELECIONE O TEMPO DO APARTE")
             self.status_label.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 20px; padding: 10px;")
        else:
             # Cancelou
             self.status_label.setText("▶️ Em Execução")
             self.status_label.setStyleSheet("background-color: rgba(0, 242, 254, 0.2); color: #00f2fe; border-radius: 20px; padding: 10px;")

    def executar_conceder_aparte(self, tempo_segundos):
        """Lógica interna de ativação do modo aparte"""
        if not self.selected_vereador or not self.live_vereador:
            return
            
        # Lógica de Modo Aparte
        # O orador que estava falando (live_vereador) vira o concedente
        # O selecionado (selected_vereador) vira o receptor
        
        self.is_parte_mode = True
        self.concedente = self.live_vereador
        self.receptor = self.selected_vereador
        
        # Salvar tempo do orador principal para restaurar depois
        self.saved_main_seconds = self.remaining_seconds
        self.saved_main_total = self.total_seconds
        
        # Aparte visual
        self.update_speaker_panel()
        
        # Parar temporariamente (reseta is_parte_mode no stop, então restauramos)
        self._stop_timer_internal(reset_ui=False) 
        self.is_parte_mode = True 
        
        print(f"DEBUG: Modo Aparte ativado. Concedente: {self.concedente.get('nome')} -> Receptor: {self.receptor.get('nome')} | Tempo: {tempo_segundos}s")
        self.update_speaker_panel()

        # Configurar tempo de aparte (Já validado pelo menu, mas capar por segurança)
        tempo_aparte = min(tempo_segundos, self.saved_main_seconds)
            
        self.aparte_total_seconds = tempo_aparte # Salvar para cálculo de desconto
        self.set_time(tempo_aparte)
        
        # Atualizar live_vereador para o receptor (já que ele vai falar agora)
        # Mas mantemos a referencia do concedente visualmente
        self.live_vereador = self.receptor
        
        # Sincronizar com tela do plenário e API
        self.sync_tela_plenario()
        api_post('speaker', {'speaker': self.live_vereador})
        
        # Iniciar cronômetro automaticamente para o aparte
        self.start_timer()
        
        # Atualizar botão para "Encerrar"
        self.update_aparte_button_state()

    def encerrar_aparte(self):
        """Encerrar o aparte e devolver a palavra ao concedente"""
        if not self.is_parte_mode or not hasattr(self, 'concedente'):
            return

        print("DEBUG: Encerrando aparte...")
        
        # Parar timer do aparte
        self._stop_timer_internal(reset_ui=False)
        
        # Calcular tempo gasto no aparte
        tempo_gasto = 0
        if hasattr(self, 'aparte_total_seconds'):
            tempo_gasto = self.aparte_total_seconds - self.remaining_seconds
            if tempo_gasto < 0: tempo_gasto = 0
            
        tempo_descontado = max(0, tempo_gasto - APARTE_TOLERANCE_SECONDS)
        print(
            f"DEBUG: Tempo gasto no aparte: {tempo_gasto}s | "
            f"Tolerância: {APARTE_TOLERANCE_SECONDS}s | "
            f"Descontado do orador: {tempo_descontado}s"
        )
        
        # Restaurar orador principal e seleção
        self.live_vereador = self.concedente
        self.selected_vereador = self.concedente
        
        # Restaurar tempo subtraindo apenas o que exceder a tolerância
        self.remaining_seconds = self.saved_main_seconds - tempo_descontado
        if self.remaining_seconds < 0:
            self.remaining_seconds = 0
            
        # Manter o total original do orador (se salvo) ou o saved_seconds
        if hasattr(self, 'saved_main_total'):
            self.total_seconds = self.saved_main_total
        else:
            self.total_seconds = self.saved_main_seconds
        
        # Sair do modo aparte
        self.is_parte_mode = False
        self.concedente = None
        self.receptor = None
        
        # Restaurar visual
        self.update_speaker_panel()
        self.update_display()
        
        # Sincronizar a lista visualmente (tentar achar o item e selecionar)
        self.sync_list_selection()
        
        # Atualizar botão
        self.update_aparte_button_state()
        
        # Sincronizar (volta ao normal)
        self.sync_tela_plenario()
        api_post('speaker', {'speaker': self.live_vereador})

        # Retomar contagem automaticamente (devolver a palavra)
        if self.remaining_seconds > 0:
            self.start_timer()
        

    
    def pause_timer(self):
        """Pausar cronômetro"""
        self.is_running = False
        self.is_paused = True
        self.timer.stop()
        
        # Cortar áudio (Async)
        self._run_arduino_async(self.arduino.cut_audio)
        
        # Atualizar UI
        self.status_label.setText("⏸️ Pausado")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #fee140;
                background: rgba(254, 225, 64, 0.2);
                border-radius: 20px;
                padding: 10px 20px;
                margin: 5px;
            }
        """)
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.update_presets_state()
        
        # Enviar para Servidor (API)
        api_post('timer', {'action': 'pause', 'remaining': self.remaining_seconds})
        
        # Sincronizar com tela do plenário
        self.sync_tela_plenario()
    
    def stop_timer(self):
        """Parar cronômetro (Slot UI / Manual)"""
        self._stop_timer_internal(reset_ui=True)
        
    def _stop_timer_internal(self, reset_ui=True):
        """Lógica interna de parada"""
        self.is_running = False
        self.is_paused = False
        self.timer.stop()
        
        # Cortar áudio (Async)
        self._run_arduino_async(self.arduino.cut_audio)
        
        # Se for apenas uma pausa técnica (transição de aparte), não reseta nada
        if not reset_ui:
            return

        # Resetar modo aparte
        self.is_parte_mode = False
        self.update_speaker_panel()
        
        # Resetar tempo
        self.remaining_seconds = self.total_seconds
        self.update_display()
        
        # Atualizar UI
        self.status_label.setText("⏸️ Aguardando")
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 10px 20px;
                margin: 5px;
            }
        """)
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.btn_aparte.setEnabled(False)
        self.update_presets_state()
        
        # Enviar para Servidor (API)
        api_post('timer', {'action': 'stop', 'total': self.total_seconds})
        
        # Sincronizar com tela do plenário
        self.sync_tela_plenario()

        for tela in [self.tela_plenario, self.tela_plenario_lateral]:
            if tela:
                tela.reset_timer_state()
    
    def update_timer(self):
        """Atualizar cronômetro"""
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_display()
            
            # Enviar para Servidor (API)
            api_post('timer', {'action': 'update', 'remaining': self.remaining_seconds})
            
            # Sincronizar com tela do plenário
            self.sync_tela_plenario()
            
            # Se estiver preparando aparte, atualizar botões (devido ao decréscimo de tempo)
            if self.is_preparing_aparte:
                self.update_presets_state()
            
            # Verificar se chegou a zero
            if self.remaining_seconds == 0:
                self.on_time_up()
    
    def on_time_up(self):
        """Tempo esgotado"""
        if self.is_parte_mode:
            # Se for aparte, encerramos o aparte e voltamos pro principal
            self.encerrar_aparte()
            # Se após encerrar o principal também estiver zerado, mostramos aviso
            if self.remaining_seconds <= 0:
                 self.mostrar_aviso_tempo_esgotado()
            return

        self.stop_timer()
        self.mostrar_aviso_tempo_esgotado()

    def mostrar_aviso_tempo_esgotado(self):
        """Mostrar Aviso 'TEMPO ESGOTADO' no lugar do timer"""
        self.timer_label.setText("TEMPO\nESGOTADO")
        self.timer_label.setStyleSheet("""
            QLabel {
                font-size: 60px;
                font-weight: bold;
                color: #ff4d4d;
                background: rgba(255, 0, 0, 0.15);
                border-radius: 15px;
                padding: 10px;
                border: 2px solid #ff4d4d;
                margin: 10px;
            }
        """)
        
        # Restaurar display normal após 3 segundos
        QTimer.singleShot(3000, self.restore_display_style)
        
    def restore_display_style(self):
        """Restaurar display para mostrar o tempo total selecionado"""
        # Apenas se não estiver rodando (usuário não iniciou outro timer)
        if not self.is_running:
            self.update_display()
    
    def update_display(self):
        """Atualizar display do timer"""
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        
        # Estilização do Timer
        if self.is_parte_mode:
             # Modo Aparte: Amarelo
             self.timer_label.setStyleSheet("""
                QLabel {
                    font-size: 60px;
                    font-weight: bold;
                    color: #fceabb;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(248, 181, 0, 0.2),
                        stop:1 rgba(252, 234, 187, 0.2));
                    border-radius: 15px;
                    padding: 10px;
                    border: 2px solid #f8b500;
                    margin: 10px;
                }
            """)
        elif self.remaining_seconds <= 10 and self.remaining_seconds > 0 and self.is_running:
             # Danger Zone: Vermelho
             self.timer_label.setStyleSheet("""
                QLabel {
                    font-size: 60px;
                    font-weight: bold;
                    color: #e74c3c;
                    background: rgba(231, 76, 60, 0.1);
                    border-radius: 15px;
                    padding: 10px;
                    border: 2px solid #e74c3c;
                    margin: 10px;
                }
            """)
        elif self.remaining_seconds <= 30 and self.remaining_seconds > 0 and self.is_running:
             # Warning Zone: Amarelo/Laranja
             self.timer_label.setStyleSheet("""
                QLabel {
                    font-size: 60px;
                    font-weight: bold;
                    color: #f39c12;
                    background: rgba(243, 156, 18, 0.1);
                    border-radius: 15px;
                    padding: 10px;
                    border: 2px solid #f39c12;
                    margin: 10px;
                }
            """)
        else:
             # Normal: Azul
             self.timer_label.setStyleSheet("""
                QLabel {
                    font-size: 60px;
                    font-weight: bold;
                    color: #4facfe;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(102, 126, 234, 0.1),
                        stop:1 rgba(118, 75, 162, 0.1));
                    border-radius: 15px;
                    padding: 10px;
                    margin: 10px;
                }
            """)
    
    def connect_arduino(self):
        """Conectar ao Arduino"""
        if self.arduino.connect():
            self.arduino_status.setText("✅ Arduino: Conectado")
            self.arduino_status.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(0, 242, 254, 0.4);
                    border: 1px solid #00f2fe;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            
            # Enviar status para Servidor (API)
            api_post('arduino', {'connected': True})
        else:
            self.arduino_status.setText("❌ Arduino: Desconectado")
            self.arduino_status.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(250, 112, 154, 0.4);
                    border: 1px solid #fa709a;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
    
    def check_connections(self):
        """Verificar todas as conexões periodicamente e manter Arduino vivo"""
        # 1. Verificar Arduino (check_connection é rápido)
        arduino_ok = self.arduino.check_connection()
        self.update_arduino_status(arduino_ok)
        
        # Keep Alive (Resetar watchdog do Arduino para não cortar som)
        if arduino_ok:
            self.arduino.keep_alive()
        
        # 2. Verificar Servidor (API Ping)
        self.check_server_status()
        
    def update_arduino_status(self, connected):
        """Atualizar UI do status do Arduino"""
        self.is_arduino_connected = connected
        
        # Se conectou, salvar a porta atual como preferencial
        if connected and self.arduino.port:
             if self.session_config:
                 current_saved = self.session_config.get_arduino_port()
                 if current_saved != self.arduino.port:
                     print(f"DEBUG: Salvando nova porta do Arduino: {self.arduino.port}")
                     self.session_config.set_arduino_port(self.arduino.port)
        
        # Atualizar Admin se estiver aberto
        if self.admin_dialog and self.admin_dialog.isVisible():
            is_server = getattr(self, 'is_server_connected', False)
            self.admin_dialog.update_connection_status(connected, is_server)

    def check_server_status(self):
        """Verificar status do servidor API em background"""
        # Thread worker simples para não travar
        worker = threading.Thread(target=self._verify_server_sync, daemon=True)
        worker.start()

    def _verify_server_sync(self):
        """Ping interno para verificar se o servidor está respondendo, ignorando proxies do Windows"""
        try:
            import urllib.request
            # Criar um opener que ignora completamente as configurações de proxy do sistema
            # Isso evita que o Windows tente rotear requisições de localhost para um proxy
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            url = "http://127.0.0.1:5000/api/state"
            
            with opener.open(url, timeout=1.0) as response:
                if response.status == 200:
                    QTimer.singleShot(0, lambda: self.update_server_status(True))
                else:
                    QTimer.singleShot(0, lambda: self.update_server_status(False))
        except Exception:
            # Em caso de erro (ex: servidor ainda subindo), marca como offline
            QTimer.singleShot(0, lambda: self.update_server_status(False))

    def update_server_status(self, connected):
        """Atualizar UI do status do Servidor no painel principal e no admin"""
        self.is_server_connected = connected
        
        # 1. Atualizar label no painel principal (se existir)
        if hasattr(self, 'server_status_label'):
            if connected:
                self.server_status_label.setText("✅ Servidor: Online")
                self.server_status_label.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #ffffff;
                        background-color: rgba(0, 242, 254, 0.4);
                        border: 1px solid #00f2fe;
                        border-radius: 8px;
                        padding: 8px;
                    }
                """)
            else:
                self.server_status_label.setText("❌ Servidor: Offline")
                self.server_status_label.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #ffffff;
                        background-color: rgba(250, 112, 154, 0.4);
                        border: 1px solid #fa709a;
                        border-radius: 8px;
                        padding: 8px;
                    }
                """)
        
        # 2. Atualizar Admin se estiver aberto
        if self.admin_dialog and self.admin_dialog.isVisible():
            is_arduino = getattr(self, 'is_arduino_connected', False)
            self.admin_dialog.update_connection_status(is_arduino, connected)

    def on_arduino_connection_change(self, connected, port=None):
        """Callback de mudança de conexão Arduino"""
        # Atualizar UI na thread principal
        QTimer.singleShot(0, lambda: self.update_arduino_status(connected))
        # Enviar status para Servidor (API)
        api_post('arduino', {'connected': connected})

    def start_websocket(self):
        """Iniciar verificação do servidor"""
        self.check_connections()
    
    def on_websocket_connection_change(self, connected):
        """Callback de mudança de conexão WebSocket"""
        pass
    

    def open_admin(self):
        """Abrir painel administrativo"""
        try:
            # Sempre criar nova instância para evitar problemas de estado/referência
            if self.admin_dialog:
                self.admin_dialog.close()
            
            # Debug
            print("Tentando abrir painel admin...")
                
            self.admin_dialog = VereadoresAdminDialog(self)
            self.admin_dialog.vereadores_updated.connect(self.on_vereadores_updated)
            self.admin_dialog.session_updated.connect(self.on_session_updated)
            
            # Injetar estado atual das conexões
            is_arduino = getattr(self, 'is_arduino_connected', False)
            is_server = getattr(self, 'is_server_connected', False)
            self.admin_dialog.update_connection_status(is_arduino, is_server)
            
            self.admin_dialog.show()
            self.admin_dialog.raise_()
            self.admin_dialog.activateWindow()
            print("Painel admin aberto com sucesso.")
        except Exception as e:
            import traceback
            error_msg = f"Erro ao abrir Admin:\n{str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            QMessageBox.critical(self, "Erro no Admin", error_msg)
    
    def on_vereadores_updated(self):
        """Callback quando vereadores são atualizados"""
        self.load_vereadores()
        print("✅ Lista de vereadores atualizada")
    
    def on_session_updated(self):
        """Callback quando sessão é atualizada"""
        # Recarregar configuração local
        self.session_config.load_config()
        
        # Atualizar presets de tempo na UI
        self.rebuild_preset_buttons()
        self.update_presets_state() # Garantir estado habilitado/desabilitado correto

        # Gerenciar janelas: alternar plenario/lateral se houver alteração
        target_type = self.session_config.get_secondary_screen_type()
        
        if target_type == 'lateral':
            if self.tela_plenario:
                self.tela_plenario.close()
                self.tela_plenario = None
            if not self.tela_plenario_lateral:
                self.open_tela_plenario_lateral()
        else:
            if self.tela_plenario_lateral:
                self.tela_plenario_lateral.close()
                self.tela_plenario_lateral = None
            if not self.tela_plenario:
                self.open_tela_plenario()

        for tela in [self.tela_plenario, self.tela_plenario_lateral]:
            if tela:
                tela.session_config.load_config()
                if hasattr(tela, 'apply_background_image'):
                    tela.apply_background_image()
                tela.update_header()
                if not tela.timer_started:
                    tela.show_session_info()
                    
        self.sync_tela_plenario()
        print("✅ Configuração da sessão atualizada nas telas do plenário")

        # Avisar clientes web (Lower Third)
        api_post('config_update', {})

    def rebuild_preset_buttons(self):
        """Reconstruir os botões de preset com base na configuração"""
        # Limpar layout anterior se houver
        while self.presets_layout.count():
            item = self.presets_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Carregar presets da configuração
        time_presets_min = self.session_config.get_time_presets()
        
        self.preset_buttons = []
        for i, minutes in enumerate(time_presets_min):
            seconds = minutes * 60
            label = f"{minutes} min"
            
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, s=seconds: self.set_time(s))
            btn.setMinimumHeight(70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    font-size: 22px;
                }
                QPushButton:hover {
                    background: rgba(102, 126, 234, 0.3);
                    border-color: #667eea;
                }
                QPushButton:disabled {
                    background: rgba(255, 255, 255, 0.05);
                    color: #444;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                }
            """)
            self.presets_layout.addWidget(btn, i // 3, i % 3)
            self.preset_buttons.append((btn, seconds))
    
    def open_secondary_screen(self):
        """Abre a tela secundária configurada no admin"""
        self._open_secondary_configured_with_layout_fallback()

    def _position_window_on_secondary_with_fallback(self, window, window_name, retry=0):
        """Posicionar janela no monitor secundário com fallback para macOS."""
        if not window:
            return

        app = QApplication.instance()
        if app is None:
            return

        screens = app.screens()
        if len(screens) < 2:
            print(f"⚠️ {window_name}: apenas um monitor detectado.")
            return

        primary = app.primaryScreen()
        target_screen = None
        for screen in screens:
            if screen != primary:
                target_screen = screen
                break
        if target_screen is None:
            target_screen = screens[1]

        try:
            handle = window.windowHandle()
            if handle:
                handle.setScreen(target_screen)

            # Alguns ambientes no mac ignoram setScreen na primeira tentativa.
            window.setGeometry(target_screen.geometry())
            window.showFullScreen()

            current_screen = window.screen()
            if current_screen == target_screen:
                print(f"✅ {window_name}: fallback de monitor aplicado ({target_screen.name()}).")
                return

            if retry < 4:
                delay_ms = 150 * (retry + 1)
                QTimer.singleShot(
                    delay_ms,
                    lambda w=window, n=window_name, r=retry + 1: self._position_window_on_secondary_with_fallback(w, n, r)
                )
            else:
                print(f"⚠️ {window_name}: não foi possível fixar no monitor secundário após retries.")
        except Exception as e:
            print(f"⚠️ {window_name}: erro ao aplicar fallback de monitor ({e}).")

    def _open_secondary_configured_with_layout_fallback(self):
        """Abrir tela secundária com fallback entre layouts padrão/lateral."""
        preferred_type = self.session_config.get_secondary_screen_type()
        try:
            if preferred_type == 'lateral':
                self.open_tela_plenario_lateral()
            else:
                self.open_tela_plenario()
            return
        except Exception as e:
            print(f"⚠️ Falha ao abrir layout '{preferred_type}': {e}")

        # Fallback de layout: tenta o outro tipo para não ficar sem tela secundária.
        fallback_type = 'padrao' if preferred_type == 'lateral' else 'lateral'
        try:
            if fallback_type == 'lateral':
                self.open_tela_plenario_lateral()
            else:
                self.open_tela_plenario()
            print(f"✅ Fallback de layout aplicado: {fallback_type}")
        except Exception as e:
            print(f"❌ Falha no fallback de layout secundário ({fallback_type}): {e}")

    def open_tela_plenario(self):
        """Abrir tela do plenário (Monitor 2) — layout padrão"""
        if not self.tela_plenario:
            self.tela_plenario = TelaPlenario()
            self.tela_plenario.show()
            self._position_window_on_secondary_with_fallback(self.tela_plenario, "Tela do Plenário (padrão)")
            print("✅ Tela do Plenário aberta (layout padrão)")

    def open_tela_plenario_lateral(self):
        """Abrir tela do plenário (Monitor 2) — layout com foto lateral"""
        if not self.tela_plenario_lateral:
            self.tela_plenario_lateral = TelaPlenarioLateral()
            self.tela_plenario_lateral.show()
            self._position_window_on_secondary_with_fallback(self.tela_plenario_lateral, "Tela do Plenário (lateral)")
            print("✅ Tela do Plenário aberta (layout lateral)")
    
    def sync_tela_plenario(self):
        """Sincronizar dados com ambas as telas do plenário"""
        for tela in [self.tela_plenario, self.tela_plenario_lateral]:
            if tela is None:
                continue
            # Atualizar vereador (Usa o live_vereador que é a verdade atual)
            if self.live_vereador:
                tela.update_vereador(self.live_vereador)
            elif self.selected_vereador and not self.is_running:
                 # Fallback para preview se parado
                 tela.update_vereador(self.selected_vereador)

            # Atualizar timer (Passar total para barra de progresso e flag de aparte)
            tela.update_timer(self.remaining_seconds, self.total_seconds, self.is_parte_mode)

            # Atualizar status
            tela.update_status(self.is_running)
    
    def closeEvent(self, event):
        """Evento de fechamento da janela"""
        # Parar timer
        if self.is_running:
            self.stop_timer()

        # Desconectar Arduino
        self.arduino.disconnect()

        # Fechar telas do plenário
        if self.tela_plenario:
            self.tela_plenario.close()
        if self.tela_plenario_lateral:
            self.tela_plenario_lateral.close()

        # Servidor roda em thread daemon, será encerrado automaticamente
        event.accept()


def main():
    """Função principal"""
    
    logger_setup.setup_logger("painel")

    # Iniciar servidor Flask-SocketIO em THREAD (Processo Único)
    # Isso unifica logs e simplifica o gerenciamento
    import threading
    print("🚀 Iniciando servidor Flask-SocketIO (Integrado) - Acessível na Rede...")
    # host='0.0.0.0' libera o acesso para outros computadores na mesma rede WiFi/Cabo
    server_thread = threading.Thread(target=server.run_server, kwargs={'host': '0.0.0.0', 'debug': False}, daemon=True)
    server_thread.start()
    
    # Aguardar um pouco para garantir que servidor subiu
    import time
    time.sleep(1)

    # Tentar criar mutex
    if not create_app_mutex():
        print("ALERTA: O sistema já está em execução.")
    
    app = QApplication(sys.argv)
    
    # Configurar fonte padrão
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Criar e mostrar janela
    window = PainelPresidente()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
