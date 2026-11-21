"""Definición de tokens y errores léxicos del compilador."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class TokenType(str, Enum):
    """Categorías léxicas soportadas por el compilador (paridad 1:1 con TypeScript)."""

    # Literales e identificadores
    ID = "ID"
    NUM = "NUM"

    # Palabras reservadas de tipos (análisis semántico)
    INT = "INT"
    FLOAT = "FLOAT"

    # Operadores aritméticos y de asignación
    ASSIGN = "ASSIGN"
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"

    # Delimitadores
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    SEMICOLON = "SEMICOLON"

    # Fin de entrada
    EOF = "EOF"


KEYWORDS: Dict[str, TokenType] = {
    "int": TokenType.INT,
    "float": TokenType.FLOAT,
}

SINGLE_CHAR_TOKENS: Dict[str, TokenType] = {
    "=": TokenType.ASSIGN,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ";": TokenType.SEMICOLON,
}

TOKEN_DISPLAY: Dict[TokenType, str] = {
    TokenType.ID: "id",
    TokenType.NUM: "num",
    TokenType.INT: "int",
    TokenType.FLOAT: "float",
    TokenType.ASSIGN: "=",
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.LPAREN: "(",
    TokenType.RPAREN: ")",
    TokenType.LBRACE: "{",
    TokenType.RBRACE: "}",
    TokenType.SEMICOLON: ";",
    TokenType.EOF: "$",
}


@dataclass(frozen=True)
class Token:
    """Representa una unidad léxica inmutable con metadatos de ubicación."""

    type: TokenType
    lexeme: str
    line: int
    column: int

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el token para telemetría JSON."""
        return {
            "type": self.type.value,
            "lexeme": self.lexeme,
            "line": self.line,
            "column": self.column,
        }

    def __repr__(self) -> str:
        return f"Token({self.type.value}, {self.lexeme!r}, L{self.line}:C{self.column})"


class LexicalError(Exception):
    """Excepción estructurada para caracteres inválidos o comentarios sin cerrar."""

    def __init__(self, char: str, line: int, column: int, detail: str = "") -> None:
        self.char = char
        self.line = line
        self.column = column
        self.detail = detail or f"Símbolo no reconocido '{char}'"
        self.message = f"Error léxico en línea {line}, columna {column}: {self.detail}."
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": "LEXING",
            "char": self.char,
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }