# Formato de archivo `.nrv` (versión de esquema 1, borrador)

> **Estado: borrador.** Se congela con la primera versión publicada de la GUI. Hasta entonces se puede cambiar sin migración; después, todo cambio sigue §6.

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
├── nervi.json          # obligatorio: manifiesto (versión de esquema, generador, fechas)
├── modelo.json         # obligatorio: el modelo (§4)
├── vista.json          # opcional: estado de la GUI (cámara, capas, selección)
├── resultados/         # opcional, reservado: caché de resultados (§5)
└── adjuntos/           # opcional, reservado: imágenes, memorias, etc.
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
  "modificado": "2026-11-10T09:30:00Z"
}
```

| Clave | Tipo | Obligatoria | Contenido |
|---|---|---|---|
| `formato` | texto | sí | Siempre `"nervi.proyecto"`. |
| `version_esquema` | entero ≥ 1 | sí | Versión del esquema de **todo** el contenedor (§6). |
| `generador` | objeto | sí | Programa y versión que escribió el archivo. Solo informativo. |
| `creado`, `modificado` | texto ISO 8601 UTC | no | Fechas. |

`version_esquema` es independiente de `VERSION_CONTRATO` (el contrato Rust ↔ Python, `docs/contrato-datos.md`) y de la versión del programa.

## 4. Modelo (`modelo.json`), esquema 1

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
    {"caso": 2, "barra": 2, "tipo": "puntual", "ejes": "global", "a": 2.5, "py": -20.0}
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
- **Unidades.** El motor no impone unidades (`docs/convenciones.md`); `unidades` declara en qué sistema consistente están los números, para que la GUI muestre etiquetas y convierta. No se convierte nada al leer. Valores de esquema 1: `fuerza` ∈ {`N`, `kN`, `kgf`, `tf`}, `longitud` ∈ {`mm`, `cm`, `m`}.
- **Convenciones de signos y ejes:** las de `docs/convenciones.md`, sin excepción.
- **Valores por omisión.** Una clave numérica ausente vale 0 (`fx`, `qy`, `kx`…), `liberaciones` ausente vale seis `false`, y en `apoyos` un GDL ausente vale `false`.
- **Números.** Se escriben con la representación más corta que vuelve exactamente al mismo `float64` (lo que hace `json` de Python y `serde_json` con `ryu`): guardar y abrir no cambia ni un bit. `NaN` e `Infinity` están prohibidos.
- **Nombres de casos únicos.** `combinaciones[].factores` referencia casos por `nombre`, igual que `Resultados.combinar`.
- **`extensiones`.** Objeto libre para complementos y pruebas, con claves con prefijo (`"miplugin.algo"`). El lector lo conserva sin interpretarlo. Nada de lo que Nervi necesita para calcular puede vivir ahí.
- **Validación.** Al abrir se valida contra el esquema y además: referencias a `id` existentes, barras con nudos distintos, `E`, `A`, `I` > 0, `0 ≤ a ≤ L` en cargas puntuales. Un error dice archivo, ruta JSON y motivo (por ejemplo `modelo.json: barras[3].j = 17: no existe el nudo 17`).

### 4.2 Lo que viene en esquemas posteriores (no es parte del esquema 1)

Materiales y secciones con nombre (en lugar de `E, A, I` por barra), modelo 3D (Fase 2), masas y espectros, normas y criterios de diseño (Fase 3), cargas trapezoidales, térmicas y momentos en el tramo. Cada uno entra subiendo `version_esquema` con su migración (§6).

## 5. Resultados (`resultados/`, reservado)

En el esquema 1 los resultados **no se guardan**: se recalculan al abrir (un pórtico de 10 000 barras se resuelve en menos de un segundo). El directorio queda reservado para una caché futura con esta regla: cada resultado lleva el SHA-256 de `modelo.json` con el que se calculó, y si no coincide se descarta. Un lector que no entiende `resultados/` lo ignora, y nunca es fuente de verdad.

## 6. Versiones y migraciones

1. `version_esquema` es un **entero** que sube en 1 con cada cambio del contenido de los JSON, compatible o no. No se usa semver: un solo número es más simple de comparar y de migrar.
2. Al abrir un archivo con versión **menor** que la actual, el lector aplica las migraciones en cadena (`migrar_1_a_2`, `migrar_2_a_3`, …) sobre los diccionarios JSON, antes de validar. Cada migración es una función pura en `python/nervi/formato/migraciones.py`, con su prueba en `tests/` y un archivo de ejemplo de la versión vieja en `tests/datos/nrv/` que nunca se borra.
3. Al guardar se escribe siempre la versión actual. Si el archivo venía de una versión anterior, la GUI avisa ("este archivo se actualizó al formato 2 y ya no se podrá abrir con Nervi 0.x") y guarda una copia `.bak`.
4. Al abrir un archivo con versión **mayor** que la que conoce el programa: error claro con la versión del archivo y la del programa ("Este archivo es del formato 3; esta versión de Nervi lee hasta el 2. Actualizá Nervi."). No se intenta abrir a medias.
5. `formato` distinto de `"nervi.proyecto"` o falta de `mimetype`: no es un proyecto de Nervi (por ejemplo, una compilación de Nero), error claro.
6. Cada cambio de esquema se anota en este documento (§9) y en la bitácora.

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

## 8. Implementación prevista

- `python/nervi/formato/` con `guardar(modelo, ruta)`, `abrir(ruta) -> Modelo` y `migraciones.py`. Solo biblioteca estándar (`zipfile`, `json`) más la validación; sin dependencias nuevas obligatorias.
- `Modelo` gana `ids` estables o el módulo de formato mantiene la tabla `id → índice`; se decide al implementar.
- Pruebas: ida y vuelta bit a bit (guardar, abrir, `arreglos()` iguales), archivo con versión futura, archivo de Nero o ZIP cualquiera, `mimetype` comprimido o ausente, referencias rotas, rutas con `..`.
- La GUI (PySide6) solo llama a `nervi.formato`; no escribe JSON por su cuenta.

## 9. Historial del esquema

| Versión | Fecha | Cambio |
|---|---|---|
| 1 | 2026-11-09 (borrador) | Versión inicial: pórtico 2D de la Fase 1. |
