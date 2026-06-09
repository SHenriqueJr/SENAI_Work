# =============================================================================
#  dsp.py  —  Processamento Digital de Sinais em MicroPython puro
#  FFT, média móvel, oversampling, janelamento
#  Compatível com RP2040 (sem dependências externas)
# =============================================================================

import math


# ---------------------------------------------------------------------------
# Média Móvel (Moving Average)
# ---------------------------------------------------------------------------
class MovingAverage:
    """
    Filtro de média móvel circular (FIR de coeficientes iguais).
    Reduz ruído de alta frequência em leituras de ADC.

    Complexidade: O(1) por amostra (buffer circular).
    """

    def __init__(self, size=16):
        self.size   = size
        self._buf   = [0] * size
        self._idx   = 0
        self._total = 0
        self._full  = False

    def add(self, value):
        """Insere um novo valor e retorna a média atual."""
        self._total -= self._buf[self._idx]
        self._buf[self._idx] = value
        self._total += value
        self._idx = (self._idx + 1) % self.size
        if self._idx == 0:
            self._full = True
        count = self.size if self._full else (self._idx or self.size)
        return self._total / count

    def reset(self):
        self._buf   = [0] * self.size
        self._idx   = 0
        self._total = 0
        self._full  = False


# ---------------------------------------------------------------------------
# Janelas de apodização (para FFT)
# ---------------------------------------------------------------------------
def window_hann(n):
    """Gera vetor de janela de Hann de tamanho n."""
    return [0.5 * (1 - math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]

def window_hamming(n):
    """Gera vetor de janela de Hamming de tamanho n."""
    return [0.54 - 0.46 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]

def apply_window(samples, window):
    """Aplica vetor de janela element-wise à lista de amostras."""
    return [samples[i] * window[i] for i in range(len(samples))]


# ---------------------------------------------------------------------------
# FFT Radix-2 Cooley-Tukey (in-place, potência de 2)
# ---------------------------------------------------------------------------
def fft(re, im=None):
    """
    Transformada Rápida de Fourier (FFT) Radix-2 iterativa.
    Implementação em MicroPython puro — sem numpy.

    Parâmetros:
        re : lista de floats — parte real das amostras
        im : lista de floats — parte imaginária (None → todos zeros)

    Retorna:
        (re, im) : partes real e imaginária do espectro complexo
        O índice k corresponde à frequência k * Fs / N

    N deve ser potência de 2.
    """
    n = len(re)
    if im is None:
        im = [0.0] * n

    # Verificação de potência de 2
    if n & (n - 1) != 0:
        raise ValueError("FFT: tamanho deve ser potência de 2 (ex: 32, 64, 128)")

    # Bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]

    # Butterfly stages
    length = 2
    while length <= n:
        half = length >> 1
        angle = -2 * math.pi / length
        wr0 = math.cos(angle)
        wi0 = math.sin(angle)
        for i in range(0, n, length):
            wr = 1.0
            wi = 0.0
            for k in range(half):
                tr = wr * re[i + k + half] - wi * im[i + k + half]
                ti = wr * im[i + k + half] + wi * re[i + k + half]
                re[i + k + half] = re[i + k] - tr
                im[i + k + half] = im[i + k] - ti
                re[i + k] += tr
                im[i + k] += ti
                wr_new = wr * wr0 - wi * wi0
                wi      = wr * wi0 + wi * wr0
                wr      = wr_new
        length <<= 1

    return re, im


def fft_magnitude(re, im):
    """
    Calcula o vetor de magnitudes do espectro FFT.
    Retorna apenas a metade positiva (índices 0 a N/2).
    """
    n = len(re)
    half = n // 2
    return [math.sqrt(re[i]**2 + im[i]**2) / n for i in range(half)]


def fft_dominant_freq(magnitudes, sample_rate, ignore_dc=True):
    """
    Encontra a frequência dominante no espectro.
    ignore_dc : ignora o bin DC (índice 0)
    Retorna (frequência_hz, magnitude)
    """
    start = 1 if ignore_dc else 0
    n     = len(magnitudes)
    if n == 0:
        return 0.0, 0.0
    idx = start + max(range(start, n), key=lambda i: magnitudes[i])
    freq = idx * sample_rate / (2 * n)
    return freq, magnitudes[idx]


def fft_band_energy(magnitudes, sample_rate, f_low, f_high):
    """
    Soma a energia do espectro em uma faixa de frequência [f_low, f_high] Hz.
    Útil para visualizadores de bandas (graves, médios, agudos).
    """
    n      = len(magnitudes)
    bin_hz = sample_rate / (2 * n)
    i_low  = max(0, int(f_low  / bin_hz))
    i_high = min(n - 1, int(f_high / bin_hz))
    return sum(magnitudes[i_low:i_high + 1])


# ---------------------------------------------------------------------------
# Oversampling (aumento de resolução efetiva do ADC)
# ---------------------------------------------------------------------------
def oversample(adc, n_samples=16):
    """
    Técnica de oversampling: lê o ADC n_samples vezes e calcula a média.
    Aumenta resolução efetiva em 0.5 * log2(n_samples) bits.
    Ex: 16 amostras → +2 bits de resolução efetiva.

    adc       : objeto machine.ADC
    n_samples : deve ser potência de 2 (4, 16, 64...)
    Retorna valor médio em 12 bits (0–4095).
    """
    total = 0
    for _ in range(n_samples):
        total += adc.read_u16() >> 4  # 16→12 bits
    return total // n_samples


# ---------------------------------------------------------------------------
# Controlador PID digital
# ---------------------------------------------------------------------------
class PID:
    """
    Controlador PID digital de tempo discreto.

    u(k) = Kp*e(k) + Ki*sum(e) + Kd*(e(k)-e(k-1))

    Recursos:
        - Anti-windup por clamping do integrador
        - Saída limitada a [out_min, out_max]
        - Medição de tempo de execução (WCET)
    """

    def __init__(self, kp=1.0, ki=0.0, kd=0.0,
                 out_min=0.0, out_max=4095.0,
                 integrator_limit=None):
        self.kp  = kp
        self.ki  = ki
        self.kd  = kd
        self.out_min = out_min
        self.out_max = out_max
        self.integrator_limit = integrator_limit or (out_max / (ki + 1e-9))

        self._integral  = 0.0
        self._prev_err  = 0.0
        self._last_wcet = 0  # µs

    def compute(self, setpoint, measured, dt=0.01):
        """
        Calcula a saída do controlador.

        setpoint : valor desejado
        measured : valor medido da planta
        dt       : período de amostragem em segundos

        Retorna u (sinal de controle) dentro de [out_min, out_max].
        """
        import time as _t
        t0  = _t.ticks_us()

        error = setpoint - measured

        # Termo proporcional
        p = self.kp * error

        # Termo integral com anti-windup
        self._integral += error * dt
        self._integral  = max(-self.integrator_limit,
                              min(self.integrator_limit, self._integral))
        i = self.ki * self._integral

        # Termo derivativo (sem filtro — simples para fins educacionais)
        d = self.kd * (error - self._prev_err) / dt if dt > 0 else 0.0
        self._prev_err = error

        # Saída saturada
        u = max(self.out_min, min(self.out_max, p + i + d))

        self._last_wcet = _t.ticks_diff(_t.ticks_us(), t0)
        return u, error

    @property
    def wcet_us(self):
        """Retorna o tempo de execução do último cálculo em µs (para análise de WCET)."""
        return self._last_wcet

    def reset(self):
        self._integral = 0.0
        self._prev_err = 0.0

    def tune(self, kp=None, ki=None, kd=None):
        """Ajusta os ganhos em tempo de execução."""
        if kp is not None: self.kp = kp
        if ki is not None: self.ki = ki
        if kd is not None: self.kd = kd
        self.reset()
