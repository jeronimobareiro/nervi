---
hide:
  - navigation
  - toc
---

# Nervi { .nv-oculto }

<div class="nv-portada" markdown>

<img class="nv-logo nv-claro" src="marca/nervi-logotipo-claro.svg" alt="Nervi">
<img class="nv-logo nv-oscuro" src="marca/nervi-logotipo-oscuro.svg" alt="Nervi">

<p class="nv-lema">Software libre de análisis y dimensionamiento estructural.</p>

Un motor de elementos finitos en Rust, una capa de aplicación en Python y cada fórmula verificada contra una solución conocida. Hecho en abierto, para ingenieros, docentes y estudiantes.

[Guía rápida](guia-rapida.md){ .md-button .md-button--primary }
[Código en GitHub](https://github.com/jeronimobareiro/nervi){ .md-button }

</div>

!!! warning "Versión preliminar, no apta para proyecto"
    Nervi está en la **Fase 1** (pórtico plano lineal elástico). Todavía no tiene diseño según normas ni interfaz gráfica publicada. Asiste al ingeniero; no reemplaza su criterio ni su responsabilidad profesional.

<div class="grid cards nv-tarjetas" markdown>

-   **Verificable**

    Cada caso de cálculo se compara con una fórmula cerrada y cita su fuente. Los resultados se pueden revisar línea por línea.

-   **Libre**

    Licencia GPL-3.0 o posterior. Podés usarlo, enseñar con él, estudiarlo y mejorarlo, sin licencias ni llaves.

-   **Abierto a universidades**

    La [hoja de ruta](hoja-de-ruta.md) marca tareas para un primer aporte, proyectos de cátedra y tesis.

</div>

## Qué hace hoy

- Pórticos planos con cargas nodales, uniformes y puntuales, articulaciones, cerchas, apoyos elásticos y asentamientos.
- Varios casos de carga y combinaciones, con reacciones, diagramas N, V y M y deformada.
- Un pórtico de 8 100 barras se resuelve en unos 45 ms.

```python
import nervi

m = nervi.Modelo()
a = m.agregar_nudo(0, 0)
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)   # kN, m
m.apoyar(a, ux=True, uy=True, rz=False)
m.apoyar(b, ux=False, uy=True, rz=False)
m.carga_uniforme("D", viga, qy=-20)

res = m.resolver().combinar("1.0D", {"D": 1.0})
print(res.diagrama(viga)["M"].max())        # 20 · 6² / 8 = 90 kN·m
```

## Documentación

- [Guía rápida](guia-rapida.md): Instalar, compilar y primer cálculo
- [Estado actual](estado.md): Qué funciona hoy y qué sigue
- [Especificación técnica](especificacion-tecnica.md): Arquitectura, método de cálculo y fases
- [Convenciones de signos](convenciones.md): Ejes, cargas y esfuerzos
- [Hoja de ruta](hoja-de-ruta.md): Hitos e issues para colaborar
- [Cómo contribuir](comunidad/contribuir.md): Reglas para aportar código y verificación
- [Bitácora](bitacora/index.md): Historia de cada aporte al proyecto
