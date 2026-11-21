/**
 * Analizador léxico sin efectos secundarios para el compilador (Port 1:1 de lexer/lexer.py).
 */

import {
  KEYWORDS,
  LexicalError,
  SINGLE_CHAR_TOKENS,
  Token,
  TokenType,
} from './tokens';

function isAlpha(ch: string): boolean {
  return /^[A-Za-z]$/.test(ch);
}

function isDigit(ch: string): boolean {
  return /^[0-9]$/.test(ch);
}

function isAlnumOrUnderscore(ch: string): boolean {
  return /^[A-Za-z0-9_]$/.test(ch);
}

export class Lexer {
  private pos = 0;
  private line = 1;
  private column = 1;
  public readonly errors: LexicalError[] = [];

  constructor(public readonly source: string) {}

  private current(): string | null {
    return this.pos < this.source.length ? this.source[this.pos] : null;
  }

  private peek(): string | null {
    const idx = this.pos + 1;
    return idx < this.source.length ? this.source[idx] : null;
  }

  private advance(): string | null {
    const char = this.current();
    if (char === null) {
      return null;
    }
    this.pos += 1;
    if (char === '\n') {
      this.line += 1;
      this.column = 1;
    } else {
      this.column += 1;
    }
    return char;
  }

  private skipIgnorable(raiseOnError: boolean = false): void {
    while (true) {
      const char = this.current();
      if (char === null) {
        return;
      }

      if (char === ' ' || char === '\t' || char === '\r' || char === '\n') {
        this.advance();
        continue;
      }

      // Comentario de línea: // ...
      if (char === '/' && this.peek() === '/') {
        while (this.current() !== null && this.current() !== '\n') {
          this.advance();
        }
        continue;
      }

      // Comentario de bloque: /* ... */
      if (char === '/' && this.peek() === '*') {
        const startLine = this.line;
        const startCol = this.column;
        this.advance();
        this.advance();
        let closed = false;
        while (this.current() !== null) {
          if (this.current() === '*' && this.peek() === '/') {
            this.advance();
            this.advance();
            closed = true;
            break;
          }
          this.advance();
        }
        if (!closed) {
          const err = new LexicalError(
            '/*',
            startLine,
            startCol,
            "Comentario de bloque '/*' sin cierre '*/'"
          );
          this.errors.push(err);
          if (raiseOnError) {
            throw err;
          }
          return;
        }
        continue;
      }

      return;
    }
  }

  private readIdentifier(): Token {
    const startLine = this.line;
    const startCol = this.column;
    const startPos = this.pos;
    while (this.current() !== null && isAlnumOrUnderscore(this.current()!)) {
      this.advance();
    }
    const lexeme = this.source.slice(startPos, this.pos);
    const tokenType = KEYWORDS[lexeme] ?? TokenType.ID;
    return new Token(tokenType, lexeme, startLine, startCol);
  }

  private readNumber(raiseOnError: boolean = false): Token | null {
    const startLine = this.line;
    const startCol = this.column;
    const startPos = this.pos;
    while (this.current() !== null && isDigit(this.current()!)) {
      this.advance();
    }
    if (this.current() === '.') {
      if (this.peek() !== null && isDigit(this.peek()!)) {
        this.advance();
        while (this.current() !== null && isDigit(this.current()!)) {
          this.advance();
        }
      } else {
        this.advance();
        const badLexeme = this.source.slice(startPos, this.pos);
        const err = new LexicalError(
          badLexeme,
          startLine,
          startCol,
          `Literal decimal malformado '${badLexeme}' (se esperaban dígitos después del punto)`
        );
        this.errors.push(err);
        if (raiseOnError) {
          throw err;
        }
        return null;
      }
    }
    const lexeme = this.source.slice(startPos, this.pos);
    return new Token(TokenType.NUM, lexeme, startLine, startCol);
  }

  tokenize(raiseOnError: boolean = false): Token[] {
    const tokens: Token[] = [];
    this.errors.length = 0;

    while (true) {
      this.skipIgnorable(raiseOnError);
      const char = this.current();

      if (char === null) {
        tokens.push(new Token(TokenType.EOF, '$', this.line, this.column));
        break;
      }

      const line = this.line;
      const col = this.column;

      if (isAlpha(char) || char === '_') {
        tokens.push(this.readIdentifier());
        continue;
      }

      if (isDigit(char)) {
        const tok = this.readNumber(raiseOnError);
        if (tok !== null) {
          tokens.push(tok);
        }
        continue;
      }

      if (char === '.' && this.peek() !== null && isDigit(this.peek()!)) {
        const startPos = this.pos;
        this.advance();
        while (this.current() !== null && isDigit(this.current()!)) {
          this.advance();
        }
        const badLexeme = this.source.slice(startPos, this.pos);
        const err = new LexicalError(
          badLexeme,
          line,
          col,
          `Literal decimal malformado '${badLexeme}' (se requiere dígito antes del punto)`
        );
        this.errors.push(err);
        if (raiseOnError) {
          throw err;
        }
        continue;
      }

      if (char in SINGLE_CHAR_TOKENS) {
        this.advance();
        tokens.push(new Token(SINGLE_CHAR_TOKENS[char], char, line, col));
        continue;
      }

      const err = new LexicalError(char, line, col);
      this.errors.push(err);
      this.advance();
      if (raiseOnError) {
        throw err;
      }
    }

    return tokens;
  }
}
