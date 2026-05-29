# 🛠️ Manual de Hardware e Montagem - Sistema de Tribuna

Este documento descreve os componentes necessários e o diagrama de ligação para montar o sistema de controle automático de áudio da tribuna com segurança e eficiência.

> 📘 **Infográfico Interativo**: Para uma visualização mais rica, consulte o [Manual Interativo](./Manual_de_Hardware.html) incluído no projeto.

---

## 📋 Lista de Materiais Necessários

### 1. Computador Base
Para rodar o software de controle (Painel do Presidente):
*   **Sistema Operacional**: Windows 10 ou 11 (64 bits).
*   **Monitores**: Recomendado **2 telas** (uma para o operador, outra para a saída HDMI do plenário/projetor/OBS).
*   **Portas**: Pelo menos 1 porta USB disponível para o Arduino.

### 2. Kit de Automação (Corte de Áudio)
*   **Microcontrolador**: 
    *   1x **Arduino Uno R3** (com cabo USB A-B) **OU** 
    *   1x **Arduino Nano V3** (com cabo Mini-USB).
*   **Módulo Relé**:
    *   1x **Módulo Relé 5V de 2 Canais**.
    *   *Nota: O módulo deve suportar acionamento lógico de 5V.*
*   **Cabos de Conexão**:
    *   4x Cabos Jumper (Fêmea-Macho ou Macho-Macho dependendo do relé).

### 3. Cabeamento de Áudio
Você precisará interceptar o cabo que vai do microfone da tribuna para a mesa de som.
*   **Cabos de Áudio**: Conectores P10, XLR ou fios desencapados.
*   **Fios para Interceptação**: Fio paralelo simples.
*   **Componentes de Proteção (Opcional, mas recomendado)**:
    *   2x Capacitores **100nF** (Filtro Snubber) para eliminar estalos ("pop") ao acionar o relé.

---

## 🔌 Esquema de Ligação (Eletrônica)

### Conexão Arduino -> Módulo Relé
Ligue o Arduino ao Módulo Relé usando os Jumpers conforme a tabela abaixo. O código está configurado para usar os **Pinos Digitais 7 e 8**.

| Arduino (Pino) | Módulo Relé (Pino) | Função |
| :--- | :--- | :--- |
| **5V** | **VCC** / **V+** | Alimentação (+5V) |
| **GND** | **GND** / **V-** | Terra (Negativo) |
| **Pino 7** | **IN1** | Controle Canal 1 (Microfone 1) |
| **Pino 8** | **IN2** | Controle Canal 2 (Microfone 2) |

---

## 🔊 Esquema de Ligação de Áudio (FAIL-SAFE)

Para garantir a segurança do evento, utilizamos a lógica **"Normalmente Fechado" (NC)**. Isso significa que, sem energia, o contato fecha e o som passa.

**⚠️ Regra de Ouro:** Ligue SEMPRE nos terminais **COM** e **NC**.

### Diagrama de Áudio:
Você deve cortar apenas o **fio positivo** do sinal de áudio e passar pelo relé:

```text
[Microfone] ────── POSITIVO (+) ────────┐
                                        │
                                   ┌────▼────┐
                                   │  Relé   │
                                   │ COM  NC │  <-- O fio sai daqui
                                   └────┬────┘
                                        │
[Mesa de Som] <──── POSITIVO (+) ───────┘

* O fio TERRA/MALHA passa direto, sem cortar.
```

### Por que Fail-Safe?
1.  **Sem energia/USB desconectado**: Relé desliga → Contato NC fecha → **Som funciona**.
2.  **Sistema travou**: Relé desliga → Contato NC fecha → **Som funciona**.
3.  **Apenas quando o sistema manda "CORTAR"**: Relé liga → Contato NC abre → **Som mudo**.

---

## 💿 Como Gravar o Firmware no Arduino

Para que o Arduino receba os comandos do computador, você precisa gravar o código nele uma única vez.

### Passo 1: Instalar Arduino IDE
1.  Baixe a **Arduino IDE** no site oficial: [arduino.cc/en/software](https://www.arduino.cc/en/software).
2.  Instale e abra o programa.

### Passo 2: Configurar Placa
1.  Conecte o Arduino na USB do computador.
2.  No menu superior da IDE, vá em **Tools (Ferramentas) > Board** e selecione o modelo do seu Arduino (ex: "Arduino Uno").
3.  Vá em **Tools (Ferramentas) > Port** e selecione a porta COM que apareceu (ex: "COM3 (Arduino Uno)").

### Passo 3: Carregar o Código
1.  Na IDE, vá em **File > Open** e selecione o arquivo `arduino_relay_control.ino` que está na pasta deste projeto.
2.  Clique no botão **Verify** (ícone de ✔️) para conferir se está tudo certo.
3.  Clique no botão **Upload** (ícone de ➡️ seta para direita).
4.  Aguarde a barra inferior completar e a mensagem "Done uploading".

Seu Arduino está pronto para uso! Não precisa gravar novamente, a menos que mude o código.

---

## 🧪 Testes Finais

Antes do evento real, faça estes testes:
1.  **Teste do Desconectado**: Com o Arduino desconectado da USB, fale no microfone. O som DEVE sair.
2.  **Teste do Sistema**: Conecte o USB, abra o programa e clique em "Iniciar". O som deve sair. Clique em "Parar", o som deve cortar.
3.  **Teste de Pânico**: Com o som liberado pelo sistema, arranque o cabo USB do computador. O som DEVE continuar funcionando (graças ao sistema Fail-Safe).
