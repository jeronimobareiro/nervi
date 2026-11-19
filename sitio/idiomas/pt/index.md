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

![Janela do Nervi com os diagramas de momento de um pórtico](img/interfaz.png){ .nv-captura }

!!! warning "Versão preliminar, não apta para projeto"
    O Nervi está em desenvolvimento. Hoje calcula pórticos planos com análise linear elástica; o dimensionamento de vigas de concreto armado segundo norma é experimental e ainda não foi revisado por um engenheiro estrutural. Ele auxilia o engenheiro, não substitui seu critério nem sua assinatura.

<div class="grid cards nv-tarjetas" markdown>

-   **Verificável**

    Cada tipo de cálculo é comparado com uma fórmula conhecida e cita sua fonte. Você pode conferir como ele chega a cada número.

-   **Livre e gratuito**

    Licença GPL-3.0. Você pode usá-lo, ensinar com ele, estudá-lo e melhorá-lo, sem pagar licenças.

-   **Feito com universidades**

    Estudantes, professores e engenheiros podem contribuir com trabalhos práticos, teses ou revisões. Veja [como participar](participar/index.md).

</div>

## O que faz hoje

- **Pórticos planos** com barras, rótulas, treliças, apoios fixos ou elásticos e recalques.
- **Cargas** em nós e em barras: uniformes, pontuais, trapezoidais ou parciais e momentos concentrados no vão.
- **Casos e combinações** de carga, por exemplo 1.2D + 1.6L.
- **Vigas de concreto armado** segundo a ACI 318-19, em versão experimental: armadura de flexão, barras comerciais e estribos, flechas, fissuração e ancoragens, a partir do Python.
- **Pilares de concreto armado** segundo a ACI 318-19, em versão experimental: flexo-compressão em duas direções, esbeltez e escolha da armadura, a partir do Python.
- **Etapa Diseño** (dimensionamento) na interface: dimensiona todas as vigas e pilares do pórtico, marca quais atendem e mostra cada verificação com o artigo da norma.
- **Resultados**: reações, diagramas de esforço normal, cortante e momento, e a deformada. Ao passar o cursor sobre uma barra, os valores naquele ponto aparecem. Com o visualizador 3D opcional, o modelo, as cargas e os diagramas aparecem em perspectiva.
- **Interface de desktop** em uma única janela, com tabelas para montar o modelo, ou uso a partir do Python para quem programa.
- **Projetos** salvos em arquivos `.nrv`.
- **Memória de cálculo em PDF** (em espanhol), com os dados do modelo, as cargas, as combinações, as tabelas de resultados, os diagramas e, se você dimensionou, as armaduras e verificações das vigas, a partir de um modelo editável.
- **Pórticos espaciais (3D)**, por enquanto só a partir do Python e em versão preliminar: barras com flexão em dois planos e torção, treliças espaciais e seções retangulares e circulares.
- **Análise modal e espectro de resposta** do pórtico espacial, a partir do Python e em versão preliminar: períodos, formas modais, massa participante e resposta sísmica com combinação SRSS ou CQC a partir do espectro indicado pela norma.
- **Edifícios com diafragma rígido por pavimento e trechos rígidos** no pórtico espacial, a partir do Python e em versão preliminar: a massa de cada pavimento no nó mestre, centro de massa, deslocamentos relativos entre pavimentos e esforços das vigas na face do pilar.
- **Modos e espectros na interface**, em versão preliminar: na aba **Dinámica** você escolhe de quais casos sai a massa e informa o espectro; vê a tabela de períodos e massa participante, cada forma modal desenhada e animada, e o cortante basal e os diagramas de cada espectro. Tudo é salvo no projeto e vai para a memória de cálculo.

## O que vem a seguir

Pórticos 3D na interface, espectros sísmicos de norma e P-Δ, flechas, fissuração e detalhamento de armaduras, intercâmbio com programas BIM (IFC) e memorial de cálculo. A ordem e as tarefas estão no [roteiro](hoja-de-ruta.md).

## Para continuar lendo

- [Baixar e instalar](descargar.md)
- [Primeiros passos](primeros-pasos.md): seu primeiro pórtico, com a interface ou com Python
- [Documentação técnica](tecnica/especificacion.md): como calcula, convenções de sinais e formato de arquivo
- [Como participar](participar/index.md)
