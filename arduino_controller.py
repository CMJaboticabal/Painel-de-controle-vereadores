import serial
import serial.tools.list_ports
import time
import threading

class ArduinoController:
    """Controlador para comunicação Serial com Arduino"""
    
    def __init__(self):
        self.serial = None
        self.port = None
        self.is_connected = False
        self.on_connection_change = None # Callback function (bool, port_name)
        self.lock = threading.Lock()
        
    def find_arduino(self):
        """Tenta encontrar uma porta serial com Arduino conectado"""
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            # Lógica simples: tenta conectar em portas com descrição típica ou todas COM disponíveis
            # Em Windows, Arduinos geralmente aparecem como "USB Serial Device" ou "Arduino Uno"
            if "Arduino" in port.description or "USB Serial" in port.description:
                return port.device
        
        # Se não achou por nome, retorna a primeira COM disponível (fallback)
        if ports:
            return ports[0].device
            
        return None

    def connect(self, port_name=None):
        """Conecta ao Arduino (Automaticamente ou em Porta Específica)"""
        with self.lock:
            if self.is_connected:
                return True
                
            port = port_name if port_name else self.find_arduino()
            
            if not port:
                print("Nenhum Arduino encontrado.")
                if self.on_connection_change:
                    self.on_connection_change(False, None)
                return False
                
            try:
                self.serial = serial.Serial(port, 9600, timeout=1)
                time.sleep(2) # Aguarda inicialização do Arduino (reset)
                
                self.port = port
                self.is_connected = True
                print(f"Arduino conectado em {port}")
                
                if self.on_connection_change:
                    self.on_connection_change(True, port)
                    
                return True
            except Exception as e:
                print(f"Erro ao conectar Arduino em {port}: {e}")
                self.is_connected = False
                if self.on_connection_change:
                    self.on_connection_change(False, None)
                return False
    
    def keep_alive(self):
        """Mantém a conexão serial ativa (Envia pulso simples)"""
        # Envia um caractere vazio (newline) apenas para manter o link ativo
        # Isso evita que alguns arduinos entrem em idle ou que o watchdog do firmware desligue o relé
        try:
            with self.lock:
                if self.is_connected and self.serial:
                    self.serial.write(b'\n')
        except Exception:
            pass # Ignorar erros no keepalive para não spanar logs

    def disconnect(self):
        """Desconecta do Arduino"""
        with self.lock:
            if self.serial and self.serial.is_open:
                self.serial.close()
            
            self.serial = None
            self.is_connected = False
            self.port = None
            
            if self.on_connection_change:
                self.on_connection_change(False, None)

    def send_command(self, command):
        """Envia um comando para o Arduino"""
        with self.lock:
            if not self.is_connected or not self.serial:
                print(f"Erro: Tentativa de enviar comando '{command}' sem conexão.")
                # Tenta reconectar automaticamente
                if not self.connect():
                    return False
            
            try:
                # Envia comando com quebra de linha
                cmd_str = f"{command}\n"
                self.serial.write(cmd_str.encode('utf-8'))
                print(f"Comando enviado Arduino: {command}")
                return True
            except Exception as e:
                print(f"Erro ao enviar comando serial: {e}")
                self.disconnect() # Assume desconexão em erro de escrita
                return False

    def open_audio(self):
        """
        Liberar áudio.
        Lógica Invertida para Relé NF (Normalmente Fechado):
        Envia '0' para DESLIGAR o relé, permitindo que o contato repouse em Fechado (Som ON).
        """
        self.send_command('0')

    def cut_audio(self):
        """
        Cortar áudio.
        Lógica Invertida para Relé NF (Normalmente Fechado):
        Envia '1' para LIGAR o relé, abrindo o contato NF (Som OFF).
        """
        self.send_command('1')

    def check_connection(self):
        """Verifica se a porta ainda está acessível"""
        if not self.port:
            return False
        
        # Modo simples: tentar achar a porta na lista novamente
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return self.port in ports

    def list_available_ports(self):
        """Retorna lista de portas COM disponíveis como dicionários"""
        return [{'device': p.device, 'description': p.description} for p in serial.tools.list_ports.comports()]
