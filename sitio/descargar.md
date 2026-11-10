# Descargar e instalar

Nervi es gratuito para Windows y Linux.

## Instaladores

Los instaladores para **Windows** (`.exe`) y **Linux** (AppImage) se publican en la página de versiones de GitHub, junto con la primera versión preliminar.

[Ver versiones publicadas](https://github.com/jeronimobareiro/nervi/releases){ .md-button .md-button--primary }

Si todavía no aparece ninguna versión, la primera está en preparación. Mientras tanto podés instalarlo desde el código fuente, como se explica más abajo.

!!! note "Aviso de Windows al instalar"
    Los instaladores todavía no tienen firma digital, por lo que Windows puede mostrar el aviso "Windows protegió su PC". Si descargaste el archivo desde la página oficial de versiones, elegí **Más información → Ejecutar de todas formas**.

En Linux, después de descargar el AppImage, dale permiso de ejecución (clic derecho → Propiedades → Permisos, o `chmod +x Nervi-*.AppImage`) y abrilo con doble clic.

## Desde el código fuente

Para quien quiere la última versión en desarrollo o usar Nervi desde Python. Necesitás [Rust](https://www.rust-lang.org/es/tools/install) y [Python](https://www.python.org/downloads/) 3.10 o posterior.

```bash
git clone https://github.com/jeronimobareiro/nervi.git
cd nervi
python -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install maturin PySide6-Essentials
maturin develop --release
python -m nervi.gui                # abre la interfaz
```

Si solo vas a usar Nervi desde Python, no hace falta instalar `PySide6-Essentials`.

## Requisitos

- Windows 10 u 11, o una distribución de Linux de 64 bits reciente.
- No necesita conexión a internet: todo el cálculo se hace en tu computadora y tus modelos no salen de ella.
