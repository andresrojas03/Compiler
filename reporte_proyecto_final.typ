// ============================================================================
// CONFIGURACIÓN GENERAL DEL DOCUMENTO TYPST (UNAM - FACULTAD DE INGENIERÍA)
// ============================================================================
#set document(
  title: "Integración de Analizador Léxico, Parser LL(1) y Generador de Código Intermedio (TAC) con Visualizador Web Interactivo",
  author: "Andrés Urquiza Rojas",
)

#set page(
  paper: "us-letter",
  margin: (x: 2.2cm, y: 2.2cm),
  numbering: "1",
)

#set text(
  lang: "es",
  region: "MX",
  size: 10.5pt,
)

#set par(
  justify: true,
  leading: 0.68em,
)

#set heading(numbering: "1.1.")

// Paleta "Soft Twilight & Pastel Lavender"
#let c-twilight = rgb("#251F38")
#let c-panel = rgb("#322A4B")
#let c-lavender = rgb("#6631DB")
#let c-pink = rgb("#C2298A")
#let c-sky = rgb("#1E60B8")
#let c-mint = rgb("#059669")
#let c-rose = rgb("#D93870")
#let c-code-bg = rgb("#F7F5FF")
#let c-code-border = rgb("#D0BCFC")

// Bloques estilizados
#let callout(title, body, border-color: c-lavender, bg-color: c-code-bg) = block(
  width: 100%,
  stroke: 1pt + border-color,
  fill: bg-color,
  radius: 6pt,
  inset: 11pt,
  breakable: true,
)[
  #text(weight: "bold", fill: border-color)[#title]
  #v(4pt)
  #body
]

// ============================================================================
// PORTADA ACADÉMICA
// ============================================================================
#page(numbering: none)[
  #align(center)[
    #v(1.2cm)
    #text(size: 15pt, weight: "bold")[UNIVERSIDAD NACIONAL AUTÓNOMA DE MÉXICO]\
    #v(0.2cm)
    #text(size: 13pt, weight: "bold")[FACULTAD DE INGENIERÍA]\
    #v(0.15cm)
    #text(size: 10.5pt)[División de Ingeniería Eléctrica — Departamento de Computación]

    #v(1.6cm)
    #line(length: 100%, stroke: 0.9pt + c-lavender)
    #v(0.4cm)
    #text(size: 17pt, weight: "bold", fill: c-twilight)[
      Integración de Analizador Léxico, Parser LL(1) y Generador de Código Intermedio (TAC) con Visualizador Web Interactivo
    ]
    #v(0.4cm)
    #line(length: 100%, stroke: 0.9pt + c-lavender)

    #v(1.1cm)
    #text(size: 12.5pt, weight: "bold")[Reporte Técnico de Proyecto Final]\
    #v(0.2cm)
    #text(size: 11pt)[Asignatura: Compiladores]

    #v(2.0cm)
    #grid(
      columns: (auto, auto),
      gutter: 14pt,
      align: (right, left),
      [*Autor:*], [Andrés Urquiza Rojas],
      [*Profesora:*], [Melissa Brigitthe Hinojosa],
      [*Semestre:*], [2027-1],
    )

    #v(1fr)
    #text(size: 10.5pt)[Ciudad Universitaria, Ciudad de México]\
    #v(0.1cm)
    #text(size: 10.5pt, weight: "bold")[Noviembre de 2026]
    #v(0.6cm)
  ]
]

#outline(title: "Índice de Contenido", indent: 1.2em)
#pagebreak()

// ============================================================================
// SECCIÓN 1: ANTECEDENTES
// ============================================================================
= Antecedentes

== Objetivos del Proyecto

=== Objetivo General
Diseñar, implementar y verificar un compilador modular integrado en Python que una las fases de análisis léxico, análisis sintáctico descendente predictivo $L L(1)$, análisis semántico con tabla de símbolos por ámbitos, generación de código intermedio de tres direcciones (_Three-Address Code_, TAC) mediante Traducción Dirigida por Sintaxis (_Syntax-Directed Translation_, SDT) y optimización no destructiva de código intermedio; complementado, como aporte personal didáctico para la asignatura, con un visualizador web interactivo que permite inspeccionar paso a paso el proceso de compilación.

=== Objetivos Específicos
+ Unificar los módulos desarrollados en entregas previas (Analizador Léxico y Analizador Sintáctico $L L(1)$) bajo un contrato inmutable de tokens (`Token(type, lexeme, line, column)`) libre de efectos secundarios.
+ Extender la gramática $L L(1)$ sin recursión izquierda para soportar sentencias de asignación obligatoriamente terminadas en punto y coma (`S -> id = E ;`), declaraciones explícitas (`int`, `float`) y bloques léxicos anidados (`{ StmtList }`).
+ Implementar acciones semánticas en tiempo de análisis sintáctico utilizando atributos heredados (`.inh`) y sintetizados (`.place`), generando temporales secuenciales (`t1, t2, ...`) mediante `newTemp()` y `emit()` sin construir un árbol sintáctico abstracto (AST) intermedio.
+ Garantizar atomicidad transaccional estricta mediante un buffer de emisión con operaciones `commit()` y `rollback()`, asegurando que ante cualquier error léxico, sintáctico o semántico se descarten los temporales intermedios y la salida TAC sea exactamente vacía.
+ Incorporar un pase de optimización sobre el TAC crudo (plegado de constantes, simplificación algebraica, propagación de copias y fusión de temporales redundantes) y desarrollar como contribución adicional una herramienta web interactiva de apoyo académico para futuros cursos de la profesora y del Departamento de Computación.

== Marco Conceptual de las Fases de Compilación

- *Análisis Léxico (Escaneo)*: Primera fase del compilador encargada de leer el flujo de caracteres del programa fuente, omitir elementos no significativos (espacios en blanco, tabuladores, saltos de línea y comentarios `//` o `/* ... */`) y agrupar los caracteres en unidades léxicas indivisibles denominadas _tokens_. Detecta errores léxicos ante símbolos fuera del alfabeto o literales decimales malformados (`3.` o `.5`).
- *Análisis Sintáctico Descendente Predictivo $L L(1)$*: Verifica que la secuencia de tokens cumpla con las reglas estructurales de una gramática libre de contexto sin recursión izquierda, procesando la entrada de izquierda a derecha con un único símbolo de anticipación (_lookahead_ $= 1$) guiado por los conjuntos disjuntos $"FIRST"$ y $"FOLLOW"$.
- *Análisis Semántico y Tabla de Símbolos*: Valida la coherencia de tipos de datos, el alcance léxico (_scoping_) de los identificadores, el sombreado (_shadowing_) en bloques anidados y la detección de divisiones explícitas entre cero literal (`0`, `0.0`, `0.00`).
- *Generación de Código Intermedio (TAC) mediante SDT*: Representa expresiones complejas mediante instrucciones lineales elementales `resultado = arg1 op arg2` o copias `resultado = arg1`. Mediante un esquema $L$-atribuido, las reglas gramaticales propagan operandos izquierdos hacia abajo usando atributos heredados (`.inh`) y devuelven referencias o temporales hacia arriba usando atributos sintetizados (`.place`).
- *Optimización de Código Intermedio*: Fase posterior no destructiva que transforma una copia del TAC crudo para reducir instrucciones y temporales sin alterar la semántica observable del programa.

// ============================================================================
// SECCIÓN 2: DESCRIPCIÓN DEL SISTEMA E INTEGRACIÓN
// ============================================================================
= Descripción del Sistema e Integración

El sistema se estructuró bajo una arquitectura modular cuyo núcleo principal reside en Python 3.10+, complementado con una versión interactiva en línea concebida como material didáctico abierto.

#callout("Arquitectura General del Compilador y Telemetría Paso a Paso")[
  `Código Fuente` $arrow.r$ *Lexer* (`Token[]`) $arrow.r$ *LLParserSDT* (`.inh` / `.place`) $arrow.r$ *CodeGenerator* (`Staging Buffer`)\
  $arrow.b$ _Éxito_: `commit()` $arrow.r$ *TAC Crudo* $arrow.r$ *Optimizador* $arrow.r$ *TAC Optimizado*\
  $arrow.b$ _Error_: `rollback()` $arrow.r$ *Vaciamiento Atómico (0 TAC)* $+$ *Diagnóstico L:C*\
  $arrow.t.b$ _En cada transición_: *CompilerTracer* captura instantáneas inmutables `TraceStep[]` (JSON)
]

== Núcleo Compilador en Python (Entregable Principal)
El núcleo en Python 3.10+ está diseñado sin dependencias externas y organizado en cuatro paquetes:
+ `/lexer` (`tokens.py`, `lexer.py`): Define `TokenType`, el dataclass inmutable `Token(type, lexeme, line, column)` y `LexicalError` sin efectos secundarios (`print()` eliminados).
+ `/parser_code_gen` (`parser.py`, `code_generator.py`, `symbol_table.py`, `tracer.py`): Contiene el parser predictivo recursivo `LLParserSDT`, la tabla de símbolos jerárquica `SymbolTable`, el generador transaccional `CodeGenerator` y `CompilerTracer`.
+ `/main` (`main.py`): CLI con menú interactivo, batería oficial (`--official`), compilación directa (`-e`) y visor de traza (`--trace`).

== Aporte Personal Académico: Visualizador Web Interactivo para la Asignatura
Como una iniciativa y contribución personal más allá de los requerimientos base del proyecto, se portó el motor completo del compilador 1:1 a TypeScript dentro de una aplicación web interactiva desarrollada en Angular (`web-visualizer/`) y publicada en línea para acceso directo desde cualquier navegador.

El propósito de este aporte es ofrecer una herramienta visual y pedagógica que pueda ser utilizada como material de apoyo en futuros semestres de la asignatura _Compiladores_ impartida por la profesora Melissa Brigitthe Hinojosa, así como por estudiantes del Departamento de Computación de la Facultad de Ingeniería de la UNAM. La interfaz implementa la dirección visual _Soft Twilight & Pastel Lavender_ (tipografías *Satoshi* y *JetBrains Mono*, superficies `#251F38`/`#3A3153`, `.inh` en azul cielo `#ACD0FF` y `.place` en rosa `#FF6CD2`) e incluye un recorrido guiado de bienvenida (`OnboardingTourComponent`) de 5 pasos.

// ============================================================================
// SECCIÓN 3: ESPECIFICACIÓN FORMAL Y LÓGICA DESARROLLADA
// ============================================================================
= Especificación Formal y Lógica Desarrollada

== Gramática $L L(1)$ sin Recursión Izquierda

$
  "Program" &arrow.r "Stmt" "StmtList" \
  "StmtList" &arrow.r "Stmt" "StmtList" | epsilon \
  "Stmt" &arrow.r "Decl" | S | "Block" \
  "Decl" &arrow.r "Type" bold("id") bold(";") \
  "Type" &arrow.r bold("int") | bold("float") \
  "Block" &arrow.r bold("{") "StmtList" bold("}") \
  S &arrow.r bold("id") bold("=") E bold(";") \
  E &arrow.r T E' \
  E' &arrow.r bold("+") T E' | bold("-") T E' | epsilon \
  T &arrow.r F T' \
  T' &arrow.r bold("*") F T' | bold("/") F T' | epsilon \
  F &arrow.r bold("(") E bold(")") | bold("id") | bold("num")
$

== Esquema de Traducción Dirigida por Sintaxis (SDT)

#table(
  columns: (1.2fr, 2.5fr),
  inset: 7pt,
  stroke: 0.5pt + c-code-border,
  fill: (col, row) => if row == 0 { c-code-bg } else { white },
  [*Producción Gramatical*], [*Acciones Semánticas Ejecutadas Durante el Parsing*],
  [`S -> id = E ;`], [`emit(id.lexeme + " = " + E.place); symbol_table.record_assignment(...)`],
  [`E -> T E'`], [`E'.inh = T.place; E.place = E'.place;`],
  [`E' -> + T E'1`], [`t = newTemp(); emit(t + " = " + E'.inh + " + " + T.place); E'1.inh = t; E'.place = E'1.place;`],
  [`E' -> - T E'1`], [`t = newTemp(); emit(t + " = " + E'.inh + " - " + T.place); E'1.inh = t; E'.place = E'1.place;`],
  [`E' -> ε`], [`E'.place = E'.inh;`],
  [`T -> F T'`], [`T'.inh = F.place; T.place = T'.place;`],
  [`T' -> * F T'1`], [`t = newTemp(); emit(t + " = " + T'.inh + " * " + F.place); T'1.inh = t; T'.place = T'1.place;`],
  [`T' -> / F T'1`], [`Validar F.place != 0; t = newTemp(); emit(t + " = " + T'.inh + " / " + F.place); T'1.inh = t; T'.place = T'1.place;`],
  [`T' -> ε`], [`T'.place = T'.inh;`],
  [`F -> ( E )`], [`F.place = E.place;`],
  [`F -> id | num`], [`F.place = token.lexeme;`],
)

// ============================================================================
// SECCIÓN 4: MANUAL DE EJECUCIÓN
// ============================================================================
= Manual de Ejecución

== Ejecución del Compilador en Python
*Requisitos*: Python 3.10 o superior (únicamente biblioteca estándar, sin dependencias externas).

```bash
# 1. Menú interactivo en consola
python main/main.py

# 2. Batería oficial de ejemplos del PDF
python main/main.py --official

# 3. Compilación directa con traza paso a paso
python main/main.py -e "x = a + b * c;" --trace
```

// ============================================================================
// SECCIÓN 5: PRUEBAS REALIZADAS Y ANÁLISIS DE RESULTADOS
// ============================================================================
= Pruebas Realizadas y Análisis de Resultados

#table(
  columns: (1.1fr, 1.2fr, 0.7fr, 2.2fr),
  inset: 6.5pt,
  stroke: 0.5pt + c-code-border,
  fill: (col, row) => if row == 0 { c-code-bg } else { white },
  [*Caso*], [*Entrada*], [*Estado*], [*Salida TAC Crudo / Diagnóstico y Rollback*],
  [Válido (a)], [`x = a;`], [Válida], [`x = a`],
  [Válido (b)], [`x = a + b;`], [Válida], [`t1 = a + b`, `x = t1` $arrow.r$ Opt: `x = a + b`],
  [Válido (c)], [`x = a + b * c;`], [Válida], [`t1 = b * c`, `t2 = a + t1`, `x = t2` $arrow.r$ Opt: `t1 = b * c`, `x = a + t1`],
  [Válido (d)], [`x = (a + b) * c;`], [Válida], [`t1 = a + b`, `t2 = t1 * c`, `x = t2` $arrow.r$ Opt: `t1 = a + b`, `x = t1 * c`],
  [Inválido (a)], [`x = a + * b;`], [Inválida], [Error sintáctico L1:C9 (`'*'` inesperado) · 0 TAC],
  [Inválido (b)], [`x = (a + b;`], [Inválida], [Error sintáctico L1:C11 (falta `')'`) · Rollback (`t1` descartado)],
  [Inválido (c)], [`x = ((a + b) *`], [Inválida], [Error sintáctico L1:C15 (`'$'` tras `'*'`) · Rollback (`t1` descartado)],
  [Error léxico], [`x = a @ b;`], [Inválida], [Error léxico L1:C7 (símbolo `'@'`) · 0 TAC],
  [Falta `;`], [`x = a + b`], [Inválida], [Error sintáctico L1:C10 (falta `';'`) · Rollback (0 TAC)],
)

// ============================================================================
// SECCIÓN 6: CONCLUSIONES
// ============================================================================
= Conclusiones

+ *Integración Modular y Contrato Inmutable*: La unificación bajo `Token(type, lexeme, line, column)` eliminó efectos secundarios entre el lexer y el parser $L L(1)$ y permitió compartir el contrato `TraceStep` de manera uniforme.
+ *SDT $L$-Atribuido sin Recursión Izquierda*: El paso de `.inh` por argumento y retorno de `.place` garantizó precedencia de `*`/`/` sobre `+`/`-` y asociatividad izquierda estricta sin requerir un AST intermedio.
+ *Atomicidad Transaccional*: El mecanismo `commit()` / `rollback()` sobre el buffer TAC aseguró que errores tardíos como `x = ((a + b) *` descarten los temporales previamente emitidos, garantizando cero código residual.
+ *Aporte Personal Didáctico para Futuros Cursos*: El visualizador web interactivo desarrollado e integrado como iniciativa personal queda a disposición de la profesora Melissa Brigitthe Hinojosa y del Departamento de Computación de la Facultad de Ingeniería como recurso pedagógico para futuros cursos de la asignatura.
