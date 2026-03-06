# BASE DE CONOCIMIENTO — ANÁLISIS TÉCNICO DE LOS MERCADOS FINANCIEROS
## John J. Murphy | Gestión 2000
### Fuente: Libro completo (547 páginas) — Conocimiento estructurado para APEX Trading Bot

---

## CAPÍTULO 1 — FILOSOFÍA DEL ANÁLISIS TÉCNICO

### Definición y Premisas Fundamentales
El análisis técnico es el estudio de los movimientos del mercado, principalmente mediante el uso de gráficos, con el objetivo de pronosticar las futuras tendencias de los precios.

**Las tres premisas sobre las que se apoya el análisis técnico:**
1. **Los movimientos del mercado lo descuentan todo** — Cualquier factor que pueda afectar al precio (fundamental, político, psicológico) ya está reflejado en el precio. Por lo tanto, el estudio del gráfico de precios es todo lo que necesitamos.
2. **Los precios se mueven en tendencias** — El objetivo del análisis técnico es identificar las tendencias en sus etapas iniciales para operar en la dirección de esa tendencia. Una tendencia en movimiento tiene más probabilidades de continuar que de revertirse.
3. **La historia se repite** — Los patrones gráficos reflejan la psicología humana (miedo y codicia). Como la psicología humana tiende a ser constante, esos patrones tienden a funcionar con consistencia a lo largo del tiempo.

### Análisis Técnico vs. Análisis Fundamental
- El análisis fundamental estudia las causas del movimiento; el técnico estudia el efecto.
- Los técnicos creen que el mercado siempre conoce las noticias con antelación.
- Ambos enfoques son complementarios. En trading de corto plazo, el técnico es más práctico.
- El análisis técnico es más útil para el **timing** (momento de entrada/salida).

---

## CAPÍTULO 2 — TEORÍA DE DOW

### Los Seis Principios de la Teoría de Dow
1. **Los índices lo descuentan todo** — Cada factor conocido o previsible ya está reflejado en los índices.
2. **El mercado tiene tres tendencias:**
   - **Tendencia primaria:** Dura de 1 a varios años. El movimiento más importante.
   - **Tendencia secundaria:** Correcciones contra la tendencia primaria. Dura de 3 semanas a 3 meses. Retrocede entre 1/3 y 2/3 de la tendencia primaria (normalmente el 50%).
   - **Tendencia menor:** Oscilaciones de menos de 3 semanas. Fluctuaciones dentro de la tendencia secundaria.
3. **Las tendencias primarias tienen tres fases:**
   - **Mercado alcista:** Fase de acumulación (inversores inteligentes compran contra el pesimismo general) → Fase de participación pública (noticias mejoran, tendencia sube) → Fase de distribución (especulación excesiva, los inteligentes venden).
   - **Mercado bajista:** Fase de distribución → Fase de pánico → Fase de desaliento.
4. **Los índices deben confirmarse entre sí** — Una señal alcista o bajista en el Dow Industrial debe ser confirmada por el Dow Transportation. Si no hay confirmación, la señal es dudosa.
5. **El volumen debe confirmar la tendencia** — El volumen debe expandirse en la dirección de la tendencia principal.
6. **Una tendencia se asume que está en vigor hasta que haya señales definitivas de reversión** — No se puede asumir que una tendencia ha terminado hasta tener señales claras.

---

## CAPÍTULO 3 — CONSTRUCCIÓN DE GRÁFICOS

### Tipos de Gráficos
- **Gráfico de barras (OHLC):** Cada barra muestra Apertura, Máximo, Mínimo y Cierre.
- **Gráfico de líneas:** Conecta únicamente los precios de cierre. Útil para ver tendencia general.
- **Gráfico de velas japonesas (Candlestick):** Cuerpo real (apertura/cierre) + mechas (máximo/mínimo). Proporciona más información visual que la barra.
- **Gráficos Point & Figure:** Sin dimensión temporal. Solo registran cambios de precio significativos.

### Escala Aritmética vs. Logarítmica
- **Aritmética:** Igual distancia vertical = igual diferencia de precio. Útil para plazos cortos.
- **Logarítmica (semilog):** Igual distancia vertical = igual porcentaje de cambio. Recomendada para análisis de largo plazo porque muestra la variación porcentual real.

### El Período Temporal del Gráfico
- **Largo plazo (mensual/semanal):** Para identificar tendencia primaria y contexto.
- **Medio plazo (diario):** Para análisis y decisión táctica.
- **Corto plazo (4H, 1H):** Para refinamiento de entrada/salida.
- **Intradía (15min, 5min):** Para precisión de ejecución.

**Regla:** Siempre analizar de mayor a menor temporalidad.

---

## CAPÍTULO 4 — CONCEPTOS BÁSICOS DE TENDENCIA

### Definición de Tendencia
- **Tendencia alcista:** Sucesión de máximos y mínimos CRECIENTES (cada máximo y mínimo es más alto que el anterior).
- **Tendencia bajista:** Sucesión de máximos y mínimos DECRECIENTES.
- **Tendencia lateral (consolidación):** Máximos y mínimos aproximadamente en el mismo nivel.

### Soportes y Resistencias
- **Soporte:** Nivel de precio donde la demanda supera a la oferta y detiene o revierte una caída. Son mínimos previos.
- **Resistencia:** Nivel donde la oferta supera a la demanda y detiene o revierte una subida. Son máximos previos.
- **Principio de inversión de polaridad:** Un soporte roto se convierte en resistencia, y una resistencia rota se convierte en soporte. Es uno de los conceptos más importantes del análisis técnico.
- La **importancia** de un nivel S/R depende de: (1) duración del tiempo que el precio lo respetó, (2) volumen negociado en ese nivel, (3) cuánto tiempo ha pasado desde que se formó.

### Líneas de Tendencia
- Una línea de tendencia alcista se traza uniendo dos mínimos crecientes (el segundo mínimo más alto que el primero). Se necesita un tercer punto para confirmarla.
- Una línea de tendencia bajista conecta dos máximos decrecientes.
- **Cuanto más veces ha sido tocada y más tiempo ha durado, más importante es la línea.**
- El precio debe cerrar claramente al otro lado de la línea para considerarla rota (no solo picarla intradiaria).

### Canales de Precio
- Se traza una línea paralela a la línea de tendencia principal.
- En tendencia alcista: la línea del canal conecta los máximos. El precio tiende a rebotar entre ambas líneas.
- Útil para establecer objetivos de precio y para detectar señales de agotamiento cuando el precio no llega a la línea superior del canal.

### Retrocesos (Porcentajes)
- Las correcciones en tendencia tienden a retroceder en proporciones matemáticas predecibles:
  - **Retroceso del 50%:** El más conocido y observado.
  - **Retroceso de 1/3 (33%):** Mínimo retroceso tolerable en una tendencia sólida.
  - **Retroceso de 2/3 (66%):** Máximo retroceso antes de que la tendencia se considere en peligro.
  - **Retrocesos de Fibonacci:** 38.2%, 50%, 61.8% (el más importante = "golden ratio").

### Gaps (Huecos)
- **Gap común (area gap):** Ocurre en rangos laterales. Se cierra rápidamente. Poca importancia.
- **Gap de rotura (breakaway gap):** Ocurre al inicio de una nueva tendencia, rompiendo una zona consolidada. Señal fuerte. Raramente se cierra en el corto plazo.
- **Gap de continuación (runaway/measuring gap):** Ocurre a mitad de la tendencia. Señala que la tendencia continúa. Permite medir el objetivo de precio.
- **Gap de agotamiento (exhaustion gap):** Aparece al final de la tendencia, con movimiento acelerado. Se cierra rápidamente. Señal de reversión.

---

## CAPÍTULO 5 — PATRONES DE REVERSIÓN

### Cabeza y Hombros (H&S)
El patrón de reversión más fiable del análisis técnico.

**Formación:**
- Hombro izquierdo: Máximo con volumen elevado → Corrección
- Cabeza: Nuevo máximo más alto con volumen MENOR → Corrección a la línea del cuello
- Hombro derecho: Máximo más bajo que la cabeza, volumen AÚN MENOR → Ruptura de neckline

**Señal de entrada:** Cierre por debajo de la línea del cuello (neckline) con volumen.
**Objetivo de precio:** Medir la distancia desde la cabeza hasta la neckline y proyectarla hacia abajo desde el punto de ruptura.
**Pullback:** Frecuentemente el precio regresa a testear la neckline desde abajo antes de continuar el descenso.

**Cabeza y Hombros Invertido:** Mismo patrón pero al revés. Señal alcista. El volumen en la ruptura alcista es MÁS IMPORTANTE que en el techo.

### Dobles Techos y Dobles Suelos (M y W)
- **Doble Techo:** Dos máximos a niveles similares separados por un mínimo. Señal bajista cuando el precio cierra por debajo del mínimo intermedio (línea de confirmación).
- **Doble Suelo:** Imagen espejo. Señal alcista.
- El volumen suele ser menor en el segundo techo/suelo. En el doble suelo, el volumen en la ruptura alcista debe ser elevado.
- **Objetivo:** Medir la altura del patrón y proyectarla.

### Triples Techos y Triples Suelos
- Similar al H&S pero los tres techos/suelos están al mismo nivel.
- Menos frecuente pero muy fiable.

### Platillos (Saucers) y Picas (Spikes)
- **Platillo:** Cambio de tendencia lento y gradual. Forma curva. Volumen bajo durante el proceso, elevado en la confirmación.
- **Pica (V-reversal):** Cambio brusco sin proceso de distribución. Difícil de operar.

---

## CAPÍTULO 6 — PATRONES DE CONTINUACIÓN

### Triángulos
Los triángulos son patrones de continuación de la tendencia previa.

**Triángulo Simétrico:**
- Dos líneas convergentes: mínimos crecientes y máximos decrecientes.
- Neutral por naturaleza, pero rompe en la dirección de la tendencia previa.
- La ruptura suele ocurrir entre 2/3 y 3/4 de la formación.
- El volumen disminuye durante la formación y aumenta en la ruptura.

**Triángulo Ascendente:**
- Línea horizontal de resistencia + línea de soporte ascendente.
- Alcista por naturaleza. Señal de compra en la ruptura de la resistencia horizontal.

**Triángulo Descendente:**
- Línea horizontal de soporte + línea de resistencia descendente.
- Bajista por naturaleza. Señal de venta en la ruptura del soporte horizontal.

**Objetivo de precio:** Medir la altura máxima del triángulo y proyectarla desde el punto de ruptura.

### Banderas y Banderines (Flags y Pennants)
- Patrones de consolidación a corto plazo que ocurren a mitad de movimientos bruscos.
- La **bandera** es un pequeño rectángulo inclinado contra la tendencia.
- El **banderín** es un pequeño triángulo simétrico.
- Ambos requieren un "asta" (movimiento vertical brusco) antes del patrón.
- El volumen disminuye durante la consolidación y se dispara en la ruptura.
- **Son los patrones más fiables y más rápidos.**
- Objetivo: La distancia del asta se repite desde el punto de ruptura ("el palo de la bandera").

### Cuñas (Wedges)
- Dos líneas convergentes inclinadas en la misma dirección.
- **Cuña ascendente:** Señal bajista (el precio sube pero los impulsos son cada vez menores).
- **Cuña descendente:** Señal alcista.
- Pueden ser de reversión o continuación dependiendo del contexto.

### Rectángulos (Trading Ranges)
- Precios oscilan horizontalmente entre soporte y resistencia paralelos.
- Suelen ser de continuación pero también pueden ser de reversión.
- Operación: comprar en el soporte, vender en resistencia, o esperar ruptura.

---

## CAPÍTULO 7 — VOLUMEN E INTERÉS ABIERTO

### Principios del Volumen
- **El volumen confirma la tendencia:** En una tendencia alcista, el volumen debe ser mayor en los días alcistas y menor en los días bajistas.
- Si el volumen decrece durante los impulsos de la tendencia, la tendencia está perdiendo fuerza.
- **Volumen en rupturas:** Una ruptura con volumen elevado tiene más probabilidades de ser válida. Una ruptura con volumen bajo es sospechosa de ser falsa.

### On Balance Volume (OBV) — Granville
- Indicador acumulativo: suma el volumen cuando el precio sube, lo resta cuando baja.
- Cuando el OBV hace nuevos máximos, confirma la tendencia alcista.
- **Divergencia bajista:** El precio hace nuevos máximos pero el OBV no los confirma → señal de debilidad.
- **Divergencia alcista:** El precio hace nuevos mínimos pero el OBV no los confirma → señal de fortaleza oculta.

### Interés Abierto (Mercados de Futuros)
- Número total de contratos pendientes de liquidar.
- **Tendencia alcista + Interés abierto sube + Volumen sube:** Señal alcista fuerte (dinero nuevo entra en la tendencia).
- **Tendencia alcista + Interés abierto baja:** El alza puede ser débil (cierre de cortos, no nueva compra).
- **Caída con interés abierto elevado:** Señal bajista fuerte (posiciones largas siendo liquidadas a pérdida).

---

## CAPÍTULO 8 — GRÁFICOS A LARGO PLAZO

### Importancia del Análisis Multitemporal
- Antes de analizar un gráfico diario, revisar siempre el semanal y mensual.
- Un nivel de soporte/resistencia en gráfico mensual tiene mucha más importancia que uno en gráfico de 15 minutos.
- Las tendencias en gráficos de largo plazo dominan sobre las tendencias de corto plazo.
- Los patrones de precio también aparecen en gráficos de largo plazo y son igualmente válidos (más tiempo = más fiables).

---

## CAPÍTULO 9 — MEDIAS MÓVILES (MM)

### Fundamentos
Las medias móviles funcionan mejor en mercados con tendencia. En mercados laterales generan muchas señales falsas.
... (etc)
---

## CAPÍTULO 16 — GESTIÓN MONETARIA Y TÁCTICAS
... (etc)
---

## PRINCIPIOS UNIVERSALES DEL TRADER PROFESIONAL (Síntesis Murphy)

1. **Opera con la tendencia, nunca contra ella.** "The trend is your friend."
2. **Espera la confirmación antes de actuar.** Los patrones se confirman; no se anticipan.
3. **El volumen confirma el precio.** Una señal sin volumen es sospechosa.
4. **Gestiona el riesgo primero, las ganancias después.** El objetivo es sobrevivir en el mercado.
5. **La disciplina supera a la inteligencia.** Un sistema mediocre con disciplina perfecta supera a un sistema brillante sin disciplina.
6. **Las divergencias predicen, los cruces confirman.** Usar ambas para timing óptimo.
7. **El mercado siempre tiene razón.** Si tu análisis contradice al mercado, el mercado gana.
8. **Analiza de mayor a menor temporalidad.** Mensual → Semanal → Diario → 4H → 1H → 15min.
9. **La posición correcta del stop define el éxito de la operación**, no el precio de entrada.
10. **Cuantas más confluencias técnicas, mayor probabilidad de éxito.** Busca siempre mínimo 3.
