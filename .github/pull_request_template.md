## Qué cambia

## Fuente de las fórmulas

<!-- Norma con edición y artículo, libro con página o derivación. Escribí "no aplica" si no hay fórmulas nuevas. -->

## Verificación

<!-- Pruebas agregadas y contra qué se comparan. -->

## Rendimiento

<!-- Si el cambio toca cálculo: tiempo del pórtico de referencia antes y después (`python scripts/medir_diseno.py`). Escribí "no aplica" si no toca cálculo. -->

## Documentación actualizada

<!-- Archivos informativos actualizados en este PR (README y traducciones, CONTRIBUTING.md, AGENTS.md, docs/ESTADO.md, hoja de ruta, sitio, docs técnicos), o por qué no hizo falta. Ver CONTRIBUTING.md §Documentación al día. -->

## Lista de control

- [ ] Los commits están firmados (`git commit -s`, ver CONTRIBUTING.md).
- [ ] Agregué una entrada en `docs/bitacora/` y actualicé `docs/ESTADO.md`, o pido ayuda para hacerlo.
- [ ] Actualicé en este mismo PR la documentación que el cambio deja desactualizada (README y traducciones, CONTRIBUTING, AGENTS, hoja de ruta, sitio, docs técnicos).
- [ ] Si toca cálculo que recorre barras, nudos, combinaciones o puntos, está en Rust con la misma API de Python, medí el tiempo antes y después y da exactamente los mismos resultados (`scripts/medir_diseno.py --comparar`, sin bajar tolerancias).
- [ ] Si toca la interfaz, usa el sistema de diseño de `estilo.py` en los dos temas y, si cambia el diseño, mostré antes una muestra visual.
- [ ] No incluye código, texto de normas ni gráficos de terceros con derechos incompatibles.
- [ ] Si es un módulo normativo, queda marcado como experimental hasta la revisión de un ingeniero.
