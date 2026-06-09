# =============================================================================
#  bitdoglab.py  —  Utilitários gerais da placa BitDogLab
#  Buzzer PWM, botões com debounce, leitura de joystick ADC, timers
# =============================================================================
#
#  USO:
#      from lib.bitdoglab import Buzzer, Button, Joystick
# =============================================================================

from machine import Pin, PWM, ADC
import time

# ---------------------------------------------------------------------------
# Pinout padrão BitDogLab (baseado no esquemático e documentação)
# ---------------------------------------------------------------------------
PIN_BTN_A    = 5    # Botão A (pull-up interno — ativo em LOW)
PIN_BTN_B    = 6    # Botão B (pull-up interno — ativo em LOW)
PIN_BUZZER   = 10   # Buzzer piezoelétrico (PWM)
PIN_LED_R    = 13   # LED vermelho (PWM)  — LED RGB central
PIN_LED_G    = 11   # LED verde   (PWM)
PIN_LED_B    = 12   # LED azul    (PWM)
PIN_JOY_X    = 27   # Joystick eixo X (ADC1)
PIN_JOY_Y    = 26   # Joystick eixo Y (ADC0)
PIN_JOY_BTN  = 22   # Botão do joystick (click)
PIN_I2C_SDA  = 14   # I2C SDA (display OLED)
PIN_I2C_SCL  = 15   # I2C SCL (display OLED)
PIN_WS2812   = 7    # Data da matriz de LEDs RGB 5×5
PIN_MIC_CLK  = 3    # Clock PDM do microfone MEMS
PIN_MIC_DATA = 2    # Dados PDM do microfone MEMS


# ---------------------------------------------------------------------------
# Buzzer
# ---------------------------------------------------------------------------
class Buzzer:
    """
    Controla o buzzer piezoelétrico da BitDogLab via PWM.

    O volume é controlado pelo duty cycle: 50% = máximo, 0% = mudo.
    A frequência define a nota musical.
    """

    NOTAS = {
        "DO3": 130, "RE3": 147, "MI3": 165, "FA3": 175,
        "SOL3": 196, "LA3": 220, "SI3": 247,
        "DO4": 262, "RE4": 294, "MI4": 330, "FA4": 349,
        "SOL4": 392, "LA4": 440, "SI4": 494,
        "DO5": 523, "RE5": 587, "MI5": 659, "FA5": 698,
        "SOL5": 784, "LA5": 880, "SI5": 988,
        "DO6": 1047,
    }

    def __init__(self, pin=PIN_BUZZER):
        self._pwm = PWM(Pin(pin))
        self._pwm.freq(1000)
        self._pwm.duty_u16(0)  # mudo por padrão

    def tone(self, freq, duration_ms=0, volume=0.5):
        """
        Toca um tom.
        freq        : frequência em Hz
        duration_ms : duração em ms (0 = contínuo até stop())
        volume      : 0.0–1.0 (duty cycle)
        """
        self._pwm.freq(max(20, int(freq)))
        duty = int(32768 * min(1.0, max(0.0, volume)))
        self._pwm.duty_u16(duty)
        if duration_ms > 0:
            time.sleep_ms(duration_ms)
            self.stop()

    def nota(self, nome, duration_ms=200, volume=0.4):
        """Toca uma nota pelo nome (ex: 'LA4', 'DO5')."""
        freq = self.NOTAS.get(nome.upper(), 440)
        self.tone(freq, duration_ms, volume)

    def beep(self, count=1, freq=1000, duration_ms=100, gap_ms=80):
        """Emite 'count' bipes curtos."""
        for _ in range(count):
            self.tone(freq, duration_ms)
            time.sleep_ms(gap_ms)

    def alerta(self):
        """Sequência de alerta — tom descendente."""
        for f in [880, 660, 440]:
            self.tone(f, 120)
            time.sleep_ms(30)

    def vitoria(self):
        """Melodia de vitória — 3 notas ascendentes."""
        for nota in ["DO4", "MI4", "SOL4", "DO5"]:
            self.nota(nota, 120)
            time.sleep_ms(20)

    def stop(self):
        """Para o buzzer (duty = 0)."""
        self._pwm.duty_u16(0)

    def deinit(self):
        self._pwm.deinit()


# ---------------------------------------------------------------------------
# Botão com debounce por software
# ---------------------------------------------------------------------------
class Button:
    """
    Lê um botão com debounce por software (filtra bouncing mecânico).

    O botão é ativo em LOW (resistor pull-up interno habilitado).
    Detecta: pressionado, solto, borda de descida/subida.
    """

    def __init__(self, pin, debounce_ms=50):
        self._pin        = Pin(pin, Pin.IN, Pin.PULL_UP)
        self._debounce   = debounce_ms
        self._last_time  = 0
        self._last_state = 1   # solto = HIGH
        self._state      = 1

    def _read_raw(self):
        return self._pin.value()

    def update(self):
        """
        Deve ser chamado periodicamente no loop principal.
        Retorna True se houve mudança de estado confirmada.
        """
        now = time.ticks_ms()
        raw = self._read_raw()
        if raw != self._last_state:
            if time.ticks_diff(now, self._last_time) >= self._debounce:
                self._last_state = raw
                self._state      = raw
                self._last_time  = now
                return True
        return False

    @property
    def pressed(self):
        """True enquanto o botão estiver pressionado (LOW)."""
        return self._pin.value() == 0

    def fell(self):
        """True no ciclo em que o botão foi pressionado (borda de descida)."""
        self.update()
        if self._state == 0 and self._last_state == 0:
            val = self._state
            return val == 0
        return False

    def wait_press(self, timeout_ms=10000):
        """
        Bloqueia até o botão ser pressionado ou timeout expirar.
        Retorna True se pressionado, False se timeout.
        """
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self._pin.value() == 0:
                time.sleep_ms(self._debounce)
                if self._pin.value() == 0:
                    return True
            time.sleep_ms(5)
        return False

    def wait_release(self):
        """Bloqueia até o botão ser solto."""
        while self._pin.value() == 0:
            time.sleep_ms(5)


# ---------------------------------------------------------------------------
# Joystick analógico (ADC 12 bits)
# ---------------------------------------------------------------------------
class Joystick:
    """
    Lê o joystick analógico da BitDogLab.

    Valores brutos: 0–4095 (ADC 12 bits, 0–3,3 V)
    Valores normalizados: -1.0 a +1.0 (centro ≈ 0.0)
    Botão do joystick: ativo em LOW (pull-up interno)
    """

    def __init__(self, pin_x=PIN_JOY_X, pin_y=PIN_JOY_Y,
                 pin_btn=PIN_JOY_BTN, avg_samples=8):
        self._adc_x   = ADC(Pin(pin_x))
        self._adc_y   = ADC(Pin(pin_y))
        self._btn     = Pin(pin_btn, Pin.IN, Pin.PULL_UP)
        self._samples = avg_samples
        # Calibração do centro (ajustada na primeira leitura ou manualmente)
        self._center_x = 2048
        self._center_y = 2048
        self._dead_zone = 150  # zona morta ao redor do centro

    def _read_avg(self, adc):
        """Leitura com média simples para reduzir ruído."""
        total = 0
        for _ in range(self._samples):
            total += adc.read_u16() >> 4  # converte 16→12 bits
        return total // self._samples

    def calibrate(self):
        """
        Calibra o ponto central do joystick.
        Chame com o joystick na posição neutra (solto).
        """
        self._center_x = self._read_avg(self._adc_x)
        self._center_y = self._read_avg(self._adc_y)
        return self._center_x, self._center_y

    @property
    def raw(self):
        """Retorna (x, y) como valores brutos 0–4095."""
        return (self._read_avg(self._adc_x), self._read_avg(self._adc_y))

    @property
    def norm(self):
        """
        Retorna (x, y) normalizados em -1.0 a +1.0.
        Aplica zona morta para eliminar drift no centro.
        """
        rx, ry = self.raw
        dx = rx - self._center_x
        dy = ry - self._center_y

        def scale(delta):
            if abs(delta) < self._dead_zone:
                return 0.0
            max_range = 2048 - self._dead_zone
            clamped = max(-max_range, min(max_range, delta - (self._dead_zone if delta > 0 else -self._dead_zone)))
            return clamped / max_range

        return (scale(dx), scale(dy))

    @property
    def button(self):
        """True se o botão do joystick estiver pressionado."""
        return self._btn.value() == 0

    def moving_average(self, n=16):
        """
        Retorna médias de N leituras consecutivas — maior filtragem de ruído.
        Bloqueia por (N × ~20 µs).
        """
        sx, sy = 0, 0
        for _ in range(n):
            x, y = self.raw
            sx += x
            sy += y
        return sx // n, sy // n


# ---------------------------------------------------------------------------
# LED RGB central (3 pinos PWM independentes)
# ---------------------------------------------------------------------------
class LEDRGB:
    """
    Controla o LED RGB central da BitDogLab via PWM (pinos R, G, B separados).
    """

    def __init__(self, pin_r=PIN_LED_R, pin_g=PIN_LED_G, pin_b=PIN_LED_B, freq=1000):
        self._r = PWM(Pin(pin_r), freq=freq)
        self._g = PWM(Pin(pin_g), freq=freq)
        self._b = PWM(Pin(pin_b), freq=freq)
        self.off()

    def set(self, r, g, b):
        """Define a cor do LED (r, g, b de 0 a 255)."""
        self._r.duty_u16(int(r / 255 * 65535))
        self._g.duty_u16(int(g / 255 * 65535))
        self._b.duty_u16(int(b / 255 * 65535))

    def off(self):
        self.set(0, 0, 0)

    def red(self,   v=200): self.set(v, 0, 0)
    def green(self, v=200): self.set(0, v, 0)
    def blue(self,  v=200): self.set(0, 0, v)
    def white(self, v=100): self.set(v, v, v)
    def yellow(self,v=150): self.set(v, v, 0)
    def cyan(self,  v=150): self.set(0, v, v)
    def purple(self,v=150): self.set(v, 0, v)

    def deinit(self):
        self._r.deinit()
        self._g.deinit()
        self._b.deinit()


# ---------------------------------------------------------------------------
# Timer de precisão (µs / ms)
# ---------------------------------------------------------------------------
class Timer:
    """Timer de alta resolução baseado em time.ticks_us()."""

    def __init__(self):
        self._start = time.ticks_us()

    def reset(self):
        self._start = time.ticks_us()

    @property
    def elapsed_us(self):
        return time.ticks_diff(time.ticks_us(), self._start)

    @property
    def elapsed_ms(self):
        return self.elapsed_us // 1000

    @property
    def elapsed_s(self):
        return self.elapsed_us / 1_000_000
