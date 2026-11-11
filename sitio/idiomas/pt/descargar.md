# Baixar e instalar

O Nervi é gratuito para Windows e Linux.

## Instaladores

Os instaladores para **Windows** (`.exe`) e **Linux** (AppImage) são publicados na página de versões do GitHub, junto com a primeira versão preliminar.

[Ver versões publicadas](https://github.com/jeronimobareiro/nervi/releases){ .md-button .md-button--primary }

Se ainda não aparecer nenhuma versão, a primeira está em preparação. Enquanto isso, você pode instalá-lo a partir do código-fonte, como explicado abaixo.

!!! note "Aviso do Windows na instalação"
    Os instaladores ainda não têm assinatura digital, então o Windows pode mostrar o aviso "O Windows protegeu o computador". Se você baixou o arquivo da página oficial de versões, escolha **Mais informações → Executar assim mesmo**.

No Linux, depois de baixar o AppImage, dê a ele permissão de execução (clique direito → Propriedades → Permissões, ou `chmod +x Nervi-*.AppImage`) e abra com um clique duplo.

## A partir do código-fonte

Para quem quer a última versão em desenvolvimento ou usar o Nervi a partir do Python. Você precisa do [Rust](https://www.rust-lang.org/pt-BR/tools/install) e do [Python](https://www.python.org/downloads/) 3.10 ou posterior.

```bash
git clone https://github.com/jeronimobareiro/nervi.git
cd nervi
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install maturin PySide6-Essentials
maturin develop --release
python -m nervi.gui                # abre a interface
```

Se for usar o Nervi apenas a partir do Python, não é preciso instalar o `PySide6-Essentials`.

## Requisitos

- Windows 10 ou 11, ou uma distribuição Linux recente de 64 bits.
- Não precisa de conexão com a internet: todo o cálculo é feito no seu computador e seus modelos não saem dele.
