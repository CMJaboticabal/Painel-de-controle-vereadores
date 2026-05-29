# Sistema de Controle de Tribuna Parlamentar

Sistema profissional para gerenciamento de tempo de fala, apartes e exibição em telão para Câmaras Municipais. Desenvolvido em Python com interface moderna em PyQt6 e integração com Arduino para controle de hardware.

## 🚀 Funcionalidades Principais

*   **Painel do Presidente (Operador):** Interface intuitiva para controle total da sessão.
*   **Cronômetro de Orador:** Contagem regressiva com alertas visuais (Verde, Amarelo, Vermelho).
*   **Gestão de Apartes:** Controle de tempo adicional para apartes com cronômetro dedicado.
*   **Tela do Plenário (Telão):** Janela independente para exibição em projetores/TVs, mostrando orador atual, foto, partido e tempo.
*   **Integração com Hardware (Arduino):** Acionamento automático de relés para microfones ou luzes de bancada.
*   **Servidor Web Integrado:** API local e WebSocket para integração com OBS Studio (Lower Thirds) e tablets.
*   **Cadastro de Vereadores:** Gerenciamento fácil com fotos e dados partidários.

## �️ Requisitos do Sistema

*   Windows 10 ou 11 (64 bits)
*   Python 3.10 ou superior
*   Driver CH340 (para comunicação com Arduino, incluído na pasta do projeto)

## � Instalação e Configuração Inicial

1.  **Clone ou Baixe o Repositório:**
    Certifique-se de que todos os arquivos estejam em uma pasta acessível.

2.  **Instalação Automática:**
    Execute o arquivo `install.bat` com dois cliques.
    *   Este script criará o ambiente virtual Python `.venv`.
    *   Instalará todas as dependências necessárias automaticamente.

3.  **Configuração do Hardware (Opcional):**
    *   Conecte o Arduino via USB.
    *   O sistema detectará automaticamente a porta COM correta.
    *   Certifique-se de instalar o driver `CH34x_Install_Windows_v3_4.EXE` caso o Arduino não seja reconhecido.

## ▶️ Como Iniciar o Sistema

Para utilizar o sistema no dia a dia, siga estes passos simples:

1.  Abra a pasta do projeto.
2.  Execute o arquivo **`run.bat`** (clique duplo).
3.  Aguarde a inicialização:
    *   Uma janela de terminal se abrirá mostrando os logs de carregamento.
    *   A interface de controle (Painel do Presidente) abrirá automaticamente.
    *   A Tela do Plenário será projetada no segundo monitor (se disponível).

> **Nota:** Não feche a janela preta do terminal enquanto estiver usando o sistema, pois ela mantém o servidor e a aplicação rodando.

## 🖥️ Integração com OBS Studio (Transmissão)

O sistema fornece uma página web automática para uso em transmissões ao vivo (Lower Thirds):

1.  No OBS Studio, adicione uma fonte de "Navegador" (Browser Source).
2.  Na URL, insira: `http://localhost:5000/`
3.  Defina a largura e altura conforme sua transmissão (ex: 1920x1080).
4.  Ative "Atualizar navegador quando a cena se tornar ativa".

As informações do orador e tempo serão atualizadas em tempo real na transmissão.

## 📂 Estrutura de Arquivos Importantes

*   `main.py`: Código principal da aplicação Desktop.
*   `server.py`: Servidor Web/API para integrações.
*   `vereadores.json`: Banco de dados dos parlamentares.
*   `fotos/`: Diretório para armazenar as fotos dos vereadores (formato PNG/JPG).
*   `logs/`: Registros de funcionamento e erros para suporte.

## 🤝 Suporte

Em caso de dúvidas ou problemas, verifique os arquivos na pasta `logs/` ou entre em contato com o desenvolvedor.
