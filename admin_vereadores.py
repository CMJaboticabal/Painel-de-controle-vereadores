"""
Painel Administrativo - Gerenciamento de Vereadores
Interface para cadastro, edição e exclusão de vereadores
"""

import sys
import json
import os
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QWidget, QInputDialog,
    QTabWidget, QColorDialog, QFrame, QScrollArea, QApplication,
    QComboBox, QGridLayout, QSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont
import csv
import shutil

class VereadoresAdminDialog(QDialog):
    """Dialog para administração de vereadores"""
    
    vereadores_updated = Signal()  # Sinal emitido quando vereadores são atualizados
    session_updated = Signal()     # Sinal emitido quando configuração da sessão muda
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vereadores = []
        self.current_vereador = None
        
        # Configuração de sessão
        from session_config import SessionConfig
        self.session_config = SessionConfig()
        
        # Caminho da lista vem da configuração
        self.update_json_path()
        
        # Obter caminhos persistentes do SessionConfig
        self.fotos_dir = self.session_config.get_data_path('fotos')
        self.presets_dir = self.session_config.get_data_path('presets')
        
        # Garantir diretórios (SessionConfig já cria, mas por segurança)
        os.makedirs(self.fotos_dir, exist_ok=True)
        os.makedirs(self.presets_dir, exist_ok=True)
        
        # Detectar IP Local para exibir na UI
        self.local_ip = self.get_local_ip()
        
        self.init_ui()
        self.load_vereadores()
        
    def get_local_ip(self):
        """Detecta o IP da máquina na rede local"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            # Não precisa conectar de fato, apenas para forçar a escolha da interface certa
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
        
    def update_json_path(self):
        """Atualiza caminho do JSON baseado na configuração (usa AppData)"""
        relative_path = self.session_config.get_active_list()
        self.json_path = self.session_config.get_data_path(relative_path)
        
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        
        # Se arquivo não existe, criar lista vazia
        if not os.path.exists(self.json_path):
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def update_connection_status(self, arduino_enabled, server_enabled):
        """Atualiza indicadores de status na interface admin"""
        # Arduino
        if arduino_enabled:
            self.arduino_status.setText("✅ Arduino: Conectado")
            self.arduino_status.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(0, 242, 254, 0.4);
                    border: 1px solid #00f2fe;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        else:
            self.arduino_status.setText("❌ Arduino: Desconectado")
            self.arduino_status.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(250, 112, 154, 0.4);
                    border: 1px solid #fa709a;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            
        # Servidor
        if server_enabled:
            ip_display = self.local_ip if hasattr(self, 'local_ip') else '127.0.0.1'
            self.websocket_status.setText(f"✅ WebSocket/API: Online\nhttp://{ip_display}:5000")
            self.websocket_status.setStyleSheet("""
                QLabel {
                    font-size: 15px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(0, 242, 254, 0.4);
                    border: 1px solid #00f2fe;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
        else:
            self.websocket_status.setText("❌ WebSocket/API: Offline")
            self.websocket_status.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #ffffff;
                    background-color: rgba(250, 112, 154, 0.4);
                    border: 1px solid #fa709a;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
    
    def init_ui(self):
        """Inicializar interface com ABAS"""
        self.setWindowTitle("Administração do Sistema")
        self.setMinimumSize(1000, 750)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Criar Tab Widget
        self.tabs = QTabWidget()
        
        # Aba 1: Vereadores (Reutiliza lógica existente)
        self.tab_vereadores = QWidget()
        layout_vereadores = QHBoxLayout()
        # Seções existentes criadas pelos métodos auxiliares
        layout_vereadores.addWidget(self.create_list_section(), 1)
        layout_vereadores.addWidget(self.create_form_section(), 2)
        self.tab_vereadores.setLayout(layout_vereadores)
        
        self.tabs.addTab(self.tab_vereadores, "👤 VEREADORES")
        
        # Aba 2: Customização
        self.tabs.addTab(self.create_config_tab(), "⚙️ CUSTOMIZAÇÃO")
        
        # Aba 3: Listas
        self.tabs.addTab(self.create_lists_tab(), "📋 LISTAS")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        self.apply_styles()
    
    def create_list_section(self):
        """Criar seção da lista"""
        group = QGroupBox("Vereadores Cadastrados")
        layout = QVBoxLayout()
        
        # Lista
        self.vereadores_list = QListWidget()
        self.vereadores_list.itemClicked.connect(self.select_vereador)
        layout.addWidget(self.vereadores_list)
        
        # Botões
        btn_layout = QVBoxLayout()
        
        self.btn_novo = QPushButton("➕ Novo")
        self.btn_novo.clicked.connect(self.novo_vereador)
        btn_layout.addWidget(self.btn_novo)
        
        self.btn_excluir = QPushButton("🗑️ Excluir")
        self.btn_excluir.clicked.connect(self.excluir_vereador)
        self.btn_excluir.setEnabled(False)
        btn_layout.addWidget(self.btn_excluir)
        
        btn_layout.addSpacing(20)
        
        # --- Controles de Reordenação ---
        order_layout = QHBoxLayout()
        order_layout.setSpacing(5)
        
        btn_up = QPushButton("⬆️")
        btn_up.setToolTip("Mover para cima")
        btn_up.clicked.connect(self.mover_cima)
        btn_up.setFixedWidth(50)
        
        btn_down = QPushButton("⬇️")
        btn_down.setToolTip("Mover para baixo")
        btn_down.clicked.connect(self.mover_baixo)
        btn_down.setFixedWidth(50)
        
        btn_save_order = QPushButton("💾 Salvar Ordem")
        btn_save_order.setToolTip("Salvar nova ordem da lista")
        btn_save_order.clicked.connect(self.salvar_ordem_lista)
        btn_save_order.setStyleSheet("background-color: #f1c40f; color: black; font-weight: bold;")
        
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addWidget(btn_save_order)
        
        btn_layout.addLayout(order_layout)
        
        btn_layout.addSpacing(20)

        # Botão Importar CSV + Botão Baixar Modelo (lado a lado)
        csv_row_layout = QHBoxLayout()
        csv_row_layout.setSpacing(5)

        self.btn_importar_csv = QPushButton("📥 Importar CSV")
        self.btn_importar_csv.clicked.connect(self.importar_csv)
        self.btn_importar_csv.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f39c12, stop:1 #e67e22);
            }
        """)
        csv_row_layout.addWidget(self.btn_importar_csv)

        btn_modelo_csv = QPushButton("📋")
        btn_modelo_csv.setFixedWidth(38)
        btn_modelo_csv.setToolTip("Abrir arquivo modelo CSV (modelo_vereadores.csv)")
        btn_modelo_csv.clicked.connect(self.abrir_modelo_csv)
        btn_modelo_csv.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border: 1px solid #f39c12;
                border-radius: 5px;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
        """)
        csv_row_layout.addWidget(btn_modelo_csv)

        btn_layout.addLayout(csv_row_layout)
        
        self.btn_config_sessao = QPushButton("⚙️ Configurar Sessão")
        self.btn_config_sessao.clicked.connect(self.config_sessao)
        self.btn_config_sessao.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #764ba2, stop:1 #667eea);
            }
        """)
        btn_layout.addWidget(self.btn_config_sessao)
        
        btn_layout.addSpacing(10)
        
        self.btn_presets = QPushButton("📋 Gerenciar Listas")
        self.btn_presets.clicked.connect(self.gerenciar_presets)
        self.btn_presets.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #11998e, stop:1 #38ef7d);
            }
        """)
        btn_layout.addWidget(self.btn_presets)
        
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group
    
    def create_form_section(self):
        """Criar seção do formulário"""
        group = QGroupBox("Dados do Vereador")
        layout = QVBoxLayout()
        
        # Foto
        foto_layout = QHBoxLayout()
        
        self.foto_label = QLabel()
        self.foto_label.setFixedSize(150, 150)
        self.foto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto_label.setStyleSheet("""
            QLabel {
                border: 2px solid rgba(102, 126, 234, 0.5);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.05);
            }
        """)
        self.set_placeholder_photo()
        foto_layout.addWidget(self.foto_label)
        
        foto_btn_layout = QVBoxLayout()
        self.btn_selecionar_foto = QPushButton("📷 Selecionar Foto")
        self.btn_selecionar_foto.clicked.connect(self.selecionar_foto)
        foto_btn_layout.addWidget(self.btn_selecionar_foto)
        
        self.btn_remover_foto = QPushButton("❌ Remover Foto")
        self.btn_remover_foto.clicked.connect(self.remover_foto)
        foto_btn_layout.addWidget(self.btn_remover_foto)
        foto_btn_layout.addStretch()
        
        foto_layout.addLayout(foto_btn_layout)
        layout.addLayout(foto_layout)
        
        # Formulário
        form_layout = QFormLayout()
        
        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Nome completo do vereador")
        form_layout.addRow("Nome:", self.input_nome)
        
        self.input_partido = QLineEdit()
        self.input_partido.setPlaceholderText("Sigla do partido (ex: PSDB)")
        form_layout.addRow("Partido:", self.input_partido)
        
        layout.addLayout(form_layout)
        
        # Botões de ação
        btn_layout = QHBoxLayout()
        
        self.btn_salvar = QPushButton("💾 Salvar")
        self.btn_salvar.clicked.connect(self.salvar_vereador)
        self.btn_salvar.setEnabled(False)
        btn_layout.addWidget(self.btn_salvar)
        
        self.btn_cancelar = QPushButton("❌ Cancelar")
        self.btn_cancelar.clicked.connect(self.cancelar_edicao)
        self.btn_cancelar.setEnabled(False)
        btn_layout.addWidget(self.btn_cancelar)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def apply_styles(self):
        """Aplicar estilos"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f0f23, stop:1 #1a1a2e);
            }
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #303050;
                background: #162447;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1a1a2e;
                color: #bdc3c7;
                padding: 12px 25px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
                font-size: 14px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #162447;
                color: #fff;
                border-top: 3px solid #e94560;
            }
            QTabBar::tab:hover {
                background: #1f4068;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 14px;
            }
            QLineEdit {
                background: #1a1a2e;
                color: white;
                border: 1px solid #303050;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #e94560;
            }
            QListWidget {
                background: #1a1a2e;
                border: 1px solid #303050;
                border-radius: 5px;
                color: white;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #303050;
            }
            QListWidget::item:selected {
                background: #e94560;
                color: white;
            }
            QPushButton {
                background-color: #1f4068;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #265077;
            }
            QGroupBox {
                border: 1px solid #303050;
                border-radius: 8px;
                margin-top: 20px;
                font-weight: bold;
                color: #e94560;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

    def create_vereadores_tab(self):
        """Aba de gerenciamento de vereadores"""
        tab = QWidget()
        layout = QHBoxLayout()
        
        # Coluna Esquerda: Lista
        left_layout = QVBoxLayout()
        
        # Busca
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar vereador...")
        self.search_input.textChanged.connect(self.filter_vereadores)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)
        
        # Lista
        self.vereadores_list = QListWidget()
        self.vereadores_list.itemClicked.connect(self.select_vereador)
        left_layout.addWidget(self.vereadores_list)
        
        # Botões da lista
        list_btn_layout = QHBoxLayout()
        btn_novo = QPushButton("➕ Novo Vereador")
        btn_novo.clicked.connect(self.novo_vereador)
        btn_novo.setStyleSheet("background-color: #2ecc71;")
        
        btn_excluir = QPushButton("🗑️ Excluir")
        btn_excluir.clicked.connect(self.excluir_vereador)
        btn_excluir.setStyleSheet("background-color: #e74c3c;")
        
        list_btn_layout.addWidget(btn_novo)
        list_btn_layout.addWidget(btn_excluir)
        list_btn_layout.addWidget(btn_novo)
        list_btn_layout.addWidget(btn_excluir)
        left_layout.addLayout(list_btn_layout)
        
        # --- Controles de Reordenação ---
        order_layout = QHBoxLayout()
        
        btn_up = QPushButton("⬆️")
        btn_up.setToolTip("Mover para cima")
        btn_up.clicked.connect(self.mover_cima)
        
        btn_down = QPushButton("⬇️")
        btn_down.setToolTip("Mover para baixo")
        btn_down.clicked.connect(self.mover_baixo)
        
        btn_save_order = QPushButton("💾 Salvar Ordem")
        btn_save_order.setToolTip("Salvar nova ordem da lista")
        btn_save_order.clicked.connect(self.salvar_ordem_lista)
        btn_save_order.setStyleSheet("background-color: #f1c40f; color: black;")
        
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addWidget(btn_save_order)
        
        left_layout.addLayout(order_layout)
        
        # Coluna Direita: Formulário
        right_layout = QVBoxLayout()
        form_group = QGroupBox("📝 Detalhes do Vereador")
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.nome_input = QLineEdit()
        self.nome_input.setPlaceholderText("Nome Completo")
        
        self.partido_input = QLineEdit()
        self.partido_input.setPlaceholderText("Sigla do Partido")
        
        form_layout.addRow("Nome:", self.nome_input)
        form_layout.addRow("Partido:", self.partido_input)
        
        # Foto
        foto_container = QVBoxLayout()
        self.foto_label = QLabel()
        self.foto_label.setFixedSize(200, 200)
        self.foto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_placeholder_photo()
        
        btn_foto = QPushButton("📷 Alterar Foto")
        btn_foto.clicked.connect(self.escolher_foto)
        
        btn_remover_foto = QPushButton("❌ Remover Foto")
        btn_remover_foto.clicked.connect(self.remover_foto)
        btn_remover_foto.setStyleSheet("background-color: #95a5a6; font-size: 11px;")
        
        foto_container.addWidget(self.foto_label, 0, Qt.AlignmentFlag.AlignCenter)
        foto_container.addWidget(btn_foto)
        foto_container.addWidget(btn_remover_foto)
        
        form_layout.addRow(foto_container)
        
        # Botão Salvar
        btn_salvar = QPushButton("💾 SALVAR ALTERAÇÕES")
        btn_salvar.clicked.connect(self.salvar_vereador)
        btn_salvar.setStyleSheet("""
            background-color: #3498db; 
            padding: 15px; 
            font-size: 16px;
            margin-top: 10px;
        """)
        btn_salvar.setMinimumHeight(50)
        
        form_group.setLayout(form_layout)
        right_layout.addWidget(form_group)
        right_layout.addWidget(btn_salvar)
        right_layout.addStretch()
        
        layout.addLayout(left_layout, 1) # Peso 1
        layout.addLayout(right_layout, 1) # Peso 1
        
        tab.setLayout(layout)
        return tab

    def create_config_tab(self):
        """Aba de customização e configuração"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        tab.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(30)
        
        # --- SEÇÃO DADOS DA SESSÃO ---
        sessao_group = QGroupBox("📅 Dados da Sessão")
        sessao_layout = QFormLayout()
        sessao_layout.setSpacing(15)
        
        self.session_input = QLineEdit()
        self.session_input.setObjectName("txtSessionName")
        self.session_input.setText(self.session_config.get_session_name())
        self.session_input.setPlaceholderText("Ex: SESSÃO ORDINÁRIA 47")
        sessao_layout.addRow("Nome da Sessão:", self.session_input)
        
        self.city_input = QLineEdit()
        self.city_input.setObjectName("txtCityName")
        self.city_input.setText(self.session_config.get_city_name())
        self.city_input.setPlaceholderText("Ex: SINOP")
        sessao_layout.addRow("Nome da Cidade:", self.city_input)
        
        self.website_input = QLineEdit()
        self.website_input.setObjectName("txtWebsiteUrl")
        self.website_input.setText(self.session_config.get_website_url())
        self.website_input.setPlaceholderText("Ex: www.sinop.mt.leg.br")
        sessao_layout.addRow("Site (Lower Third):", self.website_input)
        
        # Botão de Backup
        btn_backup = QPushButton("📦 Exportar Backup Config (.json)")
        btn_backup.setStyleSheet("background-color: #f39c12; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        btn_backup.clicked.connect(self.exportar_backup)
        sessao_layout.addRow("", btn_backup)
        
        # Logo
        logo_layout = QHBoxLayout()
        self.logo_path_label = QLabel(self.session_config.get_logo() or "Nenhuma logo selecionada")
        btn_logo = QPushButton("📁 Escolher Logo")
        btn_logo.clicked.connect(self.escolher_logo)
        
        logo_layout.addWidget(self.logo_path_label)
        logo_layout.addWidget(btn_logo)
        sessao_layout.addRow("Logo da Casa:", logo_layout)
        
        sessao_group.setLayout(sessao_layout)
        layout.addWidget(sessao_group)
        
        # --- SEÇÃO TELA SECUNDÁRIA ---
        tela_group = QGroupBox("🖥️ Tela Secundária (Monitor 2)")
        tela_layout = QFormLayout()
        tela_layout.setSpacing(15)
        
        self.combo_screen_type = QComboBox()
        self.combo_screen_type.setObjectName("comboScreenType")
        self.combo_screen_type.addItem("🖥️  Tela Plenário Padrão (clássica)", "plenario")
        self.combo_screen_type.addItem("🖼️  Layout Lateral (foto + nome + cronômetro)", "lateral")
        
        # Restaurar seleção salva
        current_type = self.session_config.get_secondary_screen_type()
        idx = self.combo_screen_type.findData(current_type)
        if idx >= 0:
            self.combo_screen_type.setCurrentIndex(idx)
        
        self.combo_screen_type.setMinimumHeight(40)
        self.combo_screen_type.setStyleSheet("""
            QComboBox {
                background: #1a1a2e;
                color: white;
                border: 1px solid #303050;
                padding: 8px 14px;
                border-radius: 6px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: #162447;
                color: white;
                selection-background-color: #e94560;
            }
        """)
        tela_layout.addRow("Tipo de Tela:", self.combo_screen_type)
        
        tela_note = QLabel("A seleção é salva automaticamente ao clicar em 'Salvar Configurações'.")
        tela_note.setStyleSheet("color: rgba(200,200,255,0.6); font-size: 12px; font-style: italic;")
        tela_layout.addRow(tela_note)
        
        tela_group.setLayout(tela_layout)
        layout.addWidget(tela_group)
        
        # --- SEÇÃO CONEXÕES ---
        connections_group = QGroupBox("🔌 Status de Conexões")
        connections_layout = QVBoxLayout()
        
        self.arduino_status = QLabel("❌ Arduino: Desconectado")
        self.arduino_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.arduino_status.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                background-color: rgba(250, 112, 154, 0.4);
                border: 1px solid #fa709a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        connections_layout.addWidget(self.arduino_status)
        
        # --- Controles Arduino Avançados ---
        arduino_controls = QHBoxLayout()
        
        # Combo de Portas
        self.combo_ports = QComboBox()
        self.combo_ports.setMinimumWidth(150)
        self.refresh_ports() # Popular inicialmente
        arduino_controls.addWidget(self.combo_ports)
        
        # Botão Atualizar Lista
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(40)
        btn_refresh.setToolTip("Atualizar lista de portas")
        btn_refresh.clicked.connect(self.refresh_ports)
        arduino_controls.addWidget(btn_refresh)
        
        # Botão Conectar Manual
        btn_connect = QPushButton("Conectar")
        btn_connect.clicked.connect(self.manual_connect_arduino)
        btn_connect.setStyleSheet("background-color: #2980b9;")
        arduino_controls.addWidget(btn_connect)
        
        connections_layout.addLayout(arduino_controls)
        
        # Botões de Teste
        test_layout = QHBoxLayout()
        btn_open = QPushButton("🔊 Testar: ABRIR")
        btn_open.clicked.connect(lambda: self.test_arduino('1'))
        btn_open.setStyleSheet("background-color: #27ae60; color: white;")
        
        btn_cut = QPushButton("🔇 Testar: CORTAR")
        btn_cut.clicked.connect(lambda: self.test_arduino('0'))
        btn_cut.setStyleSheet("background-color: #c0392b; color: white;")
        
        test_layout.addWidget(btn_open)
        test_layout.addWidget(btn_cut)
        connections_layout.addLayout(test_layout)
        
        connections_layout.addSpacing(10)
        
        self.websocket_status = QLabel("❌ WebSocket: Desconectado")
        self.websocket_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.websocket_status.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                background-color: rgba(250, 112, 154, 0.4);
                border: 1px solid #fa709a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        connections_layout.addWidget(self.websocket_status)
        
        connections_group.setLayout(connections_layout)
        layout.addWidget(connections_group)
        
        # --- SEÇÃO PRESETS DE TEMPO ---
        presets_group = QGroupBox("⏱️ Presets de Tempo (Minutos)")
        presets_layout = QGridLayout()
        presets_layout.setSpacing(10)
        
        self.preset_inputs = []
        current_presets = self.session_config.get_time_presets()
        for i in range(6):
            val = current_presets[i] if i < len(current_presets) else (i + 1)
            inp = QSpinBox()
            inp.setRange(1, 999)
            inp.setValue(val)
            inp.setSuffix(" min")
            inp.setMinimumHeight(35)
            presets_layout.addWidget(QLabel(f"Botão {i+1}:"), i // 3, (i % 3) * 2)
            presets_layout.addWidget(inp, i // 3, (i % 3) * 2 + 1)
            self.preset_inputs.append(inp)
            
        presets_group.setLayout(presets_layout)
        layout.addWidget(presets_group)
        
        # --- SEÇÃO CORES ---
        cores_group = QGroupBox("🎨 Identidade Visual (Lower Third)")
        cores_layout = QVBoxLayout()
        
        colors = self.session_config.get_colors()
        
        # Função auxiliar para criar linha de cor
        def create_color_row(label, color_key, default_color):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(150)
            
            # Preview da cor
            preview = QLabel()
            preview.setFixedSize(100, 30)
            preview.setStyleSheet(f"background-color: {colors.get(color_key, default_color)}; border: 1px solid #555; border-radius: 4px;")
            
            # Input de texto (hexa)
            inp = QLineEdit(colors.get(color_key, default_color))
            inp.setFixedWidth(100)
            
            # Botão
            btn = QPushButton("🖌️")
            btn.setFixedWidth(40)
            
            # Atualizar preview ao digitar
            inp.textChanged.connect(lambda t: preview.setStyleSheet(f"background-color: {t}; border: 1px solid #555; border-radius: 4px;"))
            
            # Ação do botão
            def pick_color():
                color = QColorDialog.getColor(
                    QColor(inp.text()), 
                    self, 
                    f"Escolher {label}",
                    QColorDialog.ColorDialogOption.ShowAlphaChannel
                )
                if color.isValid():
                    # Converter para formato CSS (rgba ou hex)
                    if color.alpha() < 255:
                         hex_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()/255:.2f})"
                    else:
                         hex_color = color.name().upper()
                    
                    inp.setText(hex_color)
                    preview.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #555; border-radius: 4px;")
            
            btn.clicked.connect(pick_color)
            
            row.addWidget(lbl)
            row.addWidget(preview)
            row.addWidget(inp)
            row.addWidget(btn)
            row.addStretch()
            
            return row, inp

        # Criar os seletores
        self.row_primary, self.input_primary = create_color_row("Cor Primária (Nome):", 'primary', '#10a37f')
        self.row_secondary, self.input_secondary = create_color_row("Cor Secundária (Info):", 'secondary', '#1e4586')
        self.row_text_primary, self.input_text_primary = create_color_row("Cor do Nome Orador:", 'text_primary', '#ffffff')
        self.row_text_secondary, self.input_text_secondary = create_color_row("Cor demais Textos:", 'text_secondary', '#ffffff')
        self.row_bg, self.input_bg = create_color_row("Cor de Fundo (Sistema):", 'background', '#1a1a2e')
        
        cores_layout.addLayout(self.row_primary)
        cores_layout.addLayout(self.row_secondary)
        cores_layout.addLayout(self.row_text_primary)
        cores_layout.addLayout(self.row_text_secondary)
        cores_layout.addLayout(self.row_bg)
        
        cores_group.setLayout(cores_layout)
        layout.addWidget(cores_group)
        
        # Botão Salvar Geral
        btn_salvar_config = QPushButton("💾 SALVAR CONFIGURAÇÕES")
        btn_salvar_config.clicked.connect(self.salvar_configuracoes)
        btn_salvar_config.setStyleSheet("background-color: #3498db; padding: 15px; font-size: 16px;")
        layout.addWidget(btn_salvar_config)
        
        # --- ZONA DE PERIGO ---
        danger_group = QGroupBox("⛔ Controle do Sistema")
        danger_layout = QVBoxLayout()
        
        btn_shutdown = QPushButton("🛑 ENCERRAR SISTEMA COMPLETO")
        btn_shutdown.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                font-weight: bold;
                padding: 15px;
                font-size: 16px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)
        btn_shutdown.clicked.connect(self.shutdown_system)
        danger_layout.addWidget(btn_shutdown)
        
        danger_group.setLayout(danger_layout)
        layout.addWidget(danger_group)
        
        layout.addStretch()
        
        tab.setWidget(content)
        return tab

    def shutdown_system(self):
        """Encerra todo o sistema"""
        reply = QMessageBox.question(
            self, "Encerrar Sistema",
            "Tem certeza que deseja fechar todo o sistema (Painel e Servidor)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            print("🛑 Encerrando sistema pelo Painel Admin...")
            # Tentar fechar a janela pai (Main Window)
            if self.parent():
                self.parent().close()
            
            # Fechar o dialog atual
            self.close()
            
            # Forçar saída do app
            QApplication.quit()

    def escolher_logo(self):
        file, _ = QFileDialog.getOpenFileName(self, "Selecionar Logo", "", "Imagens (*.png *.jpg *.jpeg)")
        if file:
            self.new_logo_path = file
            self.logo_path_label.setText(os.path.basename(file))

    
    def refresh_ports(self):
        """Atualizar lista de portas COM"""
        self.combo_ports.clear()
        if self.parent() and hasattr(self.parent(), 'arduino'):
            ports = self.parent().arduino.list_available_ports()
            for port in ports:
                # Exibe: "COM3 - USB-SERIAL CH340"
                self.combo_ports.addItem(f"{port['device']} - {port['description']}", port['device'])
            
            if self.combo_ports.count() == 0:
                self.combo_ports.addItem("Nenhuma porta encontrada")

    def manual_connect_arduino(self):
        """Forçar conexão na porta selecionada"""
        port_device = self.combo_ports.currentData()
        if not port_device:
            return
            
        if self.parent() and hasattr(self.parent(), 'arduino'):
            self.parent().arduino.disconnect() # Desconecta anterior
            if self.parent().arduino.connect(port_device):
                QMessageBox.information(self, "Sucesso", f"Conectado a {port_device} com sucesso!")
                # Atualizar status visual via callback natural ou forçado
                self.update_connection_status(True, getattr(self.parent(), 'is_server_connected', False))
            else:
                QMessageBox.warning(self, "Erro", f"Falha ao conectar em {port_device}.")
                self.update_connection_status(False, getattr(self.parent(), 'is_server_connected', False))

    def test_arduino(self, command):
        """Testar comando do Arduino"""
        if self.parent() and hasattr(self.parent(), 'arduino'):
            arduino = self.parent().arduino
            if arduino.is_connected:
                if command == '1':
                    arduino.open_audio()
                else:
                    arduino.cut_audio()
            else:
                 QMessageBox.warning(self, "Aviso", "Arduino desconectado! Conecte primeiro.")
                 
    def exportar_backup(self):
        """Exportar o arquivo session_config.json para backup"""
        import shutil
        from datetime import datetime
        default_name = f"backup_config_tribuna_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_path, _ = QFileDialog.getSaveFileName(self, "Salvar Backup de Configuração", default_name, "JSON Files (*.json)")
        
        if save_path:
            try:
                # Force save before export just in case
                self.salvar_configuracoes(show_msg=False)
                shutil.copy2(self.session_config.config_path, save_path)
                QMessageBox.information(self, "Sucesso", f"Backup das configurações salvo em:\\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao exportar backup:\\n{e}")
    
    def salvar_configuracoes(self, show_msg=True):
        """Salva sessão e cores"""
        
        # Debug: Listar line edits (ajuda a ver duplicatas)
        all_edits = self.findChildren(QLineEdit)
        for e in all_edits:
             name = e.objectName()
             val = e.text()
             visible = e.isVisible()
             print(f"DEBUG: QLineEdit(name='{name}', visible={visible}) = '{val}'")

        # Busca robusta
        input_widget = self.findChild(QLineEdit, "txtSessionName")
        if input_widget:
             text = input_widget.text().strip()
             print(f"DEBUG: Texto obtido via findChild: '{text}'")
        else:
             text = self.session_input.text().strip()
             print(f"DEBUG: Texto obtido via self.reference: '{text}'")

        print(f"DEBUG: Tentando salvar sessão: '{text}'")
        
        # Salvar Sessão e Cidade (Força Bruta para garantir escrita)
        from session_config import SessionConfig
        temp_conf = SessionConfig()
        temp_conf.set_session_name(text)
        
        # Buscar Nome da Cidade
        input_city = self.findChild(QLineEdit, "txtCityName")
        city_text = input_city.text().strip() if input_city else self.city_input.text().strip()
        temp_conf.set_city_name(city_text)
        
        # Buscar Website
        input_web = self.findChild(QLineEdit, "txtWebsiteUrl")
        web_text = input_web.text().strip() if input_web else getattr(self, 'website_input', QLineEdit()).text().strip()
        temp_conf.set_website_url(web_text)
        
        # Atualizar local
        self.session_config.load_config()
        
        if hasattr(self, 'new_logo_path'):
            # Copiar logo para pasta assets ou usar caminho absoluto? 
            # O sistema atual usa caminho absoluto salvo no json
             self.session_config.set_logo(self.new_logo_path)
        
        # Salvar Cores
        self.session_config.set_colors(
            self.input_primary.text(),
            self.input_secondary.text(),
            self.input_text_primary.text(),
            self.input_text_secondary.text(),
            self.input_bg.text()
        )
        
        # Salvar Presets de Tempo
        new_presets = [inp.value() for inp in self.preset_inputs]
        self.session_config.set_time_presets(new_presets)
        
        # Salvar Tipo de Tela Secundária
        screen_type = self.combo_screen_type.currentData()
        if screen_type:
            self.session_config.set_secondary_screen_type(screen_type)
        
        if show_msg:
            QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso!")
        self.session_updated.emit()

    def create_lists_tab(self):
        """Aba de gerenciamento de listas (Presets)"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Grupo Lista
        group = QGroupBox("📁 Listas Disponíveis")
        group_layout = QVBoxLayout()
        
        self.presets_list_widget = QListWidget()
        group_layout.addWidget(self.presets_list_widget)
        
        self.active_list_label = QLabel(f"Lista Ativa: {os.path.basename(self.session_config.get_active_list())}")
        self.active_list_label.setStyleSheet("color: #38ef7d; font-weight: bold; font-size: 16px; margin: 10px;")
        group_layout.addWidget(self.active_list_label)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # Botões de Ação
        btn_layout = QHBoxLayout()
        
        btn_ativar = QPushButton("✅ ATIVAR SELECIONADA")
        btn_ativar.clicked.connect(self.ativar_preset_tab)
        btn_ativar.setStyleSheet("background: #2ecc71; color: white;")
        
        btn_novo = QPushButton("➕ NOVA LISTA")
        btn_novo.clicked.connect(self.novo_preset_tab)
        
        btn_excluir = QPushButton("🗑️ EXCLUIR")
        btn_excluir.clicked.connect(self.excluir_preset_tab)
        btn_excluir.setStyleSheet("background: #e74c3c; color: white;")
        
        btn_layout.addWidget(btn_ativar)
        btn_layout.addWidget(btn_novo)
        btn_layout.addWidget(btn_excluir)
        
        layout.addLayout(btn_layout)
        
        # Atualizar lista inicial
        self.refresh_presets_list()
        
        tab.setLayout(layout)
        return tab

    def refresh_presets_list(self):
        """Atualiza a lista de presets na aba"""
        self.presets_list_widget.clear()
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
            
        current_active = self.session_config.get_active_list().replace('\\', '/')
            
        for filename in os.listdir(self.presets_dir):
            if filename.endswith(".json"):
                item = QListWidgetItem(filename)
                
                # Comparação normalizada
                item_path = f"presets/{filename}"
                
                if item_path == current_active:
                    item.setBackground(QColor("#2ecc71"))
                    item.setForeground(QColor("white"))
                    item.setText(f"{filename} (ATIVO)")
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                     item.setForeground(QColor("white"))
                
                self.presets_list_widget.addItem(item)
                
    def ativar_preset_tab(self):
        item = self.presets_list_widget.currentItem()
        if not item:
            return
        
        filename = item.text().replace(" (ATIVO)", "")
        path = f"presets/{filename}"
        
        self.session_config.set_active_list(path)
        self.update_json_path()
        self.load_vereadores()
        
        self.active_list_label.setText(f"Lista Ativa: {filename}")
        self.refresh_presets_list()
        
        self.vereadores_updated.emit()
        self.session_updated.emit()
        QMessageBox.information(self, "Sucesso", f"Lista '{filename}' ativada!")

    def novo_preset_tab(self):
        name, ok = QInputDialog.getText(self, "Nova Lista", "Nome da lista (sem .json):")
        if ok and name:
            filename = f"{name}.json"
            path = os.path.join(self.presets_dir, filename)
            
            if os.path.exists(path):
                QMessageBox.warning(self, "Erro", "Lista já existe!")
                return
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            
            self.refresh_presets_list()

    def excluir_preset_tab(self):
        item = self.presets_list_widget.currentItem()
        if not item:
            return
        
        filename = item.text().replace(" (ATIVO)", "")
        if f"presets/{filename}" == self.session_config.get_active_list():
            QMessageBox.warning(self, "Erro", "Não é possível excluir a lista ativa!")
            return
            
        reply = QMessageBox.question(
            self, "Confirmação",
            f"Excluir lista '{filename}' permanentemente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            os.remove(os.path.join(self.presets_dir, filename))
            self.refresh_presets_list()
    
    def filter_vereadores(self, text):
        """Filtra a lista de vereadores com base no texto de busca."""
        for i in range(self.vereadores_list.count()):
            item = self.vereadores_list.item(i)
            vereador = item.data(Qt.ItemDataRole.UserRole)
            if text.lower() in vereador['nome'].lower() or text.lower() in vereador['partido'].lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def escolher_foto(self):
        """Alias para selecionar_foto para o novo nome de método."""
        self.selecionar_foto()

    def set_placeholder_photo(self):
        """Define uma imagem de placeholder para a foto do vereador."""
        placeholder_path = self.session_config.get_bundle_path(os.path.join('assets', 'placeholder_vereador.png'))
        if os.path.exists(placeholder_path):
            pixmap = QPixmap(placeholder_path)
            self.foto_label.setPixmap(pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.foto_label.setText("Sem Foto")
            self.foto_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #667eea;
                    border-radius: 10px;
                    background: rgba(255, 255, 255, 0.05);
                    color: #aaa;
                    font-size: 14px;
                }
            """)
    
    
    def mover_cima(self):
        """Mover item selecionado para cima"""
        row = self.vereadores_list.currentRow()
        if row > 0:
            item = self.vereadores_list.takeItem(row)
            self.vereadores_list.insertItem(row - 1, item)
            self.vereadores_list.setCurrentRow(row - 1)
            
    def mover_baixo(self):
        """Mover item selecionado para baixo"""
        row = self.vereadores_list.currentRow()
        if row < self.vereadores_list.count() - 1:
            item = self.vereadores_list.takeItem(row)
            self.vereadores_list.insertItem(row + 1, item)
            self.vereadores_list.setCurrentRow(row + 1)
            
    def salvar_ordem_lista(self):
        """Salva a nova ordem dos vereadores no JSON"""
        nova_lista = []
        for i in range(self.vereadores_list.count()):
            item = self.vereadores_list.item(i)
            # Recuperar o objeto vereador completo armazenado no item
            vereador = item.data(Qt.ItemDataRole.UserRole)
            nova_lista.append(vereador)
            
        self.vereadores = nova_lista
        
        # Salvar no arquivo
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(self.vereadores, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "Sucesso", "Nova ordem salva com sucesso!")
            self.vereadores_updated.emit() # Notificar janela principal para recarregar
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar ordem: {e}")

    def load_vereadores(self):
        """Carregar vereadores do JSON"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.vereadores = json.load(f)
            self.populate_list()
        except FileNotFoundError:
            self.vereadores = []
    
    def save_vereadores(self):
        """Salvar vereadores no JSON"""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.vereadores, f, ensure_ascii=False, indent=4)
        self.vereadores_updated.emit()
    
    def populate_list(self):
        """Preencher lista de vereadores"""
        self.vereadores_list.clear()
        for vereador in self.vereadores:
            item = QListWidgetItem(f"{vereador['nome']} ({vereador['partido']})")
            item.setData(Qt.ItemDataRole.UserRole, vereador)
            self.vereadores_list.addItem(item)
    
    def select_vereador(self, item):
        """Selecionar vereador para edição"""
        self.current_vereador = item.data(Qt.ItemDataRole.UserRole)
        
        self.input_nome.setText(self.current_vereador['nome'])
        self.input_partido.setText(self.current_vereador['partido'])
        
        # Carregar foto e manter referência
        if self.current_vereador.get('foto'):
            # Manter foto atual
            current_foto = self.current_vereador['foto']
            self.selected_foto_path = current_foto  
            
            # Tentar primeiro em AppData, depois no Bundle
            foto_path = self.session_config.get_data_path(current_foto)
            if not os.path.exists(foto_path):
                foto_path = self.session_config.get_bundle_path(current_foto)
                
            if os.path.exists(foto_path):
                pixmap = QPixmap(foto_path)
                self.foto_label.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.set_placeholder_photo()
        else:
            self.selected_foto_path = None
            self.set_placeholder_photo()
        
        self.btn_salvar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_excluir.setEnabled(True)
    
    def novo_vereador(self):
        """Criar novo vereador"""
        self.current_vereador = None
        self.input_nome.clear()
        self.input_partido.clear()
        self.set_placeholder_photo()
        
        self.btn_salvar.setEnabled(True)
        self.btn_cancelar.setEnabled(True)
        self.btn_excluir.setEnabled(False)
        
        self.input_nome.setFocus()
    
    def salvar_vereador(self):
        """Salvar vereador"""
        nome = self.input_nome.text().strip()
        partido = self.input_partido.text().strip().upper()
        
        if not nome or not partido:
            QMessageBox.warning(self, "Aviso", "Preencha nome e partido!")
            return
        
        # Obter foto atual
        foto = None
        if hasattr(self, 'selected_foto_path'):
            foto = self.selected_foto_path
        elif self.current_vereador and self.current_vereador.get('foto'):
            foto = self.current_vereador['foto']
        
        if self.current_vereador:
            # Editar existente - CORREÇÃO: Atualizar na lista original, pois self.current_vereador é uma cópia
            found = False
            for i, v in enumerate(self.vereadores):
                if v['id'] == self.current_vereador['id']:
                    self.vereadores[i]['nome'] = nome
                    self.vereadores[i]['partido'] = partido
                    self.vereadores[i]['foto'] = foto
                    found = True
                    break
            
            # Fallback (não deve acontecer)
            if not found:
                print("ERRO: Vereador editado não encontrado na lista original!")
        else:
            # Criar novo
            novo_id = max([v['id'] for v in self.vereadores], default=0) + 1
            novo_vereador = {
                'id': novo_id,
                'nome': nome,
                'partido': partido,
                'foto': foto
            }
            self.vereadores.append(novo_vereador)
        
        self.save_vereadores()
        self.populate_list()
        self.cancelar_edicao()
        
        QMessageBox.information(self, "Sucesso", "Vereador salvo com sucesso!")
    
    def excluir_vereador(self):
        """Excluir vereador"""
        if not self.current_vereador:
            return
        
        reply = QMessageBox.question(
            self, "Confirmação",
            f"Deseja realmente excluir {self.current_vereador['nome']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.vereadores = [v for v in self.vereadores if v['id'] != self.current_vereador['id']]
            self.save_vereadores()
            self.populate_list()
            self.cancelar_edicao()
            
            QMessageBox.information(self, "Sucesso", "Vereador excluído com sucesso!")
    
    def cancelar_edicao(self):
        """Cancelar edição"""
        self.current_vereador = None
        self.input_nome.clear()
        self.input_partido.clear()
        self.set_placeholder_photo()
        
        self.btn_salvar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
        self.btn_excluir.setEnabled(False)
        
        if hasattr(self, 'selected_foto_path'):
            delattr(self, 'selected_foto_path')
    
    def selecionar_foto(self):
        """Selecionar foto do vereador"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Foto",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            # Copiar foto para diretório de fotos
            import shutil
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.fotos_dir, filename)
            
            shutil.copy2(file_path, dest_path)
            
            # Salvar caminho relativo
            self.selected_foto_path = f"fotos/{filename}"
            
            # Exibir foto
            pixmap = QPixmap(dest_path)
            self.foto_label.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    
    def importar_csv(self):
        """Importar lista de vereadores de um arquivo CSV"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar CSV",
            "",
            "Arquivos CSV (*.csv)"
        )
        
        if not file_path:
            return
            
        # Perguntar se deve substituir ou adicionar
        reply = QMessageBox.question(
            self, "Modo de Importação",
            "Deseja SUBSTITUIR a lista atual ou ADICIONAR os vereadores do CSV à lista existente?\n\n"
            "Escolha 'Yes' para Substituir e 'No' para Adicionar.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
            
        substituir = (reply == QMessageBox.StandardButton.Yes)
        
        try:
            novos_vereadores = []
            
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                # Tentar detectar o delimitador, padrão será ; 
                # (ou podemos forçar ; e usar fallback pra , se não tiver ; na primeira linha)
                first_line = f.readline()
                f.seek(0)
                delimiter = ';' if ';' in first_line else ','
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                # Normalizar cabeçalhos para letras minúsculas e sem espaços extras
                headers = [h.strip().lower() for h in (reader.fieldnames or [])]
                if not headers or 'nome' not in headers or 'partido' not in headers:
                     QMessageBox.warning(self, "Erro", "CSV inválido. As colunas obrigatórias são 'nome' e 'partido'. A coluna 'foto' é opcional.")
                     return
                
                reader.fieldnames = headers

                if substituir:
                    next_id = 1
                else:
                    next_id = max([v['id'] for v in self.vereadores], default=0) + 1
                    
                for row in reader:
                    nome = row.get('nome', '').strip()
                    partido = row.get('partido', '').strip()
                    foto_path = row.get('foto', '').strip()
                    
                    if not nome or not partido:
                        continue # Pular linhas inválidas
                        
                    novo_foto_rel = None
                    if foto_path and os.path.exists(foto_path) and os.path.isfile(foto_path):
                        # Copiar imagem local
                        filename = os.path.basename(foto_path)
                        dest_path = os.path.join(self.fotos_dir, filename)
                        
                        try:
                            # Só copia se não for o mesmo arquivo
                            if os.path.abspath(foto_path) != os.path.abspath(dest_path):
                                shutil.copy2(foto_path, dest_path)
                            novo_foto_rel = f"fotos/{filename}"
                        except Exception as e:
                            print(f"Erro ao copiar foto {foto_path}: {e}")
                    
                    novos_vereadores.append({
                        'id': next_id,
                        'nome': nome,
                        'partido': partido.upper(),
                        'foto': novo_foto_rel
                    })
                    next_id += 1
            
            if substituir:
                self.vereadores = novos_vereadores
            else:
                self.vereadores.extend(novos_vereadores)
                
            self.save_vereadores()
            self.populate_list()
            self.cancelar_edicao()
            
            QMessageBox.information(self, "Sucesso", f"{len(novos_vereadores)} vereadores importados com sucesso!")
            
        except Exception as e:
             QMessageBox.critical(self, "Erro na Importação", f"Ocorreu um erro ao processar o CSV:\n{e}")

    def abrir_modelo_csv(self):
        """Abre o arquivo modelo_vereadores.csv com o programa padrão do sistema"""
        import subprocess
        
        # Tentar encontrar o modelo na pasta do bundle (executável) ou no diretório de trabalho
        modelo_path = self.session_config.get_bundle_path("modelo_vereadores.csv")
        
        if not os.path.exists(modelo_path):
            # Fallback: pasta onde o script está rodando
            modelo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modelo_vereadores.csv")
        
        if os.path.exists(modelo_path):
            try:
                os.startfile(modelo_path)
            except Exception as e:
                # Fallback: abrir a pasta que contém o arquivo
                try:
                    subprocess.Popen(f'explorer /select,"{modelo_path}"')
                except Exception as e2:
                    QMessageBox.warning(self, "Erro", f"Não foi possível abrir o modelo:\n{e2}")
        else:
            QMessageBox.warning(
                self, "Arquivo não encontrado",
                "O arquivo modelo_vereadores.csv não foi encontrado.\n\n"
                "Crie um arquivo CSV com as colunas:\n"
                "  nome;partido;foto\n\n"
                "Exemplo:\n"
                "  João Silva;PSDB;\n"
                "  Maria Santos;PT;C:\\fotos\\maria.jpg"
            )

    def remover_foto(self):
        """Remover foto do vereador"""
        self.set_placeholder_photo()
        self.selected_foto_path = None  # Definir como None ao invés de deletar
    
    def config_sessao(self):
        """Configurar sessão (logo e número)"""
        from session_config import SessionConfig
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
        
        session_config = SessionConfig()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Configurar Sessão")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Número da sessão
        layout.addWidget(QLabel("Número da Sessão:"))
        session_input = QLineEdit()
        session_input.setText(self.session_config.get_session_number())
        session_input.setPlaceholderText("Ex: 123")
        layout.addWidget(session_input)
        
        # Logo
        layout.addWidget(QLabel("Logo da Câmara:"))
        logo_label = QLabel("Nenhum logo selecionado")
        current_logo = session_config.get_logo()
        if current_logo:
            logo_label.setText(f"Logo atual: {os.path.basename(current_logo)}")
        layout.addWidget(logo_label)
        
        logo_path_var = [current_logo]  # Lista para manter referência
        
        def selecionar_logo():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Selecionar Logo",
                "",
                "Imagens (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                import shutil
                filename = os.path.basename(file_path)
                dest_path = self.session_config.get_data_path(os.path.join('fotos', filename))
                shutil.copy2(file_path, dest_path)
                logo_path_var[0] = dest_path
                logo_label.setText(f"Logo selecionado: {filename}")
        
        btn_logo = QPushButton("📷 Selecionar Logo")
        btn_logo.clicked.connect(selecionar_logo)
        layout.addWidget(btn_logo)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        def salvar():
            session_config.set_session_name(session_input.text().strip())
            if logo_path_var[0]:
                session_config.set_logo(logo_path_var[0])
            QMessageBox.information(dialog, "Sucesso", "Configuração salva!")
            self.session_updated.emit()  # Emitir sinal
            dialog.accept()
        
        btn_salvar = QPushButton("💾 Salvar")
        btn_salvar.clicked.connect(salvar)
        btn_layout.addWidget(btn_salvar)
        
        btn_cancelar = QPushButton("❌ Cancelar")
        btn_cancelar.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancelar)
        
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        dialog.setStyleSheet(self.styleSheet())  # Usar mesmo estilo
        dialog.exec()
    
    def gerenciar_presets(self):
        """Gerenciar presets de listas (Vereadores, Mirim, etc)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Gerenciar Listas de Presença")
        dialog.setMinimumSize(500, 400)
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout()
        
        # Lista de arquivos
        list_widget = QListWidget()
        layout.addWidget(QLabel("Listas Disponíveis (Presets):"))
        layout.addWidget(list_widget)
        
        # Label ativo
        active_label = QLabel(f"Lista Ativa: {os.path.basename(self.session_config.get_active_list())}")
        active_label.setStyleSheet("color: #38ef7d; font-weight: bold; font-size: 14px;")
        layout.addWidget(active_label)
        
        # Refresh function
        def refresh_list():
            list_widget.clear()
            current_active = self.session_config.get_active_list().replace('\\', '/')
            
            for filename in os.listdir(self.presets_dir):
                if filename.endswith(".json"):
                    item = QListWidgetItem(filename)
                    item_path = f"presets/{filename}"
                    
                    if item_path == current_active:
                        item.setBackground(QColor("#38ef7d"))
                        item.setForeground(QColor("black"))
                        item.setText(f"{filename} (ATIVO)")
                    list_widget.addItem(item)
        
        refresh_list()
        
        # Botões
        btn_layout = QHBoxLayout()
        
        def ativar_preset():
            item = list_widget.currentItem()
            if not item:
                return
            
            filename = item.text().replace(" (ATIVO)", "")
            path = f"presets/{filename}"
            
            self.session_config.set_active_list(path)
            self.update_json_path()
            self.load_vereadores()
            
            active_label.setText(f"Lista Ativa: {filename}")
            refresh_list()
            
            self.vereadores_updated.emit()
            self.session_updated.emit()
            QMessageBox.information(dialog, "Sucesso", f"Lista '{filename}' ativada!")
        
        def novo_preset():
            name, ok = QInputDialog.getText(dialog, "Nova Lista", "Nome da lista (sem .json):")
            if ok and name:
                filename = f"{name}.json"
                path = os.path.join(self.presets_dir, filename)
                
                if os.path.exists(path):
                    QMessageBox.warning(dialog, "Erro", "Lista já existe!")
                    return
                
                with open(path, 'w', encoding='utf-8') as f:
                    # Pode inicializar com lista vazia ou copiar a atual
                    # Vamos criar vazia por segurança
                    json.dump([], f)
                
                refresh_list()
        
        def excluir_preset():
            item = list_widget.currentItem()
            if not item:
                return
            
            filename = item.text().replace(" (ATIVO)", "")
            if f"presets/{filename}" == self.session_config.get_active_list():
                QMessageBox.warning(dialog, "Erro", "Não é possível excluir a lista ativa!")
                return
                
            reply = QMessageBox.question(
                dialog, "Confirmação",
                f"Excluir lista '{filename}' permanentemente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                os.remove(os.path.join(self.presets_dir, filename))
                refresh_list()
        
        btn_ativar = QPushButton("✅ Ativar Selecionada")
        btn_ativar.clicked.connect(ativar_preset)
        btn_ativar.setStyleSheet("background: #38ef7d; color: black;")
        
        btn_novo = QPushButton("➕ Nova Lista")
        btn_novo.clicked.connect(novo_preset)
        
        btn_excluir = QPushButton("🗑️ Excluir")
        btn_excluir.clicked.connect(excluir_preset)
        
        btn_layout.addWidget(btn_ativar)
        btn_layout.addWidget(btn_novo)
        btn_layout.addWidget(btn_excluir)
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec()
    
    def set_placeholder_photo(self):
        """Definir foto placeholder"""
        self.foto_label.setText("👤\nSem Foto")
        self.foto_label.setStyleSheet("""
            QLabel {
                border: 2px solid rgba(102, 126, 234, 0.5);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.05);
                font-size: 48px;
                color: rgba(255, 255, 255, 0.3);
            }
        """)
