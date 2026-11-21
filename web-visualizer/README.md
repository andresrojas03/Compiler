# Visualizador Interactivo del Compilador LL(1) + SDT + TAC (Fase 2)

Aplicación web **100% Client-Side** en **Angular Standalone Components + Signals + TypeScript** que porta 1:1 el motor del compilador de Python (`Lexer`, `LLParserSDT`, `SymbolTable`, `CodeGenerator` con `newTemp()`/`emit()`/`rollback()`/`optimize()` y `CompilerTracer`).

## 1. Ejecución en Local

```bash
cd web-visualizer
npm install
npm start
```

La aplicación se abrirá automáticamente en `http://localhost:4200`.

Para generar el bundle estático de producción:

```bash
npm run build
```

## 2. Despliegue en Vercel

### Opción A — Desde la CLI de Vercel
```bash
cd web-visualizer
npx vercel --prod
```

### Opción B — Desde el Dashboard de Vercel (GitHub/GitLab)
1. Importa el repositorio en Vercel.
2. Configura **Root Directory** como `web-visualizer`.
3. `vercel.json` ya incluye `buildCommand` (`npm run build`) y `outputDirectory` (`dist/compiler-ll1-visualizer/browser`).
