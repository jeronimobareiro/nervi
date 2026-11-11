# Primeiros passos

Este guia resolve uma viga biapoiada de 6 m com uma carga uniforme de 20 kN/m. O momento máximo esperado é q·L²/8 = 20 · 6² / 8 = **90 kN·m**.

As unidades deste guia são kN e m. O sentido dos eixos e os sinais dos esforços estão em [Convenções de sinais](tecnica/convenciones.md).

## Com a interface

Todo o trabalho é feito em uma única janela. No alto está o percurso **Geometria › Cargas › Análise › Resultados**, à esquerda a árvore do projeto e à direita as propriedades do que você seleciona.

1. **Geometria.** Na tabela de nós, cadastre N1 em (0, 0) e N2 em (6, 0). Na tabela de barras, una N1 com N2 e digite E = 2.5e7, A = 0.125, I = 0.0026.
2. **Apoios.** N1 com deslocamentos X e Y impedidos (apoio fixo) e N2 apenas com Y impedido (apoio móvel).
3. **Cargas.** Crie o caso D e adicione à barra uma carga uniforme qy = −20 (para baixo).
4. **Calcular.** Pressione **F5** ou o botão **Calcular**. Se o modelo estiver incompleto, por exemplo sem um apoio, a aba **Revisão do modelo** diz o que falta.
5. **Resultados.** Escolha o diagrama de **Momento**. Ao passar o cursor pela barra você vê M, V e N em cada ponto, e no centro aparece o máximo de 90 kN·m. As reações estão na tabela de baixo.
6. **Salvar.** Ctrl+S salva o projeto como arquivo `.nrv`.

Com **Ctrl+K** você abre uma busca para encontrar qualquer comando ou elemento do modelo pelo nome.

## Com Python

O mesmo cálculo, escrito como programa:

```python
import nervi

m = nervi.Modelo()
a = m.agregar_nudo(0, 0)
b = m.agregar_nudo(6, 0)
viga = m.agregar_barra(a, b, E=2.5e7, A=0.125, I=2.6e-3)
m.apoyar(a, ux=True, uy=True, rz=False)    # apoio fixo
m.apoyar(b, ux=False, uy=True, rz=False)   # apoio móvel
m.carga_uniforme("D", viga, qy=-20)        # kN/m para baixo
m.carga_uniforme("L", viga, qy=-10)

res = m.resolver()
d = res.combinar("D", {"D": 1.0})
print(d.diagrama(viga)["M"].max())         # 90 kN·m
print(d.reacciones[a])                     # [Rx, Ry, Mz] = [0, 60, 0]

u = res.combinar("1.2D+1.6L", {"D": 1.2, "L": 1.6})
print(u.diagrama(viga)["M"].max())         # 0.125 · 40 · 6² = 180 kN·m
```

Os nomes de funções e argumentos estão em espanhol, o idioma de trabalho do projeto (`Modelo` é o modelo, `agregar_nudo` adiciona um nó, `agregar_barra` adiciona uma barra, `apoyar` define um apoio, `carga_uniforme` adiciona uma carga uniforme, `resolver` resolve, `combinar` combina casos de carga). Um exemplo mais completo, um pórtico com cargas de vento e combinações, está em [`examples/portico_simple.py`](https://github.com/jeronimobareiro/nervi/blob/main/examples/portico_simple.py).

## Se um resultado não fechar

Sempre confira com um cálculo à mão ou com outro método. Se encontrar um resultado que considera incorreto, [abra um relato](https://github.com/jeronimobareiro/nervi/issues/new/choose) com o modelo e o valor que esperava. Se o erro puder afetar uma estrutura real, siga a [política de segurança](participar/seguridad.md).
