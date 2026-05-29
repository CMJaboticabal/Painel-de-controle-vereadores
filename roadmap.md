Roadmap: Sistema de Controle de Tribuna Parlamentar

Este documento estabelece as fases de desenvolvimento, tecnologias e arquitetura do sistema de controle de tempo e áudio.

1. Tecnologias Propostas

Core (Backend & Desktop)

Linguagem: Python 3.11+

Interface Desktop (Monitor 1 e 2): PyQt6 ou PySide6.

Motivo: Permite criar janelas independentes para cada monitor e gerenciar processos pesados sem travar a interface.

Servidor Web Interno: Flask + Flask-SocketIO.

Motivo: Responsável por servir a página da Lower Third para o OBS e garantir sincronia via WebSocket.

Comunicação & Hardware

Comunicação Serial: pyserial.

Microcontrolador: Arduino (Uno ou Nano).

Atuador: Módulo Relé 5V (para interrupção física do sinal de áudio).

Frontend (Lower Third)

Tecnologias: HTML5, CSS3 (Animações), JavaScript (Socket.io-client).

2. Arquitetura do Sistema

O sistema funcionará como um Processo Único com múltiplas saídas:

Monitor 1 (Operador): Painel de controle administrativo.

Monitor 2 (Plenário): Janela Fullscreen (Foto + Cronômetro).

Porta Serial (USB): Comando para o Relé do Arduino.

Servidor HTTP (Porta 5000): Stream de dados para a Lower Third Web.

3. Fases de Desenvolvimento

Fase 1: Fundação e Servidor Local (Semana 1)

[ ] Configuração do ambiente virtual Python.

[ ] Implementação do servidor Flask-SocketIO básico.

[ ] Criação do banco de dados local (vereadores.json) para armazenar nomes, partidos e caminhos das fotos.

[ ] Script de teste de comunicação Serial com o Arduino.

Fase 2: Hardware e Corte de Áudio (Semana 1)

[ ] Codificação do Firmware Arduino (.ino).

[ ] Montagem do circuito de teste com LED (simulando o relé).

[ ] Implementação da lógica de segurança: Se o software fechar, o relé deve (por padrão) cortar o som.

Fase 3: Interfaces Desktop (Semana 2)

[ ] Painel do Presidente (Monitor 1):

Listagem de vereadores.

Seletor de tempo pré-definido.

Botões Play/Pause/Stop.

[ ] Painel do Plenário (Monitor 2):

Lógica de "Janela Secundária" detectando o segundo monitor automaticamente.

Design responsivo para exibir a foto do vereador em alta resolução.

Fase 4: Lower Third Web (Semana 2)

[ ] Desenvolvimento da página HTML/CSS transparente.

[ ] Implementação do Buffer de Delay:

O evento de início chega via Socket.

O JavaScript inicia um setTimeout(10000) antes de disparar a animação de entrada.

Fase 5: Integração e Testes (Semana 3)

[ ] Teste de sincronia: Garantir que o cronômetro do Plenário e da Lower Third terminem juntos, apesar do atraso na entrada da imagem.

[ ] Teste de estresse: Simular quedas de conexão USB e reconexão automática do Arduino.

[ ] Ajuste fino das animações da Lower Third.

4. Requisitos de Hardware (Lista de Compras)

Arduino Uno ou Nano + Cabo USB.

Módulo Relé 5V de 1 Canal.

Cabo de Áudio (XLR ou P10) para confecção do "Jumper" de corte.

Caixa de Proteção para o Arduino (evitar interferências eletromagnéticas próximas à mesa de som).

5. Próximos Passos Imediatos

Definir o layout visual da Lower Third (cores, fontes da câmara).

Validar a porta COM do Arduino no computador principal.

Iniciar o desenvolvimento do Servidor Python Base.