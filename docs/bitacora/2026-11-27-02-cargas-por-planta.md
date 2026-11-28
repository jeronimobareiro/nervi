# 2026-11-27-02 · Cargas por planta: reparto de las losas a vigas y muros

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-r1brv3`
- **Fase de la hoja de ruta:** Fase 6/7, issue #78 (camino sin láminas), sobre el modelo físico de #73

## Qué se pidió

Cargas por planta sobre el modelo físico del edificio: cargas permanentes y sobrecargas en las losas, repartidas a las vigas. Es la opción 1 que Jerónimo Bareiro eligió el 27/11/2026.

## Qué se hizo

- `crates/nervi-core/src/losas.rs` (nuevo): reparto por áreas tributarias.
  - Cada punto de una losa convexa carga al borde apoyado más cercano. La zona de cada borde es la losa recortada con semiplanos (Sutherland y Hodgman).
  - El ancho tributario es lineal entre los vértices de la zona, así que cada tramo es una carga trapezoidal exacta.
  - Un borde está apoyado si lo cubren entero apoyos sobre su recta. Si lo cubren varios, cada uno recibe su parte.
  - Avisa las losas no convexas, las que no tienen apoyos, los bordes apoyados en parte y las zonas que se salen de su borde. Las losas se reparten en paralelo con rayon.
- `crates/nervi-py/src/losas.rs` (nuevo): `repartir_losas`, contrato `VERSION_CONTRATO_LOSAS = 1` (`docs/contrato-datos.md` §Reparto de losas).
- `python/nervi/reparto.py` (nuevo): arma los datos desde el modelo físico y devuelve `RepartoCargas`.
  - Casos `peso_propio`, `permanente` y `sobrecarga`.
  - Tramos en kN/m por viga y muro, resultantes y áreas tributarias. Se suman sobre los arreglos; los objetos `TramoCarga` se arman recién cuando se piden.
  - Zonas tributarias, avisos y el total de las losas para comprobar el equilibrio.
  - Los muros apoyan las losas de los pisos que alcanzan por encima de su base.
- `python/nervi/fisico.py`:
  - `agregar_piso` y `agregar_losa` aceptan `permanente` y `sobrecarga`, y `agregar_material` acepta `peso`.
  - Métodos nuevos `cargas_losa` y `repartir_cargas`.
- `python/nervi/formato/fisico.py`, `contenedor.py` y `migraciones.py`: módulo `fisico` versión 2, con las claves opcionales nuevas y la migración `fisico_1_a_2`, que no cambia nada.
- `tests/datos/nrv/fisico-v2.nrv` y `fisico-v2.esperado.json`: archivo de referencia con cargas, la carga de una losa y un hormigón de 20 kN/m³, con las resultantes del reparto.
- Interfaz (`python/nervi/gui/edificio.py` y `ventana.py`):
  - Botón *Cargas* con ícono (`ICONO_CARGAS`) y selector de caso en el modo *Edificio*.
  - Zonas tributarias y fuerza por viga en la planta.
  - Diagrama de carga (`DiagramaCarga`) y tabla por caso para la viga o el muro elegido.
  - Cargas editables en la planta, en las tablas *Pisos* y *Losas* y en las propiedades de la losa (la carga que se toma del piso se ve en gris).
  - Peso específico en *Materiales*.
- `examples/edificio_fisico.py`: cargas por planta y reparto con el equilibrio.
- `scripts/medir_reparto.py` (nuevo): banco de tiempos del reparto.

## Cómo se verificó

- `crates/nervi-core/tests/reparto_losas.rs` (9 casos), contra el cálculo a mano:
  - cuadrado en cuatro triángulos;
  - rectángulo de 6 × 4 m con trapecios de 8 m² y triángulos de 4 m², y los anchos en cada abscisa;
  - losa en una dirección;
  - losa con un borde libre (9 + 7,5 + 7,5 m²);
  - borde con dos vigas y losas vecinas con una viga corrida;
  - triángulo equilátero en sentido horario y antihorario;
  - hexágono irregular con un vértice alineado, con equilibrio exacto;
  - avisos y datos inválidos.
- 2 pruebas unitarias del módulo de Rust.
- `tests/test_reparto.py` (11 pruebas):
  - criterio de salida del issue: la losa rectangular contra el cálculo a mano y el equilibrio global exacto (tolerancia relativa 1e-13) en el edificio de ejemplo;
  - la misma carga en mm y en m;
  - cargas de la losa contra las del piso, y peso del material;
  - muros como apoyo;
  - avisos, zonas que cubren la losa, cargas inválidas y la ida y vuelta por el `.nrv`.
- `tests/test_formato_compatibilidad.py`: `fisico-v2.nrv` reparte lo mismo, y `fisico-v1.nrv` se migra y reparte solo el peso propio.
- `tests/test_gui_cargas.py` (5 pruebas):
  - el botón y el caso;
  - la viga V106 con 37,5 kN y 15 kN/m de peso propio;
  - las cargas del piso editadas y deshechas;
  - la tabla de losas con la carga heredada;
  - la losa sin repartir.
- `cargo test -p nervi-core`, `cargo clippy -D warnings`, `cargo fmt --check`, `pytest` completo (517 pasan, 4 se saltean), `ruff check` y `ruff format --check`: en verde.
- Rendimiento:
  - `scripts/medir_reparto.py`: 2000 losas y 4400 vigas (20 pisos de 10 × 10 vanos), 20 000 tramos, en 24 ms (11 ms en Rust). Una primera versión que armaba todo en Python tardaba 170 ms.
  - `scripts/medir_diseno.py`: no cambia (130 barras, diseño en 2,34 s), porque el diseño no se tocó.
- Capturas reales de la ventana en los dos temas, revisadas antes de implementar (`docs/img/cargas-planta.png`).

## Decisiones tomadas

- Las cargas de superficie se guardan por piso, con la posibilidad de reemplazarlas en cada losa. El reparto no se guarda: se calcula cuando se pide, porque es rápido y así nunca queda desactualizado.
- El peso propio se calcula del espesor con 25 kN/m³ si el material no da su `peso`. Va como caso aparte del resto de la permanente, para que el modelo de cálculo (#74) los pueda combinar como quiera.
- Las zonas tributarias son las del borde apoyado más cercano. Son las bisectrices a 45° en losas rectangulares y valen también para cualquier losa convexa. Las losas no convexas no se reparten todavía: se avisa y se dividen a mano en losas convexas.
- Si una viga y un muro están sobre el mismo borde, la carga va a la viga (el primer apoyo de la lista). Un borde cubierto solo en parte se toma como libre y se avisa.
- La tolerancia geométrica para decidir si un apoyo está sobre un borde es 1e-6 del tamaño del modelo (al menos 1 m). No interviene en el cálculo del reparto, que es cerrado.
- Interfaz: la muestra del 27/11/2026 se aprobó con un cambio de Jerónimo Bareiro, el botón *Cargas* con ícono en lugar de texto. Entre tres variantes mostradas en los dos temas eligió la losa con sus líneas de quiebre (zona tributaria) y no las flechas, para que no se confunda con las futuras cargas distribuidas y puntuales en barras, que llevarán flechas. El ícono quedó en el catálogo de íconos (entrada 2026-11-27-01) como `cargas_planta`, ahora en uso, junto con la familia de cargas que lo acompaña: flechas para las cargas de barra y la losa para las de superficie.
- **Firma DCO:** Jerónimo Bareiro autorizó por escrito, en el hilo del proyecto el 27/11/2026 ("Firmá por mi"), firmar este trabajo a su nombre. Se usó su correo `noreply` de GitHub (AGENTS.md §3.5).
- El diagrama de carga de una viga va en el panel de propiedades y no sobre la planta, porque sobre la planta tapaba las zonas y los rótulos.

## Documentación actualizada

- `docs/ESTADO.md`: las cargas por planta en "Qué funciona", la visión, la cantidad de pruebas y los próximos pasos.
- `docs/hoja-de-ruta.md`: #78 en curso.
- `docs/formato-nrv.md`: §4f para la versión 2 del módulo `fisico`, y la tabla de módulos y de versiones.
- `docs/contrato-datos.md`: §Reparto de losas (`repartir_losas`).
- `docs/diseno-interfaz.md`: §Cargas por planta, con la captura `docs/img/cargas-planta.png`.
- `docs/iconos.md` y `python/nervi/gui/iconos.py`: `cargas_planta` en uso (botón *Cargas*).
- `docs/glosario.md`: peso propio, carga permanente, sobrecarga de uso, peso específico, cargas por planta, área tributaria, reparto de cargas y borde apoyado o libre.
- `tests/datos/nrv/README.md`: `fisico-v2.nrv`.
- `AGENTS.md` y `CONTRIBUTING.md`: el banco de tiempos del reparto.
- `README.md` y sus traducciones, y `sitio/index.md` y sus traducciones (en, pt, ru): las cargas por planta en "Qué hace hoy".

## Pendiente y problemas conocidos

- Cargas en zonas de la losa y cargas lineales sobre la losa (tabiques), y el camino con losas malladas que tiene que dar la misma carga total (resto de #78, con #32 y #77).
- Losas no convexas: hoy se avisan y no se reparten.
- Bordes libres oblicuos y voladizos: hoy se avisan y no se reparten.
- Las cargas repartidas todavía no pasan al modelo de cálculo (#74).
- El método de reparto (zonas a 45° y bordes libres) tiene que revisarlo un ingeniero estructural antes de usarlo en un proyecto real.

## Para quien siga

- Para el modelo de cálculo (#74), `ModeloFisico.repartir_cargas().de_viga(id)` da los tramos trapezoidales de cada viga, con abscisas desde `p1`, que pasan directo a `carga_trapezoidal`.
- El método, las fuentes y los casos que no se reparten están en la documentación de `crates/nervi-core/src/losas.rs`.
