/**
 * Tabla de símbolos jerárquica con ámbitos, verificación/inferencia de tipos y advertencias
 * (Port 1:1 de parser_code_gen/symbol_table.py).
 */

export class SemanticError extends Error {
  public override readonly message: string;

  constructor(
    rawMessage: string,
    public readonly line: number,
    public readonly column: number
  ) {
    const formatted = `Error semántico en línea ${line}, columna ${column}: ${rawMessage}`;
    super(formatted);
    this.name = 'SemanticError';
    this.message = formatted;
  }

  toDict(): Record<string, unknown> {
    return {
      phase: 'SEMANTIC',
      line: this.line,
      column: this.column,
      message: this.message,
    };
  }
}

export interface SemanticWarningDto {
  readonly message: string;
  readonly line: number;
  readonly column: number;
}

export class SemanticWarning implements SemanticWarningDto {
  constructor(
    public readonly message: string,
    public readonly line: number,
    public readonly column: number
  ) {}

  toDict(): SemanticWarningDto {
    return {
      line: this.line,
      column: this.column,
      message: this.message,
    };
  }

  toString(): string {
    return `Advertencia semántica (L${this.line}:C${this.column}): ${this.message}`;
  }
}

export interface SymbolEntryDto {
  name: string;
  data_type: string;
  scope_level: number;
  scope_id: string;
  declared: boolean;
  initialized: boolean;
  line: number;
  column: number;
  last_place: string | null;
}

export class SymbolEntry implements SymbolEntryDto {
  constructor(
    public name: string,
    public data_type: string,
    public scope_level: number,
    public scope_id: string,
    public declared: boolean,
    public initialized: boolean,
    public line: number,
    public column: number,
    public last_place: string | null = null
  ) {}

  toDict(): SymbolEntryDto {
    return {
      name: this.name,
      data_type: this.data_type,
      scope_level: this.scope_level,
      scope_id: this.scope_id,
      declared: this.declared,
      initialized: this.initialized,
      line: this.line,
      column: this.column,
      last_place: this.last_place,
    };
  }
}

export class SymbolTable {
  private scopeStack: Array<{ id: string; table: Map<string, SymbolEntry> }> = [
    { id: 'global', table: new Map<string, SymbolEntry>() },
  ];
  private allEntries: SymbolEntry[] = [];
  private blockCounter = 0;
  public readonly warnings: SemanticWarning[] = [];
  private warnedKeys = new Set<string>();

  constructor(public readonly strictMode: boolean = false) {}

  get currentScopeLevel(): number {
    return this.scopeStack.length - 1;
  }

  get currentScopeId(): string {
    return this.scopeStack[this.scopeStack.length - 1].id;
  }

  enterScope(): string {
    this.blockCounter += 1;
    const scopeId = `block_${this.blockCounter}`;
    this.scopeStack.push({ id: scopeId, table: new Map<string, SymbolEntry>() });
    return scopeId;
  }

  exitScope(): string {
    if (this.scopeStack.length <= 1) {
      return 'global';
    }
    const popped = this.scopeStack.pop()!;
    return popped.id;
  }

  private addWarningOnce(
    category: string,
    symbolName: string,
    message: string,
    line: number,
    col: number
  ): void {
    const key = `${category}::${this.currentScopeId}::${symbolName}`;
    if (!this.warnedKeys.has(key)) {
      this.warnedKeys.add(key);
      this.warnings.push(new SemanticWarning(message, line, col));
    }
  }

  lookup(name: string): SymbolEntry | null {
    for (let i = this.scopeStack.length - 1; i >= 0; i--) {
      const table = this.scopeStack[i].table;
      const found = table.get(name);
      if (found !== undefined) {
        return found;
      }
    }
    return null;
  }

  declare(name: string, dataType: string, line: number, column: number): SymbolEntry {
    const top = this.scopeStack[this.scopeStack.length - 1];
    if (top.table.has(name)) {
      throw new SemanticError(
        `La variable '${name}' ya fue declarada en el ámbito '${top.id}'.`,
        line,
        column
      );
    }
    const entry = new SymbolEntry(
      name,
      dataType,
      this.currentScopeLevel,
      top.id,
      true,
      false,
      line,
      column,
      null
    );
    top.table.set(name, entry);
    this.allEntries.push(entry);
    return entry;
  }

  recordUse(name: string, line: number, column: number): SymbolEntry {
    let entry = this.lookup(name);
    if (entry === null) {
      if (this.strictMode) {
        throw new SemanticError(
          `La variable '${name}' se utiliza sin haber sido declarada previamente.`,
          line,
          column
        );
      }
      const top = this.scopeStack[this.scopeStack.length - 1];
      entry = new SymbolEntry(
        name,
        'inferred',
        this.currentScopeLevel,
        top.id,
        false,
        false,
        line,
        column,
        null
      );
      top.table.set(name, entry);
      this.allEntries.push(entry);
      this.addWarningOnce(
        'undeclared_read',
        name,
        `Variable '${name}' utilizada sin declaración ni inicialización previa (registrada como 'inferred').`,
        line,
        column
      );
      return entry;
    }

    if (!entry.initialized) {
      this.addWarningOnce(
        'uninitialized_read',
        name,
        `Variable '${name}' leída antes de recibir una asignación previa.`,
        line,
        column
      );
    }
    return entry;
  }

  recordAssignment(
    name: string,
    exprType: string,
    place: string,
    line: number,
    column: number
  ): SymbolEntry {
    let entry = this.lookup(name);
    if (entry === null) {
      if (this.strictMode) {
        throw new SemanticError(
          `No se puede asignar a '${name}' porque no ha sido declarada.`,
          line,
          column
        );
      }
      const top = this.scopeStack[this.scopeStack.length - 1];
      const inferredType =
        exprType === 'int' || exprType === 'float' ? exprType : 'inferred';
      entry = new SymbolEntry(
        name,
        inferredType,
        this.currentScopeLevel,
        top.id,
        false,
        true,
        line,
        column,
        place
      );
      top.table.set(name, entry);
      this.allEntries.push(entry);
      this.addWarningOnce(
        'undeclared_assign',
        name,
        `Variable '${name}' asignada sin declaración explícita (tipo inferido: '${inferredType}').`,
        line,
        column
      );
      return entry;
    }

    if (entry.data_type === 'int' && exprType === 'float') {
      if (this.strictMode) {
        throw new SemanticError(
          `Incompatibilidad de tipos: no se puede asignar 'float' a '${name}' de tipo 'int'.`,
          line,
          column
        );
      }
      this.addWarningOnce(
        'narrowing',
        name,
        `Posible pérdida de precisión al asignar expresión 'float' a variable 'int' ('${name}').`,
        line,
        column
      );
    } else if (
      entry.data_type === 'inferred' &&
      (exprType === 'int' || exprType === 'float')
    ) {
      entry.data_type = exprType;
    }

    entry.initialized = true;
    entry.last_place = place;
    return entry;
  }

  static resolveBinaryType(leftType: string, rightType: string, op: string): string {
    if (op === '/') {
      return 'float';
    }
    if (leftType === 'float' || rightType === 'float') {
      return 'float';
    }
    if (leftType === 'int' && rightType === 'int') {
      return 'int';
    }
    return 'inferred';
  }

  entries(): SymbolEntry[] {
    return this.allEntries.map(
      (e) =>
        new SymbolEntry(
          e.name,
          e.data_type,
          e.scope_level,
          e.scope_id,
          e.declared,
          e.initialized,
          e.line,
          e.column,
          e.last_place
        )
    );
  }

  snapshot(): SymbolEntryDto[] {
    return this.allEntries.map((entry) => entry.toDict());
  }
}
