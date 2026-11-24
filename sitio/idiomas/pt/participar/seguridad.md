# Erros críticos e segurança

!!! info "Tradução"
    Esta é uma tradução do [original em espanhol](../../../participar/seguridad/), que é o texto de referência.

O Nervi calcula estruturas. Um resultado incorreto pode levar a uma estrutura insegura, por isso tratamos esses erros com prioridade.

## O que relatar em privado

- Resultados incorretos que possam subestimar esforços, deformações ou a armadura necessária.
- Verificações normativas que aprovam um elemento que não cumpre a norma.
- Vulnerabilidades de software (por exemplo, ao ler arquivos de terceiros).

Escreva para **jerobareiro@gmail.com** com o menor modelo que reproduz o problema, a versão do Nervi e o resultado que você esperava com sua fonte. Respondemos o mais rápido possível e publicamos a correção junto com um aviso nas notas da versão.

Os erros sem impacto na segurança (mensagens, documentação, desempenho) vão como issue pública.

## Responsabilidade

O Nervi é distribuído **sem nenhuma garantia**, conforme as seções 15 e 16 da [licença GPL-3.0](https://github.com/jeronimobareiro/nervi/blob/main/LICENSE). O software auxilia o profissional; não substitui seu critério. Todo cálculo usado em um projeto real deve ser verificado e assinado por um profissional habilitado, que é o responsável pelo projeto.
