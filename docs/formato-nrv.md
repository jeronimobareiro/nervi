# Formato de archivo `.nrv` (contenedor 1, módulo `modelo` 1, borrador)

> **Estado: borrador.** Se congela con la primera versión publicada de la GUI (v0.1.0). Hasta entonces se puede cambiar sin migración; después, todo cambio sigue §6.
>
> **Compromiso:** un `.nrv` guardado con cualquier versión publicada de Nervi se abre con todas las versiones posteriores y da los mismos resultados. No se quita nunca la lectura de un formato viejo. Ver §6.

Un archivo `.nrv` guarda un **proyecto de Nervi completo**: geometría, materiales y secciones, apoyos, casos y combinaciones de carga, y (más adelante) normas, criterios de diseño, resultados y estado de la vista. IFC queda para **importar y exportar** (especificación §6): no guarda casos, combinaciones, configuración de normas ni resultados de forma fiable, así que no sirve como formato de trabajo.

La especificación es pública y forma parte del proyecto (GPL-3.0-or-later el código, el formato es libre de implementar por cualquiera).

## 1. Extensión y tipo MIME

| Dato | Valor |
|---|---|
| Extensión | `.nrv` (minúsculas al escribir; al leer, sin distinguir mayúsculas) |
| Tipo MIME | `application/vnd.nervi.proyecto+zip` (no registrado en IANA; registrarlo es opcional y gratuito) |
| Firma | ZIP cuyo primer miembro es `mimetype` sin comprimir (§2.1) |

**Choque con otras extensiones.** La única otra aplicación conocida que usa `.nrv` es Nero (compilaciones de Video-CD de Nero Burning ROM / Nero Vision, formato binario de los años 2000, sin tipo MIME registrado). Ningún programa de ingeniería la usa. El riesgo es bajo y se cubre con la firma de §2.1: Nervi y el sistema operativo distinguen un `.nrv` de Nervi por su contenido, no solo por el nombre. Fuentes: [file-extensions.org](https://www.file-extensions.org/extension/nrv), [filext.com](https://filext.com/file-extension/NRV), [file.org](https://file.org/extension/nrv).

## 2. Contenedor

Un `.nrv` es un archivo **ZIP** (como `.docx`, `.odt` o `.3mf`) con esta estructura:

```
proyecto.nrv
├── mimetype            # obligatorio, primer miembro, sin comprimir
├── nervi.json          # obligatorio: manifiesto (versión del contenedor, módulos, generador, fechas)
├── modelo.json         # módulo "modelo", obligatorio: el modelo analítico (§4)
├── diseno.json …       # módulo "diseno", Fase 3 (previsto)
├── resultados/         # módulo "resultados", caché (previsto, §5)
├── vista.json          # módulo "vista", estado de la GUI (previsto)
└── adjuntos/           # módulo "adjuntos": imágenes, memorias (previsto)
```

### 2.1 Firma (`mimetype`)

- Primer miembro del ZIP, nombre exacto `mimetype`, método **STORED** (sin compresión), sin campo extra.
- Contenido: los bytes ASCII `application/vnd.nervi.proyecto+zip`, sin salto de línea.
- Resultado: el archivo empieza con `PK\x03\x04` y en el desplazamiento 30 aparece `mimetypeapplication/vnd.nervi.proyecto+zip`. Es el mismo truco que usan ODF y EPUB, y lo que usa `shared-mime-info` en Linux para reconocerlo (§7.2).

### 2.2 Reglas del ZIP

- Los JSON van en UTF-8 sin BOM, comprimidos con DEFLATE.
- Nombres de miembros en minúsculas, separador `/`, sin rutas absolutas ni `..` (el lector los rechaza).
- El lector ignora los miembros que no conoce y **los conserva** al volver a guardar.
- Límites del lector para no abrir archivos maliciosos: 200 MB descomprimidos por miembro y 10 000 miembros; si se superan, error claro.

### 2.3 Escritura segura

Guardar es: escribir en `proyecto.nrv.tmp` en la misma carpeta, `fsync`, y renombrar sobre `proyecto.nrv` (`os.replace`). Un corte de luz deja el archivo viejo o el nuevo, nunca uno a medias. La GUI puede guardar además una copia `proyecto.nrv.bak` antes de sobrescribir.

## 3. Manifiesto (`nervi.json`)

```json
{
  "formato": "nervi.proyecto",
  "version_esquema": 1,
  "generador": {"nombre": "Nervi", "version": "0.1.0"},
  "creado": "2026-11-10T08:00:00Z",
  "modificado": "2026-11-10T09:30:00Z",
  "modulos": {
    "modelo": {"version": 1, "miembros": ["modelo.json"], "requerido": true}
  }
}
```

| Clave | Tipo | Obligatoria | Contenido |
|---|---|---|---|
| `formato` | texto | sí | Siempre `"nervi.proyecto"`. |
| `version_esquema` | entero ≥ 1 | sí | Versión del **contenedor**: la estructura del ZIP y del manifiesto. No cambia cuando un módulo agrega datos (§6). |
| `modulos` | objeto | sí (§3.1) | Los módulos del proyecto, cada uno con su versión. |
| `generador` | objeto | sí | Programa y versión que escribió el archivo. Solo informativo. |
| `creado`, `modificado` | texto ISO 8601 UTC | no | Fechas. |

Las versiones del formato son independientes de `VERSION_CONTRATO` (el contrato Rust ↔ Python, `docs/contrato-datos.md`) y de la versión del programa.

### 3.1 Módulos

Un proyecto se arma con **módulos**: piezas independientes, cada una con sus archivos dentro del ZIP, su propia versión y sus propias migraciones. Así cada fase de la hoja de ruta agrega su módulo sin tocar los demás: un proyecto de la Fase 1 es un proyecto que solo tiene el módulo `modelo`.

| Clave de `modulos.<nombre>` | Tipo | Contenido |
|---|---|---|
| `version` | entero ≥ 1 | Versión de ese módulo. |
| `miembros` | lista de textos | Archivos del ZIP que le pertenecen. Un nombre que termina en `/` es una carpeta entera (`resultados/`). |
| `requerido` | booleano (omisión `false`) | `true` si el proyecto no se puede usar sin entender ese módulo. |

Nombres de módulo: minúsculas, dígitos y `_`, con `.` para separar un prefijo (`miplugin.algo`). Los nombres sin prefijo están reservados para Nervi.

| Módulo | Estado | Requerido | Contenido |
|---|---|---|---|
| `modelo` | versión 1 | siempre | Modelo analítico: nudos, barras, apoyos, cargas, casos y combinaciones (§4). |
| `diseno` | previsto (Fase 3) | no | Normas, criterios, secciones de armado y resultados de diseño. |
| `resultados` | previsto (§5) | no | Caché de resultados. |
| `vista` | previsto | no | Cámara, capas, selección. |
| `adjuntos` | previsto | no | Imágenes, memorias, planos. |

Reglas del lector:

1. **Módulo conocido, versión igual o menor:** se lee y, si hace falta, se migra (§6).
2. **Módulo desconocido o de versión más nueva, no requerido:** se abre el resto del proyecto, se avisa al usuario y el módulo se **conserva byte a byte** al guardar, con su entrada del manifiesto.
3. **Módulo desconocido o de versión más nueva, requerido:** el archivo no se abre y el error dice qué módulo y qué versión hacen falta ("Este proyecto usa el módulo 'portico_3d'… Actualizá Nervi.").
4. **Manifiesto sin `modulos`:** es un archivo guardado antes de que existieran (noviembre de 2026). Se lee como `{"modelo": {"version": 1, "miembros": ["modelo.json"], "requerido": true}}`.

Un módulo no requerido que hace referencia a `id` del modelo (diseño, resultados) guarda el SHA-256 del `modelo.json` con el que se armó. Si al leerlo no coincide, el programa que lo conoce sabe que el modelo cambió después (por ejemplo, porque lo editó una versión que no conocía el módulo) y lo trata como desactualizado, nunca como válido.

## 4. Módulo `modelo` (`modelo.json`), versión 1

Cubre lo que hoy modela `nervi.Modelo` (Fase 1, pórtico plano). El esquema formal está en [`esquemas/nrv-modelo-v1.schema.json`](esquemas/nrv-modelo-v1.schema.json) (JSON Schema 2020-12).

```json
{
  "tipo": "portico_2d",
  "unidades": {"fuerza": "kN", "longitud": "m"},
  "nudos": [
    {"id": 1, "x": 0.0, "y": 0.0},
    {"id": 2, "x": 0.0, "y": 3.0},
    {"id": 3, "x": 5.0, "y": 3.0},
    {"id": 4, "x": 5.0, "y": 0.0}
  ],
  "barras": [
    {"id": 1, "i": 1, "j": 2, "E": 2.5e7, "A": 0.09, "I": 6.75e-4},
    {"id": 2, "i": 2, "j": 3, "E": 2.5e7, "A": 0.12, "I": 1.6e-3, "liberaciones": [false, false, true, false, false, false]},
    {"id": 3, "i": 3, "j": 4, "E": 2.5e7, "A": 0.09, "I": 6.75e-4}
  ],
  "apoyos": [
    {"nudo": 1, "ux": true, "uy": true, "rz": true},
    {"nudo": 4, "ux": true, "uy": true, "rz": false}
  ],
  "resortes": [],
  "casos": [
    {"id": 1, "nombre": "D"},
    {"id": 2, "nombre": "L"}
  ],
  "cargas_nodales": [
    {"caso": 2, "nudo": 2, "fx": 10.0}
  ],
  "cargas_barra": [
    {"caso": 1, "barra": 2, "tipo": "uniforme", "ejes": "local", "qy": -12.0},
    {"caso": 2, "barra": 2, "tipo": "puntual", "ejes": "global", "a": 2.5, "py": -20.0},
    {"caso": 1, "barra": 2, "tipo": "trapezoidal", "ejes": "local", "a": 1.0, "b": 4.0, "qy1": -5.0, "qy2": -15.0}
  ],
  "desplazamientos_impuestos": [],
  "combinaciones": [
    {"nombre": "1.2D+1.6L", "factores": {"D": 1.2, "L": 1.6}}
  ],
  "extensiones": {}
}
```

### 4.1 Reglas

- **Identificadores estables.** Nudos, barras y casos llevan un `id` entero positivo, único dentro de su lista, que **no** tiene que ser consecutivo. Las referencias (`i`, `j`, `nudo`, `barra`, `caso`) usan ese `id`, no la posición. Así la GUI puede borrar un nudo sin renumerar el resto, y un `diff` entre versiones del archivo es legible. Al cargar, el lector arma la tabla `id → índice` que pide `nervi.Modelo`.
- **Unidades.** El motor no impone unidades (`docs/convenciones.md`); `unidades` declara en qué sistema consistente están los números, para que la GUI muestre etiquetas y convierta. No se convierte nada al leer. Valores de la versión 1: `fuerza` ∈ {`N`, `kN`, `kgf`, `tf`}, `longitud` ∈ {`mm`, `cm`, `m`}.
- **Convenciones de signos y ejes:** las de `docs/convenciones.md`, sin excepción.
- **Valores por omisión.** Una clave numérica ausente vale 0 (`fx`, `qy`, `kx`…), `liberaciones` ausente vale seis `false`, y en `apoyos` un GDL ausente vale `false`.
- **Números.** Se escriben con la representación más corta que vuelve exactamente al mismo `float64` (lo que hace `json` de Python y `serde_json` con `ryu`): guardar y abrir no cambia ni un bit. `NaN` e `Infinity` están prohibidos.
- **Cargas en barras.** `tipo` ∈ {`uniforme`, `puntual`, `trapezoidal`, `termica`, `momento`}, cada uno con sus claves y ninguna otra: `uniforme` usa `qx, qy` (toda la luz); `puntual` usa `a, px, py` (`a` obligatoria); `trapezoidal` usa `a, b, qx1, qy1, qx2, qy2`, una carga que varía linealmente de `(qx1, qy1)` en `a` a `(qx2, qy2)` en `b`, con `0 ≤ a < b ≤ L`. En la trapezoidal, `a` ausente vale 0 y `b` ausente significa "hasta el nudo j", así la carga sigue a la barra si cambia su longitud. Con `qy1 = qy2` es una uniforme parcial. Es el tipo 2 del contrato de datos v2 (`docs/contrato-datos.md`). `momento` usa `a` (obligatoria, `0 ≤ a ≤ L`) y `mz` (momento concentrado, antihorario positivo); `ejes` se guarda pero no se usa. Es el tipo 4 del contrato. `termica` usa `alfa` (obligatoria, coeficiente de dilatación), `dt` (variación uniforme), `gradiente` (`T(cara -y) - T(cara +y)`) y `h` (canto, obligatorio si hay gradiente); `ejes` se guarda pero no se usa. Es el tipo 3 del contrato.
- **Nombres de casos únicos.** `combinaciones[].factores` referencia casos por `nombre`, igual que `Resultados.combinar`.
- **`extensiones`.** Objeto libre para complementos y pruebas, con claves con prefijo (`"miplugin.algo"`). El lector lo conserva sin interpretarlo. Nada de lo que Nervi necesita para calcular puede vivir ahí.
- **Validación.** Al abrir se valida contra el esquema y además: referencias a `id` existentes, barras con nudos distintos, `E`, `A`, `I` > 0, `0 ≤ a ≤ L` en cargas puntuales y momentos, `0 ≤ a < b ≤ L` en trapezoidales y `h > 0` en térmicas con gradiente. Un error dice archivo, ruta JSON y motivo (por ejemplo `modelo.json: barras[3].j = 17: no existe el nudo 17`).

### 4.2 Lo que viene después (no es parte de la versión 1)

Materiales y secciones con nombre (en lugar de `E, A, I` por barra), modelo 3D (Fase 2) y masas y espectros entran al módulo `modelo` subiendo su versión. Normas y criterios de diseño (Fase 3) van en el módulo propio `diseno`. Las trapezoidales, las térmicas y los momentos en el tramo entraron a la versión 1 antes de congelarla (issues #2, #4 y #3), porque solo agregan un valor de `tipo` y los archivos anteriores siguen siendo válidos. Después del congelamiento, cada agregado sube la versión del módulo que toca y trae su migración (§6). Un `tipo: "portico_2d"` sigue siendo válido para siempre: el 3D se agrega como otro `tipo`, no reemplaza al plano.

## 5. Resultados (`resultados/`, reservado)

En la versión actual los resultados **no se guardan**: se recalculan al abrir (un pórtico de 10 000 barras se resuelve en menos de un segundo). El directorio queda reservado para una caché futura con esta regla: cada resultado lleva el SHA-256 de `modelo.json` con el que se calculó, y si no coincide se descarta. Será el módulo no requerido `resultados` (§3.1): un lector que no lo entiende lo conserva sin leerlo, y nunca es fuente de verdad.

## 6. Versiones, migraciones y compatibilidad para siempre

### 6.1 Versiones

1. Cada módulo tiene su versión, un **entero** que sube en 1 con cada cambio de su contenido, compatible o no. No se usa semver: un solo número es más simple de comparar y de migrar.
2. `version_esquema` es la versión del contenedor. Solo cambia si cambia la estructura del ZIP o del manifiesto, algo que no se espera que pase.
3. Un módulo nuevo **no** sube la versión de nada: se agrega a `modulos` (§3.1).

### 6.2 Migraciones

1. Al abrir un módulo con versión **menor** que la que conoce el programa, se aplican en cadena sus migraciones (`migrar_1_a_2`, `migrar_2_a_3`, …) sobre los JSON, antes de validar. Cada migración es una función pura registrada en `MIGRACIONES[módulo][versión]` de `python/nervi/formato/migraciones.py`.
2. Al guardar se escribe siempre la versión actual de cada módulo conocido. Si hubo migración, la GUI avisa y guarda una copia `.bak`.
3. Al abrir un archivo con una versión de contenedor mayor, o un módulo requerido más nuevo: error claro con la versión del archivo y la del programa. No se intenta abrir a medias. Un módulo no requerido más nuevo se conserva sin leer (§3.1).
4. `formato` distinto de `"nervi.proyecto"` o falta de `mimetype`: no es un proyecto de Nervi (por ejemplo, una compilación de Nero), error claro.

### 6.3 Compromiso de compatibilidad

Un `.nrv` guardado con cualquier versión publicada de Nervi se abre con **todas** las versiones posteriores y da los mismos resultados. Por ejemplo, un pórtico plano de la v0.1.0 se abre con la versión de dentro de cinco años. Para que esto no dependa de la memoria de nadie:

1. **Archivos de referencia.** `tests/datos/nrv/` tiene al menos un archivo por cada versión publicada de cada módulo (`modelo-v1.nrv`, después `modelo-v2.nrv`…) con sus resultados esperados (`*.esperado.json`). `tests/test_formato_compatibilidad.py` los abre, los resuelve y compara con tolerancia relativa 1e-9 en cada CI. También exige que exista el archivo de cada versión de cada módulo conocido.
2. **Lo que no se hace nunca:** borrar, regenerar o editar un archivo de referencia; borrar o cambiar una migración publicada; quitar un `tipo` o una clave que una versión publicada pudo escribir. Si una prueba de compatibilidad falla, el error está en el cambio nuevo.
3. **Lo que se hace en cada cambio de un módulo:** subir su versión, escribir la migración desde la versión anterior, agregar el archivo de referencia de la versión nueva y anotarlo en §9 y en la bitácora.
4. **Si cambia el motor:** un resultado distinto en un archivo viejo solo se acepta si corrige un error demostrado. En ese caso se agrega un `*.esperado.json` nuevo junto al viejo, con la explicación en la bitácora; el viejo no se borra.

La compatibilidad hacia adelante (que una versión vieja abra un archivo nuevo) no se promete. Lo que sí se garantiza es que la versión vieja lo diga con claridad, y que conserve lo que no entiende si el módulo no es requerido.

## 7. Asociación de la extensión en el sistema

### 7.1 Windows

El instalador registra (en `HKCU` para instalación por usuario, `HKLM` para todos):

```
HKCR\.nrv                          (Predeterminado) = Nervi.Proyecto.1
                                   Content Type     = application/vnd.nervi.proyecto+zip
HKCR\.nrv\OpenWithProgids          Nervi.Proyecto.1
HKCR\Nervi.Proyecto.1              (Predeterminado) = Proyecto de Nervi
HKCR\Nervi.Proyecto.1\DefaultIcon  (Predeterminado) = "C:\...\Nervi.exe",1
HKCR\Nervi.Proyecto.1\shell\open\command
                                   (Predeterminado) = "C:\...\Nervi.exe" "%1"
```

Si en la máquina ya hay una asociación de Nero para `.nrv`, el instalador **no** la pisa en silencio: agrega Nervi a `OpenWithProgids` y ofrece hacerlo predeterminado. Windows 10/11 igual pide confirmación al usuario la primera vez.

### 7.2 Linux

Archivo `share/mime/packages/nervi.xml` (lo instala el paquete o el AppImage con su integración):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/vnd.nervi.proyecto+zip">
    <comment>Proyecto de Nervi</comment>
    <sub-class-of type="application/zip"/>
    <generic-icon name="application-x-nervi"/>
    <magic priority="70">
      <match type="string" offset="30" value="mimetypeapplication/vnd.nervi.proyecto+zip"/>
    </magic>
    <glob pattern="*.nrv"/>
  </mime-type>
</mime-info>
```

Y en `nervi.desktop`: `MimeType=application/vnd.nervi.proyecto+zip;` con `Exec=nervi %f`. Después, `update-mime-database` y `update-desktop-database`.

### 7.3 macOS (más adelante)

`UTExportedTypeDeclarations` en el `Info.plist` con identificador `io.github.jeronimobareiro.nervi.proyecto` (dominio invertido de un sitio que el proyecto controla), conforme a `public.zip-archive`, extensión `nrv`.

## 8. Implementación

Implementado en `python/nervi/formato/`:

- `abrir(ruta) -> Documento` y `guardar(documento, ruta, copia_bak=False)`. Un `Documento` tiene el manifiesto, el diccionario de `modelo.json` y los miembros que el programa no interpreta (`otros`), que se conservan al guardar. Se eligió devolver el documento y no un `Modelo` porque `Modelo` no guarda `id`, unidades, combinaciones ni extensiones.
- `construir_modelo(modelo_json) -> (Modelo, Indices)`: el módulo de formato mantiene la tabla `id → índice`; `Modelo` no cambia.
- `desde_modelo(Modelo, combinaciones) -> modelo_json` (los `id` son índice + 1) y `validar(modelo_json)`, escrita a mano según el esquema y §4.1 para no sumar `jsonschema` como dependencia.
- `MODULOS` en `contenedor.py`: los módulos que conoce esta versión y la versión que escribe de cada uno. `Documento.migrado_desde` dice qué módulos se migraron y `Documento.avisos` qué se conservó sin leer.
- `migraciones.py`: una cadena por módulo, vacía mientras todos estén en su versión 1.
- `tests/test_formato_compatibilidad.py` y `tests/datos/nrv/`: archivos de referencia permanentes (§6.3).
- Pruebas en `tests/test_formato.py`: ida y vuelta bit a bit, firma `mimetype`, miembros desconocidos conservados, `id` no consecutivos, versión futura, archivo de Nero, ZIP cualquiera, `mimetype` comprimido, rutas con `..`, referencias rotas y demás reglas de §4.1.
- La GUI (PySide6) solo llama a `nervi.formato`; no escribe JSON por su cuenta.

## 9. Historial del esquema

| Versión | Fecha | Cambio |
|---|---|---|
| Contenedor 1, `modelo` 1 | 2026-11-09 (borrador) | Versión inicial: pórtico 2D de la Fase 1. |
| Contenedor 1, `modelo` 1 | 2026-11-12 (borrador) | Manifiesto con `modulos` (§3.1), versión y migraciones por módulo, archivos de referencia permanentes (§6.3). Los archivos sin `modulos` se siguen leyendo. |
