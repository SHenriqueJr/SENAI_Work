# =============================================================================
#  PROJETO 3 — Sistema de Controle com Realimentação (Malha Fechada / PID)
# =============================================================================

# Agora as tuas importações normais vão funcionar sem dar erro no PC:
from machine import Pin, PWM, ADC, I2C
import time 
import sys

sys.path.insert(0, "/lib")

from lib.ssd1306   import SSD1306_I2C
from lib.ws2812b   import WS2812B
from lib.bitdoglab import Buzzer, PIN_I2C_SDA, PIN_I2C_SCL
from lib.dsp       import PID
# ---------------------------------------------------------------------------
# Configuração de hardware
# ---------------------------------------------------------------------------
i2c  = I2C(1, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=400_000)
oled = SSD1306_I2C(128, 64, i2c)
leds = WS2812B(pin=7, num_leds=25, brightness=1.0)
buz  = Buzzer()

adc_sp   = ADC(Pin(27))  # Joystick X → setpoint
adc_fb   = ADC(Pin(26))  # Joystick Y → realimentação

btn_a = Pin(5, Pin.IN, Pin.PULL_UP)
btn_b = Pin(6, Pin.IN, Pin.PULL_UP)

# ---------------------------------------------------------------------------
# Parâmetros do controlador PID
# ---------------------------------------------------------------------------
KP_INIT  = 0.8
KI_INIT  = 0.05
KD_INIT  = 0.02

T_SAMPLE = 0.020          # 20 ms (50 Hz)
ADC_MAX  = 4095.0
ERR_LIMIAR = 400          

pid = PID(
    kp=KP_INIT, ki=KI_INIT, kd=KD_INIT,
    out_min=0.0, out_max=ADC_MAX,
    integrator_limit=ADC_MAX * 2
)

# ---------------------------------------------------------------------------
# Variáveis de estado do sistema
# ---------------------------------------------------------------------------
ganho_sel   = 0
GANHOS      = ["Kp", "Ki", "Kd"]
STEP_GANHOS = [0.05, 0.005, 0.002]

setpoint    = 0.0
medicao     = 0.0
erro        = 0.0
u           = 0.0
wcet_us     = 0
brilho_ant  = -1 # Guarda o último estado para evitar reenvio nos LEDs

alarme_ativo   = False
t_erro_inicio  = 0

t_ultimo_oled  = time.ticks_ms()
loop_count     = 0
wcet_max       = 0

# Variáveis para debounce e detecção de borda/hold não-bloqueante
btn_a_pressionado = False
btn_b_pressionado = False
t_btn_b_down = 0
b_hold_disparado = False
mostrando_ganhos = False
t_ganhos_exibicao = 0

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def ler_adc_avg(adc, n=4):
    return sum(adc.read_u16() >> 4 for _ in range(n)) // n

def aplicar_saida_leds(u_val):
    global brilho_ant
    # Converte o sinal u (0 a 4095) para uma escala de brilho interno (0 a 255)
    brilho = max(0, min(255, int(u_val * 255 / ADC_MAX)))
    
    # Otimização: só atualiza a matriz se o valor mudar significativamente
    if abs(brilho - brilho_ant) < 2:
        return
    brilho_ant = brilho

    # Calcula quantas linhas (de 0 a 5) devem acender com base no sinal de controle u
    # Adicionamos "+ 1" se o brilho for maior que zero para garantir que pelo menos a primeira linha acenda
    if brilho > 0:
        linhas_acesas = max(1, min(5, int(brilho * 5 / 255)))
    else:
        linhas_acesas = 0

    # Determina a cor com base no erro absoluto atual do sistema
    erro_abs = abs(erro)
    if erro_abs <= 150:
        r, g, b = 0, 40, 0       # Verde suave (Sistema Estabilizado no alvo)
    elif erro_abs <= ERR_LIMIAR:
        r, g, b = 40, 40, 0      # Amarelo/Laranja (Sistema tentando corrigir)
    else:
        r, g, b = 100, 0, 0      # Vermelho Alerta (Erro crítico, acima do limiar)

    # Varre as 5 linhas da matriz aplicando a cor ou apagando
    for z in range(5):
        if z < linhas_acesas:
            leds.set_row(z, r, g, b)
        else:
            leds.set_row(z, 0, 0, 0) # Apaga as linhas superiores se a força 'u' for baixa
            
    leds.show()

def gerenciar_alarme(err_abs):
    global alarme_ativo, t_erro_inicio
    agora = time.ticks_ms()

    if err_abs > ERR_LIMIAR:
        if not alarme_ativo:
            if t_erro_inicio == 0:
                t_erro_inicio = agora
            elif time.ticks_diff(agora, t_erro_inicio) > 500:
                alarme_ativo = True
                buz.alerta()
        else:
            if loop_count % 50 == 0:
                buz.tone(880, 80)
    else:
        alarme_ativo  = False
        t_erro_inicio = 0
        buz.stop()


def draw_oled_principal():
    oled.fill(0)
    oled.text("PID MALHA FECHADA", 0, 0)
    oled.line(0, 9, 127, 9, 1)

    oled.text("SP:{:4d}".format(int(setpoint)), 0, 12)
    oled.text("PV:{:4d}".format(int(medicao)),  65, 12)

    sinal_err = "-" if erro < 0 else "+"
    oled.text("e:{}{:4d}".format(sinal_err, int(abs(erro))), 0, 22)
    oled.text("u:{:4d}".format(int(u)), 65, 22)

    oled.text("SP", 0, 33)
    oled.bar(16, 33, 108, 6, int(setpoint), 4095)
    oled.text("PV", 0, 41)
    oled.bar(16, 41, 108, 6, int(medicao), 4095)

    oled.line(0, 50, 127, 50, 1)

    for i, nome in enumerate(GANHOS):
        x   = i * 28
        sel = ">" if i == ganho_sel else " "
        oled.text("{}{}".format(sel, nome), x, 53)

    oled.text("{}us".format(wcet_max), 88, 53)
    oled.show()


def draw_oled_ganhos():
    oled.fill(0)
    oled.text("AJUSTE DE GANHOS", 0, 0)
    oled.line(0, 9, 127, 9, 1)

    for i, nome in enumerate(GANHOS):
        y   = 12 + i * 14
        sel = ">>> " if i == ganho_sel else "    "
        val = [pid.kp, pid.ki, pid.kd][i]
        oled.text("{}{}: {:.3f}".format(sel, nome, val), 0, y)

    oled.line(0, 54, 127, 54, 1)
    oled.text("A=+  B=-  Hold B=sel", 0, 56)
    oled.show()


def splash_screen():
    oled.fill(0)
    oled.text("CONTROL PID", 16, 2)
    oled.text("Malha Fechada", 12, 13)
    oled.line(0, 23, 127, 23, 1)
    oled.text("JoyX->PID->LEDs", 5, 27)
    oled.text("    ^         |", 5, 36)
    oled.text("    |__JoyY___+", 5, 45)
    oled.line(0, 54, 127, 54, 1)
    oled.text("A/B:ajuste:ganhos", 0, 56)
    oled.show()
    buz.beep(2, freq=660, duration_ms=100)
    time.sleep_ms(25000)

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
splash_screen()

print("=== CONTROLADOR PID — BitDogLab ===")
print("Kp={:.3f} Ki={:.3f} Kd={:.3f}".format(KP_INIT, KI_INIT, KD_INIT))
print("Ts={}ms | SP=JoyX | PV=JoyY | u->LEDs".format(int(T_SAMPLE*1000)))

# ---------------------------------------------------------------------------
# Loop principal de controle (Tempo Real Estrito)
# ---------------------------------------------------------------------------
while True:
    t_inicio_loop = time.ticks_us()
    agora_ms      = time.ticks_ms()

    # 1. LEITURA DE SENSORES
    setpoint = ler_adc_avg(adc_sp)
    medicao  = ler_adc_avg(adc_fb)

    # 2. CÁLCULO DO PID
    u, erro = pid.compute(setpoint, medicao, T_SAMPLE)
    wcet_us = pid.wcet_us
    if wcet_us > wcet_max:
        wcet_max = wcet_us

    # 3. ATUAÇÃO NA PLANTA (LEDs)
    aplicar_saida_leds(u)

    # 4. ALARME
    gerenciar_alarme(abs(erro))
    loop_count += 1

    # 5. TRATAMENTO NÃO-BLOQUEANTE DOS BOTÕES (Ajuste de Ganhos)
    # --- BOTÃO A (Incremento) ---
    if btn_a.value() == 0:
        if not btn_a_pressionado:
            btn_a_pressionado = True
            vals = [pid.kp, pid.ki, pid.kd]
            vals[ganho_sel] += STEP_GANHOS[ganho_sel]
            pid.tune(
                kp=vals[0] if ganho_sel == 0 else None,
                ki=vals[1] if ganho_sel == 1 else None,
                kd=vals[2] if ganho_sel == 2 else None,
            )
            mostrando_ganhos = True
            t_ganhos_exibicao = agora_ms  # Reseta o timeout de exibição
            draw_oled_ganhos()
            buz.tone(880, 30)
    else:
        btn_a_pressionado = False

    # --- BOTÃO B (Decremento / Seleção por Hold) ---
    if btn_b.value() == 0:
        if not btn_b_pressionado:
            btn_b_pressionado = True
            t_btn_b_down = agora_ms
            b_hold_disparado = False
        else:
            # Verifica se deu o tempo de HOLD sem travar o loop
            if not b_hold_disparado and time.ticks_diff(agora_ms, t_btn_b_down) > 600:
                ganho_sel = (ganho_sel + 1) % 3
                b_hold_disparado = True
                mostrando_ganhos = True
                t_ganhos_exibicao = agora_ms
                draw_oled_ganhos()
                buz.beep(1, freq=660, duration_ms=80)
    else:
        if btn_b_pressionado:
            # Se foi solto antes do Hold, registra como TAP (Decremento)
            if not b_hold_disparado:
                vals = [pid.kp, pid.ki, pid.kd]
                vals[ganho_sel] = max(0.0, vals[ganho_sel] - STEP_GANHOS[ganho_sel])
                pid.tune(
                    kp=vals[0] if ganho_sel == 0 else None,
                    ki=vals[1] if ganho_sel == 1 else None,
                    kd=vals[2] if ganho_sel == 2 else None,
                )
                mostrando_ganhos = True
                t_ganhos_exibicao = agora_ms
                draw_oled_ganhos()
                buz.tone(440, 30)
            btn_b_pressionado = False

    # Timeout para voltar à tela principal após 2 segundos sem mexer nos botões
    if mostrando_ganhos and time.ticks_diff(agora_ms, t_ganhos_exibicao) > 2000:
        mostrando_ganhos = False

    # 6. DISPLAY OLED (Atualização Cadenciada a ~10 Hz)
    if mostrando_ganhos:
        if loop_count % 5 == 0: # Atualiza tela de ganho de forma cadenciada
            draw_oled_ganhos()
    else:
        if time.ticks_diff(agora_ms, t_ultimo_oled) >= 100:
            t_ultimo_oled = agora_ms
            draw_oled_principal()

    # 7. LOG SERIAL (A cada ~1 segundo)
    if loop_count % 50 == 0:
        print("SP={:4d} PV={:4d} e={:+4d} u={:4d} | Kp={:.2f} Ki={:.3f} Kd={:.3f} | WCET={:3d}us max={:3d}us".format(
            int(setpoint), int(medicao), int(erro), int(u),
            pid.kp, pid.ki, pid.kd,
            wcet_us, wcet_max))

    # 8. CONTROLE DE PERÍODO E DETERMINISMO (Ts = 20 ms)
    elapsed = time.ticks_diff(time.ticks_us(), t_inicio_loop)
    periodo_us = int(T_SAMPLE * 1_000_000)
    espera = periodo_us - elapsed

    if espera > 100:
        time.sleep_us(espera)
    elif espera < 0:
        print("AVISO: loop lento! elapsed={}us > Ts={}us".format(elapsed, periodo_us))