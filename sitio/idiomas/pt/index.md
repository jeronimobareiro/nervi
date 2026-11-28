---
hide:
  - navigation
  - toc
---

# Nervi { .nv-oculto }

<div class="nv-portada" markdown>

<img class="nv-logo nv-claro" src="marca/nervi-logotipo-claro.svg" alt="Nervi">
<img class="nv-logo nv-oscuro" src="marca/nervi-logotipo-oscuro.svg" alt="Nervi">

<p class="nv-lema">Software livre para calcular estruturas.</p>

O Nervi analisa pórticos pelo método dos elementos finitos e mostra reações, esforços e deformações. É gratuito, de código aberto e cada resultado é comparado com uma solução conhecida.

[Baixar](descargar.md){ .md-button .md-button--primary }
[Primeiros passos](primeros-pasos.md){ .md-button }

[Por que se chama Nervi?](por-que-nervi.md){ .nv-porque }

</div>

![Janela do Nervi com os diagramas de momento de um pórtico](img/interfaz-claro.png){ .nv-captura .nv-claro }
![Janela do Nervi com os diagramas de momento de um pórtico](img/interfaz-oscuro.png){ .nv-captura .nv-oscuro }

!!! warning "Versão preliminar, não apta para projeto"
    O Nervi está em desenvolvimento. Calcula pórticos planos e espaciais com análise linear elástica; o espacial e a dinâmica são preliminares e o projeto de concreto armado segundo a ACI 318-19 é experimental até que um engenheiro estrutural o revise. Ele auxilia o engenheiro, não substitui seu critério nem sua assinatura.

<div class="grid cards nv-tarjetas" markdown>

-   **Verificável**

    Cada tipo de cálculo é comparado com uma fórmula conhecida e cita sua fonte. Você pode conferir como ele chega a cada número e ver os [casos verificados](casos-verificados.md).

-   **Livre e gratuito**

    Licença GPL-3.0. Você pode usá-lo, ensinar com ele, estudá-lo e melhorá-lo, sem pagar licenças.

-   **Feito com universidades**

    Estudantes, professores e engenheiros podem contribuir com trabalhos práticos, teses ou revisões. Veja [como participar](participar/index.md).

</div>

## O que faz hoje

- **Pórticos planos** com barras, rótulas, treliças, apoios fixos ou elásticos e recalques.
- **Pórticos espaciais (3D)**, em versão preliminar: barras de 12 graus de liberdade, trechos rígidos e diafragma rígido por pavimento.
- **Cargas** em nós e em barras: uniformes, pontuais, trapezoidais ou parciais, momentos concentrados e térmicas.
- **Casos e combinações** de carga, por exemplo 1.2D + 1.6L.
- **Resultados**: reações, diagramas de esforço normal, cortante e momento, e a deformada, em 2D e em um visualizador 3D. Ao passar o cursor sobre uma barra, os valores naquele ponto aparecem. Se o modelo for um mecanismo, indica qual nó se move sem rigidez.
- **Análise dinâmica**: modos de vibração, participação de massa e espectro de resposta (CQC e SRSS), em versão preliminar.
- **Projeto de concreto armado segundo a ACI 318-19**, experimental: vigas (flexão, cisalhamento, flechas e detalhamento das armaduras) e pilares (flexão composta biaxial e esbeltez), cada verificação com seu artigo.
- **Modelo físico do edifício**, em versão preliminar: pavimentos, eixos, pilares, vigas, lajes maciças e paredes desenhados com o mouse em cada planta, com atração a extremos, eixos e grade, ou preenchidos em tabelas, com um gerenciador para adicionar, mover e copiar pavimentos. As cargas de cada pavimento são distribuídas das lajes às vigas por áreas de influência. Ainda não gera o modelo de cálculo.
- **Memorial de cálculo em PDF** com geometria, cargas, diagramas, projeto e análise dinâmica.
- **Interface de desktop** em uma única janela, com painel da estrutura, tabelas ou desenho com o mouse para montar o modelo (nós, barras, apoios e cargas), tema claro e noturno, e uso a partir do Python para quem programa.
- **Assistente de IA do seu jeito**: você conecta a IA que já usa (pelo padrão MCP) para consultar o modelo e os resultados. Ela só propõe mudanças que você aplica ou descarta, e cada número é calculado pelo motor do Nervi, nunca pela IA.
- **Projetos** salvos em arquivos `.nrv` e dezenas de casos de verificação contra soluções conhecidas.

## O que vem a seguir

A meta é que o engenheiro receba a planta de arquitetura em DXF e entregue a estrutura calculada com a documentação completa: memorial, quantitativos, tabelas de armaduras e desenhos de detalhe de concreto e de aço. No caminho vêm efeitos de segunda ordem (P-Δ), normas e espectros regionais (CIRSOC, NBR, NCh, Eurocódigo), edição gráfica do modelo, lajes e paredes, cargas de vento e sismo, pré-dimensionamento, estruturas de aço (AISC 360) e mistas, fundações, intercâmbio com programas BIM (IFC), complementos da comunidade e um chat dentro do Nervi. A ordem e as tarefas estão no [roteiro](hoja-de-ruta.md).

## Para continuar lendo

- [Baixar e instalar](descargar.md)
- [Primeiros passos](primeros-pasos.md): seu primeiro pórtico, com a interface ou com Python
- [Documentação técnica](tecnica/especificacion.md): como calcula, convenções de sinais e formato de arquivo
- [Como participar](participar/index.md)
