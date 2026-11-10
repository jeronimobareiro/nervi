# Primeros pasos

Esta guía resuelve una viga simplemente apoyada de 6 m con una carga uniforme de 20 kN/m. El momento máximo esperado es q·L²/8 = 20 · 6² / 8 = **90 kN·m**.

Las unidades de esta guía son kN y m. El sentido de los ejes y los signos de los esfuerzos están en [Convenciones de signos](tecnica/convenciones.md).

## Con la interfaz

Todo el trabajo se hace en una sola ventana. Arriba está el recorrido **Geometría › Cargas › Análisis › Resultados**, a la izquierda el árbol del proyecto y a la derecha las propiedades de lo que seleccionás.

1. **Geometría.** En la tabla de nudos cargá N1 en (0, 0) y N2 en (6, 0). En la tabla de barras uní N1 con N2 y escribí E = 2.5e7, A = 0.125, I = 0.0026.
2. **Apoyos.** N1 con desplazamientos X e Y impedidos (articulado fijo) y N2 solo con Y impedido (carrito).
3. **Cargas.** Creá el caso D y agregá a la barra una carga uniforme qy = −20 (hacia abajo).
4. **Calcular.** Presioná **F5** o el botón **Calcular**. Si al modelo le falta algo, como un apoyo, la pestaña **Revisión del modelo** te dice qué es.
5. **Resultados.** Elegí el diagrama de **Momento**. Al pasar el cursor por la barra ves M, V y N en cada punto, y en el centro aparece el máximo de 90 kN·m. Las reacciones están en la tabla de abajo.
6. **Guardar.** Ctrl+S guarda el proyecto como archivo `.nrv`.

Con **Ctrl+K** abrís un buscador para encontrar cualquier comando o elemento del modelo por su nombre.

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

## Si un resultado no te cierra

Verificá siempre con un cálculo a mano o con otro método. Si encontrás un resultado que creés incorrecto, [abrí un reporte](https://github.com/jeronimobareiro/nervi/issues/new/choose) con el modelo y el valor que esperabas. Si el error puede afectar una estructura real, seguí la [política de seguridad](participar/seguridad.md).
