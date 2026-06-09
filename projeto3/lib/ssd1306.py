# =============================================================================
#  ssd1306.py  —  Driver MicroPython para display OLED SSD1306 via I2C
#  Compatível com BitDogLab (RP2040 / Raspberry Pi Pico)
#  Resolução: 128 x 64 pixels
#  Protocolo: I2C (endereço padrão 0x3C)
# =============================================================================
#
#  USO BÁSICO:
#      from machine import I2C, Pin
#      from lib.ssd1306 import SSD1306_I2C
#      i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
#      oled = SSD1306_I2C(128, 64, i2c)
#      oled.text("Ola BitDogLab!", 0, 0)
#      oled.show()
# =============================================================================

import framebuf

# ---------------------------------------------------------------------------
# Comandos do controlador SSD1306
# ---------------------------------------------------------------------------
SET_CONTRAST        = 0x81
SET_ENTIRE_ON       = 0xA4
SET_NORM_INV        = 0xA6
SET_DISP            = 0xAE
SET_MEM_ADDR        = 0x20
SET_COL_ADDR        = 0x21
SET_PAGE_ADDR       = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP       = 0xA0
SET_MUX_RATIO       = 0xA8
SET_COM_OUT_DIR     = 0xC0
SET_DISP_OFFSET     = 0xD3
SET_COM_PIN_CFG     = 0xDA
SET_DISP_CLK_DIV    = 0xD5
SET_PRECHARGE       = 0xD9
SET_VCOM_DESEL      = 0xDB
SET_CHARGE_PUMP     = 0x8D


class SSD1306:
    """Classe base SSD1306 — independente do protocolo de comunicação."""

    def __init__(self, width, height, external_vcc=False):
        self.width        = width
        self.height       = height
        self.external_vcc = external_vcc
        self.pages        = height // 8
        # Buffer de pixels: 1 bit por pixel, organizado em páginas de 8 linhas
        self.buffer = bytearray(self.pages * self.width)
        self.fb     = framebuf.FrameBuffer(self.buffer, width, height, framebuf.MONO_VLSB)
        self.init_display()

    # ------------------------------------------------------------------
    # Inicialização do hardware
    # ------------------------------------------------------------------
    def init_display(self):
        init_seq = [
            SET_DISP | 0x00,          # display off
            SET_MEM_ADDR, 0x00,        # modo de endereçamento horizontal
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,      # column 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,    # scan do COM[N-1] para COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG,
                0x02 if (self.width > 2 * self.height) else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE,
                0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,             # output segue RAM
            SET_NORM_INV,              # não invertido
            SET_CHARGE_PUMP,
                0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,           # display on
        ]
        for cmd in init_seq:
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    # ------------------------------------------------------------------
    # Controle do display
    # ------------------------------------------------------------------
    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        """Define o contraste (0–255)."""
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        """Inverte as cores do display."""
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def rotate(self, rotate):
        """Rotaciona 180° quando rotate=True."""
        self.write_cmd(SET_COM_OUT_DIR | ((rotate & 1) << 3))
        self.write_cmd(SET_SEG_REMAP   | (rotate & 1))

    # ------------------------------------------------------------------
    # Transferência do buffer para o display
    # ------------------------------------------------------------------
    def show(self):
        x0, x1 = 0, self.width - 1
        if self.width != 128:
            col_offset = (128 - self.width) // 2
            x0 += col_offset
            x1 += col_offset
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)

    # ------------------------------------------------------------------
    # Wrapper para FrameBuffer (desenho)
    # ------------------------------------------------------------------
    def fill(self, col):
        self.fb.fill(col)

    def pixel(self, x, y, col):
        self.fb.pixel(x, y, col)

    def scroll(self, dx, dy):
        self.fb.scroll(dx, dy)

    def text(self, string, x, y, col=1):
        """Escreve texto com fonte 8×8. Cada caractere ocupa 8 pixels de largura."""
        self.fb.text(string, x, y, col)

    def line(self, x1, y1, x2, y2, col):
        self.fb.line(x1, y1, x2, y2, col)

    def rect(self, x, y, w, h, col):
        self.fb.rect(x, y, w, h, col)

    def fill_rect(self, x, y, w, h, col):
        self.fb.fill_rect(x, y, w, h, col)

    def blit(self, fbuf, x, y):
        self.fb.blit(fbuf, x, y)

    # ------------------------------------------------------------------
    # Utilitários de texto (múltiplas linhas, centrado)
    # ------------------------------------------------------------------
    def text_center(self, string, y, col=1):
        """Centraliza texto horizontalmente."""
        x = max(0, (self.width - len(string) * 8) // 2)
        self.text(string, x, y, col)

    def multiline(self, lines, start_y=0, spacing=10, col=1):
        """
        Exibe uma lista de strings, uma por linha.
        lines    : lista de strings
        start_y  : posição Y da primeira linha
        spacing  : espaço vertical entre linhas em pixels
        """
        for i, line in enumerate(lines):
            y = start_y + i * spacing
            if y + 8 <= self.height:
                self.text(line, 0, y, col)

    def bar(self, x, y, width, height, value, max_val, col=1):
        """
        Desenha uma barra de progresso horizontal.
        value / max_val define o preenchimento.
        """
        self.rect(x, y, width, height, col)
        filled = int(width * value / max_val)
        if filled > 2:
            self.fill_rect(x + 1, y + 1, filled - 2, height - 2, col)

    def vbar(self, x, y_bottom, height_total, value, max_val, col=1):
        """
        Desenha uma barra de progresso vertical (cresce para cima).
        """
        filled = int(height_total * value / max_val)
        if filled > 0:
            self.fill_rect(x, y_bottom - filled, 6, filled, col)

    # ------------------------------------------------------------------
    # Métodos abstratos — implementados por SSD1306_I2C
    # ------------------------------------------------------------------
    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Implementação I2C
# ---------------------------------------------------------------------------
class SSD1306_I2C(SSD1306):
    """
    Driver SSD1306 via I2C.

    Parâmetros:
        width, height : resolução do display (tipicamente 128, 64)
        i2c           : objeto machine.I2C já inicializado
        addr          : endereço I2C (padrão 0x3C)
        external_vcc  : True se VCC externo, False para carga interna
    """

    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c  = i2c
        self.addr = addr
        # Buffer de comando: byte de controle 0x00 + 1 byte de comando
        self.temp = bytearray(2)
        # Buffer de dados: byte de controle 0x40 + payload
        self._data_buf = bytearray(1 + width * (height // 8))
        self._data_buf[0] = 0x40
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co=1, D/C#=0 → comando
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        # Copia buffer no payload e envia em bloco (mais eficiente que byte a byte)
        self._data_buf[1:] = buf
        self.i2c.writeto(self.addr, self._data_buf)
