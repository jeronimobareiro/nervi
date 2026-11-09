# Errores críticos y seguridad

Nervi calcula estructuras. Un resultado incorrecto puede llevar a una estructura insegura, así que tratamos esos errores con prioridad.

## Qué reportar en privado

- Resultados incorrectos que podrían subestimar esfuerzos, deformaciones o la armadura necesaria.
- Verificaciones normativas que aprueban un elemento que no cumple.
- Vulnerabilidades de software (por ejemplo, al leer archivos de terceros).

Escribí a **jerobareiro@gmail.com** con el modelo mínimo que reproduce el problema, la versión de Nervi y el resultado que esperabas con su fuente. Respondemos lo antes posible y publicamos la corrección junto con un aviso en las notas de la versión.

Los errores sin impacto en la seguridad (mensajes, documentación, rendimiento) van como issue público.

## Responsabilidad

Nervi se distribuye **sin ninguna garantía**, según las secciones 15 y 16 de la [licencia GPL-3.0](LICENSE). El software asiste al profesional; no reemplaza su criterio. Todo cálculo usado en un proyecto real debe ser verificado y firmado por un profesional habilitado, que es responsable del diseño.
