import { CommonModule } from '@angular/common';
import {
  Component,
  EventEmitter,
  HostListener,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  SimpleChanges,
  signal,
} from '@angular/core';

export interface TourStepConfig {
  readonly id: number;
  readonly targetId: string;
  readonly title: string;
  readonly description: string;
  readonly preferredPlacement: 'bottom' | 'top' | 'right' | 'left';
}

export const ONBOARDING_TOUR_STEPS: readonly TourStepConfig[] = [
  {
    id: 1,
    targetId: 'tour-step-1',
    title: '1. Escribe o elige una expresión',
    description:
      'Ingresa una sentencia terminada en punto y coma (ej. x = a + b * c;) o selecciona cualquiera de los casos válidos e inválidos del proyecto.',
    preferredPlacement: 'bottom',
  },
  {
    id: 2,
    targetId: 'tour-step-2',
    title: '2. Controla el tiempo de compilación',
    description:
      'Usa "Paso a paso" para avanzar instrucción por instrucción, activa Auto-Play o muévete libremente con las flechas ← y → de tu teclado.',
    preferredPlacement: 'bottom',
  },
  {
    id: 3,
    targetId: 'tour-step-3',
    title: '3. Analizador Léxico en vivo',
    description:
      'Aquí verás cada token reconocido. El bloque iluminado indica el token exacto que el parser está leyendo en este instante.',
    preferredPlacement: 'bottom',
  },
  {
    id: 4,
    targetId: 'tour-step-4',
    title: '4. Flujo de atributos .inh y .place',
    description:
      'Observa cómo evoluciona la pila predictiva sin recursión izquierda y cómo viajan los valores heredados (azul) y sintetizados (rosa).',
    preferredPlacement: 'top',
  },
  {
    id: 5,
    targetId: 'tour-step-5',
    title: '5. Código Intermedio y Optimización',
    description:
      'Consulta las instrucciones TAC generadas en vivo, compáralas con la versión optimizada y revisa la tabla de símbolos actualizada.',
    preferredPlacement: 'top',
  },
];

@Component({
  selector: 'app-onboarding-tour',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="tour-backdrop"
      *ngIf="active"
      (click)="onBackdropClick($event)"
      aria-modal="true"
      role="dialog"
    >
      <!-- Tarjeta Popover Flotante en Satoshi -->
      <div
        class="tour-popover"
        [style.top.px]="popoverTop()"
        [style.left.px]="popoverLeft()"
        (click)="$event.stopPropagation()"
      >
        <div class="tour-popover-header">
          <span class="tour-step-pill">
            Paso {{ stepIndex + 1 }} de {{ steps.length }}
          </span>

          <div class="tour-dots">
            <button
              *ngFor="let s of steps; let i = index"
              type="button"
              class="tour-dot"
              [class.dot-current]="i === stepIndex"
              [class.dot-done]="i < stepIndex"
              (click)="goToStep.emit(i)"
              [attr.aria-label]="'Ir al paso ' + (i + 1)"
            ></button>
          </div>
        </div>

        <h3 class="tour-title">{{ currentStep.title }}</h3>
        <p class="tour-desc">{{ currentStep.description }}</p>

        <div class="tour-footer">
          <button
            type="button"
            class="tour-btn-skip"
            (click)="closeTour.emit()"
            title="Cerrar guía (Esc)"
          >
            Omitir
          </button>

          <div class="tour-nav-btns">
            <button
              type="button"
              class="tour-btn-prev"
              *ngIf="stepIndex > 0"
              (click)="prevStep.emit()"
            >
              Anterior
            </button>
            <button
              type="button"
              class="tour-btn-next"
              (click)="onNextOrFinish()"
            >
              {{
                stepIndex === steps.length - 1
                  ? '¡Entendido, empezar!'
                  : 'Siguiente'
              }}
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .tour-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(22, 18, 36, 0.68);
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
        z-index: 900;
        transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      }

      .tour-popover {
        position: fixed;
        z-index: 1002;
        width: min(370px, calc(100vw - 28px));
        background: var(--surface-popover, #322a4b);
        color: var(--text-body, #f3eeff);
        border: 1px solid rgba(208, 188, 252, 0.34);
        border-radius: 16px;
        padding: 1.05rem 1.2rem;
        box-shadow: 0 18px 42px rgba(15, 11, 28, 0.55),
          0 0 0 1px rgba(208, 188, 252, 0.14);
        display: flex;
        flex-direction: column;
        gap: 0.65rem;
        transition: top 0.26s cubic-bezier(0.16, 1, 0.3, 1),
          left 0.26s cubic-bezier(0.16, 1, 0.3, 1);
      }

      .tour-popover-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem;
      }

      .tour-step-pill {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        padding: 0.2rem 0.62rem;
        border-radius: 999px;
        background: rgba(208, 188, 252, 0.16);
        border: 1px solid rgba(208, 188, 252, 0.3);
        color: var(--accent-lavender, #d0bcfc);
      }

      .tour-dots {
        display: flex;
        align-items: center;
        gap: 0.32rem;
      }

      .tour-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        border: none;
        background: rgba(208, 188, 252, 0.24);
        cursor: pointer;
        padding: 0;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      }

      .tour-dot.dot-done {
        background: rgba(208, 188, 252, 0.55);
      }

      .tour-dot.dot-current {
        width: 20px;
        background: var(--accent-lavender, #d0bcfc);
      }

      .tour-title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-heading, #ffffff);
        letter-spacing: -0.01em;
      }

      .tour-desc {
        font-size: 0.84rem;
        line-height: 1.5;
        color: var(--text-secondary, #b9aed8);
      }

      .tour-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 0.25rem;
        padding-top: 0.55rem;
        border-top: 1px solid rgba(208, 188, 252, 0.14);
      }

      .tour-btn-skip {
        background: transparent;
        border: none;
        color: var(--text-secondary, #b9aed8);
        font-family: var(--font-sans);
        font-size: 0.78rem;
        font-weight: 500;
        cursor: pointer;
        padding: 0.28rem 0.4rem;
        border-radius: 6px;
        transition: color 0.18s ease;
      }

      .tour-btn-skip:hover {
        color: var(--text-heading, #ffffff);
      }

      .tour-nav-btns {
        display: flex;
        align-items: center;
        gap: 0.45rem;
      }

      .tour-btn-prev {
        background: rgba(208, 188, 252, 0.1);
        color: var(--text-body, #f3eeff);
        border: 1px solid rgba(208, 188, 252, 0.24);
        border-radius: 9px;
        padding: 0.38rem 0.75rem;
        font-family: var(--font-sans);
        font-size: 0.78rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      }

      .tour-btn-prev:hover {
        background: rgba(208, 188, 252, 0.2);
      }

      .tour-btn-next {
        background: linear-gradient(135deg, #7b45f0 0%, #b796fe 100%);
        color: #ffffff;
        border: none;
        border-radius: 9px;
        padding: 0.4rem 0.92rem;
        font-family: var(--font-sans);
        font-size: 0.79rem;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      }

      .tour-btn-next:hover {
        filter: brightness(1.07);
        transform: translateY(-1px);
      }
    `,
  ],
})
export class OnboardingTourComponent implements OnInit, OnChanges, OnDestroy {
  @Input() active = false;
  @Input() stepIndex = 0;

  @Output() nextStep = new EventEmitter<void>();
  @Output() prevStep = new EventEmitter<void>();
  @Output() goToStep = new EventEmitter<number>();
  @Output() closeTour = new EventEmitter<void>();

  readonly steps = ONBOARDING_TOUR_STEPS;
  readonly popoverTop = signal<number>(120);
  readonly popoverLeft = signal<number>(120);

  get currentStep(): TourStepConfig {
    return this.steps[this.stepIndex] ?? this.steps[0];
  }

  ngOnInit(): void {
    if (this.active) {
      setTimeout(() => this.updatePopoverPosition(true), 40);
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['active'] || changes['stepIndex']) {
      if (this.active) {
        setTimeout(() => this.updatePopoverPosition(true), 30);
      }
    }
  }

  @HostListener('window:resize')
  @HostListener('window:scroll')
  onViewportChange(): void {
    if (this.active) {
      this.updatePopoverPosition(false);
    }
  }

  onNextOrFinish(): void {
    if (this.stepIndex >= this.steps.length - 1) {
      this.closeTour.emit();
    } else {
      this.nextStep.emit();
    }
  }

  onBackdropClick(event: MouseEvent): void {
    event.stopPropagation();
  }

  private updatePopoverPosition(scrollIntoView: boolean): void {
    const step = this.currentStep;
    const targetEl = document.getElementById(step.targetId);
    const popoverWidth = Math.min(370, window.innerWidth - 28);
    const popoverHeight = 198;
    const margin = 14;

    if (!targetEl) {
      this.popoverTop.set(Math.max(20, window.innerHeight / 2 - popoverHeight / 2));
      this.popoverLeft.set(Math.max(14, window.innerWidth / 2 - popoverWidth / 2));
      return;
    }

    if (scrollIntoView) {
      const rectCheck = targetEl.getBoundingClientRect();
      if (rectCheck.top < 0 || rectCheck.bottom > window.innerHeight) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    const rect = targetEl.getBoundingClientRect();
    let top = 0;
    let left = rect.left + rect.width / 2 - popoverWidth / 2;

    if (step.preferredPlacement === 'bottom') {
      if (rect.bottom + margin + popoverHeight <= window.innerHeight - 12) {
        top = rect.bottom + margin;
      } else {
        top = Math.max(14, rect.top - popoverHeight - margin);
      }
    } else {
      // preferredPlacement === 'top'
      if (rect.top - margin - popoverHeight >= 14) {
        top = rect.top - popoverHeight - margin;
      } else if (rect.bottom + margin + popoverHeight <= window.innerHeight - 12) {
        top = rect.bottom + margin;
      } else {
        top = Math.max(18, Math.min(window.innerHeight - popoverHeight - 18, rect.top + 16));
      }
    }

    // Clamp horizontal y vertical para no salirse nunca de la pantalla
    const clampedLeft = Math.max(
      14,
      Math.min(window.innerWidth - popoverWidth - 14, left)
    );
    const clampedTop = Math.max(
      14,
      Math.min(window.innerHeight - popoverHeight - 14, top)
    );

    this.popoverLeft.set(Math.round(clampedLeft));
    this.popoverTop.set(Math.round(clampedTop));
  }

  ngOnDestroy(): void {}
}
