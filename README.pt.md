<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/marca/nervi-logotipo-oscuro.svg">
    <img alt="Nervi" src="docs/marca/nervi-logotipo-claro.svg" width="320">
  </picture>
</p>

# Nervi

[Español](README.md) · [English](README.en.md) · **Português** · [Русский](README.ru.md)

Software livre e colaborativo de projeto e cálculo de estruturas, com um núcleo numérico em Rust e uma camada de aplicação em Python. A meta: que os engenheiros pré-dimensionem, calculem e dimensionem estruturas de concreto armado, aço e mistas a partir da planta de arquitetura, e entreguem o memorial, os quantitativos, as tabelas de armaduras e os desenhos de detalhe. Hoje cobre a análise de pórticos e o dimensionamento de vigas e pilares de concreto; o resto está no [roteiro](docs/hoja-de-ruta.md) (em espanhol).

Site: **[jeronimobareiro.github.io/nervi](https://jeronimobareiro.github.io/nervi/)**.

> **Estado: versão preliminar em desenvolvimento.** O pórtico plano linear elástico (Fase 1) está quase completo e tem interface de desktop. O pórtico espacial e a dinâmica (Fase 2) e o dimensionamento de concreto armado segundo a ACI 318-19 (Fase 3) já começaram e são preliminares ou experimentais. Ainda não há norma regional nem IFC. Detalhes em [`docs/ESTADO.md`](docs/ESTADO.md) e o plano no [roteiro](docs/hoja-de-ruta.md) (ambos em espanhol).
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

### Análise

- **Pórtico plano** com barras de Euler-Bernoulli (3 graus de liberdade por nó): cargas nodais; cargas uniformes, concentradas, trapezoidais ou parciais e térmicas nas barras, em eixos locais ou globais; momentos concentrados no vão; articulações, liberações de extremidade e treliças; apoios rígidos, elásticos e recalques impostos.
- Vários casos de carga com uma única fatoração e combinações lineares. Reações, esforços nas extremidades, diagramas `N`, `V`, `M` e deformada, com os pontos de momento máximo.
- Detecção de mecanismos (indica qual nó e qual grau de liberdade se movem sem rigidez) e validação de dados com mensagens claras.
- **Pórtico espacial** a partir do Python (`nervi.Modelo3D`, preliminar): barras de 12 graus de liberdade com flexão em dois planos, esforço normal e torção, eixos locais definidos por um vetor de referência, barras de treliça espacial e seções usuais em `nervi.secciones`. **Diafragma rígido por pavimento** (`Modelo3D.diafragma`, restrição mestre-escravo por transformação, com centro de massa e deslocamentos relativos entre pavimentos) e **trechos rígidos** nas extremidades das barras (`brazo_i`, `brazo_j`), com esforços na face do nó. Ainda sem interface nem `.nrv`.
- **Dinâmica** (preliminar): massas nodais, das barras (concentradas ou consistentes) e a partir dos casos de carga; análise modal com períodos, formas e massa participante por direção; espectro de resposta com SRSS ou CQC (`Modelo3D.modal`). O espectro da norma é fornecido por quem projeta. No pórtico plano, também pela interface (`nervi.dinamica_plana`).
- **Modelo físico** do edifício (`nervi.fisico.ModeloFisico`, preliminar): pavimentos com sua cota, eixos, materiais e seções, e pilares, vigas, lajes maciças e paredes como objetos, salvos no arquivo `.nrv`. Na interface, o modo *Edificio* (edifício) mostra a planta de cada pavimento (▲▼ para subir e descer), a árvore, tabelas e propriedades editáveis e um gerenciador de pavimentos. As **cargas por pavimento** (permanente e sobrecarga em kN/m², mais o peso próprio de cada laje) são distribuídas às vigas e paredes por áreas de influência, com equilíbrio exato, e o botão *Cargas* mostra as áreas e o que cada viga recebe. Ainda não gera o modelo de cálculo nem desenha com o mouse.

### Dimensionamento de concreto armado segundo a ACI 318-19 (experimental)

- Combinações de carga e envoltórias por seção (`nervi.design`).
- **Vigas** retangulares: armadura de flexão simples ou dupla, escolha de barras comerciais e estribos para cortante; flechas imediatas e diferidas com inércia efetiva, fissuração e comprimentos de ancoragem, ganchos e emendas (`aci318.servicio`, `aci318.detalle`). A flexão e a escolha de barras rodam em Rust.
- **Pilares**: flexo-compressão oblíqua com diagrama de interação, esbeltez por amplificação de momentos e escolha da armadura, a partir do pórtico plano ou espacial. O cálculo roda em Rust.

Ainda não foi revisado por um engenheiro estrutural: não use em projetos reais.

### Interface de desktop e documentos

- **Interface** (`nervi-gui`, PySide6) em uma única janela, com as etapas Geometria › Cargas › Análise › Resultados › Dimensionamento: tabelas do modelo, cálculo com F5, diagramas com leitura de esforços sob o cursor, um só visualizador para a vista de frente e a 3D (o botão direito gira em torno do ponto sob o cursor; a 3D é opcional), aba **Dinámica** (massas, modos animados e espectros), etapa **Diseño** (todas as vigas e pilares, cada verificação com seu artigo), revisão do modelo, console Python, paleta de comandos (Ctrl+K), desfazer e refazer (Ctrl+Z, Ctrl+Y) e painel do assistente de IA para aplicar ou descartar o que a sua IA propõe. Tema claro por padrão e tema escuro com as cores da marca. Por enquanto a interface está em espanhol.
- **Projetos** no formato [`.nrv`](docs/formato-nrv.md), com módulos versionados (modelo, dimensionamento, dinâmica) e migrações para que projetos antigos sempre abram.
- **Memória de cálculo em PDF**, em espanhol e com modelo editável: capa, normas de referência, dados do modelo, cargas, combinações, resultados, diagramas, envoltórias e, quando houver, os capítulos de dimensionamento e de análise dinâmica (`nervi.memoria`, ou Ctrl+P na interface).
- **Resultados com precisão completa** em JSON, sem o arredondamento da memória: deslocamentos, reações, esforços de extremidade e diagramas de cada caso e combinação, e o dimensionamento e a dinâmica quando atualizados, com a impressão digital do modelo a que correspondem ([`formato-resultados.md`](docs/formato-resultados.md)).
- **Importar DXF**: as linhas de um desenho do AutoCAD ou de outro programa, por camada, viram nós e barras, com pré-visualização antes de aplicar (*Archivo › Importar DXF*). Não precisa de IA.
- **Conexão com agentes de IA** por MCP (`nervi-mcp`): o agente que você já usa (Claude, Gemini ou outro cliente MCP) consulta o projeto aberto ou um arquivo e explica os resultados, com cada número tirado do motor; não altera nada, só propõe mudanças que você aplica ou descarta ([`agentes-ia.md`](docs/agentes-ia.md), em espanhol).

### Desempenho

Apoios por partição dos graus de liberdade (sem penalização) e Cholesky esparso com [`faer`](https://github.com/sarah-quinones/faer-rs): um pórtico de 8 100 barras é resolvido em cerca de 45 ms (release). Com o dimensionamento de pilares e de vigas em Rust, a etapa de dimensionamento do pórtico de referência de 130 barras caiu de 132 s para 2,4 s (`scripts/medir_diseno.py`).

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

Mais exemplos em [`examples/`](examples/) (pórtico plano, pórtico espacial, edifício com diafragma, dimensionamento de vigas e pilares). Convenções de sinais em [`docs/convenciones.md`](docs/convenciones.md).

### Interface de desktop (preliminar)

```
pip install "nervi[gui]"       # ou, a partir do código-fonte: pip install PySide6-Essentials
pip install "nervi[visor3d]"   # opcional: visualizador 3D (PyVista e VTK)
nervi-gui                      # ou: python -m nervi.gui projeto.nrv
```

O tema claro ou escuro e o tamanho da letra são escolhidos em **Preferencias** (o ícone de baixo na barra lateral); os dados da capa, os materiais e os critérios de dimensionamento, em **Configuración del proyecto** (menu Archivo). Os instaladores para Windows (`.exe`) e Linux (AppImage) são gerados em [Releases](https://github.com/jeronimobareiro/nervi/releases) ao publicar uma tag `v*`; não são assinados. Um guia passo a passo está no [site](https://jeronimobareiro.github.io/nervi/pt/).

> **Versão preliminar, não apta para projetos reais.** A análise linear elástica está verificada contra soluções analíticas; o pórtico espacial e a dinâmica são preliminares, e o dimensionamento segundo a ACI 318-19 é experimental e ainda não foi revisado por um engenheiro estrutural.

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
crates/nervi-core/   núcleo numérico em Rust puro (sem Python)
  src/                pórtico plano: elementos, análise, mecanismos
  src/espacial/       pórtico espacial, diafragmas e trechos rígidos, dinâmica
  src/diseno/         cálculo pesado do dimensionamento (flexo-compressão de pilares)
  tests/              casos contra soluções analíticas
crates/nervi-py/     ponte PyO3 (contratos em docs/contrato-datos.md)
python/nervi/        pacote Python: API, formato .nrv, memória PDF
  design/             dimensionamento segundo normas (ACI 318-19)
  gui/                interface de desktop e seu sistema de design (estilo.py)
tests/               testes da API Python e da interface
verification/        casos de verificação em TOML, sem Rust
examples/            exemplos de uso
scripts/             banco de tempos, controles do CI e montagem do site
docs/                especificação, convenções, contratos, estado e registro
sitio/               site público
```

## Verificação

Cada caso de `crates/nervi-core/tests/` e de `verification/` é comparado com uma solução fechada ou um exemplo publicado, com tolerância relativa de 1e-9 na análise: balanços, vigas biapoiadas, biengastadas e contínuas, pórticos com carga lateral, treliças, recalques, apoios elásticos, mecanismos, pórticos espaciais, diafragmas, modos e espectros. O dimensionamento é verificado com cálculos à mão e contra outras bibliotecas livres; falta compará-lo com exemplos publicados.

## Como trabalhamos

Estas regras valem para toda contribuição, de pessoas ou de agentes de IA. Detalhes em [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`AGENTS.md`](AGENTS.md).

1. **Verificação e fontes.** Toda funcionalidade nova chega com seus casos de verificação e a fonte de cada fórmula.
2. **Desempenho em primeiro lugar.** Todo cálculo que percorra barras, nós, combinações ou pontos (análise, dimensionamento, envoltórias, diagramas de interação) vai em Rust e é exposto ao Python com a mesma API. O Python fica para a interface, a memória PDF, os exemplos e os protótipos. Cada migração ou otimização é medida antes e depois com o banco de tempos, passa pelos mesmos testes e dá exatamente os mesmos resultados: nunca se reduzem tolerâncias nem exatidão para ganhar tempo.
3. **Um único sistema de design na interface.** Todo controle toma seu estilo de [`estilo.py`](python/nervi/gui/estilo.py), seguindo a [linha de design](docs/diseno-interfaz.md): tema claro por padrão e o tema escuro da marca. As mudanças de design são combinadas com uma amostra visual antes de serem implementadas.
4. **Documentação em dia.** Cada contribuição atualiza, no mesmo pull request, os arquivos informativos afetados: o README e suas traduções, `CONTRIBUTING.md`, `AGENTS.md`, `docs/ESTADO.md`, o roteiro, o site e a documentação técnica relacionada, além de sua entrada no registro. Assim quem chega sabe onde o projeto está.

## O que vem a seguir

- Desempenho: incluir o banco de tempos no CI e acelerar a busca da armadura de pilares, que hoje é quase todo o tempo do dimensionamento.
- Fechar a Fase 1: exemplos resolvidos de livros em `verification/` ([#6](https://github.com/jeronimobareiro/nervi/issues/6)) e material didático ([#10](https://github.com/jeronimobareiro/nervi/issues/10)).
- Pórtico espacial na interface e no `.nrv`, verificação contra exemplos 3D publicados ([#15](https://github.com/jeronimobareiro/nervi/issues/15)), P-Δ ([#19](https://github.com/jeronimobareiro/nervi/issues/19)) e espectro da norma regional ([#20](https://github.com/jeronimobareiro/nervi/issues/20)).
- Revisão de engenharia do dimensionamento de concreto armado e comparação com exemplos publicados.
- Visão ampliada (fases 6 a 12): modelo físico a partir do DXF de arquitetura, cascas para lajes e paredes, cargas normativas e pré-dimensionamento, aço segundo a AISC 360-22, lajes, paredes e fundações, estruturas mistas e documentação de obra (tabelas de armaduras, desenhos de detalhe, quantitativos). Issues [#73](https://github.com/jeronimobareiro/nervi/issues/73) a [#98](https://github.com/jeronimobareiro/nervi/issues/98).

## Contribuir

O Nervi está aberto a estudantes, professores, pesquisadores e engenheiros de qualquer lugar do mundo. Comece pelo [guia de contribuição](CONTRIBUTING.md#contributing-from-other-countries) e pelo [glossário](docs/glosario.md). As issues com a etiqueta `buen-primer-aporte` são boas primeiras contribuições; `proyecto-academico` e `tesis-posible` indicam temas do tamanho de um trabalho de disciplina ou de uma tese. As regras de convivência estão no [Código de conduta](CODE_OF_CONDUCT.md) e as de decisão em [`GOVERNANCE.md`](GOVERNANCE.md). Se encontrar um resultado incorreto que possa afetar uma estrutura real, siga [`SECURITY.md`](SECURITY.md).

Para citar o Nervi em um trabalho acadêmico, use [`CITATION.cff`](CITATION.cff).

## Licença

Copyright (C) 2026 Jerónimo Bareiro e colaboradores do Nervi ([`AUTHORS.md`](AUTHORS.md)).

GPL-3.0 ou posterior. Veja [`LICENSE`](LICENSE). O Nervi é distribuído sem nenhuma garantia; todo cálculo usado em um projeto real deve ser verificado e assinado por um profissional habilitado.

O Nervi implementa métodos descritos em normas técnicas (ACI, AISC, Eurocódigos e outras) citando seus artigos; não reproduz seus textos e não é certificado nem endossado por esses organismos. O nome e o logotipo do Nervi identificam o projeto (veja [`GOVERNANCE.md`](GOVERNANCE.md#marca)).

*Se esta tradução e o [README em espanhol](README.md) divergirem, prevalece a versão em espanhol.*
