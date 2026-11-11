# Скачать и установить

Nervi бесплатна для Windows и Linux.

## Установщики

Установщики для **Windows** (`.exe`) и **Linux** (AppImage) публикуются на странице релизов GitHub вместе с первой предварительной версией.

[Посмотреть опубликованные версии](https://github.com/jeronimobareiro/nervi/releases){ .md-button .md-button--primary }

Если пока не видно ни одной версии, значит, первая ещё готовится. А пока можно установить программу из исходного кода, как описано ниже.

!!! note "Предупреждение Windows при установке"
    У установщиков пока нет цифровой подписи, поэтому Windows может показать предупреждение «Windows защитила ваш компьютер». Если вы скачали файл с официальной страницы релизов, выберите **Подробнее → Выполнить в любом случае**.

В Linux после загрузки AppImage дайте ему право на выполнение (правый клик → «Свойства» → «Права доступа» или `chmod +x Nervi-*.AppImage`) и запустите двойным щелчком.

## Из исходного кода

Для тех, кто хочет получить последнюю версию из разработки или использовать Nervi из Python. Понадобятся [Rust](https://www.rust-lang.org/ru/tools/install) и [Python](https://www.python.org/downloads/) версии 3.10 или новее.

```bash
git clone https://github.com/jeronimobareiro/nervi.git
cd nervi
python -m venv .venv
source .venv/bin/activate          # в Windows: .venv\Scripts\activate
pip install maturin PySide6-Essentials
maturin develop --release
python -m nervi.gui                # открывает интерфейс
```

Если вы будете пользоваться Nervi только из Python, устанавливать `PySide6-Essentials` не нужно.

## Требования

- Windows 10 или 11 либо современный 64-разрядный дистрибутив Linux.
- Подключение к интернету не требуется: весь расчёт выполняется на вашем компьютере, а ваши модели никуда не передаются.
