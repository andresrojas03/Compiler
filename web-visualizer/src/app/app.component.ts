import { CommonModule } from '@angular/common';
import {
  Component,
  HostListener,
  OnDestroy,
  computed,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  AttributeFrameDto,
  CompilationResult,
  SymbolEntryDto,
  Token,
  TraceStep,
  compileSource,
} from './compiler-engine';
import {
  ONBOARDING_TOUR_STEPS,
  OnboardingTourComponent,
} from './onboarding-tour.component';

export interface PresetCase {
  readonly id: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly category: 'valid' | 'invalid' | 'semantic';
  readonly code: string;
  readonly description: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, OnboardingTourComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent implements OnDestroy {
  readonly presets: PresetCase[] = [
    // 4 Casos Válidos Oficiales del PDF
    {
      id: 'valid-a',
      label: 'Válido (a) — x = a;',
      shortLabel: 'x = a;',
      category: 'valid',
      code: 'x = a;',
      description: 'Asignación directa simple sin operadores aritméticos.',
    },
    {
      id: 'valid-b',
      label: 'Válido (b) — x = a + b;',
      shortLabel: 'x = a + b;',
      category: 'valid',
      code: 'x = a + b;',
      description: 'Suma binaria con generación de temporal t1 y fusión en optimizador.',
    },
    {
      id: 'valid-c',
      label: 'Válido (c) — x = a + b * c;',
      shortLabel: 'x = a + b * c;',
      category: 'valid',
      code: 'x = a + b * c;',
      description: 'Precedencia de operadores: * se evalúa en t1 antes que + en t2.',
    },
    {
      id: 'valid-d',
      label: 'Válido (d) — x = (a + b) * c;',
      shortLabel: 'x = (a + b) * c;',
      category: 'valid',
      code: 'x = (a + b) * c;',
      description: 'Paréntesis alteran la precedencia: (a + b) genera t1 antes del producto.',
    },
    // 3 Casos Inválidos Oficiales del PDF
    {
      id: 'invalid-a',
      label: 'Inválido (a) — x = a + * b; (Operador doble)',
      shortLabel: 'x = a + * b;',
      category: 'invalid',
      code: 'x = a + * b;',
      description: "Operador duplicado: falla en T -> F T' al encontrar * en vez de factor.",
    },
    {
      id: 'invalid-b',
      label: 'Inválido (b) — x = (a + b; (Paréntesis sin cerrar)',
      shortLabel: 'x = (a + b;',
      category: 'invalid',
      code: 'x = (a + b;',
      description: 'Paréntesis sin cerrar: se encuentra ; cuando F -> ( E ) esperaba ).',
    },
    {
      id: 'invalid-c',
      label: 'Inválido (c) — x = ((a + b) * (Error tardío + Rollback)',
      shortLabel: 'x = ((a + b) *',
      category: 'invalid',
      code: 'x = ((a + b) *',
      description: 'Error tardío tras emitir t1 = a + b: activa ROLLBACK atómico (0 TAC final).',
    },
    // Presets extra para demostrar Optimización y Ámbitos Semánticos
    {
      id: 'semantic-opt',
      label: 'Extra — Plegado de Constantes + Identidad (x = a + 0 + 2 * 3;)',
      shortLabel: 'Optimización TAC',
      category: 'semantic',
      code: 'x = a + 0 + 2 * 3;',
      description:
        'Demuestra plegado de constantes (2 * 3 -> 6) y simplificación algebraica (a + 0 -> a).',
    },
  ];

  readonly validPresets = this.presets.filter((p) => p.category === 'valid');
  readonly invalidPresets = this.presets.filter((p) => p.category === 'invalid');
  readonly extraPresets = this.presets.filter((p) => p.category === 'semantic');

  // Píldoras rápidas destacadas para la demo en vivo
  readonly quickPillPresets: PresetCase[] = [
    this.presets[2], // x = a + b * c;
    this.presets[3], // x = (a + b) * c;
    this.presets[6], // x = ((a + b) *
  ];

  // Signals del Tour Interactivo de Bienvenida (activo automáticamente al cargar/recargar en memoria)
  readonly tourActive = signal<boolean>(true);
  readonly tourStepIndex = signal<number>(0);
  readonly tourTotalSteps = ONBOARDING_TOUR_STEPS.length;

  // Signals de estado principal
  readonly sourceCode = signal<string>('x = a + b * c;');
  readonly lightTheme = signal<boolean>(false);
  readonly activePresetId = signal<string>('valid-c');
  readonly rightTab = signal<'tac' | 'symbols'>('tac');

  // Resultado de compilación reactivo
  readonly compilationResult = signal<CompilationResult>(
    compileSource('x = a + b * c;', false)
  );

  // Control del reproductor de TraceStep (1..N)
  readonly currentStepIndex = signal<number>(
    this.compilationResult().trace.length
  );
  readonly isPlaying = signal<boolean>(false);
  readonly playbackSpeedMs = signal<number>(600);
  private timerId: ReturnType<typeof setInterval> | null = null;

  // Signals computadas para los paneles sincronizados
  readonly totalSteps = computed(() => this.compilationResult().trace.length);

  readonly activeStep = computed<TraceStep | null>(() => {
    const steps = this.compilationResult().trace;
    const idx = this.currentStepIndex();
    if (steps.length === 0 || idx <= 0) {
      return null;
    }
    return steps[Math.min(idx - 1, steps.length - 1)];
  });

  readonly activePhaseBadge = computed<string>(() => {
    const step = this.activeStep();
    if (!step) {
      return 'READY';
    }
    switch (step.phase) {
      case 'LEXING':
        return 'LEXER';
      case 'PARSING':
        return 'PARSER';
      case 'SEMANTIC':
      case 'CODEGEN':
        return 'SDT';
      case 'OPTIMIZATION':
        return 'OPTIMIZATION';
      case 'ROLLBACK':
        return 'ROLLBACK';
      default:
        return step.phase;
    }
  });

  readonly activeTokenIndex = computed<number>(() => {
    const step = this.activeStep();
    return step ? step.token_index : -1;
  });

  readonly activeLlStack = computed<string[]>(() => {
    const step = this.activeStep();
    if (!step) {
      return ['$', 'Program'];
    }
    return step.ll_stack;
  });

  readonly activeCallFrames = computed<AttributeFrameDto[]>(() => {
    const step = this.activeStep();
    return step ? step.call_frames : [];
  });

  readonly activeTacSnapshot = computed<string[]>(() => {
    const step = this.activeStep();
    return step ? step.tac_buffer_snapshot : [];
  });

  readonly activeSymbolSnapshot = computed<SymbolEntryDto[]>(() => {
    const step = this.activeStep();
    if (step) {
      return step.symbol_table_snapshot;
    }
    return [];
  });

  readonly hadRollbackInTrace = computed<boolean>(() =>
    this.compilationResult().trace.some((s) => s.action === 'ROLLBACK')
  );

  readonly isAtRollbackStep = computed<boolean>(
    () => this.activeStep()?.action === 'ROLLBACK'
  );

  readonly progressPercent = computed<number>(() => {
    const total = this.totalSteps();
    if (total === 0) {
      return 0;
    }
    return Math.round((this.currentStepIndex() / total) * 100);
  });

  readonly eliminatedTacCount = computed<number>(() => {
    const res = this.compilationResult();
    return Math.max(0, res.tacRaw.length - res.tacOptimized.length);
  });

  // Métodos del Tour Interactivo de Bienvenida
  openTour(): void {
    this.stopAutoPlay();
    this.tourStepIndex.set(0);
    this.tourActive.set(true);
  }

  closeTour(): void {
    this.tourActive.set(false);
  }

  nextTourStep(): void {
    const idx = this.tourStepIndex();
    if (idx < this.tourTotalSteps - 1) {
      this.tourStepIndex.set(idx + 1);
    } else {
      this.closeTour();
    }
  }

  prevTourStep(): void {
    this.tourStepIndex.update((i) => Math.max(0, i - 1));
  }

  goToTourStep(index: number): void {
    if (index >= 0 && index < this.tourTotalSteps) {
      this.tourStepIndex.set(index);
    }
  }

  isTourSpotlit(stepNumberOneBased: number): boolean {
    return this.tourActive() && this.tourStepIndex() === stepNumberOneBased - 1;
  }

  // Navegación global por teclado (soporta tanto el Tour como el Reproductor TraceStep)
  @HostListener('window:keydown', ['$event'])
  handleGlobalKeydown(event: KeyboardEvent): void {
    if (this.tourActive()) {
      if (event.key === 'Escape') {
        event.preventDefault();
        this.closeTour();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        this.nextTourStep();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        this.prevTourStep();
      }
      return;
    }

    const target = event.target as HTMLElement | null;
    if (target) {
      const tag = target.tagName.toLowerCase();
      if (
        tag === 'textarea' ||
        tag === 'select' ||
        (tag === 'input' && (target as HTMLInputElement).type !== 'range') ||
        target.isContentEditable
      ) {
        return;
      }
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      this.nextStep();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      this.prevStep();
    } else if (event.code === 'Space') {
      event.preventDefault();
      this.toggleAutoPlay();
    }
  }

  onPresetSelectChange(presetId: string): void {
    const found = this.presets.find((p) => p.id === presetId);
    if (found) {
      this.loadPreset(found);
    }
  }

  loadPreset(preset: PresetCase): void {
    this.stopAutoPlay();
    this.activePresetId.set(preset.id);
    this.sourceCode.set(preset.code);
    this.runCompilation(false);
  }

  onCodeChange(newCode: string): void {
    this.sourceCode.set(newCode);
    this.activePresetId.set('custom');
  }

  toggleTheme(): void {
    this.lightTheme.update((v) => !v);
  }

  runCompilation(startAtFirstStep: boolean = false): void {
    this.stopAutoPlay();
    const res = compileSource(this.sourceCode(), false);
    this.compilationResult.set(res);
    this.currentStepIndex.set(
      startAtFirstStep ? (res.trace.length > 0 ? 1 : 0) : res.trace.length
    );
  }

  // Controles de navegación paso a paso sobre TraceStep[]
  resetToStart(): void {
    this.stopAutoPlay();
    const total = this.totalSteps();
    this.currentStepIndex.set(total > 0 ? 1 : 0);
  }

  prevStep(): void {
    this.stopAutoPlay();
    this.currentStepIndex.update((idx) => Math.max(1, idx - 1));
  }

  nextStep(): void {
    this.stopAutoPlay();
    const total = this.totalSteps();
    this.currentStepIndex.update((idx) => Math.min(total, idx + 1));
  }

  executeAll(): void {
    this.stopAutoPlay();
    this.currentStepIndex.set(this.totalSteps());
  }

  jumpToStep(stepOneBased: number): void {
    this.stopAutoPlay();
    const total = this.totalSteps();
    this.currentStepIndex.set(Math.max(1, Math.min(total, stepOneBased)));
  }

  toggleAutoPlay(): void {
    if (this.isPlaying()) {
      this.stopAutoPlay();
      return;
    }
    const total = this.totalSteps();
    if (total === 0) {
      return;
    }
    if (this.currentStepIndex() >= total) {
      this.currentStepIndex.set(1);
    }
    this.isPlaying.set(true);
    this.timerId = setInterval(() => {
      const curr = this.currentStepIndex();
      if (curr < this.totalSteps()) {
        this.currentStepIndex.set(curr + 1);
      } else {
        this.stopAutoPlay();
      }
    }, this.playbackSpeedMs());
  }

  stopAutoPlay(): void {
    if (this.timerId !== null) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    this.isPlaying.set(false);
  }

  isTerminalSymbol(sym: string): boolean {
    return [
      'id',
      'num',
      'int',
      'float',
      '=',
      '+',
      '-',
      '*',
      '/',
      '(',
      ')',
      '{',
      '}',
      ';',
      '$',
    ].includes(sym);
  }

  isRawInstrOptimizedOut(rawText: string): boolean {
    const optTexts = new Set(
      this.compilationResult().tacOptimized.map((i) => i.text)
    );
    return !optTexts.has(rawText);
  }

  isOptInstrTransformed(optText: string): boolean {
    const rawTexts = new Set(
      this.compilationResult().tacRaw.map((i) => i.text)
    );
    return !rawTexts.has(optText);
  }

  trackByIndex(index: number): number {
    return index;
  }

  trackByToken(index: number, tok: Token): string {
    return `${index}-${tok.type}-${tok.line}:${tok.column}`;
  }

  ngOnDestroy(): void {
    this.stopAutoPlay();
  }
}
