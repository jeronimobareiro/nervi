# 2026-11-27-01 · Catálogo de íconos de la interfaz

- **Agente:** Claude (Claude Code)
- **Pedido por:** Jerónimo Bareiro
- **Rama / PR / commit:** `claude/project-thread-l1weoz`
- **Fase de la hoja de ruta:** Fase 5 · Interfaz gráfica (transversal a todas las fases)

## Qué se pidió

Un catálogo de todos los íconos que va a necesitar la interfaz, también para las implementaciones futuras de la hoja de ruta, para que cualquier aporte tome sus íconos de ahí.

## Qué se hizo

- `python/nervi/gui/iconos.py` (nuevo): `CATALOGO` con 120 íconos en 11 grupos (menús; archivo y edición; vista y navegación; modelo de cálculo; modelo físico; cargas; análisis y resultados; diseño de hormigón; diseño de acero y mixtas; documentos e intercambio; estados). Cada `Icono` tiene clave, nombre, grupo, cuerpo SVG, uso (fase o issue que lo necesita) y si ya está en uso. Funciones `svg()`, `pixmap()` (con caché) y `qicon()` (reposo `texto_2`, marcado `acento`, deshabilitado `deshabilitado`).
- Los 25 íconos que ya usaba la aplicación pasan al catálogo sin cambiar su dibujo: `estilo.ICONOS_MENU` y `estilo.svg_menu`, `arbol.ICONOS_ARBOL` y `ventana.ICONO_PLANTAS`, `ICONO_SUBIR` e `ICONO_BAJAR` ahora leen del catálogo, con los mismos nombres para no romper a quien los usa. Los del árbol conservan su grilla de 16 (campo `rejilla`) para dar exactamente los mismos píxeles.
- Los 95 restantes quedan reservados para las fases: apoyos y liberaciones (#13, #14, #31), fundaciones, escaleras, tanques y contención (#88, #89), viento, sismo y uso (#79 a #81), dinámica y P-Δ (#17 a #19), hormigón y servicio (#22 a #24, #90, #93, #101, #102), acero, uniones y mixtas (#83 a #85, #91, #92, #100), DXF, IFC, láminas, planillas, cómputos y versiones (#25 a #29, #75, #76, #95 a #98).
- `scripts/lamina_iconos.py` (nuevo): dibuja la lámina del catálogo en los dos temas (`docs/img/iconos-claro.png` y `iconos-oscuro.png`).
- `docs/iconos.md` (nuevo): guía de uso, reglas de la familia, cómo agregar un ícono y la lista completa.

## Cómo se verificó

- `tests/test_iconos.py` (nuevo, 10 pruebas): claves únicas y grupos válidos; cuerpos solo con formas (`path`, `circle`, `rect`, `ellipse`) y sin relleno, trazo ni color propios; los íconos marcados en uso son exactamente los de la barra lateral, el árbol y el modo Edificio; ancho del trazo en píxeles a 16, 18, 20 y 24 px; **los íconos en uso dibujan imágenes idénticas** a las de antes a escala 1, 1,5 y 2; `pixmap` y `qicon` con sus estados; `docs/iconos.md` lista todo el catálogo.
- `pytest` completo y `ruff check` / `ruff format --check` en verde.

## Decisiones tomadas

- Una sola grilla de 24 para los íconos nuevos, con el trazo de la barra lateral (1,7). A 16 px el trazo pasa a 2,1 unidades para medir 1,4 px como el árbol. Se descartó redibujar el árbol en la grilla de 24: escalado, cambiaba el suavizado de algunos píxeles.
- El catálogo no importa `estilo` (solo para tipos), así `estilo` puede leer de él sin ciclos.
- El ícono de *Cargas* del modo Edificio lo elige el aporte de cargas por planta; entra al catálogo como `cargas_planta` cuando se apruebe (`cargas` ya es el del árbol).
- La muestra de los íconos nuevos se mostró en los dos temas antes de implementarlos.

## Documentación actualizada

- `docs/iconos.md` (nuevo) y `docs/img/iconos-claro.png` y `iconos-oscuro.png`.
- `AGENTS.md` §2 (Interfaz) y `CONTRIBUTING.md` (regla 8 y tabla de Documentación al día): los íconos salen del catálogo.
- `docs/diseno-interfaz.md` §Menús y ajustes, `docs/hoja-de-ruta.md` (principio de interfaz) y `docs/ESTADO.md`.
- README, sitio y traducciones: no cambian, porque no cambia nada de lo que ve o hace el usuario.

## Pendiente y problemas conocidos

- Sumar `cargas_planta` cuando se apruebe el ícono de Cargas del modo Edificio.
- Los íconos reservados son una propuesta: cada aporte puede ajustar el dibujo del suyo con una muestra antes de ponerlo en uso.

## Para quien siga

- Leé `docs/iconos.md`. Para un botón nuevo: `iconos.qicon("clave", estilo.actual, 20, boton.devicePixelRatioF())`, y pasá el ícono a `en_uso=True` en el mismo PR.
- **Avisos:** los commits necesitan la firma DCO de la persona que pidió el trabajo (`git rebase --signoff origin/main`).
