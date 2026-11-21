/**
 * Generador transaccional de Código de Tres Direcciones (TAC) y optimizador
 * (Port 1:1 de parser_code_gen/code_generator.py).
 */

const TEMP_PATTERN = /^t\d+$/;
const BINARY_INSTR_PATTERN =
  /^\s*(?<result>[A-Za-z_]\w*)\s*=\s*(?<arg1>[^\s]+)\s*(?<op>[+\-*/])\s*(?<arg2>[^\s]+)\s*$/;
const COPY_INSTR_PATTERN =
  /^\s*(?<result>[A-Za-z_]\w*)\s*=\s*(?<arg1>[^\s]+)\s*$/;

export interface TACInstructionDto {
  readonly index: number;
  readonly op: string;
  readonly arg1: string;
  readonly arg2: string | null;
  readonly result: string;
  readonly text: string;
}

export class TACInstruction implements TACInstructionDto {
  constructor(
    public readonly index: number,
    public readonly op: string,
    public readonly arg1: string,
    public readonly arg2: string | null,
    public readonly result: string,
    public readonly text: string
  ) {}

  toDict(): TACInstructionDto {
    return {
      index: this.index,
      op: this.op,
      arg1: this.arg1,
      arg2: this.arg2,
      result: this.result,
      text: this.text,
    };
  }
}

function parseNumber(token: string): number | null {
  if (!/^[+-]?(\d+(\.\d+)?|\.\d+)$/.test(token)) {
    return null;
  }
  const n = Number(token);
  return Number.isFinite(n) ? n : null;
}

function formatNumber(value: number, bothInts: boolean = false): string {
  if (bothInts && Number.isInteger(value)) {
    return String(Math.trunc(value));
  }
  if (Number.isInteger(value)) {
    return String(Math.trunc(value));
  }
  return Number(value.toPrecision(6)).toString();
}

function isTemp(name: string): boolean {
  return TEMP_PATTERN.test(name);
}

export class CodeGenerator {
  private tempCounter = 0;
  private stagingBuffer: TACInstruction[] = [];
  private committedCode: TACInstruction[] = [];
  public rolledBack = false;

  new_temp(): string {
    this.tempCounter += 1;
    return `t${this.tempCounter}`;
  }

  newTemp(): string {
    return this.new_temp();
  }

  emit(instruction: string): TACInstruction {
    const text = instruction.trim();
    const index = this.stagingBuffer.length + 1;

    const binMatch = text.match(BINARY_INSTR_PATTERN);
    let instr: TACInstruction;

    if (binMatch && binMatch.groups) {
      const { result, arg1, op, arg2 } = binMatch.groups;
      instr = new TACInstruction(
        index,
        op,
        arg1,
        arg2,
        result,
        `${result} = ${arg1} ${op} ${arg2}`
      );
    } else {
      const copyMatch = text.match(COPY_INSTR_PATTERN);
      if (!copyMatch || !copyMatch.groups) {
        throw new Error(`Formato de instrucción TAC no reconocido: '${instruction}'`);
      }
      const { result, arg1 } = copyMatch.groups;
      instr = new TACInstruction(
        index,
        '=',
        arg1,
        null,
        result,
        `${result} = ${arg1}`
      );
    }

    this.stagingBuffer.push(instr);
    return instr;
  }

  commit(): TACInstruction[] {
    this.rolledBack = false;
    this.committedCode = [...this.stagingBuffer];
    return [...this.committedCode];
  }

  rollback(): TACInstruction[] {
    const discarded = [...this.stagingBuffer];
    this.stagingBuffer = [];
    this.committedCode = [];
    this.rolledBack = true;
    return discarded;
  }

  getStagingLines(): string[] {
    return this.stagingBuffer.map((instr) => instr.text);
  }

  getCommittedCode(): TACInstruction[] {
    return [...this.committedCode];
  }

  static optimize(
    rawInstructions: TACInstruction[]
  ): { instructions: TACInstruction[]; notes: string[] } {
    if (rawInstructions.length === 0) {
      return { instructions: [], notes: [] };
    }

    let working: TACInstruction[] = [...rawInstructions];
    const notes: string[] = [];

    for (let pass = 0; pass < 10; pass++) {
      let changed = false;

      // --- Paso 1: Plegado de constantes y simplificación algebraica ---
      const folded: TACInstruction[] = [];
      for (const instr of working) {
        if (instr.op === '=' || instr.arg2 === null) {
          folded.push(instr);
          continue;
        }

        const n1 = parseNumber(instr.arg1);
        const n2 = parseNumber(instr.arg2);
        const bothInts =
          n1 !== null &&
          n2 !== null &&
          !instr.arg1.includes('.') &&
          !instr.arg2.includes('.');

        // 1a. Plegado de constantes
        if (n1 !== null && n2 !== null) {
          let val: string | null = null;
          if (instr.op === '+') {
            val = formatNumber(n1 + n2, bothInts);
          } else if (instr.op === '-') {
            val = formatNumber(n1 - n2, bothInts);
          } else if (instr.op === '*') {
            val = formatNumber(n1 * n2, bothInts);
          } else if (instr.op === '/' && n2 !== 0) {
            val = formatNumber(n1 / n2, false);
          }
          if (val !== null) {
            const newInstr = new TACInstruction(
              instr.index,
              '=',
              val,
              null,
              instr.result,
              `${instr.result} = ${val}`
            );
            notes.push(`Plegado de constantes: '${instr.text}' -> '${newInstr.text}'`);
            folded.push(newInstr);
            changed = true;
            continue;
          }
          folded.push(instr);
          continue;
        }

        // 1b. Simplificación algebraica básica
        let simplifiedRhs: string | null = null;
        if (instr.op === '+') {
          if (n2 === 0) {
            simplifiedRhs = instr.arg1;
          } else if (n1 === 0) {
            simplifiedRhs = instr.arg2;
          }
        } else if (instr.op === '-') {
          if (n2 === 0) {
            simplifiedRhs = instr.arg1;
          } else if (instr.arg1 === instr.arg2) {
            simplifiedRhs = '0';
          }
        } else if (instr.op === '*') {
          if (n2 === 1) {
            simplifiedRhs = instr.arg1;
          } else if (n1 === 1) {
            simplifiedRhs = instr.arg2;
          } else if (n1 === 0 || n2 === 0) {
            simplifiedRhs = '0';
          }
        } else if (instr.op === '/') {
          if (n2 === 1) {
            simplifiedRhs = instr.arg1;
          } else if (n1 === 0) {
            simplifiedRhs = '0';
          }
        }

        if (simplifiedRhs !== null) {
          const newInstr = new TACInstruction(
            instr.index,
            '=',
            simplifiedRhs,
            null,
            instr.result,
            `${instr.result} = ${simplifiedRhs}`
          );
          notes.push(
            `Simplificación algebraica: '${instr.text}' -> '${newInstr.text}'`
          );
          folded.push(newInstr);
          changed = true;
        } else {
          folded.push(instr);
        }
      }

      working = folded;

      // --- Paso 2: Propagación de copias (t = operando) ---
      const copies = new Map<string, string>();
      const propagated: TACInstruction[] = [];
      for (let instr of working) {
        const newArg1 = copies.get(instr.arg1) ?? instr.arg1;
        const newArg2 =
          instr.arg2 !== null ? copies.get(instr.arg2) ?? instr.arg2 : null;

        if (newArg1 !== instr.arg1 || newArg2 !== instr.arg2) {
          changed = true;
          const newText =
            instr.op === '=' || newArg2 === null
              ? `${instr.result} = ${newArg1}`
              : `${instr.result} = ${newArg1} ${instr.op} ${newArg2}`;
          notes.push(`Propagación de copia: '${instr.text}' -> '${newText}'`);
          instr = new TACInstruction(
            instr.index,
            instr.op,
            newArg1,
            newArg2,
            instr.result,
            newText
          );
        }

        for (const [key, val] of Array.from(copies.entries())) {
          if (key === instr.result || val === instr.result) {
            copies.delete(key);
          }
        }

        if (instr.op === '=' && instr.arg2 === null && isTemp(instr.result)) {
          copies.set(instr.result, instr.arg1);
        }

        propagated.push(instr);
      }

      working = propagated;

      // --- Paso 3: Fusión de temporal redundante antes de asignación ---
      const merged: TACInstruction[] = [];
      let i = 0;
      while (i < working.length) {
        const curr = working[i];
        if (
          i + 1 < working.length &&
          isTemp(curr.result) &&
          working[i + 1].op === '=' &&
          working[i + 1].arg1 === curr.result &&
          working[i + 1].arg2 === null
        ) {
          const nxt = working[i + 1];
          const usedLater = working
            .slice(i + 2)
            .some(
              (later) => later.arg1 === curr.result || later.arg2 === curr.result
            );
          if (!usedLater) {
            const newText =
              curr.op === '=' || curr.arg2 === null
                ? `${nxt.result} = ${curr.arg1}`
                : `${nxt.result} = ${curr.arg1} ${curr.op} ${curr.arg2}`;
            const fused = new TACInstruction(
              curr.index,
              curr.op,
              curr.arg1,
              curr.arg2,
              nxt.result,
              newText
            );
            notes.push(
              `Eliminación de temporal redundante: '${curr.text}; ${nxt.text}' -> '${newText}'`
            );
            merged.push(fused);
            changed = true;
            i += 2;
            continue;
          }
        }
        merged.push(curr);
        i += 1;
      }

      working = merged;

      // --- Paso 4: Eliminación de temporales muertos ---
      const liveFiltered: TACInstruction[] = [];
      for (let idx = 0; idx < working.length; idx++) {
        const instr = working[idx];
        if (isTemp(instr.result)) {
          const usedLater = working
            .slice(idx + 1)
            .some(
              (later) => later.arg1 === instr.result || later.arg2 === instr.result
            );
          if (!usedLater) {
            notes.push(`Eliminación de temporal sin uso: '${instr.text}'`);
            changed = true;
            continue;
          }
        }
        liveFiltered.push(instr);
      }

      working = liveFiltered;

      if (!changed) {
        break;
      }
    }

    const reindexed = working.map(
      (instr, idx) =>
        new TACInstruction(
          idx + 1,
          instr.op,
          instr.arg1,
          instr.arg2,
          instr.result,
          instr.text
        )
    );
    return { instructions: reindexed, notes };
  }
}
