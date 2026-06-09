# SENAI_Work
Trabalho de conclusão de curso do senai utilizando a placaBitDogLab (dpscorrijo erro ortogrficos daaqui)
# 🛠️ Projeto 3 — Sistema de Controle de Malha Fechada (PID) com BitDogLab

Este repositório contém a implementação de um controlador **Proporcional-Integral-Derivativo (PID)** em tempo real estrito para a placa de desenvolvimento **BitDogLab** (baseada no microcontrolador RP2040). O sistema realiza a leitura de alvos (Setpoint) e medições (Variável de Processo) através do Joystick analógico e atua dinamicamente sobre uma matriz de LEDs WS2812B e um display OLED SSD1306.

---

## 📺 1. Interface Gráfica: Como Interpretar o Visor OLED

O layout do display OLED de $128 \times 64$ pixels foi reestruturado para operar como um painel de instrumentação industrial simétrico e moderno, substituindo texto puro por barras gráficas reais.

```text
+-----------------------------------+
| MONITOR PID                  45us | <- Título e Tempo de Execução (WCET)
|-----------------------------------|
| SP: 2048          PV: 2048        | <- Valores Digitais de Entrada (0-4095)
| E: +   0          U:  1638        | <- Erro do Sistema e Sinal de Controle
|                                   |
| S [███████████░░░░░░░░░░░░░]      | <- Barra Gráfica Dinâmica do Setpoint
| P [███████████░░░░░░░░░░░░░]      | <- Barra Gráfica Dinâmica da Realimentação
|-----------------------------------|
|    [Kp]   Ki   Kd                 | <- Indicador do Ganho Selecionado para Ajuste
+-----------------------------------+
```

---

## 📋 Descrição dos Campos

Tela Campo Significado Descrição Física / Atuação MONITOR PIDStatus do SistemaIndica que a malha de controle está ativa e operando de forma estável.XXus (WCET)Worst-Case Execution TimeO pior tempo de execução gasto para calcular a matemática do PID. Valores normais abaixo de 50us provam a alta eficiência do sistema frente ao loop total de 20 ms ($20.000\mu s$).SPSetpoint (Alvo)Valor digital (0 a 4095) desejado para o sistema. Controlado pelo Joystick no Eixo X (Esquerda/Direita).PVProcess VariableA medição atual da planta (0 a 4095). Controlada pelo Joystick no Eixo Y (Cima/Baixo).EErro InstantâneoA diferença matemática exata entre o alvo e a medição ($E = SP - PV$). O objetivo do PID é zerar este valor.USinal de ControleA força gerada pelo algoritmo PID (0 a 4095). Traduz-se no nível de preenchimento da matriz de LEDs.S / PBarras GráficasRetângulos dinâmicos desenhados com bordas (rect) e preenchimento (fill_rect) nativos do driver para dar noção real de escala (0 a 100%).[Kp] Ki KdAjuste AtivoIdentifica qual parâmetro será alterado ao pressionar os botões físicos.

---


## 🧪 2. Guia de Teste Eficiente (Passo a Passo na Placa) 

Com o mapeamento por pixels ativado, a matriz de LEDs funciona como um equalizador dinâmico, subindo e descendo de forma fluida conforme a força $U$ muda, e trocando de cor com base no erro. Execute a seguinte sequência de testes na bancada:Teste A: Verificação de Erro Zero (Estabilidade)Ação: Solte o Joystick e deixe-o completamente centralizado em repouso.No OLED: As leituras de SP e PV estarão alinhadas próximas de 2048. As barras gráficas S e P ficam travadas exatamente no meio da tela. O erro E estabiliza-se muito perto de 0.Na Matriz de LEDs: Como o sistema está em equilíbrio perfeito (Erro $\le 150$), a matriz exibe um bloco sólido de 8 a 12 LEDs acesos na base, brilhando em Verde Suave. O visual fica estático, sem oscilações abruptas ou apagões.Teste B: Resposta a Degrau Positivo (Saturação Máxima)Ação: Empurre o Joystick do Setpoint (Eixo X) totalmente para a direita e mantenha o eixo Y parado no centro.No OLED: O valor de SP salta para 4095 e a barra S preenche a tela inteira. O erro E dispara para aproximadamente +2047.Na Matriz de LEDs: O erro violou imediatamente o limite configurado (ERR_LIMIAR = 400). Toda a matriz responde instantaneamente mudando de cor para Vermelho Alerta e acendendo todos os 25 LEDs com brilho máximo, provando que o termo Proporcional aplicou força total de correção ($U = 4095$).No Buzzer: Após persistir por 500 ms nessa condição crítica, o alarme sonoro começa a apitar de forma intermitente.Teste C: Correção Manual do Erro (Fechamento de Malha)Ação: Com o alarme tocando, use a outra mão para mover gradualmente o Joystick da Realimentação (Eixo Y) totalmente para cima.No OLED: A barra inferior P crescerá até alcançar a barra S. O valor digital de E cai rapidamente em direção a zero.Na Matriz de LEDs (Efeito Equalizador): À medida que você aproxima o PV do alvo, o PID diminui a força $U$. Você verá a quantidade de LEDs acesos descer suavemente (de 25 para cerca de 10) e a cor transicionar de forma limpa, sem piscar:$\text{Vermelho (Erro }$ > $400\text{)}$ $\rightarrow \text{Amarelo (Erro Médio)}$ $\rightarrow $\text{Verde Suave (Erro }$ $\le 150\text{)}$ No Buzzer: Silencia instantaneamente assim que o erro desce abaixo de 400 unidades.

---


## 🎛️ 3. Sintonização Prática dos Ganhos

O firmware gerencia o tempo de forma não-bloqueante, permitindo alterar os parâmetros do PID em tempo real. Pressione e segure o Botão B (Hold de 0.6s) para alternar entre os ganhos no OLED e use o Botão A (+) ou Botão B (Toque rápido para -) para ajustar os valores:🟩 Configuração Recomendada: Controlador PID CompletoValores: Kp = 0.900 | Ki = 0.040 | Kd = 0.015 Comportamento: É o equilíbrio ideal para a BitDogLab. O sistema reage de forma ágil aos comandos manuais através do ganho Proporcional ($K_p$), limpa os erros residuais de aproximação usando o termo Integral ($K_i$) e utiliza a ação Derivativa ($K_d$) como um amortecedor para suavizar a transição de cores e luzes, eliminando trepidações na matriz de LEDs.

---


## Outros Cenários de Análise:

  - Controle P Puro (Kp=1.200, Ki=0, Kd=0): Resposta instantânea, mas os LEDs nunca atingem o Verde Estável devido ao erro de regime permanente.
  - Controle PI (Kp=0.850, Ki=0.080, Kd=0): Elimina o erro residual perfeitamente, mas a transição de cores pode oscilar (overshoot) caso os joysticks sejam movidos de forma brusca.

# BitDogLab — 3 Projetos para Técnico em Eletrônica
## Guia completo de instalação e uso no VS Code

---

## Estrutura de arquivos

```
bitdoglab/
│
├── lib/                        ← Bibliotecas (copiar para a raiz da placa)
│   ├── ssd1306.py              ← Driver OLED SSD1306 via I2C (feito do zero)
│   ├── ws2812b.py              ← Driver WS2812B via PIO do RP2040
│   ├── bitdoglab.py            ← Utilitários: Button, Joystick, Buzzer, LEDRGB
│   └── dsp.py                  ← FFT, média móvel, oversampling, PID digital
│
├── projeto1/
│   └── main.py                 ← Analisador de Sinais ADC + Display OLED
│
├── projeto2/
│   └── main.py                 ← Osciloscópio FFT + LEDs RGB + Buzzer
│
└── projeto3/
    └── main.py                 ← Controlador PID Malha Fechada
```

---

## Como enviar para a placa (VS Code + Pymakr)

### 1. Instalar extensão Pymakr no VS Code
- Abra o VS Code
- Extensions (Ctrl+Shift+X) → busque "Pymakr" → instalar
- Reinicie o VS Code

### 2. Conectar a BitDogLab
- Conecte via USB (cabo micro-USB)
- Segure o botão BOOTSEL enquanto conecta pela primeira vez para
  instalar o MicroPython (arraste o .uf2 para a unidade que aparecer)
- Download do firmware: https://micropython.org/download/rp2-pico/

### 3. Estrutura na placa (sistema de arquivos da RP2040)
Copie os arquivos seguindo esta hierarquia na raiz da placa:

```
/ (raiz da placa)
├── lib/
│   ├── ssd1306.py
│   ├── ws2812b.py
│   ├── bitdoglab.py
│   └── dsp.py
└── main.py              ← cole aqui o projeto que quiser executar
```

### 4. Upload via Pymakr
- Clique em "Connect Device" na barra inferior do VS Code
- Clique com botão direito no arquivo → "Upload to Device"
- Ou use o botão "Sync Project to Device"

### 5. Alternativa: Thonny IDE
- File → Open → "This Computer" → selecione o arquivo
- File → Save As → "MicroPython device"
- Salve na pasta /lib/ para as bibliotecas e como /main.py para o projeto

---

## Pinout resumido — BitDogLab

| Função           | Pino GPIO | Observação                      |
|------------------|-----------|---------------------------------|
| Joystick X       | GP27      | ADC1 — eixo horizontal          |
| Joystick Y       | GP26      | ADC0 — eixo vertical            |
| Botão joystick   | GP22      | Pull-up interno                 |
| Botão A          | GP5       | Pull-up interno, ativo LOW      |
| Botão B          | GP6       | Pull-up interno, ativo LOW      |
| Buzzer           | GP10      | PWM                             |
| LED RGB R        | GP13      | PWM                             |
| LED RGB G        | GP11      | PWM                             |
| LED RGB B        | GP12      | PWM                             |
| Matriz WS2812B   | GP7       | PIO state machine               |
| OLED SDA (I2C1)  | GP14      | 400 kHz                         |
| OLED SCL (I2C1)  | GP15      | 400 kHz                         |
| Mic PDM Data     | GP2       | PIO (não usado neste projeto)   |
| Mic PDM Clock    | GP3       | PIO                             |

---

## Projeto 1 — Analisador de Sinais ADC

### O que faz
Lê o joystick (X e Y) via ADC 12 bits, aplica dois filtros digitais e
exibe tudo em tempo real no display OLED. 4 modos de visualização.

### Modos (Botão A para trocar)
| Modo | Nome         | Descrição                                        |
|------|--------------|--------------------------------------------------|
| 0    | RAW          | Valores brutos 0–4095 + tensão em Volts          |
| 1    | MEDIA MOV    | Compara bruto vs média móvel (N=16)              |
| 2    | OVERSAMPLE   | Compara bruto vs oversampling (N=16 → +2 bits)   |
| 3    | OSCILOSCOPIO | Gráfico do histórico do eixo X (96 pontos)       |

### Botão B
Calibra o centro do joystick (mantenha o joystick solto ao pressionar).

### Experimentos sugeridos
1. Observe o ruído no Modo 0 movendo o joystick lentamente
2. Compare os valores bruto vs filtrado no Modo 1 — o filtro suaviza
3. No Modo 2, observe que o oversampling reduz a variação nos dígitos finais
4. No Modo 3, gire o joystick rapidamente e observe a senoide no gráfico

---

## Projeto 2 — Osciloscópio de Áudio com FFT

### O que faz
Gera sinais sintéticos (ou lê o ADC), aplica FFT de 64 pontos com
janela de Hann, divide o espectro em 5 bandas e exibe como VU meter
na matriz de LEDs 5×5. O buzzer toca a frequência dominante.

### Modos (Botão A para trocar)
| Modo | Nome       | Descrição                                         |
|------|------------|---------------------------------------------------|
| 0    | SINTÉTICO  | Senoide pura gerada internamente                  |
| 1    | ADC EXT.   | Joystick X como entrada de sinal variável         |
| 2    | ALIASING   | Fs reduzida para 1500 Hz — demonstra aliasing     |

### Botão B (Modo sintético)
Troca a frequência do sinal: 200 → 500 → 1000 → 2000 → 3500 Hz

### Experimentos sugeridos
1. No Modo 0, troque as frequências e observe qual coluna de LED acende
2. Compare graves (200 Hz) → coluna esquerda; agudos (3500 Hz) → direita
3. No Modo 2 com sinal de 2000 Hz (acima de Nyquist de 750 Hz):
   o aliasing fará o sinal aparecer na faixa errada — fenômeno real!
4. Discuta o Teorema de Nyquist-Shannon: Fs ≥ 2 × Fmax

### Cores das bandas na matriz de LEDs
| Coluna | Banda        | Faixa      | Cor      |
|--------|-------------|------------|----------|
| 0      | Graves      | 20–300 Hz  | Azul     |
| 1      | Médios-     | 300–800 Hz | Verde    |
| 2      | Médios      | 800–2 kHz  | Amarelo  |
| 3      | Médios+     | 2–5 kHz    | Laranja  |
| 4      | Agudos      | 5–10 kHz   | Vermelho |

---

## Projeto 3 — Controlador PID Malha Fechada

### O que faz
Implementa um PID digital completo. Joystick X = setpoint (desejado).
Joystick Y = realimentação (simula o sensor da planta). Os LEDs são
a saída da planta controlada. O OLED monitora SP, PV, erro, u e WCET.

### Controles
| Ação             | Botão                                          |
|------------------|------------------------------------------------|
| Incrementa ganho | A (tap)                                        |
| Decrementa ganho | B (tap — pressão curta <600ms)                 |
| Troca ganho sel. | B (hold — mantém pressionado >600ms)           |
| Ver ganhos       | Qualquer ajuste exibe tela de ganhos automát.  |

### Experimentos de resposta ao degrau
1. **Apenas Kp** (Ki=0, Kd=0): mova o joystick X bruscamente.
   Observe: quanto maior Kp, mais rápido mas mais oscilatório.

2. **Kp + Ki**: adicione Ki pequeno (0.01).
   Observe: o erro em regime permanente é eliminado com o tempo.

3. **Kp + Ki + Kd**: adicione Kd.
   Observe: o amortecimento reduz o sobressinal e a oscilação.

4. **Perturbação manual**: com o sistema em equilíbrio, mova o
   joystick Y (sensor) para simular uma perturbação externa.
   O PID deve compensar e retornar ao setpoint automaticamente.

5. **Anti-windup**: sature a saída (setpoint máximo por 5 s) e
   observe que o integrador não explode graças ao clamping.

### Análise de WCET
- O display mostra o WCET máximo do loop em µs
- Meta: WCET < 20000 µs (< 1 período de amostragem de 20 ms)
- Se aparecer "AVISO: loop lento!" no terminal, reduza a frequência
  de atualização do OLED ou simplifique o cálculo

### Ganhos sugeridos para início
```
Kp = 0.8    (proporcional — resposta imediata)
Ki = 0.05   (integral — elimina erro permanente devagar)
Kd = 0.02   (derivativo — amortece oscilações)
```

---

## Solução de problemas frequentes

### Display OLED não aparece
- Verifique SDA=GP14, SCL=GP15
- Confirme endereço I2C: rode no REPL:
  ```python
  from machine import I2C, Pin
  i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
  print(i2c.scan())  # deve mostrar [60] que é 0x3C em decimal
  ```

### LEDs não acendem / cores erradas
- Verifique pino GP7
- O driver WS2812B usa PIO state machine 0 — se outro código usar
  a mesma SM, mude o parâmetro sm_id=1 na instância do WS2812B

### Botões não respondem
- Pinos GP5 e GP6 com pull-up interno — certifique-se de que nenhum
  outro código reconfigurou esses pinos

### ImportError: no module named 'lib.ssd1306'
- A pasta /lib/ deve estar na raiz da placa, não numa subpasta
- Verifique com o REPL: import os; print(os.listdir('/lib'))

### Joystick lê valores errados
- GP26 e GP27 são os pinos ADC do joystick
- Se os valores estiverem invertidos (X lendo Y e vice-versa),
  troque PIN_JOY_X e PIN_JOY_Y em lib/bitdoglab.py

