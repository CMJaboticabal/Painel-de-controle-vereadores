"""
Configuração de Sessão - Logo e Número da Sessão
"""

import json
import os
import sys
import shutil

class SessionConfig:
    """Gerenciador de configuração da sessão"""
    
    def __init__(self):
        # 1. Definir base do bundle (Leitura - PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            self.base_bundle_path = sys._MEIPASS
        else:
            self.base_bundle_path = os.path.dirname(os.path.abspath(__file__))

        # 2. Definir diretório de dados do usuário (Escrita - AppData/Local)
        app_data = os.getenv('LOCALAPPDATA')
        if not app_data:
            app_data = os.path.expanduser('~')
            
        self.config_dir = os.path.join(app_data, 'PainelControleTribuna')
        
        # Criar diretório base se não existir
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
            except OSError as e:
                print(f"Erro ao criar diretório de configuração: {e}")
        
        # 3. Inicializar estrutura de pastas (fotos, presets)
        self.initialize_data_structure()
            
        self.config_path = os.path.join(self.config_dir, 'session_config.json')
        self.load_config()

    def initialize_data_structure(self):
        """Copia arquivos padrão do bundle para a pasta de dados se não existirem"""
        # Pastas necessárias
        folders = ['fotos', 'presets']
        for folder in folders:
            target_path = os.path.join(self.config_dir, folder)
            if not os.path.exists(target_path):
                source_path = os.path.join(self.base_bundle_path, folder)
                if os.path.exists(source_path):
                    try:
                        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                        print(f"DEBUG: Pasta {folder} copiada para {target_path}")
                    except Exception as e:
                        print(f"Erro ao copiar pasta {folder}: {e}")
                else:
                    os.makedirs(target_path, exist_ok=True)

        # Arquivo de vereadores padrão (vereadores.json na raiz do bundle)
        target_vereadores = os.path.join(self.config_dir, 'vereadores.json')
        if not os.path.exists(target_vereadores):
            source_vereadores = os.path.join(self.base_bundle_path, 'vereadores.json')
            if os.path.exists(source_vereadores):
                try:
                    shutil.copy2(source_vereadores, target_vereadores)
                    print(f"DEBUG: Arquivo vereadores.json copiado para {target_vereadores}")
                except Exception as e:
                    print(f"Erro ao copiar vereadores.json: {e}")
    
    def load_config(self):
        """Carregar configuração"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.logo_path = data.get('logo_path', None)
                # Migração: Tenta ler session_name, senão session_number
                self.session_name = data.get('session_name', data.get('session_number', ''))
                self.city_name = data.get('city_name', '')
                self.active_list = data.get('active_list', 'presets/padrao.json')
                
                # Cores
                self.colors = data.get('colors', {
                    'primary': '#10a37f',
                    'secondary': '#1e4586',
                    'text_primary': '#ffffff',
                    'text_secondary': '#ffffff',
                    'background': '#1a1a2e'
                })
                
                # Arduino Checkpoint
                self.arduino_port = data.get('arduino_port', None)
                
                # Presets de Tempo (Minutos)
                self.time_presets = data.get('time_presets', [1, 2, 3, 5, 10, 15])
                
                # Tipo de tela secundária: 'plenario' | 'lateral'
                self.secondary_screen_type = data.get('secondary_screen_type', 'plenario')
                
                # Website da Lower Third
                self.website_url = data.get('website_url', 'www.sinop.mt.leg.br')
                
        except FileNotFoundError:
            self.logo_path = None
            self.session_name = ''
            self.city_name = ''
            self.active_list = 'presets/padrao.json'
            self.colors = {
                'primary': '#10a37f',
                'secondary': '#1e4586',
                'text_primary': '#ffffff',
                'text_secondary': '#ffffff',
                'background': '#1a1a2e'
            }
            self.arduino_port = None
            self.time_presets = [1, 2, 3, 5, 10, 15]
            self.secondary_screen_type = 'plenario'
            self.website_url = 'www.sinop.mt.leg.br'
            self.save_config()
    
    def save_config(self):
        """Salvar configuração"""
        data = {
            'logo_path': self.logo_path,
            'session_name': self.session_name, # Salva como name
            'city_name': self.city_name,
            'active_list': self.active_list,
            'colors': self.colors,
            'arduino_port': self.arduino_port,
            'time_presets': self.time_presets,
            'secondary_screen_type': self.secondary_screen_type,
            'website_url': getattr(self, 'website_url', 'www.sinop.mt.leg.br'),
        }
        print(f"DEBUG: Gravando JSON session_name='{self.session_name}'")
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def set_colors(self, primary, secondary, text_primary=None, text_secondary=None, background=None):
        """Definir cores do tema"""
        self.colors['primary'] = primary
        self.colors['secondary'] = secondary
        if text_primary:
            self.colors['text_primary'] = text_primary
        if text_secondary:
            self.colors['text_secondary'] = text_secondary
        if background:
            self.colors['background'] = background
        self.save_config()
        
    def get_colors(self):
        """Obter cores"""
        return self.colors
    
    def set_logo(self, logo_path):
        """Definir logo"""
        self.logo_path = logo_path
        self.save_config()
    
    def set_session_name(self, name):
        """Definir nome da sessão"""
        self.session_name = name
        self.save_config()
        
    def get_session_name(self):
        """Obter nome da sessão"""
        return self.session_name
        
    def set_city_name(self, name):
        """Definir nome da cidade"""
        self.city_name = name
        self.save_config()
        
    def get_city_name(self):
        """Obter nome da cidade"""
        return self.city_name
    
    # Aliases de compatibilidade
    def set_session_number(self, number):
        self.set_session_name(number)
        
    def get_session_number(self):
        return self.get_session_name()
    
    def set_active_list(self, list_path):
        """Definir lista de vereadores ativa"""
        self.active_list = list_path
        self.save_config()
        
    def get_logo(self):
        """Obter logo"""
        return self.logo_path
        
    def get_active_list(self):
        """Obter caminho da lista ativa"""
        if not self.active_list:
            return 'presets/padrao.json'
        return self.active_list
        
    def set_arduino_port(self, port):
        """Salvar porta do Arduino"""
        self.arduino_port = port
        self.save_config()
        
    def get_arduino_port(self):
        """Obter porta salva do Arduino"""
        return self.arduino_port

    def set_time_presets(self, presets):
        """Definir presets de tempo (lista de inteiros em minutos)"""
        self.time_presets = presets
        self.save_config()

    def get_time_presets(self):
        """Obter presets de tempo"""
        return self.time_presets

    def set_secondary_screen_type(self, screen_type: str):
        """Salvar tipo de tela secundária ('plenario' ou 'lateral')"""
        self.secondary_screen_type = screen_type
        self.save_config()

    def get_secondary_screen_type(self) -> str:
        """Obter tipo de tela secundária salvo"""
        return getattr(self, 'secondary_screen_type', 'plenario')

    def set_website_url(self, url: str):
        self.website_url = url
        self.save_config()

    def get_website_url(self) -> str:
        return getattr(self, 'website_url', 'www.sinop.mt.leg.br')

    def get_data_path(self, relative_path=None):
        """Retorna o caminho absoluto na pasta de dados do usuário"""
        if not relative_path:
            return self.config_dir
        return os.path.join(self.config_dir, relative_path)

    def get_bundle_path(self, relative_path=None):
        """Retorna o caminho absoluto na pasta do bundle (somente leitura)"""
        if not relative_path:
            return self.base_bundle_path
        return os.path.join(self.base_bundle_path, relative_path)
