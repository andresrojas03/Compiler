/**
 * Sistema de telemetría paso a paso (TraceStep) exportable a JSON
 * (Port 1:1 de parser_code_gen/tracer.py).
 */

import { SymbolEntryDto } from './symbol-table';
import { Token, TokenDto } from './tokens';

export interface AttributeFrameDto {
  readonly non_terminal: string;
  readonly production: string | null;
  readonly inh: string | null;
  readonly place: string | null;
}

export class AttributeFrame implements AttributeFrameDto {
  constructor(
    public readonly non_terminal: string,
    public readonly production: string | null = null,
    public readonly inh: string | null = null,
    public readonly place: string | null = null
  ) {}

  toDict(): AttributeFrameDto {
    return {
      non_terminal: this.non_terminal,
      production: this.production,
      inh: this.inh,
      place: this.place,
    };
  }
}

export interface TraceStepDto {
  readonly step_id: number;
  readonly phase: string;
  readonly action: string;
  readonly token_index: number;
  readonly current_token: TokenDto | null;
  readonly ll_stack: string[];
  readonly call_frames: AttributeFrameDto[];
  readonly production: string | null;
  readonly emitted_tac: string | null;
  readonly tac_buffer_snapshot: string[];
  readonly symbol_table_snapshot: SymbolEntryDto[];
  readonly message: string;
}

export class TraceStep implements TraceStepDto {
  constructor(
    public readonly step_id: number,
    public readonly phase: string,
    public readonly action: string,
    public readonly token_index: number,
    public readonly current_token: TokenDto | null,
    public readonly ll_stack: string[],
    public readonly call_frames: AttributeFrameDto[],
    public readonly production: string | null,
    public readonly emitted_tac: string | null,
    public readonly tac_buffer_snapshot: string[],
    public readonly symbol_table_snapshot: SymbolEntryDto[],
    public readonly message: string
  ) {}

  toDict(): TraceStepDto {
    return {
      step_id: this.step_id,
      phase: this.phase,
      action: this.action,
      token_index: this.token_index,
      current_token: this.current_token,
      ll_stack: [...this.ll_stack],
      call_frames: [...this.call_frames],
      production: this.production,
      emitted_tac: this.emitted_tac,
      tac_buffer_snapshot: [...this.tac_buffer_snapshot],
      symbol_table_snapshot: [...this.symbol_table_snapshot],
      message: this.message,
    };
  }
}

export class CompilerTracer {
  public readonly steps: TraceStep[] = [];
  private llStack: string[] = [];
  private callFrames: AttributeFrame[] = [];

  initLlStack(startSymbol: string): void {
    this.llStack = ['$', startSymbol];
    this.callFrames = [];
  }

  expandLl(nonTerminal: string, rhs: string[]): void {
    if (
      this.llStack.length > 0 &&
      this.llStack[this.llStack.length - 1] === nonTerminal
    ) {
      this.llStack.pop();
    }
    for (let i = rhs.length - 1; i >= 0; i--) {
      if (rhs[i] !== 'ε') {
        this.llStack.push(rhs[i]);
      }
    }
  }

  matchLl(terminalSymbol: string): void {
    if (
      this.llStack.length > 0 &&
      this.llStack[this.llStack.length - 1] === terminalSymbol
    ) {
      this.llStack.pop();
    }
  }

  pushFrame(
    nonTerminal: string,
    production: string | null = null,
    inh: string | null = null,
    place: string | null = null
  ): void {
    this.callFrames.push(new AttributeFrame(nonTerminal, production, inh, place));
  }

  updateTopFrame(opts: {
    production?: string | null;
    inh?: string | null;
    place?: string | null;
  }): void {
    if (this.callFrames.length === 0) {
      return;
    }
    const top = this.callFrames[this.callFrames.length - 1];
    this.callFrames[this.callFrames.length - 1] = new AttributeFrame(
      top.non_terminal,
      opts.production !== undefined ? opts.production : top.production,
      opts.inh !== undefined ? opts.inh : top.inh,
      opts.place !== undefined ? opts.place : top.place
    );
  }

  popFrame(): AttributeFrame | null {
    return this.callFrames.pop() ?? null;
  }

  record(params: {
    phase: string;
    action: string;
    tokenIndex: number;
    currentToken: Token | null;
    tacBuffer: string[];
    symbolTableSnapshot: SymbolEntryDto[];
    message: string;
    production?: string | null;
    emittedTac?: string | null;
  }): TraceStep {
    const step = new TraceStep(
      this.steps.length + 1,
      params.phase,
      params.action,
      params.tokenIndex,
      params.currentToken ? params.currentToken.toDict() : null,
      [...this.llStack],
      this.callFrames.map((f) => f.toDict()),
      params.production ?? null,
      params.emittedTac ?? null,
      [...params.tacBuffer],
      params.symbolTableSnapshot.map((s) => ({ ...s })),
      params.message
    );
    this.steps.push(step);
    return step;
  }

  exportJson(indent: number = 2): string {
    return JSON.stringify(
      this.steps.map((s) => s.toDict()),
      null,
      indent
    );
  }
}
