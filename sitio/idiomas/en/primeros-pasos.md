# Getting started

This guide solves a 6 m simply supported beam with a uniform load of 20 kN/m. The expected maximum moment is q·L²/8 = 20 · 6² / 8 = **90 kN·m**.

The units in this guide are kN and m. The direction of the axes and the signs of the internal forces are in [Sign conventions](tecnica/convenciones.md).

## With the interface

All the work is done in a single window. At the top is the path **Geometry › Loads › Analysis › Results**, on the left the project tree and on the right the properties of whatever you select.

1. **Geometry.** In the node table enter N1 at (0, 0) and N2 at (6, 0). In the member table join N1 with N2 and type E = 2.5e7, A = 0.125, I = 0.0026.
2. **Supports.** N1 with X and Y displacements restrained (pinned) and N2 with only Y restrained (roller).
3. **Loads.** Create case D and add a uniform load qy = −20 (downwards) to the member.
4. **Calculate.** Press **F5** or the **Calculate** button. If something is missing from the model, such as a support, the **Model review** tab tells you what.
5. **Results.** Choose the **Moment** diagram. Hovering over the member shows M, V and N at each point, and at mid-span the maximum of 90 kN·m appears. The reactions are in the table below.
6. **Save.** Ctrl+S saves the project as an `.nrv` file.

With **Ctrl+K** you open a search box to find any command or model element by name.

## With Python

The same calculation, written as a program:

```python
import nervi

m = nervi.Modelo()
a = m.agregar_nudo(0, 0)
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)
m.apoyar(a, ux=True, uy=True, rz=False)    # pinned
m.apoyar(b, ux=False, uy=True, rz=False)   # roller
m.carga_uniforme("D", viga, qy=-20)        # kN/m downwards
m.carga_uniforme("L", viga, qy=-10)

res = m.resolver()
d = res.combinar("D", {"D": 1.0})
print(d.diagrama(viga)["M"].max())         # 90 kN·m
print(d.reacciones[a])                     # [Rx, Ry, Mz] = [0, 60, 0]

u = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
print(u.diagrama(viga)["M"].max())         # 0.125 · 40 · 6² = 180 kN·m
```

The function and argument names are in Spanish, the project's working language (`Modelo` is the model, `agregar_nudo` adds a node, `agregar_barra` adds a member, `apoyar` sets a support, `carga_uniforme` adds a uniform load, `resolver` solves, `combinar` combines load cases). A more complete example, a frame with wind loads and combinations, is in [`examples/portico_simple.py`](https://github.com/jeronimobareiro/nervi/blob/main/examples/portico_simple.py).

## If a result does not add up

Always check with a hand calculation or another method. If you find a result you believe is wrong, [open a report](https://github.com/jeronimobareiro/nervi/issues/new/choose) with the model and the value you expected. If the error could affect a real structure, follow the [security policy](participar/seguridad.md).
