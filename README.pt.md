<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

[Español](README.md) · [English](README.en.md) · **Português** · [Русский](README.ru.md)

Software livre e de código aberto para análise e dimensionamento estrutural, com um núcleo numérico em Rust e uma camada de aplicação em Python.

Site: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Estado: Fase 1 (pórtico plano linear elástico), com uma interface de desktop preliminar.** Ainda não há dimensionamento segundo normas nem IFC. Veja o [roteiro](docs/hoja-de-ruta.md) (em espanhol).
>
> Este software auxilia o engenheiro; não substitui seu critério nem sua responsabilidade profissional. Verifique sempre os resultados.

## O código está em espanhol, e você é bem-vindo mesmo assim

O Nervi nasceu na América Latina, por isso o código, os comentários e a documentação técnica estão em espanhol. Isso não deve impedir você de contribuir:

- O **[glossário](docs/glosario.md)** traduz cada termo estrutural e cada nome do código para português, inglês e russo (`barra` = barra, `nudo` = nó, `apoyo` = apoio, `caso de carga` = caso de carga, `momento flector` = momento fletor…). Para quem fala português, a maior parte do vocabulário é quase igual.
- **Issues, pull requests e discussões podem ser escritos em português, inglês ou russo.** Os mantenedores respondem no seu idioma.
- Na revisão ajudamos você a adaptar os nomes novos ao vocabulário em espanhol do código.
- As fórmulas, as normas (ACI, AISC, Eurocódigos, ABNT…) e a matemática são as mesmas em todo lugar.

Veja o [guia de contribuição](CONTRIBUTING.md#contributing-from-other-countries).

## O que faz hoje

- Pórticos planos com barras de Euler-Bernoulli (3 graus de liberdade por nó).
- Cargas nodais e cargas em barras uniformes, concentradas, trapezoidais ou parciais, em eixos locais ou globais; ações térmicas.
- Articulações e liberações de extremidade; treliças.
- Apoios rígidos e elásticos, e recalques impostos.
- Vários casos de carga com uma única fatoração, e combinações lineares (combinações e envoltórias da ACI 318-19, experimentais).
- Reações, esforços nas extremidades, diagramas `N`, `V`, `M` e deformada, incluindo os pontos de momento máximo.
- Detecção de mecanismos e validação de dados com mensagens claras.

Os apoios são tratados por partição dos graus de liberdade (sem penalização) e o sistema é resolvido com Cholesky esparso do [`faer`](https://github.com/sarah-quinones/faer-rs). Um pórtico de 8 100 barras é resolvido em cerca de 45 ms (release).

## Uso

A API usa nomes em espanhol; os comentários mostram o significado.

```python
import nervi

m = nervi.Modelo()                                         # modelo
a = m.agregar_nudo(0, 0)                                   # adicionar nó
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)   # adicionar barra (viga), kN, m
m.apoyar(a, ux=True, uy=True, rz=False)                    # apoio fixo
m.apoyar(b, ux=False, uy=True, rz=False)                   # apoio móvel
m.carga_uniforme("D", viga, qy=-20)                        # carga uniforme, kN/m para baixo, permanente
m.carga_uniforme("L", viga, qy=-10)                        # carga variável

res = m.resolver()                                         # resolver
combo = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})    # combinar
print(combo.reacciones[a])                 # reações [Rx, Ry, Mz]
print(combo.diagrama(viga)["M"].max())     # 0,125 · 40 · 6² = 180 kN·m
```

Mais exemplos em [`examples/`](examples/). Convenções de sinais em [`docs/convenciones.md`](docs/convenciones.md).

### Interface de desktop (preliminar)

```
pip install "nervi[gui]"       # ou, a partir do código-fonte: pip install PySide6-Essentials
nervi-gui                      # ou: python -m nervi.gui projeto.nrv
```

Tudo acontece em uma única janela: tabelas de nós, barras, apoios, cargas e combinações, cálculo com F5, diagramas N, V, M e deformada com leitura de esforços sob o cursor, propriedades da seleção, revisão do modelo, console Python e paleta de comandos (Ctrl+K). Os projetos são salvos no formato [`.nrv`](docs/formato-nrv.md). Os instaladores para Windows (`.exe`) e Linux (AppImage) são gerados em [Releases](https://github.com/jeronimobareiro/nervi/releases) ao publicar uma tag `v*`; não são assinados. Por enquanto a interface está em espanhol.

> **Versão preliminar, não apta para projetos reais.** A análise linear elástica está verificada contra soluções analíticas; o dimensionamento segundo normas ainda não existe.

## Compilar a partir do código-fonte

Requisitos: Rust estável e Python ≥ 3.10.

```bash
python -m venv .venv && source .venv/bin/activate
pip install maturin pytest
maturin develop --release
pytest
cargo test -p nervi-core
```

## Estrutura

```
crates/nervi-core/   núcleo MEF em Rust puro (sem Python)
  src/elemento.rs     rigidez, transformação, cargas equivalentes, liberações
  src/analisis.rs     montagem, solução, reações, diagramas
  tests/verificacion.rs  casos contra soluções analíticas
crates/nervi-py/     ponte PyO3 (contrato em docs/contrato-datos.md)
python/nervi/        pacote Python
tests/              testes da API Python
verification/       casos de verificação em TOML, sem precisar de Rust
docs/               especificação, convenções, contrato de dados, glossário
sitio/              site
```

## Verificação

Cada caso de `crates/nervi-core/tests/verificacion.rs` e de `verification/` é comparado com uma solução fechada ou um exemplo publicado: balanços, vigas biapoiadas, biengastadas e contínuas, carga concentrada excêntrica, pórtico com carga lateral, treliça, barras inclinadas, recalques, apoios elásticos, viga Gerber com articulação, equilíbrio global de um pórtico de vários andares e detecção de mecanismos.

**Regra para contribuir:** toda funcionalidade nova chega com seus casos de verificação e a fonte de cada fórmula (veja [`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Contribuir

O Nervi está aberto a estudantes, professores, pesquisadores e engenheiros de qualquer lugar do mundo. Comece pelo [guia de contribuição](CONTRIBUTING.md#contributing-from-other-countries) e pelo [glossário](docs/glosario.md). As issues com a etiqueta `buen-primer-aporte` são boas primeiras contribuições; `proyecto-academico` e `tesis-posible` indicam temas do tamanho de um trabalho de disciplina ou de uma tese. As regras de convivência estão no [Código de conduta](CODE_OF_CONDUCT.md) e as de decisão em [`GOVERNANCE.md`](GOVERNANCE.md). Se encontrar um resultado incorreto que possa afetar uma estrutura real, siga [`SECURITY.md`](SECURITY.md).

Para citar o Nervi em um trabalho acadêmico, use [`CITATION.cff`](CITATION.cff).

## Licença

Copyright (C) 2026 Jerónimo Bareiro e colaboradores do Nervi ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 ou posterior. Veja [`LICENSE`](LICENSE). O Nervi é distribuído sem nenhuma garantia; todo cálculo usado em um projeto real deve ser verificado e assinado por um profissional habilitado.

O Nervi implementa métodos descritos em normas técnicas (ACI, AISC, Eurocódigos e outras) citando seus artigos; não reproduz seus textos e não é certificado nem endossado por esses organismos. O nome e o logotipo do Nervi identificam o projeto (veja [`GOVERNANCE.md`](GOVERNANCE.md#marca)).

*Se esta tradução e o [README em espanhol](README.md) divergirem, prevalece a versão em espanhol.*
