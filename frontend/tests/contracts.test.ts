import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import ts from 'typescript';

test('serializer request/response fixtures typecheck with strict nullability and negative assertions', () => {
  const program = ts.createProgram([
    fileURLToPath(new URL('./contractTypes.ts', import.meta.url)),
    fileURLToPath(new URL('../src/vite-env.d.ts', import.meta.url)),
  ], {
    target: ts.ScriptTarget.ES2023,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    allowImportingTsExtensions: true,
    strict: true,
    skipLibCheck: true,
    noEmit: true,
    types: ['vite/client'],
  });
  const diagnostics = ts.getPreEmitDiagnostics(program);
  const messages = ts.formatDiagnostics(diagnostics, {
    getCanonicalFileName: (file) => file,
    getCurrentDirectory: () => process.cwd(),
    getNewLine: () => '\n',
  });
  assert.equal(diagnostics.length, 0, messages);
});
