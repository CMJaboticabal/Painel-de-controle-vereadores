# 🚀 Guia Rápido de Início

## Instalação em 3 Passos

### 1️⃣ Instalar Dependências
```bash
# Clique duas vezes em:
install.bat
```

### 2️⃣ Configurar Arduino
1. Abra **Arduino IDE**
2. Abra `arduino_relay_control.ino`
3. Selecione **Tools > Board > Arduino Uno**
4. Selecione **Tools > Port > COM[X]**
5. Clique em **Upload** (→)

### 3️⃣ Executar Sistema
```bash
# Clique duas vezes em:
run.bat
```

---

## Uso Básico

### ▶️ Iniciar Sessão

1. **Selecione um vereador** na lista
2. **Escolha o tempo:**
   - Clique em um preset (3, 5, 10, 15, 20 min)
   - OU digite tempo customizado
3. **Clique em "▶️ Iniciar"**
   - ✅ Áudio abre automaticamente
   - ✅ Cronômetro inicia
   - ✅ Lower Third aparece em 10s

### ⏸️ Pausar

- Clique em **"⏸️ Pausar"**
- Áudio é cortado automaticamente
- Timer para
- Clique em **"▶️ Iniciar"** para retomar

### ⏹️ Parar

- Clique em **"⏹️ Parar"**
- Áudio é cortado
- Timer reseta
- Lower Third desaparece

---

## Configurar OBS

### Adicionar Lower Third

1. **Adicione fonte:** `Browser`
2. **URL:** `http://127.0.0.1:5000/`
3. **Largura:** `1920`
4. **Altura:** `1080`
5. **✅ Marque:** "Shutdown source when not visible"

### Testar

1. Inicie uma sessão no Painel
2. Aguarde 10 segundos
3. Lower Third deve aparecer no OBS

---

## Atalhos de Teclado

| Tecla | Ação |
|-------|------|
| `Espaço` | Play/Pause |
| `Esc` | Parar |
| `M` | Mute (futuro) |

---

## Verificar Status

### ✅ Tudo OK
```
✅ Arduino: Conectado
✅ WebSocket: Conectado
```

### ❌ Problemas

**Arduino Desconectado:**
1. Verifique cabo USB
2. Verifique porta COM no Device Manager
3. Reinstale driver CH340 (se clone)

**WebSocket Desconectado:**
1. Verifique se servidor está rodando
2. Verifique firewall (porta 5000)
3. Reinicie o sistema

---

## Adicionar Vereadores

Edite `vereadores.json`:

```json
{
    "id": 9,
    "nome": "Novo Vereador",
    "partido": "PARTIDO",
    "foto": null
}
```

Reinicie o sistema.

---

## Adicionar Fotos

1. Coloque foto em: `fotos/nome_vereador.jpg`
2. Edite `vereadores.json`:
   ```json
   "foto": "fotos/nome_vereador.jpg"
   ```
3. Reinicie o sistema

---

## Solução de Problemas Rápida

### Áudio não corta
1. Verifique conexões do relé
2. Teste com LED (deve acender/apagar)
3. Verifique cabo de áudio

### Lower Third não aparece
1. Teste URL no navegador: `http://127.0.0.1:5000/`
2. Verifique console (F12)
3. Limpe cache do OBS

### Timer não sincroniza
1. Verifique conexão WebSocket
2. Reinicie servidor
3. Recarregue página no OBS

---

## Suporte

📖 **Documentação Completa:** `README.md`  
🔧 **Especificação Técnica:** `ESPECIFICACAO_TECNICA.md`  
🐛 **Problemas:** Verifique logs no console

---

**Desenvolvido para Câmaras Municipais** 🏛️
