# Casos verificados

Nervi no te pide que le creas: cada tipo de cálculo se compara con una solución conocida, y esa comparación corre sola en cada cambio del programa. Esta página explica cómo se verifica y lista los casos que hoy tiene la biblioteca.

## Cómo se verifica

- Cada caso es un archivo de texto con el modelo, los resultados esperados y su **fuente**: una fórmula cerrada, un libro con página y número de ejemplo, o una solución resuelta a mano con aritmética exacta.
- El control automático de GitHub resuelve todos los casos en cada aporte y se pone en rojo si algún valor se aleja del esperado más que la tolerancia (por defecto, un error relativo de 1e-9).
- Además del motor, hay decenas de pruebas analíticas en Rust (mecanismos, pórtico espacial, dinámica, brazos y diafragmas rígidos) y cientos de pruebas en Python (formato de archivo, interfaz, memoria de cálculo y diseño).
- Los módulos de **diseño de hormigón armado** (ACI 318-19) están verificados con cálculos a mano y contra programas de código abierto, pero todavía no con ejemplos publicados ni con la revisión de un ingeniero estructural: por eso se marcan como experimentales.

## Casos de la biblioteca

Hoy la carpeta [`verification/`](https://github.com/jeronimobareiro/nervi/tree/main/verification) tiene **{{N_CASOS}} casos**:

{{CASOS}}

## Cómo aportar un caso

Agregar un caso no requiere saber Rust ni tocar el motor: alcanza con escribir un archivo de texto. Un ejemplo resuelto de tu libro de cátedra es un excelente primer aporte. Las instrucciones están en el [README de la biblioteca](https://github.com/jeronimobareiro/nervi/blob/main/verification/README.md) y en [cómo participar](participar/index.md).
