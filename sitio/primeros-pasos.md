# Primeros pasos

Esta guía resuelve una viga simplemente apoyada de 6 m con una carga uniforme de 20 kN/m. El momento máximo esperado es q·L²/8 = 20 · 6² / 8 = **90 kN·m**.

Las unidades de esta guía son kN y m. El sentido de los ejes y los signos de los esfuerzos están en [Convenciones de signos](tecnica/convenciones.md).

## Con la interfaz

Todo el trabajo se hace en una sola ventana. Arriba está el recorrido **Geometría › Cargas › Análisis › Resultados › Diseño**, a la izquierda el panel **Estructura** con nudos, barras, apoyos, secciones, cargas y combinaciones en secciones plegables y a la derecha las propiedades de lo que seleccionás.

1. **Geometría.** En la tabla de nudos cargá N1 en (0, 0) y N2 en (6, 0). En la tabla de barras uní N1 con N2 y escribí E = 2.5e7, A = 0.125, I = 0.0026.
2. **Apoyos.** N1 con desplazamientos X e Y impedidos (articulado fijo) y N2 solo con Y impedido (carrito).
3. **Cargas.** Creá el caso D y agregá a la barra una carga uniforme qy = −20 (hacia abajo).
4. **Calcular.** Presioná **F5** o el botón **Calcular**. Si al modelo le falta algo, como un apoyo, la pestaña **Revisión del modelo** te dice qué es.
5. **Resultados.** Elegí el diagrama de **Momento**. Al pasar el cursor por la barra ves M, V y N en cada punto, y en el centro aparece el máximo de 90 kN·m. Las reacciones están en la tabla de abajo. Con el botón **3D**, a la izquierda de los diagramas, ves la misma viga con sus cargas en 3D: se gira arrastrando con el mouse y un clic en una barra la selecciona.
6. **Diseño (experimental).** Para armar la viga hace falta al menos una combinación: agregá en la tabla de combinaciones `1.4D` con factor 1.4 para D y calculá de nuevo. En la etapa **Diseño** elegí f'c, fy y el recubrimiento y presioná **Diseñar**. La viga se toma como rectangular con el mismo A e I (unos 250 × 500 mm en este ejemplo; podés cambiarla en la tabla). Cada barra muestra su armadura inferior, superior y estribos, y al elegirla ves cada verificación con su artículo de ACI 318-19. Las columnas muestran su armadura longitudinal (sin estribos) y la verificación a flexocompresión. Es una versión experimental, que todavía no revisó un ingeniero estructural.
7. **Guardar.** Ctrl+S guarda el proyecto como archivo `.nrv`, junto con los datos de diseño.
8. **Modos y espectro (preliminar).** En la pestaña **Dinámica** poné factor 1 a D en la tabla de masa (y, si querés, 0,25 a L), presioná **+** para agregar un espectro de ejemplo y luego **Análisis modal y espectral**. La tabla muestra el periodo y la masa participante de cada modo; al elegir uno se dibuja su forma, y **Animar modo** la hace oscilar. Al elegir el espectro ves su cortante basal y sus diagramas, que son valores absolutos combinados. Los valores del espectro de ejemplo no son de ninguna norma: cargá los que correspondan.
9. **Memoria de cálculo.** Ctrl+P (o **Exportar memoria de cálculo** en el menú) genera un PDF con el modelo, las cargas, las combinaciones, las tablas de resultados y los diagramas de cada caso y combinación. Si diseñaste, suma un capítulo con las armaduras y las verificaciones, y si analizaste la dinámica, uno con las masas, los modos y los espectros.

Con **Ctrl+K** abrís un buscador para encontrar cualquier comando o elemento del modelo por su nombre.

Los menús están en la barra de íconos de la izquierda. En **Preferencias** (el último ícono) elegís el tema claro u oscuro, el tamaño de letra y qué abrir al iniciar; Nervi lo recuerda. En **Archivo › Configuración del proyecto** cargás los datos de la carátula de la memoria, los materiales y los criterios de diseño, entre ellos los diámetros entre los que Nervi elige la armadura de las columnas.

## Con Python

El mismo cálculo, escrito como programa:

```python
import nervi

m = nervi.Modelo()
a = m.agregar_nudo(0, 0)
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)
m.apoyar(a, ux=True, uy=True, rz=False)    # articulado fijo
m.apoyar(b, ux=False, uy=True, rz=False)   # carrito
m.carga_uniforme("D", viga, qy=-20)        # kN/m hacia abajo
m.carga_uniforme("L", viga, qy=-10)

res = m.resolver()
d = res.combinar("D", {"D": 1.0})
print(d.diagrama(viga)["M"].max())         # 90 kN·m
print(d.reacciones[a])                     # [Rx, Ry, Mz] = [0, 60, 0]

u = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
print(u.diagrama(viga)["M"].max())         # 0.125 · 40 · 6² = 180 kN·m
```

Un ejemplo más completo, un pórtico con cargas de viento y combinaciones, está en [`examples/portico_simple.py`](https://github.com/jeronimobareiro/nervi/blob/main/examples/portico_simple.py).

### Pórtico espacial (preliminar)

En 3D el eje Z es vertical hacia arriba y cada nudo tiene seis grados de libertad. Este emparrillado en L está empotrado en un extremo y cargado en el otro; la barra que sale del empotramiento trabaja a flexión y a torsión:

```python
import nervi
from nervi.secciones import rectangular

m = nervi.Modelo3D()
a = m.agregar_nudo(0, 0, 0)
b = m.agregar_nudo(3, 0, 0)
c = m.agregar_nudo(3, 2, 0)
sec = rectangular(b=0.25, h=0.50)              # h sobre el eje y local (hacia arriba)
m.agregar_barra(a, b, E=2.5e7, G=1.04e7, seccion=sec)
m.agregar_barra(b, c, E=2.5e7, G=1.04e7, seccion=sec)
m.apoyar(a)                                    # empotramiento (6 GDL)
m.carga_nodal("P", c, fz=-10)                  # 10 kN hacia abajo

r = m.resolver()["P"]
print(r.desplazamientos[c, 2])                 # -0.00825 m (8.25 mm hacia abajo)
print(r.diagrama(0)["T"][0])                   # torsor en la primera barra: -20 kN·m
```

Las convenciones de ejes y signos en 3D están en la [documentación técnica](https://github.com/jeronimobareiro/nervi/blob/main/docs/convenciones.md). Un pórtico de un piso con vigas y columnas está en [`examples/portico_espacial.py`](https://github.com/jeronimobareiro/nervi/blob/main/examples/portico_espacial.py).

## Si un resultado no te cierra

Verificá siempre con un cálculo a mano o con otro método. Si encontrás un resultado que creés incorrecto, [abrí un reporte](https://github.com/jeronimobareiro/nervi/issues/new/choose) con el modelo y el valor que esperabas. Si el error puede afectar una estructura real, seguí la [política de seguridad](participar/seguridad.md).
