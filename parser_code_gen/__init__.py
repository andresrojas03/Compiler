"""Paquete de análisis sintáctico LL(1), semántica, TAC y telemetría."""

from .code_generator import CodeGenerator, TACInstruction
from .parser import (
    CompilationResult,
    CompilerError,
    LLParserSDT,
    ParserSyntaxError,
    compile_source,
)
from .symbol_table import SemanticError, SemanticWarning, SymbolEntry, SymbolTable
from .tracer import AttributeFrame, CompilerTracer, TraceStep

__all__ = [
    "AttributeFrame",
    "CodeGenerator",
    "CompilationResult",
    "CompilerError",
    "CompilerTracer",
    "LLParserSDT",
    "ParserSyntaxError",
    "SemanticError",
    "SemanticWarning",
    "SymbolEntry",
    "SymbolTable",
    "TACInstruction",
    "TraceStep",
    "compile_source",
]