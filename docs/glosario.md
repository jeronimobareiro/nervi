# Glosario · Glossary · Glossário · Глоссарий

El código, los comentarios y la documentación técnica de Nervi están en español. Este glosario traduce los términos estructurales y los nombres que aparecen en el código para que cualquiera pueda leerlo y aportar.

*Nervi's code, comments and technical docs are in Spanish. This glossary translates the structural terms and code names so anyone can read the code and contribute.*
*O código, os comentários e a documentação técnica do Nervi estão em espanhol. Este glossário traduz os termos estruturais e os nomes usados no código.*
*Код, комментарии и техническая документация Nervi написаны на испанском. Этот глоссарий переводит строительные термины и имена из кода.*

Si falta un término o una traducción se puede mejorar, abrí un PR: es un buen primer aporte.

## Modelo y geometría · Model and geometry

| Español (código) | English | Português | Русский |
|---|---|---|---|
| modelo (`Modelo`) | model | modelo | модель |
| nudo (`nudo`, `agregar_nudo`) | node, joint | nó | узел |
| barra (`Barra`, `agregar_barra`) | member, bar element | barra | стержень |
| pórtico plano | plane frame | pórtico plano | плоская рама |
| viga | beam | viga | балка |
| columna | column | pilar | колонна |
| cercha | truss | treliça | ферма |
| biela (`biarticulada`) | two-force member, pin-ended bar | biela | стержень с шарнирами по концам |
| voladizo | cantilever | balanço | консоль |
| viga biapoyada | simply supported beam | viga biapoiada | шарнирно опёртая балка |
| viga biempotrada | fixed-end beam | viga biengastada | балка с защемлёнными концами |
| viga continua | continuous beam | viga contínua | неразрезная балка |
| viga Gerber | Gerber beam, hinged continuous beam | viga Gerber | шарнирно-консольная балка |
| tramo | span, segment | vão, trecho | пролёт, участок |
| luz (`L`) | span length | vão | длина пролёта |
| sección (`Seccion`) | cross-section | seção | сечение |
| módulo de elasticidad (`E`) | modulus of elasticity | módulo de elasticidade | модуль упругости |
| área (`A`) | area | área | площадь |
| momento de inercia (`I`) | moment of inertia | momento de inércia | момент инерции |
| canto (`h`) | section depth | altura da seção | высота сечения |
| ejes locales / globales (`Ejes.Local`, `Ejes.Global`) | local / global axes | eixos locais / globais | местные / глобальные оси |
| grado de libertad, GDL (`gdl`) | degree of freedom, DOF | grau de liberdade, GL | степень свободы |

## Apoyos y vínculos · Supports and releases

| Español (código) | English | Português | Русский |
|---|---|---|---|
| apoyo, apoyar (`apoyar`) | support, to restrain | apoio, apoiar | опора, закрепить |
| restricción (`restricciones`) | restraint | restrição | связь |
| empotramiento, empotrado | fixed support, fixed | engaste, engastado | жёсткая заделка |
| articulado fijo | pinned support | apoio fixo (articulado) | шарнирно-неподвижная опора |
| carrito | roller support | apoio móvel | шарнирно-подвижная опора |
| resorte, apoyo elástico (`resorte`) | spring, elastic support | mola, apoio elástico | упругая опора, пружина |
| articulación | hinge, pin | articulação, rótula | шарнир |
| liberación (`liberaciones`) | end release | liberação | освобождение связи |
| asentamiento, desplazamiento impuesto (`desplazamiento_impuesto`) | settlement, prescribed displacement | recalque, deslocamento imposto | осадка, заданное перемещение |
| mecanismo (`Mecanismo`) | mechanism (unstable structure) | mecanismo (hipostático) | механизм (изменяемая система) |

## Cargas · Loads

| Español (código) | English | Português | Русский |
|---|---|---|---|
| carga | load | carga | нагрузка |
| carga nodal (`carga_nodal`) | nodal load | carga nodal | узловая нагрузка |
| carga uniforme (`carga_uniforme`) | uniformly distributed load | carga uniformemente distribuída | равномерно распределённая нагрузка |
| carga puntual (`carga_puntual`) | point load | carga concentrada | сосредоточенная сила |
| carga trapezoidal (`carga_trapezoidal`) | trapezoidal load | carga trapezoidal | трапециевидная нагрузка |
| carga parcial (`carga_parcial`) | partial load | carga parcial | нагрузка на части пролёта |
| carga térmica (`carga_termica`) | thermal load | ação térmica | температурное воздействие |
| caso de carga (`caso`, `CasoCarga`) | load case | caso de carga | загружение |
| combinación (`combinar`, `Combinacion`) | load combination | combinação de ações | сочетание нагрузок |
| factor de mayoración (`factores`) | load factor | coeficiente de ponderação | коэффициент надёжности по нагрузке |
| cargas equivalentes | equivalent (fixed-end) loads | cargas nodais equivalentes | эквивалентные узловые нагрузки |

## Análisis y resultados · Analysis and results

| Español (código) | English | Português | Русский |
|---|---|---|---|
| analizar, resolver (`resolver`) | analyze, solve | analisar, resolver | рассчитать, решить |
| matriz de rigidez (`rigidez_local`) | stiffness matrix | matriz de rigidez | матрица жёсткости |
| rigidez | stiffness | rigidez | жёсткость |
| ensamblaje | assembly | montagem | сборка (ансамблирование) |
| resultados (`Resultados`) | results | resultados | результаты |
| desplazamiento (`desplazamientos`) | displacement | deslocamento | перемещение |
| giro (`rz`) | rotation | rotação | угол поворота |
| reacción (`reacciones`) | reaction | reação de apoio | опорная реакция |
| fuerzas de extremo (`fuerzas_extremo`) | member end forces | esforços nas extremidades | концевые усилия |
| esfuerzo axil (`N`) | axial force | esforço normal | продольная сила |
| esfuerzo cortante (`V`) | shear force | esforço cortante | поперечная сила |
| momento flector (`M`) | bending moment | momento fletor | изгибающий момент |
| diagrama (`diagrama`) | diagram | diagrama | эпюра |
| deformada | deflected shape | deformada | деформированная схема |
| flecha | deflection | flecha | прогиб |
| envolvente (`envolvente`) | envelope | envoltória | огибающая |

## Diseño y normas · Design and codes

| Español (código) | English | Português | Русский |
|---|---|---|---|
| diseño, dimensionamiento | design, member sizing | dimensionamento | конструирование, подбор сечений |
| norma (`normas`) | design code, standard | norma | нормы проектирования |
| verificación | verification | verificação | верификация |
| hormigón armado | reinforced concrete | concreto armado | железобетон |
| acero | steel | aço | сталь |

## Verbos y palabras frecuentes en el código · Common words in the code

| Español | English | Português | Русский |
|---|---|---|---|
| agregar | add | adicionar | добавить |
| abrir / guardar | open / save | abrir / salvar | открыть / сохранить |
| validar | validate | validar | проверить |
| generar | generate | gerar | сгенерировать |
| calcular | compute | calcular | вычислить |
| actualizar | update | atualizar | обновить |
| error | error | erro | ошибка |
| aviso | warning | aviso | предупреждение |
| ventana / vista / tabla | window / view / table | janela / vista / tabela | окно / вид / таблица |
| prueba | test | teste | тест |

## Proyecto · Project

| Español | English | Português | Русский |
|---|---|---|---|
| aporte | contribution | contribuição | вклад |
| bitácora (`docs/bitacora/`) | contribution log | diário de contribuições | журнал вкладов |
| estado (`docs/ESTADO.md`) | current status | estado atual | текущее состояние |
| hoja de ruta | roadmap | roteiro | дорожная карта |
| especificación técnica | technical specification | especificação técnica | техническое задание |
| buen primer aporte (`buen-primer-aporte`) | good first issue | boa primeira contribuição | хорошая первая задача |
| proyecto académico (`proyecto-academico`) | academic project | projeto acadêmico | учебный проект |
| tesis posible (`tesis-posible`) | possible thesis | tese possível | возможная тема диссертации |
