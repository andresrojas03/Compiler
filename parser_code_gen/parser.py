"""
Parser LL(1) descendente recursivo con Traducción Dirigida por Sintaxis (SDT)
y orquestación completa del compilador.

Gramática LL(1) sin recursión izquierda (todas las sentencias terminan en ';'):
    Program  -> Stmt StmtList
    StmtList -> Stmt StmtList | ε
    Stmt     -> Decl | S | Block
    Decl     -> Type id ;
    Type     -> int | float
    Block    -> { StmtList }
    S        -> id = E ;
    E        -> T E'
    E'       -> + T E' | - T E' | ε
    T        -> F T'
    T'       -> * F T' | / F T' | ε
    F        -> ( E ) | id | num
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lexer.lexer import Lexer
from lexer.tokens import TOKEN_DISPLAY, Token, TokenType

from .code_generator import CodeGenerator, TACInstruction
from .symbol_table import SemanticError, SemanticWarning, SymbolEntry, SymbolTable
from .tracer import CompilerTracer, TraceStep


class ParserSyntaxError(Exception):
    """Error sintáctico estructurado con ubicación y conjunto de tokens esperados."""

    def __init__(
        self,
        message: str,
        token: Token,
        expected: Optional[List[str]] = None,
    ) -> None:
        self.token = token
        self.expected = expected or []
        self.line = token.line
        self.column = token.column
        self.message = f"Error sintáctico en línea {token.line}, columna {token.column}: {message}"
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": "PARSING",
            "line": self.line,
            "column": self.column,
            "token": self.token.to_dict(),
            "expected": list(self.expected),
            "message": self.message,
        }


@dataclass
class CompilerError:
    """Error unificado para cualquier fase del compilador."""

    phase: str
    message: str
    line: int
    column: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


@dataclass
class CompilationResult:
    """Resultado integral de una ejecución del compilador."""

    source: str
    success: bool
    strict_mode: bool
    tokens: List[Token]
    tac_raw: List[TACInstruction] = field(default_factory=list)
    tac_optimized: List[TACInstruction] = field(default_factory=list)
    optimization_notes: List[str] = field(default_factory=list)
    symbol_table: List[SymbolEntry] = field(default_factory=list)
    symbol_table_text: str = ""
    errors: List[CompilerError] = field(default_factory=list)
    warnings: List[SemanticWarning] = field(default_factory=list)
    trace: List[TraceStep] = field(default_factory=list)
    tracer: Optional[CompilerTracer] = None

    @property
    def raw_lines(self) -> List[str]:
        return [instr.text for instr in self.tac_raw]

    @property
    def optimized_lines(self) -> List[str]:
        return [instr.text for instr in self.tac_optimized]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "success": self.success,
            "mode": "strict" if self.strict_mode else "compatible",
            "tokens": [t.to_dict() for t in self.tokens],
            "tac_raw": [i.to_dict() for i in self.tac_raw],
            "tac_optimized": [i.to_dict() for i in self.tac_optimized],
            "optimization_notes": list(self.optimization_notes),
            "symbol_table": [s.to_dict() for s in self.symbol_table],
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "trace": [step.to_dict() for step in self.trace],
        }


def _is_zero_numeric_literal(place: str) -> bool:
    """Determina si un operando literal equivale numéricamente a cero (0, 00, 0.0, 0.00...)."""
    try:
        return float(place) == 0.0
    except ValueError:
        return False


class LLParserSDT:
    """
    Parser LL(1) predictivo recursivo que ejecuta acciones semánticas
    (.inh como parámetro y .place como retorno) directamente durante el parsing.
    """

    def __init__(
        self,
        tokens: List[Token],
        codegen: CodeGenerator,
        symbol_table: SymbolTable,
        tracer: CompilerTracer,
    ) -> None:
        self.tokens: List[Token] = tokens
        self.pos: int = 0
        self.codegen: CodeGenerator = codegen
        self.symbol_table: SymbolTable = symbol_table
        self.tracer: CompilerTracer = tracer

    @property
    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def _trace(
        self,
        *,
        phase: str,
        action: str,
        message: str,
        production: Optional[str] = None,
        emitted_tac: Optional[str] = None,
    ) -> None:
        self.tracer.record(
            phase=phase,
            action=action,
            token_index=self.pos,
            current_token=self.current,
            tac_buffer=self.codegen.get_staging_lines(),
            symbol_table_snapshot=self.symbol_table.snapshot(),
            message=message,
            production=production,
            emitted_tac=emitted_tac,
        )

    def _match(self, expected_type: TokenType) -> Token:
        tok = self.current
        if tok.type != expected_type:
            expected_lbl = TOKEN_DISPLAY[expected_type]
            found_lbl = (
                "fin de entrada ('$')"
                if tok.type == TokenType.EOF
                else f"'{tok.lexeme}' ({TOKEN_DISPLAY[tok.type]})"
            )
            raise ParserSyntaxError(
                f"Se esperaba '{expected_lbl}', pero se encontró {found_lbl}.",
                tok,
                expected=[expected_lbl],
            )
        symbol = TOKEN_DISPLAY[expected_type]
        self.tracer.match_ll(symbol)
        self._trace(
            phase="PARSING",
            action="MATCH",
            message=f"Emparejado terminal '{symbol}' con lexema '{tok.lexeme}'.",
        )
        self.pos += 1
        return tok

    def _expand(self, non_terminal: str, rhs: List[str], message: str) -> str:
        production = f"{non_terminal} -> {' '.join(rhs)}"
        self.tracer.expand_ll(non_terminal, rhs)
        self.tracer.update_top_frame(production=production)
        self._trace(
            phase="PARSING",
            action="EPSILON" if rhs == ["ε"] else "EXPAND",
            production=production,
            message=message,
        )
        return production

    # =====================================================================
    # Program -> Stmt StmtList
    # =====================================================================
    def parse(self) -> None:
        self.tracer.init_ll_stack("Program")
        self.tracer.push_frame("Program")

        if self.current.type == TokenType.EOF:
            raise ParserSyntaxError(
                "Entrada vacía: se esperaba una sentencia de asignación o declaración.",
                self.current,
                expected=["id", "int", "float", "{"],
            )

        self._expand("Program", ["Stmt", "StmtList"], "Inicio de derivación del programa.")
        self._parse_stmt()
        self._parse_stmt_list()

        if self.current.type != TokenType.EOF:
            raise ParserSyntaxError(
                f"Token inesperado '{self.current.lexeme}' tras finalizar el análisis.",
                self.current,
                expected=["$"],
            )
        self._match(TokenType.EOF)
        self.tracer.pop_frame()

    def _parse_stmt_list(self) -> None:
        self.tracer.push_frame("StmtList")
        if self.current.type in (
            TokenType.ID,
            TokenType.INT,
            TokenType.FLOAT,
            TokenType.LBRACE,
        ):
            self._expand(
                "StmtList",
                ["Stmt", "StmtList"],
                "Se detecta una nueva sentencia en StmtList.",
            )
            self._parse_stmt()
            self._parse_stmt_list()
        elif self.current.type in (TokenType.EOF, TokenType.RBRACE):
            self._expand("StmtList", ["ε"], "Fin de secuencia de sentencias (ε).")
        else:
            raise ParserSyntaxError(
                f"Inicio de sentencia inválido: se encontró '{self.current.lexeme}'.",
                self.current,
                expected=["id", "int", "float", "{", "}", "$"],
            )
        self.tracer.pop_frame()

    def _parse_stmt(self) -> None:
        self.tracer.push_frame("Stmt")
        tok = self.current
        if tok.type in (TokenType.INT, TokenType.FLOAT):
            self._expand("Stmt", ["Decl"], "Derivación hacia declaración de variable.")
            self._parse_decl()
        elif tok.type == TokenType.ID:
            self._expand("Stmt", ["S"], "Derivación hacia sentencia de asignación S.")
            self._parse_s()
        elif tok.type == TokenType.LBRACE:
            self._expand("Stmt", ["Block"], "Derivación hacia bloque con nuevo ámbito.")
            self._parse_block()
        else:
            raise ParserSyntaxError(
                f"Se esperaba una sentencia válida, pero se encontró '{tok.lexeme}'.",
                tok,
                expected=["id", "int", "float", "{"],
            )
        self.tracer.pop_frame()

    def _parse_decl(self) -> None:
        self.tracer.push_frame("Decl")
        self._expand("Decl", ["Type", "id", ";"], "Declaración tipada terminada en ';'.")
        data_type = self._parse_type()
        id_tok = self._match(TokenType.ID)
        self._match(TokenType.SEMICOLON)

        entry = self.symbol_table.declare(
            id_tok.lexeme, data_type, id_tok.line, id_tok.column
        )
        self._trace(
            phase="SEMANTIC",
            action="SYM_DECLARE",
            message=f"Declarada variable '{entry.name}' de tipo '{entry.data_type}' en ámbito '{entry.scope_id}'.",
        )
        self.tracer.pop_frame()

    def _parse_type(self) -> str:
        self.tracer.push_frame("Type")
        if self.current.type == TokenType.INT:
            self._expand("Type", ["int"], "Tipo primitivo int.")
            self._match(TokenType.INT)
            self.tracer.update_top_frame(place="int")
            self.tracer.pop_frame()
            return "int"
        if self.current.type == TokenType.FLOAT:
            self._expand("Type", ["float"], "Tipo primitivo float.")
            self._match(TokenType.FLOAT)
            self.tracer.update_top_frame(place="float")
            self.tracer.pop_frame()
            return "float"
        raise ParserSyntaxError(
            f"Se esperaba un tipo ('int' o 'float'), pero se encontró '{self.current.lexeme}'.",
            self.current,
            expected=["int", "float"],
        )

    def _parse_block(self) -> None:
        self.tracer.push_frame("Block")
        self._expand("Block", ["{", "StmtList", "}"], "Apertura de bloque de ámbito léxico.")
        self._match(TokenType.LBRACE)
        scope_id = self.symbol_table.enter_scope()
        self._trace(
            phase="SEMANTIC",
            action="SYM_DECLARE",
            message=f"Entrada al ámbito léxico '{scope_id}'.",
        )
        self._parse_stmt_list()
        self._match(TokenType.RBRACE)
        closed_scope = self.symbol_table.exit_scope()
        self._trace(
            phase="SEMANTIC",
            action="SYM_USE",
            message=f"Salida del ámbito léxico '{closed_scope}'.",
        )
        self.tracer.pop_frame()

    # =====================================================================
    # S -> id = E ;   { emit(id.name + " = " + E.place) }
    # =====================================================================
    def _parse_s(self) -> None:
        self.tracer.push_frame("S")
        self._expand("S", ["id", "=", "E", ";"], "Sentencia de asignación obligatoria con ';'.")

        target_tok = self._match(TokenType.ID)
        self._match(TokenType.ASSIGN)

        e_place, e_type = self._parse_e()
        self._match(TokenType.SEMICOLON)

        self.symbol_table.record_assignment(
            name=target_tok.lexeme,
            expr_type=e_type,
            place=e_place,
            line=target_tok.line,
            column=target_tok.column,
        )
        instr = self.codegen.emit(f"{target_tok.lexeme} = {e_place}")
        self.tracer.update_top_frame(place=target_tok.lexeme)
        self._trace(
            phase="CODEGEN",
            action="EMIT",
            emitted_tac=instr.text,
            message=f"Acción semántica de S: emit('{instr.text}').",
        )
        self.tracer.pop_frame()

    # =====================================================================
    # Regla 1: E -> T E'  { E'.inh = T.place; E.place = E'.place }
    # =====================================================================
    def _parse_e(self) -> Tuple[str, str]:
        self.tracer.push_frame("E")
        if self.current.type not in (TokenType.LPAREN, TokenType.ID, TokenType.NUM):
            raise ParserSyntaxError(
                f"Inicio de expresión inválido: se encontró '{self.current.lexeme}'.",
                self.current,
                expected=["(", "id", "num"],
            )

        self._expand("E", ["T", "E'"], "Regla 1: expansión de expresión E -> T E'.")
        t_place, t_type = self._parse_t()

        self._trace(
            phase="SEMANTIC",
            action="ATTR_PASS",
            message=f"Paso de atributo heredado: E'.inh = T.place ('{t_place}').",
        )
        e_place, e_type = self._parse_e_prime(t_place, t_type)

        self.tracer.update_top_frame(place=e_place)
        self._trace(
            phase="SEMANTIC",
            action="ATTR_RETURN",
            message=f"Síntesis de atributo: E.place = E'.place ('{e_place}').",
        )
        self.tracer.pop_frame()
        return e_place, e_type

    # =====================================================================
    # Regla 2: E' -> + T E'1 | - T E'1
    # Regla 3: E' -> ε { E'.place = E'.inh }
    # =====================================================================
    def _parse_e_prime(self, inh: str, inh_type: str) -> Tuple[str, str]:
        self.tracer.push_frame("E'", inh=inh)

        if self.current.type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self.current
            op_str = op_tok.lexeme
            self._expand(
                "E'",
                [op_str, "T", "E'"],
                f"Regla 2: expansión E' -> {op_str} T E' con E'.inh = '{inh}'.",
            )
            self._match(op_tok.type)
            t_place, t_type = self._parse_t()

            temp = self.codegen.new_temp()
            instr = self.codegen.emit(f"{temp} = {inh} {op_str} {t_place}")
            result_type = self.symbol_table.resolve_binary_type(inh_type, t_type, op_str)
            self._trace(
                phase="CODEGEN",
                action="EMIT",
                emitted_tac=instr.text,
                message=f"Acción semántica E': t = newTemp() -> '{temp}'; emit('{instr.text}').",
            )
            self._trace(
                phase="SEMANTIC",
                action="ATTR_PASS",
                message=f"Asociatividad izquierda: E'1.inh = '{temp}'.",
            )
            final_place, final_type = self._parse_e_prime(temp, result_type)
            self.tracer.update_top_frame(place=final_place)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"Síntesis E'.place = E'1.place ('{final_place}').",
            )
            self.tracer.pop_frame()
            return final_place, final_type

        if self.current.type in (TokenType.RPAREN, TokenType.SEMICOLON):
            self._expand("E'", ["ε"], f"Regla 3: E' -> ε; E'.place = E'.inh ('{inh}').")
            self.tracer.update_top_frame(place=inh)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"Retorno caso base E': E'.place = '{inh}'.",
            )
            self.tracer.pop_frame()
            return inh, inh_type

        if self.current.type == TokenType.EOF:
            raise ParserSyntaxError(
                "Fin de entrada inesperado: falta ';' o ')' para cerrar la expresión.",
                self.current,
                expected=["+", "-", ")", ";"],
            )
        raise ParserSyntaxError(
            f"Token inesperado '{self.current.lexeme}' después de término en E'. "
            "Se esperaba uno de: ['+', '-', ')', ';'].",
            self.current,
            expected=["+", "-", ")", ";"],
        )

    # =====================================================================
    # Regla 4: T -> F T'  { T'.inh = F.place; T.place = T'.place }
    # =====================================================================
    def _parse_t(self) -> Tuple[str, str]:
        self.tracer.push_frame("T")
        if self.current.type not in (TokenType.LPAREN, TokenType.ID, TokenType.NUM):
            raise ParserSyntaxError(
                f"Se esperaba un factor ('(', 'id' o 'num'), pero se encontró '{self.current.lexeme}'.",
                self.current,
                expected=["(", "id", "num"],
            )

        self._expand("T", ["F", "T'"], "Regla 4: expansión de término T -> F T'.")
        f_place, f_type = self._parse_f()

        self._trace(
            phase="SEMANTIC",
            action="ATTR_PASS",
            message=f"Paso de atributo heredado: T'.inh = F.place ('{f_place}').",
        )
        t_place, t_type = self._parse_t_prime(f_place, f_type)

        self.tracer.update_top_frame(place=t_place)
        self._trace(
            phase="SEMANTIC",
            action="ATTR_RETURN",
            message=f"Síntesis de atributo: T.place = T'.place ('{t_place}').",
        )
        self.tracer.pop_frame()
        return t_place, t_type

    # =====================================================================
    # Regla 5: T' -> * F T'1 | / F T'1
    # Regla 6: T' -> ε { T'.place = T'.inh }
    # =====================================================================
    def _parse_t_prime(self, inh: str, inh_type: str) -> Tuple[str, str]:
        self.tracer.push_frame("T'", inh=inh)

        if self.current.type in (TokenType.STAR, TokenType.SLASH):
            op_tok = self.current
            op_str = op_tok.lexeme
            self._expand(
                "T'",
                [op_str, "F", "T'"],
                f"Regla 5: expansión T' -> {op_str} F T' con T'.inh = '{inh}'.",
            )
            self._match(op_tok.type)
            f_place, f_type = self._parse_f()

            if op_str == "/" and _is_zero_numeric_literal(f_place):
                raise SemanticError(
                    "División explícita entre constante cero.",
                    op_tok.line,
                    op_tok.column,
                )

            temp = self.codegen.new_temp()
            instr = self.codegen.emit(f"{temp} = {inh} {op_str} {f_place}")
            result_type = self.symbol_table.resolve_binary_type(inh_type, f_type, op_str)
            self._trace(
                phase="CODEGEN",
                action="EMIT",
                emitted_tac=instr.text,
                message=f"Acción semántica T': t = newTemp() -> '{temp}'; emit('{instr.text}').",
            )
            self._trace(
                phase="SEMANTIC",
                action="ATTR_PASS",
                message=f"Asociatividad izquierda: T'1.inh = '{temp}'.",
            )
            final_place, final_type = self._parse_t_prime(temp, result_type)
            self.tracer.update_top_frame(place=final_place)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"Síntesis T'.place = T'1.place ('{final_place}').",
            )
            self.tracer.pop_frame()
            return final_place, final_type

        if self.current.type in (
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.RPAREN,
            TokenType.SEMICOLON,
        ):
            self._expand("T'", ["ε"], f"Regla 6: T' -> ε; T'.place = T'.inh ('{inh}').")
            self.tracer.update_top_frame(place=inh)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"Retorno caso base T': T'.place = '{inh}'.",
            )
            self.tracer.pop_frame()
            return inh, inh_type

        if self.current.type == TokenType.EOF:
            raise ParserSyntaxError(
                "Fin de entrada inesperado: falta ';' o ')' para cerrar la expresión.",
                self.current,
                expected=["*", "/", "+", "-", ")", ";"],
            )
        raise ParserSyntaxError(
            f"Token inesperado '{self.current.lexeme}' después de factor en T'. "
            "Se esperaba uno de: ['*', '/', '+', '-', ')', ';'].",
            self.current,
            expected=["*", "/", "+", "-", ")", ";"],
        )

    # =====================================================================
    # Regla 7: F -> id | num
    # Regla 8: F -> ( E )
    # =====================================================================
    def _parse_f(self) -> Tuple[str, str]:
        self.tracer.push_frame("F")
        tok = self.current

        if tok.type == TokenType.ID:
            self._expand("F", ["id"], f"Regla 7: identificador F -> id ('{tok.lexeme}').")
            id_tok = self._match(TokenType.ID)
            entry = self.symbol_table.record_use(id_tok.lexeme, id_tok.line, id_tok.column)
            self.tracer.update_top_frame(place=id_tok.lexeme)
            self._trace(
                phase="SEMANTIC",
                action="SYM_USE",
                message=f"F.place = id.name ('{id_tok.lexeme}', tipo='{entry.data_type}').",
            )
            self.tracer.pop_frame()
            return id_tok.lexeme, entry.data_type

        if tok.type == TokenType.NUM:
            self._expand("F", ["num"], f"Regla 7b: literal numérico F -> num ('{tok.lexeme}').")
            num_tok = self._match(TokenType.NUM)
            num_type = "float" if "." in num_tok.lexeme else "int"
            self.tracer.update_top_frame(place=num_tok.lexeme)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"F.place = num.lexeme ('{num_tok.lexeme}', tipo='{num_type}').",
            )
            self.tracer.pop_frame()
            return num_tok.lexeme, num_type

        if tok.type == TokenType.LPAREN:
            self._expand("F", ["(", "E", ")"], "Regla 8: subexpresión entre paréntesis F -> ( E ).")
            self._match(TokenType.LPAREN)
            e_place, e_type = self._parse_e()
            self._match(TokenType.RPAREN)
            self.tracer.update_top_frame(place=e_place)
            self._trace(
                phase="SEMANTIC",
                action="ATTR_RETURN",
                message=f"F.place = E.place ('{e_place}').",
            )
            self.tracer.pop_frame()
            return e_place, e_type

        raise ParserSyntaxError(
            f"Factor inválido: se esperaba '(', 'id' o 'num', pero se encontró '{tok.lexeme}'.",
            tok,
            expected=["(", "id", "num"],
        )


def compile_source(source: str, strict_mode: bool = False) -> CompilationResult:
    """Orquestador transaccional: Lexer -> Parser LL(1) SDT -> Optimizador."""
    lexer = Lexer(source)
    tokens = lexer.tokenize(raise_on_error=False)
    tracer = CompilerTracer()
    symbol_table = SymbolTable(strict_mode=strict_mode)
    codegen = CodeGenerator()

    if lexer.errors:
        errors = [
            CompilerError(
                phase="LEXING",
                message=err.message,
                line=err.line,
                column=err.column,
            )
            for err in lexer.errors
        ]
        tracer.record(
            phase="ERROR",
            action="ERROR",
            token_index=0,
            current_token=tokens[0] if tokens else None,
            tac_buffer=[],
            symbol_table_snapshot=[],
            message="; ".join(e.message for e in errors),
        )
        return CompilationResult(
            source=source,
            success=False,
            strict_mode=strict_mode,
            tokens=tokens,
            tac_raw=[],
            tac_optimized=[],
            symbol_table=[],
            symbol_table_text=symbol_table.format_table(),
            errors=errors,
            warnings=[],
            trace=list(tracer.steps),
            tracer=tracer,
        )

    parser = LLParserSDT(tokens, codegen, symbol_table, tracer)
    try:
        parser.parse()
    except (ParserSyntaxError, SemanticError) as exc:
        discarded = codegen.rollback()
        phase = "PARSING" if isinstance(exc, ParserSyntaxError) else "SEMANTIC"
        tracer.record(
            phase="ROLLBACK",
            action="ROLLBACK",
            token_index=parser.pos,
            current_token=parser.current,
            tac_buffer=[],
            symbol_table_snapshot=symbol_table.snapshot(),
            message=(
                f"Rollback ejecutado ({len(discarded)} instrucción(es) descartada(s)). "
                f"Causa: {exc.message}"
            ),
        )
        return CompilationResult(
            source=source,
            success=False,
            strict_mode=strict_mode,
            tokens=tokens,
            tac_raw=[],
            tac_optimized=[],
            symbol_table=symbol_table.entries(),
            symbol_table_text=symbol_table.format_table(),
            errors=[
                CompilerError(
                    phase=phase,
                    message=exc.message,
                    line=exc.line,
                    column=exc.column,
                )
            ],
            warnings=list(symbol_table.warnings),
            trace=list(tracer.steps),
            tracer=tracer,
        )

    tac_raw = codegen.commit()
    tac_optimized, opt_notes = CodeGenerator.optimize(tac_raw)

    for note in opt_notes:
        tracer.record(
            phase="OPTIMIZATION",
            action="OPT_PROPAGATE" if "Propagación" in note or "temporal" in note else "OPT_FOLD",
            token_index=len(tokens) - 1,
            current_token=tokens[-1] if tokens else None,
            tac_buffer=[i.text for i in tac_optimized],
            symbol_table_snapshot=symbol_table.snapshot(),
            message=note,
        )

    return CompilationResult(
        source=source,
        success=True,
        strict_mode=strict_mode,
        tokens=tokens,
        tac_raw=tac_raw,
        tac_optimized=tac_optimized,
        optimization_notes=opt_notes,
        symbol_table=symbol_table.entries(),
        symbol_table_text=symbol_table.format_table(),
        errors=[],
        warnings=list(symbol_table.warnings),
        trace=list(tracer.steps),
        tracer=tracer,
    )
