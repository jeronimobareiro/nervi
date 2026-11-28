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
| brazo rígido (`brazo_i`, `brazo_j`) | rigid end offset, rigid end zone | trecho rígido, braço rígido | жёсткая вставка |
| cara de la unión | joint face | face do nó | грань узла |
| diafragma rígido (`diafragma`, `Diafragma`) | rigid diaphragm | diafragma rígido | жёсткий диск перекрытия |
| nudo maestro / esclavo (`maestro`, `esclavos`) | master / slave node | nó mestre / escravo | главный / подчинённый узел |
| piso | story, floor | pavimento, andar | этаж |
| modelo físico (`ModeloFisico`, `fisico`) | physical model | modelo físico | физическая модель |
| modelo analítico, modelo de cálculo | analytical model | modelo analítico | расчётная модель |
| nivel (`nivel`) | elevation, level | cota, nível | отметка |
| planta (`PlantaEdificio`, gestor de plantas) | floor plan; story (in the floor manager) | planta; pavimento | план этажа; этаж |
| altura de entrepiso, entrepiso | story height, floor-to-floor height | pé-direito estrutural, altura entre pisos | высота этажа |
| eje de replanteo (`ejes`) | grid line | eixo (de locação) | разбивочная ось |
| losa (`losas`, `maciza`) | slab (solid) | laje (maciça) | плита (сплошная) |
| muro (`muros`) | wall | parede, pilar-parede | стена |
| contorno (`contorno`) | outline, boundary | contorno | контур |
| espesor (`espesor`) | thickness | espessura | толщина |

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
| peso propio (`peso_propio`) | self-weight | peso próprio | собственный вес |
| carga permanente (`permanente`) | superimposed dead load | carga permanente | постоянная нагрузка |
| sobrecarga de uso (`sobrecarga`) | live load | sobrecarga de utilização | полезная (временная) нагрузка |
| peso específico (`peso`) | unit weight | peso específico | удельный вес |
| cargas por planta | floor loads | cargas por pavimento | нагрузки на этаж |
| área tributaria, zona tributaria (`area_tributaria`, `ZonaTributaria`) | tributary area | área de influência | грузовая площадь |
| reparto de cargas (`repartir_cargas`, `nervi.reparto`) | load distribution, load takedown | distribuição de cargas | распределение нагрузок |
| borde apoyado, borde libre | supported edge, free edge | borda apoiada, borda livre | опёртый край, свободный край |

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
| centro de masa (`centro_masa`) | center of mass | centro de massa | центр масс |
| centro de rigidez | center of rigidity, center of stiffness | centro de rigidez | центр жёсткости |
| deriva de piso (`derivas`, `deriva_x`) | story drift ratio | deslocamento relativo entre pavimentos (drift) | относительный межэтажный перекос |
| masa participante (`masa_participante`) | mass participation ratio | massa participante | доля участвующей массы |
| dinámica del pórtico plano (`dinamica_plana`) | plane frame dynamics | dinâmica do pórtico plano | динамика плоской рамы |
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
| visor único / vista de frente | single viewer / front view | visualizador único / vista de frente | единый просмотр / вид спереди |
| cámara (`camara3d`) / acimut / elevación | camera / azimuth / elevation | câmera / azimute / elevação | камера / азимут / угол возвышения |
| girar (giro tipo plato) / centro de giro | orbit (turntable) / orbit pivot | girar (giro tipo prato) / centro de giro | вращать (поворотный стол) / центр вращения |
| brújula de vistas (`brujula`) | view compass | bússola de vistas | компас видов |
| proyección paralela / perspectiva | parallel / perspective projection | projeção paralela / perspectiva | параллельная / перспективная проекция |
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
| tema de la interfaz (`Tema`, `estilo.aplicar`), claro / oscuro | UI theme, light / dark | tema da interface, claro / escuro | тема интерфейса, светлая / тёмная |
| enganche (`nervi.enganche`, `IndiceEnganche`): extremo, medio, cruce, perpendicular, polar, prolongación, grilla | object snap: endpoint, midpoint, intersection, perpendicular, polar, extension, grid | snap (captura de ponto): extremidade, ponto médio, interseção, perpendicular, polar, extensão, grade | объектная привязка: конечная точка, середина, пересечение, перпендикуляр, полярная, продолжение, сетка |
| zoom, paneo, encuadrar (`nervi.gui.navegacion`, `Camara`) | zoom, pan, zoom to fit | zoom, deslocar, enquadrar | масштаб, панорамирование, показать всё |
| panel acoplable, acoplar, desacoplar (`nervi.gui.paneles`) | dock widget, dock, undock (float) | painel acoplável, acoplar, desacoplar | закрепляемая панель, закрепить, открепить |
| barra de título propia, botones de la ventana (`nervi.gui.marco`) | custom title bar, window controls | barra de título própria, botões da janela | собственный заголовок окна, кнопки окна |
| distribución (de los paneles) | layout (workspace) | disposição (dos painéis) | раскладка панелей |
| preferencias (`ajustes.Preferencias`, `PREFERENCIAS`) | preferences (per user) | preferências | настройки пользователя |
| configuración del proyecto (`ConfiguracionProyecto`) | project settings | configuração do projeto | параметры проекта |
| apartado (de los ajustes) | settings section | seção (das configurações) | раздел настроек |
| barra lateral de menús (`riel`) | side menu bar (icon rail) | barra lateral de menus | боковая панель меню |
| proyectos recientes (`recientes`) | recent projects | projetos recentes | недавние проекты |
| diámetros permitidos para columnas (`diametros_columna`) | allowed column bar sizes | bitolas permitidas para pilares | допустимые диаметры для колонн |
| datos del proyecto, carátula (`proyecto.json`, `para_caratula`) | project data, cover page | dados do projeto, capa | данные проекта, титульный лист |
| banco de tiempos (`scripts/medir_diseno.py`), pórtico de referencia | benchmark, reference frame | benchmark, pórtico de referência | замер времени, эталонная рама |
| comparación cruzada (`test_columna_rust.py`) | cross-check test | comparação cruzada | перекрёстная проверка |
| armadura candidata (`elegir_armadura`) | candidate reinforcement layout | armadura candidata | вариант армирования |
| proyecto sin interfaz (`nervi.proyecto.Proyecto`), evento (`suscribir`) | headless project, event | projeto sem interface, evento | проект без интерфейса, событие |
| resultados a precisión completa (`nervi.resultados`), huella del modelo (`huella_modelo`) | full-precision results, model fingerprint | resultados com precisão completa, impressão digital do modelo | результаты с полной точностью, отпечаток модели |
| deshacer, rehacer (`Proyecto.deshacer`, `rehacer`), cambio (`Cambio`) | undo, redo, change | desfazer, refazer, alteração | отменить, повторить, изменение |
| propuesta (`Proyecto.proponer`, `aplicar`, `descartar`), origen | proposal (propose, apply, discard), source | proposta (propor, aplicar, descartar), origem | предложение (предложить, применить, отклонить), источник |
| historial (módulo `historial` del `.nrv`), resumen de cambios (`resumir_cambios`) | change log, change summary | histórico, resumo de alterações | журнал изменений, сводка изменений |
| agente de IA, servidor MCP (`nervi-mcp`), herramienta de consulta (`nervi.ia.herramientas`) | AI agent, MCP server, query tool | agente de IA, servidor MCP, ferramenta de consulta | ИИ-агент, MCP-сервер, инструмент запроса |
| importar DXF (`nervi.importar.dxf`), capa, tolerancia | DXF import, layer, tolerance | importar DXF, camada, tolerância | импорт DXF, слой, допуск |
| canal local (`nervi.ia.canal`), conectar con mi IA, secreto | local channel, connect my AI, secret token | canal local, conectar minha IA, segredo | локальный канал, подключить мой ИИ, секретный токен |
