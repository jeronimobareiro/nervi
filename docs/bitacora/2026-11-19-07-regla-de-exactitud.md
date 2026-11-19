# 2026-11-19-07 · Regla de exactitud y cierre del plan de rendimiento

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-8xjxwp`
- **Fase de la hoja de ruta:** rendimiento (transversal)

## Qué se pidió

Jerónimo Bareiro decidió que bajo ningún término se bajan tolerancias ni exactitud para ganar tiempo, y que la búsqueda de la armadura óptima de columnas queda como está. Se pidió dejar esa regla escrita en el repositorio.

## Qué se hizo

- `AGENTS.md` §2: regla de exactitud, por encima de la de rendimiento. Ninguna migración u optimización baja tolerancias, iteraciones de convergencia ni exactitud, y toda da exactamente los mismos resultados que la versión anterior.
- `CONTRIBUTING.md` (regla 7), los cuatro README (principio "Rendimiento primero") y la plantilla de PR (casilla de cálculo) suman la misma regla.
- `scripts/medir_diseno.py --comparar` pasa a exigir por defecto una diferencia relativa de 1e-12 en vez de 1e-6, además del mismo estado y la misma armadura en cada elemento. Solo admite el redondeo de la aritmética de doble precisión.
- `docs/hoja-de-ruta.md` y `docs/ESTADO.md`: plan de rendimiento cerrado con las fases 0 a 2; las fases 3 y 4 no se hacen por ahora.

## Cómo se verificó

- `main` actual contra los resultados guardados antes de la fase 1, cuando columnas y vigas estaban en Python: con `--tolerancia 0`, las 130 barras del pórtico de referencia tienen la misma armadura y el mismo estado, y 36 relaciones de flexocompresión difieren en el último dígito. La mayor diferencia relativa es 1,4e-15, unas pocas unidades del último bit, porque Rust y NumPy suman en distinto orden. Con la tolerancia nueva por defecto (1e-12), `--comparar` da "igual a la referencia". Contra los resultados de antes de la fase 2, la flexión de vigas da diferencia cero.
- `ruff` en verde.

## Decisiones tomadas

- "Exactamente los mismos resultados" se define como misma armadura, mismo estado y los mismos números salvo el redondeo de doble precisión. Exigir los mismos bits entre Rust y NumPy no es posible en general, porque el orden de las sumas cambia el último bit sin cambiar la exactitud del método. 1e-12 relativa está muchos órdenes por encima de ese redondeo y muy por debajo de cualquier tolerancia de convergencia del diseño (las bisecciones paran en 1e-9 y 1e-10).
- La búsqueda de armadura de columnas no se acelera: es el cálculo que da el valor óptimo y su tiempo actual (2,4 s en el pórtico de referencia, 12 s en uno de 750 barras) se acepta.

## Documentación actualizada

- `AGENTS.md`, `CONTRIBUTING.md`, `README.md`, `README.en.md`, `README.pt.md`, `README.ru.md`, `.github/pull_request_template.md`, `docs/hoja-de-ruta.md` y `docs/ESTADO.md`. No cambió lo que un usuario puede hacer, así que `sitio/` no se tocó.

## Pendiente y problemas conocidos

- Sumar el banco de tiempos al CI.

## Para quien siga

- Antes de cualquier cambio en el cálculo: `python scripts/medir_diseno.py --guardar antes.json` en `main` y `--comparar antes.json` con tu cambio, sin pasar `--tolerancia`.
