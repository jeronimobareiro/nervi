# Casos verificados

O Nervi não pede que você acredite nele: cada tipo de cálculo é comparado com uma solução conhecida, e essa comparação roda sozinha a cada mudança do programa. Esta página explica como a verificação funciona e lista os casos que a biblioteca tem hoje.

## Como é verificado

- Cada caso é um arquivo de texto com o modelo, os resultados esperados e sua **fonte**: uma fórmula fechada, um livro com página e número de exemplo, ou uma solução resolvida à mão com aritmética exata.
- A verificação automática do GitHub resolve todos os casos a cada contribuição e fica vermelha se algum valor se afastar do esperado mais do que a tolerância (por padrão, um erro relativo de 1e-9).
- Além disso, o motor de cálculo tem dezenas de testes analíticos em Rust (mecanismos, pórtico espacial, dinâmica, trechos e diafragmas rígidos) e centenas de testes em Python (formato de arquivo, interface, memorial de cálculo e projeto).
- Os módulos de **projeto de concreto armado** (ACI 318-19) estão verificados com cálculos à mão e contra programas de código aberto, mas ainda não com exemplos publicados nem com a revisão de um engenheiro estrutural; por isso são marcados como experimentais.

## Casos da biblioteca

Hoje a pasta [`verification/`](https://github.com/jeronimobareiro/nervi/tree/main/verification) tem **{{N_CASOS}} casos**. Os títulos e as fontes estão em espanhol, o idioma de trabalho do projeto:

{{CASOS}}

## Como contribuir com um caso

Adicionar um caso não exige saber Rust nem mexer no motor de cálculo: basta escrever um arquivo de texto. Um exemplo resolvido do livro da sua disciplina é uma excelente primeira contribuição. As instruções estão no [README da biblioteca](https://github.com/jeronimobareiro/nervi/blob/main/verification/README.md) e em [como participar](participar/index.md).
