# =============================================================================
#  PROJETO 2 CORRIGIDO — Osciloscópio de Áudio com FFT e LEDs RGB
# =============================================================================

from machine import I2C, Pin, ADC
import time
import sys
import math

sys.path.insert(0, "/lib")

from ssd1306  import SSD1306_I2C
from ws2812b  import WS2812B
from bitdoglab import Button, Buzzer, PIN_I2C_SDA, PIN_I2C_SCL
from dsp      import fft, fft_magnitude, fft_band_energy, window_hann, apply_window

# ---------------------------------------------------------------------------
# Configuração de hardware
# ---------------------------------------------------------------------------
i2c  = I2C(1, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=400_000)
oled = SSD1306_I2C(128, 64, i2c)

# Matriz 5x5 conectada ao GP7
leds = WS2812B(pin=7, num_leds=25, brightness=0.25)
buz  = Buzzer()
adc  = ADC(Pin(27))   # Joystick X como entrada analógica

btn_a = Button(5)
btn_b = Button(6)

# ---------------------------------------------------------------------------
# Parâmetros da FFT
# ---------------------------------------------------------------------------
FFT_SIZE      = 64        # pontos da FFT (potência de 2)
FS_NORMAL     = 8_000     # 8 kHz — cobre voz humana (20 Hz – 4 kHz)
FS_ALIASING   = 1_500     # 1,5 kHz — demonstra aliasing para sinais >750 Hz
FS_ATUAL      = FS_NORMAL

# Janela de Hann pré-calculada
janela_hann   = window_hann(FFT_SIZE)

# Frequências de teste (modo sintético)
FREQS_TESTE   = [200, 500, 1000, 2000, 3500]
freq_idx      = 0
freq_sintese  = FREQS_TESTE[freq_idx]

# Modos do programa
modo          = 0  # 0=sintético, 1=ADC externo, 2=aliasing
NOMES_MODOS   = ["SINTETICO", "ADC EXT", "ALIASING"]

# Definição das 5 bandas de frequência (Hz)
BANDAS = [
    ("Grav",  20,   300),    # coluna 0
    ("Med-",  300,  800),    # coluna 1
    ("Med",   800,  2000),   # coluna 2
    ("Med+", 2000,  5000),   # coluna 3
    ("Agud", 5000, 10000),   # coluna 4
]

CORES_BANDAS = [
    (0,   0,   255),  # azul
    (0,   200, 100),  # verde
    (150, 200,   0),  # verde-amarelo
    (255, 100,   0),  # laranja
    (255,   0,   0),  # vermelho
]

max_hist = [1.0] * 5
DECAY    = 0.95   # Ajustado decaimento ligeiramente mais rápido para dinâmica visual

# ---------------------------------------------------------------------------
# Funções Auxiliares Customizadas (Display, Matriz e Efeitos)
# ---------------------------------------------------------------------------

def oled_text_center(texto, y):
    """Centraliza o texto horizontalmente no display."""
    x = (128 - (len(texto) * 8)) // 2
    oled.text(texto, max(0, x), y)

def color_wheel(pos):
    """Gera uma cor no espectro RGB com base em uma posição de 0 a 255."""
    pos = pos % 255
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)

def matriz_fill_column(coluna, altura, r, g, b):
    """
    Preenche uma coluna na matriz 5x5 de baixo para cima.
    BitDogLab adota disposição em zigue-zague ou linear indexada (0 a 24).
    Mapeamento padrão de coordenadas cartesianas (X, Y) para indexação física:
    """
    for linha in range(5):
        # Inverte a lógica física: linha 0 é a base inferior da coluna do VU
        # Se a linha atual estiver abaixo da altura desejada, liga o LED
        if linha < altura:
            # Cálculo do índice para matrizes lineares padrão 5x5:
            # Caso a sua matriz use mapeamento em zigue-zague, o cálculo se ajusta aqui.
            idx = (4 - linha) * 5 + coluna 
            leds.set(idx, r, g, b)

# ---------------------------------------------------------------------------
# Processamento de Sinais e Captura
# ---------------------------------------------------------------------------

def gerar_sinal_sintetico(freq_hz, fs, n, amplitude=1500, offset=2048):
    samples = []
    for i in range(n):
        t = i / fs
        val = offset + int(amplitude * math.sin(2 * math.pi * freq_hz * t))
        samples.append(max(0, min(4095, val)))
    return samples

def capturar_adc(n, fs):
    samples = []
    periodo_us = int(1_000_000 / fs)
    for _ in range(n):
        t0 = time.ticks_us()
        samples.append(adc.read_u16() >> 4)   # Reduz escala de 16 para 12 bits
        elapsed = time.ticks_diff(time.ticks_us(), t0)
        wait = periodo_us - elapsed
        if wait > 0:
            time.sleep_us(wait)
    return samples

def processar_fft(samples, fs):
    media = sum(samples) / len(samples)
    s_dc  = [x - media for x in samples]
    s_win = apply_window(s_dc, janela_hann)

    re = list(s_win)
    im = [0.0] * FFT_SIZE
    re, im = fft(re, im)
    mags = fft_magnitude(re, im)

    # Correção do Bug de Índice:
    idx_max = max(range(1, len(mags)), key=lambda i: mags[i])
    bin_hz = fs / FFT_SIZE
    freq_dom = idx_max * bin_hz
    mag_dom  = mags[idx_max]

    return mags, freq_dom, mag_dom

def calcular_energias_bandas(mags, fs):
    global max_hist
    alturas = []
    for i, (_, f_low, f_high) in enumerate(BANDAS):
        e = fft_band_energy(mags, fs, f_low, f_high)
        max_hist[i] = max(max_hist[i] * DECAY, e, 0.01)
        
        h = int(5 * e / max_hist[i])
        alturas.append(max(0, min(5, h)))
    return alturas

def atualizar_leds(alturas):
    leds.clear()
    for col, h in enumerate(alturas):
        r, g, b = CORES_BANDAS[col]
        matriz_fill_column(col, h, r, g, b)
    leds.show()

def atualizar_oled(freq_dom, mag_dom, alturas, fs):
    oled.fill(0)
    oled.text("FFT: {}".format(NOMES_MODOS[modo]), 0, 0)
    oled.line(0, 10, 127, 10, 1)

    oled.text("Fdom: {:.0f}Hz".format(freq_dom), 0, 13)
    oled.text("Amp: {:.0f}".format(mag_dom), 0, 23)
    oled.text("Fs: {:.0f}Hz".format(fs), 70, 13)
    oled.text("Fn: {:.0f}Hz".format(fs / 2), 70, 23)

    oled.line(0, 33, 127, 33, 1)

    # Desenho corrigido do Mini VU Meter
    for i, h in enumerate(alturas):
        x = i * 26 + 2
        nome_banda = BANDAS[i][0]
        oled.text(nome_banda[:4], x, 35) # Trunca string se necessário
        
        barra_h = h * 4
        if barra_h > 0:
            oled.fill_rect(x + 2, 63 - barra_h, 16, barra_h, 1)
        oled.rect(x + 2, 45, 16, 18, 1)

    if modo == 2:
        oled.fill_rect(80, 0, 48, 10, 1)
        oled.text("ALIAS", 84, 1, 0)

    oled.show()

def tocar_nota_dominante(freq_dom):
    if freq_dom < 80 or freq_dom > 4000 or modo == 1:
        # Modo 1 com ruído pode deixar o buzzer instável, opcional silenciar
        buz.stop()
        return
    buz.tone(int(freq_dom), 0, volume=0.1)

def splash_screen():
    oled.fill(0)
    oled_text_center("ANALISADOR FFT", 5)
    oled_text_center("BitDogLab v1.0", 18)
    oled.line(0, 28, 127, 28, 1)
    oled.text("A = Troca modo", 5, 33)
    oled.text("B = Troca freq.", 5, 45)
    oled.show()
    
    # Animação de inicialização na matriz RGB
    for i in range(25):
        r, g, b = color_wheel(i * 10)
        leds.set(i, r, g, b)
        leds.show()
        time.sleep_ms(20)
    leds.clear()
    leds.show()
    buz.beep(2, freq=880, duration_ms=60)
    time.sleep_ms(1000)

# ---------------------------------------------------------------------------
# Loop Executável Principal
# ---------------------------------------------------------------------------
splash_screen()

while True:
    t_loop = time.ticks_ms()

    # --- Tratamento de Entrada: Botão A ---
    if btn_a.pressed:
        time.sleep_ms(50) # Debounce
        if btn_a.pressed:
            modo = (modo + 1) % len(NOMES_MODOS)
            FS_ATUAL = FS_ALIASING if modo == 2 else FS_NORMAL
            max_hist = [1.0] * 5 # Reseta ganho automático
            buz.stop()
            while btn_a.pressed:
                time.sleep_ms(10)

    # --- Tratamento de Entrada: Botão B ---
    if btn_b.pressed:
        time.sleep_ms(50)
        if btn_b.pressed:
            freq_idx = (freq_idx + 1) % len(FREQS_TESTE)
            freq_sintese = FREQS_TESTE[freq_idx]
            buz.tone(freq_sintese, 100, volume=0.2)
            while btn_b.pressed:
                time.sleep_ms(10)

    # --- Aquisição de Dados ---
    if modo == 0:
        samples = gerar_sinal_sintetico(freq_sintese, FS_ATUAL, FFT_SIZE)
    elif modo == 1:
        samples = capturar_adc(FFT_SIZE, FS_ATUAL)
    else:
        samples = gerar_sinal_sintetico(freq_sintese, FS_ALIASING, FFT_SIZE)

    # --- DSP e Saídas ---
    mags, freq_dom, mag_dom = processar_fft(samples, FS_ATUAL)
    alturas = calcular_energias_bandas(mags, FS_ATUAL)

    atualizar_leds(alturas)
    atualizar_oled(freq_dom, mag_dom, alturas, FS_ATUAL)
    tocar_nota_dominante(freq_dom)

    # --- Estabilização Temporal do Loop ---
    dt = time.ticks_diff(time.ticks_ms(), t_loop)
    if dt < 100:
        time.sleep_ms(100 - dt)