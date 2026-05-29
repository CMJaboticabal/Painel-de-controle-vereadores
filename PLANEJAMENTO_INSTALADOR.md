# Planejamento: Criação do Instalador e Executável (.exe)

Este documento detalha o processo para transformar o **Sistema de Controle de Tribuna** (Python) em um software Windows instalável e independente.

## 🛠️ Ferramentas Necessárias
Utilizaremos ferramentas padrão da indústria para garantir compatibilidade e profissionalismo:
1.  **PyInstaller**: Para converter os scripts Python (.py) em executável (.exe).
2.  **Inno Setup Compiler**: Para criar o instalador (.msi/.exe) que o usuário final irá baixar e instalar (wizard de "Avançar > Avançar > Concluir").

---

## 📋 Passo 1: Preparação do Ambiente
Antes de gerar o executável, o código precisa estar pronto para rodar "congelado" (frozen).

### Tarefas:
- [ ] **Verificar Caminhos de Arquivos**: O código deve usar caminhos relativos robustos (`sys._MEIPASS` quando congelado) para acessar imagens, templates e JSONs. Atualmente, o código usa `os.path.dirname(__file__)`, que precisará de ajuste para funcionar dentro do executável.
- [ ] **Multiprocessing**: Como usamos `multiprocessing` para o servidor Flask, precisamos adicionar `multiprocessing.freeze_support()` logo no início do `main.py`.
- [ ] **Assets**: Listar todos os arquivos não-Python que precisam ir junto:
    - `templates/` (HTML do Lower Third)
    - `fotos/` (Fotos dos vereadores - pasta padrão)
    - `presets/` (Listas salvas)
    - `*.json` (Configs iniciais)
    - Ícone do aplicativo (.ico)

---

## 🏗️ Passo 2: Criação do Executável (PyInstaller)
Criaremos um arquivo de especificação (`build.spec`) para automatizar o processo.

### Estrutura do Build:
Como o sistema tem dois "processos" (GUI principal e Servidor Flask), a melhor abordagem é **um único executável** que gerencia o subprocesso internamente, ou dois executáveis se a complexidade for alta.
*Recomendação*: **Executável Único (`PainelTribuna.exe`)** que inicia a thread do servidor internamente.

### Comando Base (Rascunho):
```bash
pyinstaller --noconfirm --onedir --windowed --name "PainelTribuna" ^
    --add-data "templates;templates" ^
    --add-data "fotos;fotos" ^
    --add-data "presets;presets" ^
    --add-data "vereadores.json;." ^
    --add-data "session_config.json;." ^
    --icon "assets/app_icon.ico" ^
    --hidden-import "engineio.async_drivers.threading" ^
    main.py
```

### O que precisa ser feito:
1.  Criar o arquivo `build_exe.bat` para rodar o comando acima de forma reprodutível.
2.  Testar o `.exe` gerado na pasta `dist/` em um ambiente limpo (sem Python instalado) para garantir que ele sobe o servidor Flask e conecta ao Arduino.

---

## 📦 Passo 3: Criação do Instalador (Inno Setup)
O Inno Setup pegará a pasta gerada pelo PyInstaller e criará um arquivo setup único (`Instalador_PainelTribuna_v1.0.exe`).

### Funcionalidades do Instalador:
-   **Assistente de Instalação**: Português Brasileiro.
-   **Atalhos**: Criar atalho na Área de Trabalho e Menu Iniciar.
-   **Permissões**: Solicitar permissão de Administrador (necessário para serial/arduino as vezes).
-   **Firewall**: Adicionar regras para liberar a porta 5000 (Opcional, mas recomendado).
-   **Uninstaller**: Remover arquivos corretamente.

### Script do Inno Setup (`setup_script.iss`):
Precisaremos criar este script que define:
-   `AppName`, `AppVersion`, `AppPublisher`.
-   `DefaultDirName` (ex: `{autopf}\TribunaParlamentar`).
-   Arquivos a incluir (Todo o conteúdo de `dist/PainelTribuna`).

---

## 🔄 Fluxo de Trabalho (Pipeline)
Quando formos executar este plano, seguiremos esta ordem:

1.  **Adaptação do Código**:
    -   Ajustar `main.py` e `server.py` para detecção correta de caminhos (`def get_resource_path...`).
2.  **Geração do Executável**:
    -   Rodar PyInstaller.
    -   Validar funcionamento da pasta `dist`.
3.  **Empacotamento**:
    -   Compilar script do Inno Setup.
    -   Gerar o Instalador final.

## 📝 Próximos Passos Imediatos para o Usuário
1.  **Instalar o PyInstaller**: `pip install pyinstaller`.
2.  **Baixar Inno Setup**: Instalar o software "Inno Setup Compiler" no Windows.
3.  **Criar Ícone**: Precisamos de um arquivo `.ico` para o aplicativo.

---
*Este plano garante que o software final seja profissional, fácil de distribuir e fácil de instalar para o cliente final.*
