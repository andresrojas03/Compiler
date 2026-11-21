/**
 * Parser LL(1) descendente recursivo con Traducción Dirigida por Sintaxis (SDT)
 * y orquestación transaccional completa (Port 1:1 de parser_code_gen/parser.py).
 */

import { CodeGenerator, TACInstruction } from './code-generator';
import { Lexer } from './lexer';
import {
  SemanticError,
  SemanticWarning,
  SymbolEntry,
  SymbolTable,
} from './symbol-table';
import { TOKEN_DISPLAY, Token, TokenType } from './tokens';
import { CompilerTracer, TraceStep } from './tracer';

export class ParserSyntaxError extends Error {
  public readonly line: number;
  public readonly column: number;
  public override readonly message: string;

  constructor(
    rawMessage: string,
    public readonly token: Token,
    public readonly expected: string[] = []
  ) {
    const formatted = `Error sintáctico en línea ${token.line}, columna ${token.column}: ${rawMessage}`;
    super(formatted);
    this.name = 'ParserSyntaxError';
    this.line = token.line;
    this.column = token.column;
    this.message = formatted;
  }

  toDict(): Record<string, unknown> {
    return {
      phase: 'PARSING',
      line: this.line,
      column: this.column,
      token: this.token.toDict(),
      expected: [...this.expected],
      message: this.message,
    };
  }
}

export interface CompilerError {
  readonly phase: string;
  readonly message: string;
  readonly line: number;
  readonly column: number;
}

export interface CompilationResult {
  readonly source: string;
  readonly success: boolean;
  readonly strictMode: boolean;
  readonly tokens: Token[];
  readonly tacRaw: TACInstruction[];
  readonly tacOptimized: TACInstruction[];
  readonly optimizationNotes: string[];
  readonly symbolTable: SymbolEntry[];
  readonly errors: CompilerError[];
  readonly warnings: SemanticWarning[];
  readonly trace: TraceStep[];
  readonly tracer: CompilerTracer;
}

function isZeroNumericLiteral(place: string): boolean {
  if (!/^[+-]?(\d+(\.\d+)?|\.\d+)$/.test(place)) {
    return false;
  }
  const n = Number(place);
  return Number.isFinite(n) && n === 0;
}

export class LLParserSDT {
  public pos = 0;

  constructor(
    public readonly tokens: Token[],
    public readonly codegen: CodeGenerator,
    public readonly symbolTable: SymbolTable,
    public readonly tracer: CompilerTracer
  ) {}

  private peekToken(): Token {
    if (this.pos < this.tokens.length) {
      return this.tokens[this.pos];
    }
    return this.tokens[this.tokens.length - 1];
  }

  get current(): Token {
    return this.peekToken();
  }

  private trace(params: {
    phase: string;
    action: string;
    message: string;
    production?: string | null;
    emittedTac?: string | null;
  }): void {
    this.tracer.record({
      phase: params.phase,
      action: params.action,
      tokenIndex: this.pos,
      currentToken: this.peekToken(),
      tacBuffer: this.codegen.getStagingLines(),
      symbolTableSnapshot: this.symbolTable.snapshot(),
      message: params.message,
      production: params.production ?? null,
      emittedTac: params.emittedTac ?? null,
    });
  }

  private match(expectedType: TokenType): Token {
    const tok = this.peekToken();
    if (tok.type !== expectedType) {
      const expectedLbl = TOKEN_DISPLAY[expectedType];
      const foundLbl =
        tok.type === TokenType.EOF
          ? "fin de entrada ('$')"
          : `'${tok.lexeme}' (${TOKEN_DISPLAY[tok.type]})`;
      throw new ParserSyntaxError(
        `Se esperaba '${expectedLbl}', pero se encontró ${foundLbl}.`,
        tok,
        [expectedLbl]
      );
    }
    const symbol = TOKEN_DISPLAY[expectedType];
    this.tracer.matchLl(symbol);
    this.trace({
      phase: 'PARSING',
      action: 'MATCH',
      message: `Emparejado terminal '${symbol}' con lexema '${tok.lexeme}'.`,
    });
    this.pos += 1;
    return tok;
  }

  private expand(nonTerminal: string, rhs: string[], message: string): string {
    const production = `${nonTerminal} -> ${rhs.join(' ')}`;
    this.tracer.expandLl(nonTerminal, rhs);
    this.tracer.updateTopFrame({ production });
    this.trace({
      phase: 'PARSING',
      action: rhs.length === 1 && rhs[0] === 'ε' ? 'EPSILON' : 'EXPAND',
      production,
      message,
    });
    return production;
  }

  // Program -> Stmt StmtList
  parse(): void {
    this.tracer.initLlStack('Program');
    this.tracer.pushFrame('Program');

    const firstTok = this.peekToken();
    if (firstTok.type === TokenType.EOF) {
      throw new ParserSyntaxError(
        'Entrada vacía: se esperaba una sentencia de asignación o declaración.',
        firstTok,
        ['id', 'int', 'float', '{']
      );
    }

    this.expand('Program', ['Stmt', 'StmtList'], 'Inicio de derivación del programa.');
    this.parseStmt();
    this.parseStmtList();

    const endTok = this.peekToken();
    if (endTok.type !== TokenType.EOF) {
      throw new ParserSyntaxError(
        `Token inesperado '${endTok.lexeme}' tras finalizar el análisis.`,
        endTok,
        ['$']
      );
    }
    this.match(TokenType.EOF);
    this.tracer.popFrame();
  }

  private parseStmtList(): void {
    this.tracer.pushFrame('StmtList');
    const tok = this.peekToken();
    if (
      tok.type === TokenType.ID ||
      tok.type === TokenType.INT ||
      tok.type === TokenType.FLOAT ||
      tok.type === TokenType.LBRACE
    ) {
      this.expand(
        'StmtList',
        ['Stmt', 'StmtList'],
        'Se detecta una nueva sentencia en StmtList.'
      );
      this.parseStmt();
      this.parseStmtList();
    } else if (
      tok.type === TokenType.EOF ||
      tok.type === TokenType.RBRACE
    ) {
      this.expand('StmtList', ['ε'], 'Fin de secuencia de sentencias (ε).');
    } else {
      throw new ParserSyntaxError(
        `Inicio de sentencia inválido: se encontró '${tok.lexeme}'.`,
        tok,
        ['id', 'int', 'float', '{', '}', '$']
      );
    }
    this.tracer.popFrame();
  }

  private parseStmt(): void {
    this.tracer.pushFrame('Stmt');
    const tok = this.peekToken();
    if (tok.type === TokenType.INT || tok.type === TokenType.FLOAT) {
      this.expand('Stmt', ['Decl'], 'Derivación hacia declaración de variable.');
      this.parseDecl();
    } else if (tok.type === TokenType.ID) {
      this.expand('Stmt', ['S'], 'Derivación hacia sentencia de asignación S.');
      this.parseS();
    } else if (tok.type === TokenType.LBRACE) {
      this.expand('Stmt', ['Block'], 'Derivación hacia bloque con nuevo ámbito.');
      this.parseBlock();
    } else {
      throw new ParserSyntaxError(
        `Se esperaba una sentencia válida, pero se encontró '${tok.lexeme}'.`,
        tok,
        ['id', 'int', 'float', '{']
      );
    }
    this.tracer.popFrame();
  }

  private parseDecl(): void {
    this.tracer.pushFrame('Decl');
    this.expand('Decl', ['Type', 'id', ';'], "Declaración tipada terminada en ';'.");
    const dataType = this.parseType();
    const idTok = this.match(TokenType.ID);
    this.match(TokenType.SEMICOLON);

    const entry = this.symbolTable.declare(
      idTok.lexeme,
      dataType,
      idTok.line,
      idTok.column
    );
    this.trace({
      phase: 'SEMANTIC',
      action: 'SYM_DECLARE',
      message: `Declarada variable '${entry.name}' de tipo '${entry.data_type}' en ámbito '${entry.scope_id}'.`,
    });
    this.tracer.popFrame();
  }

  private parseType(): string {
    this.tracer.pushFrame('Type');
    const tok = this.peekToken();
    if (tok.type === TokenType.INT) {
      this.expand('Type', ['int'], 'Tipo primitivo int.');
      this.match(TokenType.INT);
      this.tracer.updateTopFrame({ place: 'int' });
      this.tracer.popFrame();
      return 'int';
    }
    if (tok.type === TokenType.FLOAT) {
      this.expand('Type', ['float'], 'Tipo primitivo float.');
      this.match(TokenType.FLOAT);
      this.tracer.updateTopFrame({ place: 'float' });
      this.tracer.popFrame();
      return 'float';
    }
    throw new ParserSyntaxError(
      `Se esperaba un tipo ('int' o 'float'), pero se encontró '${tok.lexeme}'.`,
      tok,
      ['int', 'float']
    );
  }

  private parseBlock(): void {
    this.tracer.pushFrame('Block');
    this.expand('Block', ['{', 'StmtList', '}'], 'Apertura de bloque de ámbito léxico.');
    this.match(TokenType.LBRACE);
    const scopeId = this.symbolTable.enterScope();
    this.trace({
      phase: 'SEMANTIC',
      action: 'SYM_DECLARE',
      message: `Entrada al ámbito léxico '${scopeId}'.`,
    });
    this.parseStmtList();
    this.match(TokenType.RBRACE);
    const closedScope = this.symbolTable.exitScope();
    this.trace({
      phase: 'SEMANTIC',
      action: 'SYM_USE',
      message: `Salida del ámbito léxico '${closedScope}'.`,
    });
    this.tracer.popFrame();
  }

  // S -> id = E ;
  private parseS(): void {
    this.tracer.pushFrame('S');
    this.expand('S', ['id', '=', 'E', ';'], "Sentencia de asignación obligatoria con ';'.");

    const targetTok = this.match(TokenType.ID);
    this.match(TokenType.ASSIGN);

    const [ePlace, eType] = this.parseE();
    this.match(TokenType.SEMICOLON);

    this.symbolTable.recordAssignment(
      targetTok.lexeme,
      eType,
      ePlace,
      targetTok.line,
      targetTok.column
    );
    const instr = this.codegen.emit(`${targetTok.lexeme} = ${ePlace}`);
    this.tracer.updateTopFrame({ place: targetTok.lexeme });
    this.trace({
      phase: 'CODEGEN',
      action: 'EMIT',
      emittedTac: instr.text,
      message: `Acción semántica de S: emit('${instr.text}').`,
    });
    this.tracer.popFrame();
  }

  // Regla 1: E -> T E'  { E'.inh = T.place; E.place = E'.place }
  private parseE(): [string, string] {
    this.tracer.pushFrame('E');
    const tok = this.peekToken();
    if (
      tok.type !== TokenType.LPAREN &&
      tok.type !== TokenType.ID &&
      tok.type !== TokenType.NUM
    ) {
      throw new ParserSyntaxError(
        `Inicio de expresión inválido: se encontró '${tok.lexeme}'.`,
        tok,
        ['(', 'id', 'num']
      );
    }

    this.expand('E', ['T', "E'"], "Regla 1: expansión de expresión E -> T E'.");
    const [tPlace, tType] = this.parseT();

    this.trace({
      phase: 'SEMANTIC',
      action: 'ATTR_PASS',
      message: `Paso de atributo heredado: E'.inh = T.place ('${tPlace}').`,
    });
    const [ePlace, eType] = this.parseEPrime(tPlace, tType);

    this.tracer.updateTopFrame({ place: ePlace });
    this.trace({
      phase: 'SEMANTIC',
      action: 'ATTR_RETURN',
      message: `Síntesis de atributo: E.place = E'.place ('${ePlace}').`,
    });
    this.tracer.popFrame();
    return [ePlace, eType];
  }

  // Regla 2: E' -> + T E'1 | - T E'1
  // Regla 3: E' -> ε { E'.place = E'.inh }
  private parseEPrime(inh: string, inhType: string): [string, string] {
    this.tracer.pushFrame("E'", null, inh, null);
    const tok = this.peekToken();

    if (
      tok.type === TokenType.PLUS ||
      tok.type === TokenType.MINUS
    ) {
      const opStr = tok.lexeme;
      this.expand(
        "E'",
        [opStr, 'T', "E'"],
        `Regla 2: expansión E' -> ${opStr} T E' con E'.inh = '${inh}'.`
      );
      this.match(tok.type);
      const [tPlace, tType] = this.parseT();

      const temp = this.codegen.newTemp();
      const instr = this.codegen.emit(`${temp} = ${inh} ${opStr} ${tPlace}`);
      const resultType = SymbolTable.resolveBinaryType(inhType, tType, opStr);

      this.trace({
        phase: 'CODEGEN',
        action: 'EMIT',
        emittedTac: instr.text,
        message: `Acción semántica E': t = newTemp() -> '${temp}'; emit('${instr.text}').`,
      });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_PASS',
        message: `Asociatividad izquierda: E'1.inh = '${temp}'.`,
      });

      const [finalPlace, finalType] = this.parseEPrime(temp, resultType);
      this.tracer.updateTopFrame({ place: finalPlace });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `Síntesis E'.place = E'1.place ('${finalPlace}').`,
      });
      this.tracer.popFrame();
      return [finalPlace, finalType];
    }

    if (
      tok.type === TokenType.RPAREN ||
      tok.type === TokenType.SEMICOLON
    ) {
      this.expand("E'", ['ε'], `Regla 3: E' -> ε; E'.place = E'.inh ('${inh}').`);
      this.tracer.updateTopFrame({ place: inh });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `Retorno caso base E': E'.place = '${inh}'.`,
      });
      this.tracer.popFrame();
      return [inh, inhType];
    }

    if (tok.type === TokenType.EOF) {
      throw new ParserSyntaxError(
        "Fin de entrada inesperado: falta ';' o ')' para cerrar la expresión.",
        tok,
        ['+', '-', ')', ';']
      );
    }
    throw new ParserSyntaxError(
      `Token inesperado '${tok.lexeme}' después de término en E'. Se esperaba uno de: ['+', '-', ')', ';'].`,
      tok,
      ['+', '-', ')', ';']
    );
  }

  // Regla 4: T -> F T'  { T'.inh = F.place; T.place = T'.place }
  private parseT(): [string, string] {
    this.tracer.pushFrame('T');
    const tok = this.peekToken();
    if (
      tok.type !== TokenType.LPAREN &&
      tok.type !== TokenType.ID &&
      tok.type !== TokenType.NUM
    ) {
      throw new ParserSyntaxError(
        `Se esperaba un factor ('(', 'id' o 'num'), pero se encontró '${tok.lexeme}'.`,
        tok,
        ['(', 'id', 'num']
      );
    }

    this.expand('T', ['F', "T'"], "Regla 4: expansión de término T -> F T'.");
    const [fPlace, fType] = this.parseF();

    this.trace({
      phase: 'SEMANTIC',
      action: 'ATTR_PASS',
      message: `Paso de atributo heredado: T'.inh = F.place ('${fPlace}').`,
    });
    const [tPlace, tType] = this.parseTPrime(fPlace, fType);

    this.tracer.updateTopFrame({ place: tPlace });
    this.trace({
      phase: 'SEMANTIC',
      action: 'ATTR_RETURN',
      message: `Síntesis de atributo: T.place = T'.place ('${tPlace}').`,
    });
    this.tracer.popFrame();
    return [tPlace, tType];
  }

  // Regla 5: T' -> * F T'1 | / F T'1
  // Regla 6: T' -> ε { T'.place = T'.inh }
  private parseTPrime(inh: string, inhType: string): [string, string] {
    this.tracer.pushFrame("T'", null, inh, null);
    const tok = this.peekToken();

    if (
      tok.type === TokenType.STAR ||
      tok.type === TokenType.SLASH
    ) {
      const opStr = tok.lexeme;
      this.expand(
        "T'",
        [opStr, 'F', "T'"],
        `Regla 5: expansión T' -> ${opStr} F T' con T'.inh = '${inh}'.`
      );
      this.match(tok.type);
      const [fPlace, fType] = this.parseF();

      if (opStr === '/' && isZeroNumericLiteral(fPlace)) {
        throw new SemanticError(
          'División explícita entre constante cero.',
          tok.line,
          tok.column
        );
      }

      const temp = this.codegen.newTemp();
      const instr = this.codegen.emit(`${temp} = ${inh} ${opStr} ${fPlace}`);
      const resultType = SymbolTable.resolveBinaryType(inhType, fType, opStr);

      this.trace({
        phase: 'CODEGEN',
        action: 'EMIT',
        emittedTac: instr.text,
        message: `Acción semántica T': t = newTemp() -> '${temp}'; emit('${instr.text}').`,
      });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_PASS',
        message: `Asociatividad izquierda: T'1.inh = '${temp}'.`,
      });

      const [finalPlace, finalType] = this.parseTPrime(temp, resultType);
      this.tracer.updateTopFrame({ place: finalPlace });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `Síntesis T'.place = T'1.place ('${finalPlace}').`,
      });
      this.tracer.popFrame();
      return [finalPlace, finalType];
    }

    if (
      tok.type === TokenType.PLUS ||
      tok.type === TokenType.MINUS ||
      tok.type === TokenType.RPAREN ||
      tok.type === TokenType.SEMICOLON
    ) {
      this.expand("T'", ['ε'], `Regla 6: T' -> ε; T'.place = T'.inh ('${inh}').`);
      this.tracer.updateTopFrame({ place: inh });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `Retorno caso base T': T'.place = '${inh}'.`,
      });
      this.tracer.popFrame();
      return [inh, inhType];
    }

    if (tok.type === TokenType.EOF) {
      throw new ParserSyntaxError(
        "Fin de entrada inesperado: falta ';' o ')' para cerrar la expresión.",
        tok,
        ['*', '/', '+', '-', ')', ';']
      );
    }
    throw new ParserSyntaxError(
      `Token inesperado '${tok.lexeme}' después de factor en T'. Se esperaba uno de: ['*', '/', '+', '-', ')', ';'].`,
      tok,
      ['*', '/', '+', '-', ')', ';']
    );
  }

  // Regla 7: F -> id | num
  // Regla 8: F -> ( E )
  private parseF(): [string, string] {
    this.tracer.pushFrame('F');
    const tok = this.peekToken();

    if (tok.type === TokenType.ID) {
      this.expand('F', ['id'], `Regla 7: identificador F -> id ('${tok.lexeme}').`);
      const idTok = this.match(TokenType.ID);
      const entry = this.symbolTable.recordUse(idTok.lexeme, idTok.line, idTok.column);
      this.tracer.updateTopFrame({ place: idTok.lexeme });
      this.trace({
        phase: 'SEMANTIC',
        action: 'SYM_USE',
        message: `F.place = id.name ('${idTok.lexeme}', tipo='${entry.data_type}').`,
      });
      this.tracer.popFrame();
      return [idTok.lexeme, entry.data_type];
    }

    if (tok.type === TokenType.NUM) {
      this.expand('F', ['num'], `Regla 7b: literal numérico F -> num ('${tok.lexeme}').`);
      const numTok = this.match(TokenType.NUM);
      const numType = numTok.lexeme.includes('.') ? 'float' : 'int';
      this.tracer.updateTopFrame({ place: numTok.lexeme });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `F.place = num.lexeme ('${numTok.lexeme}', tipo='${numType}').`,
      });
      this.tracer.popFrame();
      return [numTok.lexeme, numType];
    }

    if (tok.type === TokenType.LPAREN) {
      this.expand('F', ['(', 'E', ')'], 'Regla 8: subexpresión entre paréntesis F -> ( E ).');
      this.match(TokenType.LPAREN);
      const [ePlace, eType] = this.parseE();
      this.match(TokenType.RPAREN);
      this.tracer.updateTopFrame({ place: ePlace });
      this.trace({
        phase: 'SEMANTIC',
        action: 'ATTR_RETURN',
        message: `F.place = E.place ('${ePlace}').`,
      });
      this.tracer.popFrame();
      return [ePlace, eType];
    }

    throw new ParserSyntaxError(
      `Factor inválido: se esperaba '(', 'id' o 'num', pero se encontró '${tok.lexeme}'.`,
      tok,
      ['(', 'id', 'num']
    );
  }
}

export function compileSource(
  source: string,
  strictMode: boolean = false
): CompilationResult {
  const lexer = new Lexer(source);
  const tokens = lexer.tokenize(false);
  const tracer = new CompilerTracer();
  const symbolTable = new SymbolTable(strictMode);
  const codegen = new CodeGenerator();

  if (lexer.errors.length > 0) {
    const errors: CompilerError[] = lexer.errors.map((err) => ({
      phase: 'LEXING',
      message: err.message,
      line: err.line,
      column: err.column,
    }));

    tracer.record({
      phase: 'ERROR',
      action: 'ERROR',
      tokenIndex: 0,
      currentToken: tokens.length > 0 ? tokens[0] : null,
      tacBuffer: [],
      symbolTableSnapshot: [],
      message: errors.map((e) => e.message).join('; '),
    });

    return {
      source,
      success: false,
      strictMode,
      tokens,
      tacRaw: [],
      tacOptimized: [],
      optimizationNotes: [],
      symbolTable: [],
      errors,
      warnings: [],
      trace: [...tracer.steps],
      tracer,
    };
  }

  const parser = new LLParserSDT(tokens, codegen, symbolTable, tracer);
  try {
    parser.parse();
  } catch (exc: unknown) {
    if (exc instanceof ParserSyntaxError || exc instanceof SemanticError) {
      const discarded = codegen.rollback();
      const phase = exc instanceof ParserSyntaxError ? 'PARSING' : 'SEMANTIC';
      tracer.record({
        phase: 'ROLLBACK',
        action: 'ROLLBACK',
        tokenIndex: parser.pos,
        currentToken: parser.current,
        tacBuffer: [],
        symbolTableSnapshot: symbolTable.snapshot(),
        message: `Rollback ejecutado (${discarded.length} instrucción(es) descartada(s)). Causa: ${exc.message}`,
      });

      return {
        source,
        success: false,
        strictMode,
        tokens,
        tacRaw: [],
        tacOptimized: [],
        optimizationNotes: [],
        symbolTable: symbolTable.entries(),
        errors: [
          {
            phase,
            message: exc.message,
            line: exc.line,
            column: exc.column,
          },
        ],
        warnings: [...symbolTable.warnings],
        trace: [...tracer.steps],
        tracer,
      };
    }
    throw exc;
  }

  const tacRaw = codegen.commit();
  const { instructions: tacOptimized, notes: optNotes } =
    CodeGenerator.optimize(tacRaw);

  for (const note of optNotes) {
    tracer.record({
      phase: 'OPTIMIZATION',
      action:
        note.includes('Propagación') || note.includes('temporal')
          ? 'OPT_PROPAGATE'
          : 'OPT_FOLD',
      tokenIndex: tokens.length - 1,
      currentToken: tokens.length > 0 ? tokens[tokens.length - 1] : null,
      tacBuffer: tacOptimized.map((i) => i.text),
      symbolTableSnapshot: symbolTable.snapshot(),
      message: note,
    });
  }

  return {
    source,
    success: true,
    strictMode,
    tokens,
    tacRaw,
    tacOptimized,
    optimizationNotes: optNotes,
    symbolTable: symbolTable.entries(),
    errors: [],
    warnings: [...symbolTable.warnings],
    trace: [...tracer.steps],
    tracer,
  };
}
