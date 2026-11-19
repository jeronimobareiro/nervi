# Primeiros passos

Este guia resolve uma viga biapoiada de 6 m com uma carga uniforme de 20 kN/m. O momento máximo esperado é q·L²/8 = 20 · 6² / 8 = **90 kN·m**.

As unidades deste guia são kN e m. O sentido dos eixos e os sinais dos esforços estão em [Convenções de sinais](tecnica/convenciones.md).

## Com a interface

Todo o trabalho é feito em uma única janela. No alto está o percurso **Geometria › Cargas › Análise › Resultados › Dimensionamento**, à esquerda a árvore do projeto e à direita as propriedades do que você seleciona.

1. **Geometria.** Na tabela de nós, cadastre N1 em (0, 0) e N2 em (6, 0). Na tabela de barras, una N1 com N2 e digite E = 2.5e7, A = 0.125, I = 0.0026.
2. **Apoios.** N1 com deslocamentos X e Y impedidos (apoio fixo) e N2 apenas com Y impedido (apoio móvel).
3. **Cargas.** Crie o caso D e adicione à barra uma carga uniforme qy = −20 (para baixo).
4. **Calcular.** Pressione **F5** ou o botão **Calcular**. Se o modelo estiver incompleto, por exemplo sem um apoio, a aba **Revisão do modelo** diz o que falta.
5. **Resultados.** Escolha o diagrama de **Momento**. Ao passar o cursor pela barra você vê M, V e N em cada ponto, e no centro aparece o máximo de 90 kN·m. As reações estão na tabela de baixo. Com o botão **3D**, à esquerda dos diagramas, você vê a mesma viga com suas cargas em 3D: arraste com o mouse para girar e clique em uma barra para selecioná-la.
6. **Dimensionamento (experimental).** Para dimensionar a viga é preciso pelo menos uma combinação: adicione `1.4D` com fator 1.4 para D na tabela de combinações e calcule de novo. Na etapa **Diseño** escolha f'c, fy e o cobrimento e pressione **Diseñar**. A viga é tomada como retangular com a mesma A e I (cerca de 250 × 500 mm neste exemplo; você pode mudá-la na tabela). Cada barra mostra sua armadura inferior, superior e os estribos, e ao selecioná-la você vê cada verificação com seu artigo da ACI 318-19. Os pilares mostram sua armadura longitudinal (sem estribos) e a verificação à flexo-compressão. É uma versão experimental, que ainda não foi revisada por um engenheiro estrutural.
7. **Salvar.** Ctrl+S salva o projeto como arquivo `.nrv`, junto com os dados de dimensionamento.
8. **Modos e espectro (preliminar).** Na aba **Dinámica** coloque fator 1 para D na tabela de massa (e 0,25 para L, se quiser), clique em **+** para adicionar um espectro de exemplo e depois em **Análisis modal y espectral**. A tabela mostra o período e a massa participante de cada modo; ao escolher um, sua forma é desenhada, e **Animar modo** a faz oscilar. Ao escolher o espectro você vê o cortante basal e os diagramas, que são valores absolutos combinados. Os valores do espectro de exemplo não são de nenhuma norma: informe os que correspondem.
9. **Memória de cálculo.** Ctrl+P (ou **Exportar memoria de cálculo** no menu) gera um PDF, em espanhol, com o modelo, as cargas, as combinações, as tabelas de resultados e os diagramas de cada caso e combinação. Se você dimensionou, adiciona um capítulo com as armaduras e as verificações, e se fez a análise dinâmica, um com as massas, os modos e os espectros.

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
