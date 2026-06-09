# =============================================================================
#  PROJETO 1 — Analisador de Sinais com ADC e Display OLED
#  BitDogLab | MicroPython | VS Code + Pymakr / Thonny
# =============================================================================
#
#  DESCRIÇÃO:
#      Lê os eixos X e Y do joystick analógico via ADC 12 bits,
#      aplica filtragem digital (média móvel e oversampling) e exibe
#      os valores em tempo real no display OLED 128×64 via I2C.
#      Os botões A e B alternam entre modos de visualização.
#
#  CONCEITOS ABORDADOS:
#      - Conversão analógico-digital (ADC 12 bits, 0–4095)
#      - Ruído de ADC e técnicas de filtragem (média móvel, oversampling)
#      - Protocolo I2C (driver SSD1306)
#      - Resistores pull-up internos do RP2040
#      - Zona morta (dead zone) em joysticks
#      - Polling vs interrupção para leitura de botões
#
#  MAPEAMENTO DE PINOS (BitDogLab):
#      Joystick X  → GP27 (ADC1)
#      Joystick Y  → GP26 (ADC0)
#      Botão A     → GP5  (pull-up interno, ativo LOW)
#      Botão B     → GP6  (pull-up interno, ativo LOW)
#      OLED SDA    → GP14 (I2C1)
#      OLED SCL    → GP15 (I2C1)
#
#  ESTRUTURA DE ARQUIVOS:
#      /lib/ssd1306.py   — driver do display OLED
#      /lib/bitdoglab.py — utilitários (Button, Joystick, Buzzer)
#      /lib/dsp.py       — filtragem digital (MovingAverage, oversample)
#      /projeto1/main.py — este arquivo
#
#  MODOS DE VISUALIZAÇÃO (alterne com botão A):
#      Modo 0 — Valores brutos X e Y + barras de progresso
#      Modo 1 — Valores filtrados (média móvel N=16) vs brutos
#      Modo 2 — Valores por oversampling (N=16 amostras) vs brutos
#      Modo 3 — Gráfico de osciloscópio (histórico do eixo X)
#
#  BOTÃO B: calibra o ponto central do joystick (com joystick solto)
# =============================================================================

from machine import I2C, Pin, ADC
import time
import sys
import os

# Adiciona /lib ao path de importação
sys.path.insert(0, "/lib")

from ssd1306  import SSD1306_I2C
from bitdoglab import Button, Joystick, Buzzer, PIN_I2C_SDA, PIN_I2C_SCL
from dsp      import MovingAverage, oversample

# ---------------------------------------------------------------------------
# Configuração de hardware
# ---------------------------------------------------------------------------
i2c  = I2C(1, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=400_000)
oled = SSD1306_I2C(128, 64, i2c)

joy  = Joystick()
btn_a = Button(5)   # Botão A — troca modo
btn_b = Button(6)   # Botão B — calibrar joystick
buz  = Buzzer()

# Filtros de média móvel para X e Y
filt_x = MovingAverage(size=16)
filt_y = MovingAverage(size=16)

# Buffer do osciloscópio (histórico de 128 pontos do eixo X)
SCOPE_LEN   = 96
scope_buf   = [2048] * SCOPE_LEN
scope_idx   = 0

# Estado do programa
modo        = 0
TOTAL_MODOS = 4
NOMES_MODOS = ["RAW", "MEDIA MOV", "OVERSAMPLE", "OSCILOSCOPIO"]

# Timestamps para cálculo de taxa de atualização
t_ultimo    = time.ticks_ms()
fps         = 0
frame_count = 0

# ---------------------------------------------------------------------------
# Funções auxiliares de desenho
# ---------------------------------------------------------------------------

def draw_modo_0(x_raw, y_raw, fx, fy):
    """Modo 0: valores brutos com barras de progresso."""
    oled.fill(0)
    oled.text("MODO: RAW ADC", 0, 0)
    oled.line(0, 10, 127, 10, 1)
    # Eixo X
    oled.text("X:{:4d}".format(x_raw), 0, 14)
    oled.bar(40, 14, 85, 8, x_raw, 4095)
    # Eixo Y
    oled.text("Y:{:4d}".format(y_raw), 0, 26)
    oled.bar(40, 26, 85, 8, y_raw, 4095)
    # Tensão estimada (0–3,3 V)
    vx = x_raw * 3.3 / 4095
    vy = y_raw * 3.3 / 4095
    oled.text("Vx={:.2f}V".format(vx), 0, 40)
    oled.text("Vy={:.2f}V".format(vy), 65, 40)
    # FPS
    oled.text("{}fps".format(fps), 90, 56)
    oled.show()


def draw_modo_1(x_raw, y_raw, fx, fy):
    """Modo 1: comparação bruto vs média móvel."""
    oled.fill(0)
    oled.text("MEDIA MOVEL N=16", 0, 0)
    oled.line(0, 10, 127, 10, 1)
    # Linha de cabeçalho
    oled.text("     BRUTO  FILTRO", 0, 13)
    oled.line(0, 22, 127, 22, 1)
    # X
    oled.text("X  {:4d}  {:4d}".format(x_raw, int(fx)), 0, 25)
    # Diferença
    diff_x = abs(x_raw - int(fx))
    oled.text("dX={}".format(diff_x), 88, 25)
    # Y
    oled.text("Y  {:4d}  {:4d}".format(y_raw, int(fy)), 0, 36)
    diff_y = abs(y_raw - int(fy))
    oled.text("dY={}".format(diff_y), 88, 36)
    # Barra comparativa do eixo X
    oled.text("Bruto", 0, 48)
    oled.bar(38, 48, 88, 6, x_raw, 4095)
    oled.text("Filt.", 0, 56)
    oled.bar(38, 56, 88, 6, int(fx), 4095)
    oled.show()


def draw_modo_2(x_raw, y_raw, x_over, y_over):
    """Modo 2: comparação bruto vs oversampling."""
    oled.fill(0)
    oled.text("OVERSAMPLING N=16", 0, 0)
    oled.line(0, 10, 127, 10, 1)
    oled.text("     BRUTO  OVERS.", 0, 13)
    oled.line(0, 22, 127, 22, 1)
    oled.text("X  {:4d}  {:4d}".format(x_raw, x_over), 0, 25)
    oled.text("dX={}".format(abs(x_raw - x_over)), 88, 25)
    oled.text("Y  {:4d}  {:4d}".format(y_raw, y_over), 0, 36)
    oled.text("dY={}".format(abs(y_raw - y_over)), 88, 36)
    # Mostra resolução efetiva aprimorada
    # log2(16) = 4 → +2 bits de resolução efetiva
    oled.text("Resolucao efetiva:", 0, 48)
    oled.text("12+2 = 14 bits", 0, 56)
    oled.show()


def draw_modo_3(x_raw):
    """Modo 3: osciloscópio — gráfico do histórico do eixo X."""
    global scope_buf, scope_idx
    # Insere nova amostra no buffer circular
    scope_buf[scope_idx] = x_raw
    scope_idx = (scope_idx + 1) % SCOPE_LEN

    oled.fill(0)
    oled.text("OSCILOSCOPIO X", 0, 0)
    # Eixo horizontal
    oled.line(0, 10, SCOPE_LEN, 10, 1)
    # Eixo vertical
    oled.line(0, 10, 0, 63, 1)
    # Plota amostras
    for i in range(SCOPE_LEN):
        idx = (scope_idx + i) % SCOPE_LEN
        val = scope_buf[idx]
        # Mapeia 0–4095 → 10–63 (área do gráfico = 53 pixels)
        y = 63 - int(val * 53 / 4095)
        oled.pixel(i, y, 1)
    # Valor atual e indicador de posição
    oled.text("{:4d}".format(x_raw), 98, 56)
    # Linha de centro
    oled.line(0, 36, SCOPE_LEN, 36, 1)
    # Labels dos eixos
    oled.text("3V3", 100, 10)
    oled.text("0V ", 100, 55)
    oled.show()


def splash_screen():
    """Tela de boas-vindas com instruções."""
    oled.fill(0)
    oled.text_center("ANALISADOR ADC", 5)
    oled.text_center("BitDogLab v1.0", 18)
    oled.line(0, 28, 127, 28, 1)
    oled.text("A = Troca modo", 5, 32)
    oled.text("B = Calibrar joy", 5, 42)
    oled.text_center("Iniciando...", 54)
    oled.show()
    buz.beep(2, freq=880, duration_ms=80)
    time.sleep_ms(2000)


def calibrate_screen():
    """Exibe mensagem durante calibração."""
    oled.fill(0)
    oled.text_center("CALIBRANDO", 20)
    oled.text_center("Solte o joystick", 35)
    oled.show()
    time.sleep_ms(500)
    cx, cy = joy.calibrate()
    oled.fill(0)
    oled.text_center("CALIBRADO!", 20)
    oled.text("Cx={}".format(cx), 10, 35)
    oled.text("Cy={}".format(cy), 70, 35)
    oled.show()
    buz.beep(1, freq=1320, duration_ms=150)
    time.sleep_ms(800)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
splash_screen()
joy.calibrate()  # calibração inicial

# ADC direto para oversampling manual
adc_x = ADC(Pin(27))
adc_y = ADC(Pin(26))

print("=== ANALISADOR ADC — BitDogLab ===")
print("Botão A: troca modo | Botão B: calibrar joystick")
print("Modo inicial:", NOMES_MODOS[modo])

while True:
    t_loop = time.ticks_ms()

    # --- Leitura de sensores ---
    x_raw, y_raw = joy.raw
    fx = filt_x.add(x_raw)
    fy = filt_y.add(y_raw)
    x_over = oversample(adc_x, 16)
    y_over = oversample(adc_y, 16)

    # --- Botão A: troca modo ---
    if btn_a.pressed:
        time.sleep_ms(50)           # debounce simples
        if btn_a.pressed:
            modo = (modo + 1) % TOTAL_MODOS
            print("Modo:", NOMES_MODOS[modo])
            buz.tone(660, 60)
            # Limpa buffers ao trocar de modo
            filt_x.reset()
            filt_y.reset()
            # Aguarda soltar
            while btn_a.pressed:
                time.sleep_ms(10)

    # --- Botão B: calibrar ---
    if btn_b.pressed:
        time.sleep_ms(50)
        if btn_b.pressed:
            calibrate_screen()
            filt_x.reset()
            filt_y.reset()
            while btn_b.pressed:
                time.sleep_ms(10)

    # --- Atualiza display conforme modo ---
    if   modo == 0: draw_modo_0(x_raw, y_raw, fx, fy)
    elif modo == 1: draw_modo_1(x_raw, y_raw, fx, fy)
    elif modo == 2: draw_modo_2(x_raw, y_raw, x_over, y_over)
    elif modo == 3: draw_modo_3(x_raw)

    # --- Cálculo de FPS ---
    frame_count += 1
    if time.ticks_diff(time.ticks_ms(), t_ultimo) >= 1000:
        fps     = frame_count
        frame_count = 0
        t_ultimo = time.ticks_ms()
        # Log serial para análise
        print("X={:4d} Xf={:4d} Xo={:4d} | Y={:4d} Yf={:4d} Yo={:4d} | {}fps".format(
            x_raw, int(fx), x_over, y_raw, int(fy), y_over, fps))

    # --- Taxa de atualização: ~25 Hz ---
    dt = time.ticks_diff(time.ticks_ms(), t_loop)
    if dt < 40:
        time.sleep_ms(40 - dt)
