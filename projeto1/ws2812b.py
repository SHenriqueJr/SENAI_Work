# =============================================================================
#  ws2812b.py  —  Driver MicroPython para LEDs WS2812B via PIO (RP2040)
#  Compatível com BitDogLab (matriz 5×5 = 25 LEDs)
#  Protocolo: 1-wire serial @ 800 kbps, temporização crítica via PIO
# =============================================================================
#
#  USO BÁSICO:
#      from lib.ws2812b import WS2812B
#      leds = WS2812B(pin=7, num_leds=25)
#      leds.set(0, r=255, g=0, b=0)   # LED 0 vermelho
#      leds.fill(r=0, g=20, b=0)      # todos verde (brilho baixo)
#      leds.show()
# =============================================================================

import array
import rp2
from machine import Pin

# ---------------------------------------------------------------------------
# Programa PIO — gera o protocolo WS2812B (800 kbps, GRB)
#
# Temporização por bit (datasheet WS2812B):
#   T0H = 0,4 µs  T0L = 0,85 µs  → bit 0
#   T1H = 0,8 µs  T1L = 0,45 µs  → bit 1
#   Reset ≥ 50 µs (nível baixo)
#
# A PIO roda a 8 MHz (8 ciclos = 1 µs).  Cada loop de bit usa 10 ciclos:
#   4 ciclos HIGH para bit 1  (≈ 0,5 µs)
#   6 ciclos LOW  para bit 1  (≈ 0,75 µs)
#   2 ciclos HIGH para bit 0  (≈ 0,25 µs)
#   8 ciclos LOW  para bit 0  (≈ 1,0 µs)
# ---------------------------------------------------------------------------

@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24
)
def _ws2812b_pio():
    T1 = 2   # ciclos HIGH bit 0
    T2 = 5   # ciclos HIGH bit 1
    T3 = 3   # ciclos LOW  (shared)
    wrap_target()
    label("bitloop")
    out(x, 1)              .side(0)   [T3 - 1]   # carrega 1 bit; pino LOW
    jmp(not_x, "do_zero")  .side(1)   [T1 - 1]   # pino HIGH; desvia se bit=0
    jmp("bitloop")         .side(1)   [T2 - 1]   # bit 1: fica HIGH mais tempo
    label("do_zero")
    nop()                  .side(0)   [T2 - 1]   # bit 0: pino LOW cedo
    wrap()


class WS2812B:
    """
    Controlador para fita/matriz de LEDs WS2812B usando a PIO do RP2040.

    Parâmetros:
        pin      : número do pino GPIO de dados
        num_leds : quantidade de LEDs na cadeia
        sm_id    : ID da state machine PIO (0–7); padrão 0
        brightness: escala de brilho global 0.0–1.0 (padrão 0.3 para proteger os olhos)
    """

    def __init__(self, pin, num_leds, sm_id=0, brightness=0.3):
        self.num_leds   = num_leds
        self.brightness = max(0.0, min(1.0, brightness))
        # Array interno: 24 bits GRB por LED (armazenado como uint32)
        self._pixels = array.array("I", [0] * num_leds)
        # Inicializa a state machine PIO
        self._sm = rp2.StateMachine(
            sm_id,
            _ws2812b_pio,
            freq=8_000_000,
            sideset_base=Pin(pin)
        )
        self._sm.active(1)

    # ------------------------------------------------------------------
    # Controle individual de LEDs
    # ------------------------------------------------------------------
    def set(self, index, r=0, g=0, b=0):
        """Define a cor de um LED pelo índice (0 a num_leds-1)."""
        if 0 <= index < self.num_leds:
            br = self.brightness
            r2 = int(r * br) & 0xFF
            g2 = int(g * br) & 0xFF
            b2 = int(b * br) & 0xFF
            # Formato GRB exigido pelo WS2812B
            self._pixels[index] = (g2 << 16) | (r2 << 8) | b2

    def get(self, index):
        """Retorna (r, g, b) do LED no índice (sem aplicar brightness)."""
        v  = self._pixels[index]
        g2 = (v >> 16) & 0xFF
        r2 = (v >>  8) & 0xFF
        b2 =  v        & 0xFF
        br = self.brightness if self.brightness > 0 else 1
        return (int(r2 / br), int(g2 / br), int(b2 / br))

    # ------------------------------------------------------------------
    # Operações em bloco
    # ------------------------------------------------------------------
    def fill(self, r=0, g=0, b=0):
        """Define a mesma cor para todos os LEDs."""
        for i in range(self.num_leds):
            self.set(i, r, g, b)

    def clear(self):
        """Apaga todos os LEDs."""
        self.fill(0, 0, 0)

    def set_brightness(self, brightness):
        """Ajusta o brilho global (0.0–1.0). Requer show() após chamar."""
        self.brightness = max(0.0, min(1.0, brightness))

    # ------------------------------------------------------------------
    # Matriz 5×5 (específico para BitDogLab)
    # ------------------------------------------------------------------
    def set_matrix(self, col, row, r=0, g=0, b=0):
        """
        Define cor pelo endereço de coluna/linha na matriz 5×5.
        col: 0–4 (esquerda→direita)
        row: 0–4 (cima→baixo)
        Mapeamento: linha par → esquerda→direita; linha ímpar → direita→esquerda (serpentina)
        """
        if row % 2 == 0:
            index = row * 5 + col
        else:
            index = row * 5 + (4 - col)
        self.set(index, r, g, b)

    def fill_column(self, col, height, r=0, g=0, b=0):
        """
        Preenche uma coluna da matriz de baixo para cima até 'height' LEDs.
        Útil para visualizadores de áudio (VU meter).
        height: 0–5
        """
        for row in range(5):
            if (4 - row) < height:
                self.set_matrix(col, row, r, g, b)
            else:
                self.set_matrix(col, row, 0, 0, 0)

    def set_row(self, row, r=0, g=0, b=0):
        """Pinta uma linha inteira da matriz 5×5."""
        for col in range(5):
            self.set_matrix(col, row, r, g, b)

    def set_col(self, col, r=0, g=0, b=0):
        """Pinta uma coluna inteira da matriz 5×5."""
        for row in range(5):
            self.set_matrix(col, row, r, g, b)

    # ------------------------------------------------------------------
    # Efeitos visuais
    # ------------------------------------------------------------------
    def wheel(self, pos):
        """
        Gera uma cor do espectro (0–255) sem usar math.
        Útil para efeito arco-íris.
        """
        pos = pos & 0xFF
        if pos < 85:
            return (pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return (255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return (0, pos * 3, 255 - pos * 3)

    def rainbow(self, offset=0):
        """Preenche todos os LEDs com cores do arco-íris deslocadas por offset."""
        for i in range(self.num_leds):
            r, g, b = self.wheel((i * 256 // self.num_leds + offset) & 0xFF)
            self.set(i, r, g, b)

    def hsv_to_rgb(self, h, s, v):
        """
        Converte HSV → RGB (todos de 0 a 255).
        Útil para gradientes de cor suaves no PID e VU meter.
        """
        if s == 0:
            return (v, v, v)
        h = h % 256
        region    = h // 43
        remainder = (h - region * 43) * 6
        p = (v * (255 - s)) >> 8
        q = (v * (255 - ((s * remainder) >> 8))) >> 8
        t = (v * (255 - ((s * (255 - remainder)) >> 8))) >> 8
        if   region == 0: return (v, t, p)
        elif region == 1: return (q, v, p)
        elif region == 2: return (p, v, t)
        elif region == 3: return (p, q, v)
        elif region == 4: return (t, p, v)
        else:             return (v, p, q)

    # ------------------------------------------------------------------
    # Envio dos dados para os LEDs (obrigatório após qualquer modificação)
    # ------------------------------------------------------------------
    def show(self):
        """Transmite o buffer completo para a cadeia de LEDs via PIO."""
        for pixel in self._pixels:
            self._sm.put(pixel, 8)  # envia 24 bits MSB-first
