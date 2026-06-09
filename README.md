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
