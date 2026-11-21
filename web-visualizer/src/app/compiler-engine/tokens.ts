/**
 * Definición de tokens y errores léxicos del compilador (Paridad 1:1 con Python Fase 1).
 */

export enum TokenType {
  // Literales e identificadores
  ID = 'ID',
  NUM = 'NUM',

  // Palabras reservadas de tipos (análisis semántico)
  INT = 'INT',
  FLOAT = 'FLOAT',

  // Operadores aritméticos y de asignación
  ASSIGN = 'ASSIGN',
  PLUS = 'PLUS',
  MINUS = 'MINUS',
  STAR = 'STAR',
  SLASH = 'SLASH',

  // Delimitadores
  LPAREN = 'LPAREN',
  RPAREN = 'RPAREN',
  LBRACE = 'LBRACE',
  RBRACE = 'RBRACE',
  SEMICOLON = 'SEMICOLON',

  // Fin de entrada
  EOF = 'EOF',
}

export const KEYWORDS: Readonly<Record<string, TokenType>> = {
  int: TokenType.INT,
  float: TokenType.FLOAT,
};

export const SINGLE_CHAR_TOKENS: Readonly<Record<string, TokenType>> = {
  '=': TokenType.ASSIGN,
  '+': TokenType.PLUS,
  '-': TokenType.MINUS,
  '*': TokenType.STAR,
  '/': TokenType.SLASH,
  '(': TokenType.LPAREN,
  ')': TokenType.RPAREN,
  '{': TokenType.LBRACE,
  '}': TokenType.RBRACE,
  ';': TokenType.SEMICOLON,
};

export const TOKEN_DISPLAY: Readonly<Record<TokenType, string>> = {
  [TokenType.ID]: 'id',
  [TokenType.NUM]: 'num',
  [TokenType.INT]: 'int',
  [TokenType.FLOAT]: 'float',
  [TokenType.ASSIGN]: '=',
  [TokenType.PLUS]: '+',
  [TokenType.MINUS]: '-',
  [TokenType.STAR]: '*',
  [TokenType.SLASH]: '/',
  [TokenType.LPAREN]: '(',
  [TokenType.RPAREN]: ')',
  [TokenType.LBRACE]: '{',
  [TokenType.RBRACE]: '}',
  [TokenType.SEMICOLON]: ';',
  [TokenType.EOF]: '$',
};

export interface TokenDto {
  readonly type: TokenType;
  readonly lexeme: string;
  readonly line: number;
  readonly column: number;
}

export class Token implements TokenDto {
  constructor(
    public readonly type: TokenType,
    public readonly lexeme: string,
    public readonly line: number,
    public readonly column: number
  ) {}

  toDict(): TokenDto {
    return {
      type: this.type,
      lexeme: this.lexeme,
      line: this.line,
      column: this.column,
    };
  }
}

export class LexicalError extends Error {
  public readonly detail: string;
  public override readonly message: string;

  constructor(
    public readonly char: string,
    public readonly line: number,
    public readonly column: number,
    detail: string = ''
  ) {
    const resolvedDetail = detail || `Símbolo no reconocido '${char}'`;
    const msg = `Error léxico en línea ${line}, columna ${column}: ${resolvedDetail}.`;
    super(msg);
    this.name = 'LexicalError';
    this.detail = resolvedDetail;
    this.message = msg;
  }

  toDict(): Record<string, unknown> {
    return {
      phase: 'LEXING',
      char: this.char,
      line: this.line,
      column: this.column,
      message: this.message,
    };
  }
}
