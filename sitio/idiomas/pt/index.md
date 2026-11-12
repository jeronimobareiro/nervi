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
    O Nervi está em desenvolvimento. Hoje calcula pórticos planos com análise linear elástica; ainda não dimensiona segundo normas. Ele auxilia o engenheiro, não substitui seu critério nem sua assinatura.

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
- **Resultados**: reações, diagramas de esforço normal, cortante e momento, e a deformada. Ao passar o cursor sobre uma barra, os valores naquele ponto aparecem.
- **Interface de desktop** em uma única janela, com tabelas para montar o modelo, ou uso a partir do Python para quem programa.
- **Projetos** salvos em arquivos `.nrv`.

## O que vem a seguir

Pórticos em 3D, análise sísmica, projeto de concreto armado segundo norma, intercâmbio com programas BIM (IFC) e memorial de cálculo. A ordem e as tarefas estão no [roteiro](hoja-de-ruta.md).

## Para continuar lendo

- [Baixar e instalar](descargar.md)
- [Primeiros passos](primeros-pasos.md): seu primeiro pórtico, com a interface ou com Python
- [Documentação técnica](tecnica/especificacion.md): como calcula, convenções de sinais e formato de arquivo
- [Como participar](participar/index.md)
