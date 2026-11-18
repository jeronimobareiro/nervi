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
| pórtico espacial (`Modelo3D`, `espacial`) | space frame, 3D frame | pórtico espacial | пространственная рама |
| emparrillado | grid, grillage | grelha | ростверк, балочная клетка |
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
| vector de referencia (`referencia`) | reference vector, orientation vector | vetor de referência | вектор ориентации |
| módulo de elasticidad transversal (`G`) | shear modulus | módulo de elasticidade transversal | модуль сдвига |
| constante de torsión (`J`) | torsion constant | constante de torção | момент инерции при кручении |
| secciones (`secciones`, `rectangular`, `circular`, `tubo_circular`) | cross-sections | seções | сечения |
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
| momento concentrado (`carga_momento`) | concentrated moment | momento concentrado | сосредоточенный момент |
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
| momento torsor, torsor (`T`) | torque, twisting moment | momento torçor | крутящий момент |
| diagrama (`diagrama`) | diagram | diagrama | эпюра |
| deformada | deflected shape | deformada | деформированная схема |
| flecha | deflection | flecha | прогиб |
| envolvente (`envolvente`) | envelope | envoltória | огибающая |
| masa (`masa_nodal`, `masa_lineal`) | mass | massa | масса |
| masa concentrada / consistente (`TipoMasa`) | lumped / consistent mass | massa concentrada / consistente | сосредоточенная / согласованная масса |
| análisis modal (`modal`) | modal analysis | análise modal | модальный анализ |
| modo, forma modal (`modos`) | mode, mode shape | modo, forma modal | форма колебаний |
| periodo (`periodos`) | period | período | период |
| frecuencia circular (`omegas`) | circular frequency | frequência angular | круговая частота |
| factor de participación (`factores_participacion`) | participation factor | fator de participação | коэффициент участия |
| masa modal efectiva (`masas_efectivas`) | effective modal mass | massa modal efetiva | эффективная модальная масса |
| espectro de respuesta (`espectro`) | response spectrum | espectro de resposta | спектр ответа |
| aceleración espectral (`Sa`, `aceleraciones`) | spectral acceleration | aceleração espectral | спектральное ускорение |
| amortiguamiento (`amortiguamiento`) | damping ratio | amortecimento | демпфирование |
| combinación modal SRSS / CQC (`combinacion`) | SRSS / CQC modal combination | combinação modal SRSS / CQC | сочетание форм SRSS / CQC |
| cortante basal (`cortante_basal`) | base shear | cortante basal | сдвигающая сила в основании |
| inercias (`inercias`, `M φ`) | modal inertia forces | forças de inércia modais | инерционные силы формы |
| memoria de cálculo (`memoria`, `memoria_de_calculo`) | calculation report, design report | memória de cálculo | расчётная записка |
| plantilla (`plantilla.toml`) | template | modelo, template | шаблон |
| capítulo de la memoria (`Capitulo`) | report chapter, section | capítulo | раздел, глава |

## Diseño y normas · Design and codes

| Español (código) | English | Português | Русский |
|---|---|---|---|
| diseño, dimensionamiento | design, member sizing | dimensionamento | конструирование, подбор сечений |
| norma (`normas`) | design code, standard | norma | нормы проектирования |
| verificación | verification | verificação | верификация |
| hormigón armado | reinforced concrete | concreto armado | железобетон |
| acero | steel | aço | сталь |
| armadura (`As`, `As_comp`) | reinforcement (tension / compression steel) | armadura | арматура |
| barra de armadura, diámetro (`diametros`) | reinforcing bar, bar size | barra, bitola | арматурный стержень, диаметр |
| estribo (`Estribos`, `elegir_estribos`) | stirrup | estribo | хомут |
| recubrimiento | concrete cover | cobrimento | защитный слой бетона |
| altura útil (`d`) | effective depth | altura útil | рабочая высота сечения |
| separación libre (`s_libre`) | clear spacing | espaçamento livre | расстояние в свету |
| capa de barras (`capas`) | bar layer | camada | ряд арматуры |
| flexión (`armadura_flexion`) | flexure, bending | flexão | изгиб |
| resistencia de diseño (`phiMn`) | design strength | resistência de cálculo | расчётная прочность |
| factor de reducción (`phi`) | strength reduction factor | coeficiente de minoração | коэффициент снижения прочности |
| sección crítica | critical section | seção crítica | расчётное сечение |
| flecha inmediata / diferida (`delta_D`, `delta_diferida`) | immediate / long-term deflection | flecha imediata / diferida | мгновенный / длительный прогиб |
| inercia efectiva / fisurada (`Ie`, `Icr`) | effective / cracked moment of inertia | inércia efetiva / fissurada | эффективный / трещинообразованный момент инерции |
| momento de fisuración (`Mcr`) | cracking moment | momento de fissuração | момент трещинообразования |
| carga sostenida (`fraccion_sostenida`) | sustained load | carga de longa duração | длительная нагрузка |
| control de fisuración (`verificar_fisuracion`) | crack control | controle de fissuração | контроль трещин |
| longitud de desarrollo / anclaje (`ld`) | development length | comprimento de ancoragem | длина анкеровки |
| gancho normal (`gancho_normal`, `ldh`) | standard hook | gancho padrão | стандартный крюк |
| empalme por yuxtaposición (`empalme_traccion`) | lap splice | emenda por traspasse | нахлёсточное соединение |
| armadura de piel | skin reinforcement | armadura de pele | поверхностная арматура |
| flexocompresión biaxial | biaxial bending with axial load | flexo-compressão oblíqua | косое внецентренное сжатие |
| diagrama de interacción (`diagrama_interaccion`) | interaction diagram | diagrama de interação | диаграмма взаимодействия |
| cuantía (`cuantia`, `ρ`) | reinforcement ratio | taxa de armadura | коэффициент армирования |
| esbeltez (`esbeltez`, `k·lu/r`) | slenderness (ratio) | esbeltez | гибкость |
| magnificación de momentos (`factor_magnificacion`, `δ`) | moment magnification | amplificação de momentos | увеличение моментов (учёт продольного изгиба) |
| longitud libre (`lu`) | unsupported length | comprimento livre | свободная длина |
| pórtico desplazable / no desplazable (`desplazable`) | sway / nonsway frame | pórtico deslocável / indeslocável | рама со смещаемыми / несмещаемыми узлами |
| razón demanda/capacidad (`razon`) | demand/capacity ratio | razão solicitação/resistência | коэффициент использования |
| zuncho (`zunchada`) | spiral reinforcement | cinta helicoidal, espiral | спиральная арматура |
| elemento (`Elemento`), viga, columna | member, beam, column | elemento, viga, pilar | элемент, балка, колонна |
| diseñador (`DISENADORES`) | designer (design function per member type) | dimensionador | функция расчёта элемента |
| relación solicitación / resistencia (`relacion`) | demand / capacity ratio | razão solicitação / resistência | коэффициент использования |
| cumple / no cumple (`cumple`) | passes / fails | atende / não atende | выполняется / не выполняется |
| sección equivalente (`seccion_equivalente`) | equivalent rectangular section | seção equivalente | эквивалентное сечение |
| huella del modelo (`modelo_sha256`) | model fingerprint (hash) | impressão digital do modelo | отпечаток модели |

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
| visor 3D (`vista3d`) / escena (`escena3d`) | 3D viewer / scene | visualizador 3D / cena | 3D-просмотрщик / сцена |
| flecha / relleno / etiqueta | arrow / fill / label | seta / preenchimento / rótulo | стрелка / заливка / подпись |
| encuadrar / capturar | fit the view / render to an image | enquadrar / capturar | вписать вид / сохранить снимок |
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
