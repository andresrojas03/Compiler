"""Analizador léxico sin efectos secundarios para el compilador."""

from typing import List, Optional

from .tokens import KEYWORDS, SINGLE_CHAR_TOKENS, LexicalError, Token, TokenType


class Lexer:
    """Convierte código fuente en una secuencia de tokens validando errores léxicos."""

    def __init__(self, source: str) -> None:
        self.source: str = source
        self.pos: int = 0
        self.line: int = 1
        self.column: int = 1
        self.errors: List[LexicalError] = []

    def _current(self) -> Optional[str]:
        return self.source[self.pos] if self.pos < len(self.source) else None

    def _peek(self) -> Optional[str]:
        idx = self.pos + 1
        return self.source[idx] if idx < len(self.source) else None

    def _advance(self) -> Optional[str]:
        char = self._current()
        if char is None:
            return None
        self.pos += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _skip_ignorable(self, raise_on_error: bool = False) -> None:
        """Omite espacios en blanco, saltos de línea y comentarios (// y /* ... */)."""
        while True:
            char = self._current()
            if char is None:
                return

            if char in " \t\r\n":
                self._advance()
                continue

            # Comentario de línea: // ...
            if char == "/" and self._peek() == "/":
                while self._current() is not None and self._current() != "\n":
                    self._advance()
                continue

            # Comentario de bloque: /* ... */
            if char == "/" and self._peek() == "*":
                start_line, start_col = self.line, self.column
                self._advance()
                self._advance()
                closed = False
                while self._current() is not None:
                    if self._current() == "*" and self._peek() == "/":
                        self._advance()
                        self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    err = LexicalError(
                        "/*",
                        start_line,
                        start_col,
                        "Comentario de bloque '/*' sin cierre '*/'",
                    )
                    self.errors.append(err)
                    if raise_on_error:
                        raise err
                    return
                continue

            return

    def _read_identifier(self) -> Token:
        start_line, start_col = self.line, self.column
        start_pos = self.pos
        while self._current() is not None and (
            self._current().isalnum() or self._current() == "_"
        ):
            self._advance()
        lexeme = self.source[start_pos : self.pos]
        token_type = KEYWORDS.get(lexeme, TokenType.ID)
        return Token(token_type, lexeme, start_line, start_col)

    def _read_number(self, raise_on_error: bool = False) -> Optional[Token]:
        start_line, start_col = self.line, self.column
        start_pos = self.pos
        while self._current() is not None and self._current().isdigit():
            self._advance()
        if self._current() == ".":
            if self._peek() is not None and self._peek().isdigit():
                self._advance()
                while self._current() is not None and self._current().isdigit():
                    self._advance()
            else:
                self._advance()
                bad_lexeme = self.source[start_pos : self.pos]
                err = LexicalError(
                    bad_lexeme,
                    start_line,
                    start_col,
                    f"Literal decimal malformado '{bad_lexeme}' (se esperaban dígitos después del punto)",
                )
                self.errors.append(err)
                if raise_on_error:
                    raise err
                return None
        lexeme = self.source[start_pos : self.pos]
        return Token(TokenType.NUM, lexeme, start_line, start_col)

    def tokenize(self, raise_on_error: bool = False) -> List[Token]:
        """Escanea el código fuente completo y retorna los tokens terminados en EOF."""
        tokens: List[Token] = []
        self.errors.clear()

        while True:
            self._skip_ignorable(raise_on_error=raise_on_error)
            char = self._current()

            if char is None:
                tokens.append(Token(TokenType.EOF, "$", self.line, self.column))
                break

            line, col = self.line, self.column

            if char.isalpha() or char == "_":
                tokens.append(self._read_identifier())
                continue

            if char.isdigit():
                tok = self._read_number(raise_on_error=raise_on_error)
                if tok is not None:
                    tokens.append(tok)
                continue

            if char == "." and self._peek() is not None and self._peek().isdigit():
                start_pos = self.pos
                self._advance()
                while self._current() is not None and self._current().isdigit():
                    self._advance()
                bad_lexeme = self.source[start_pos : self.pos]
                err = LexicalError(
                    bad_lexeme,
                    line,
                    col,
                    f"Literal decimal malformado '{bad_lexeme}' (se requiere dígito antes del punto)",
                )
                self.errors.append(err)
                if raise_on_error:
                    raise err
                continue

            if char in SINGLE_CHAR_TOKENS:
                self._advance()
                tokens.append(Token(SINGLE_CHAR_TOKENS[char], char, line, col))
                continue

            err = LexicalError(char, line, col)
            self.errors.append(err)
            self._advance()
            if raise_on_error:
                raise err

        return tokens
