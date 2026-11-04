import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

// Backend tests supply real, synthetic API responses from their disposable database.
let input = '';
for await (const chunk of process.stdin) input += chunk;
const fixtures = JSON.parse(input);
assert.ok(fixtures.length > 0, 'No backend contracts supplied');
const virtualFile = fileURLToPath(new URL('./backendResponses.ts', import.meta.url));
const names = [...new Set(fixtures.flatMap((fixture) => fixture.type.match(/[A-Za-z]\w*/g)))];
names.push('PaginatedResponse');
const source = `import type { ${[...new Set(names)].join(',')} } from '../src/types/index.ts';
type ReadonlyJson<T> = T extends object ? { readonly [K in keyof T]: ReadonlyJson<T[K]> } : T;
${fixtures.map((fixture, i) => `const actual${i} = ${JSON.stringify(fixture.data)} as const;
const checked${i}: ReadonlyJson<${fixture.type}> = actual${i};`).join('\n')}`;
const options = {
  strict: true, noEmit: true, skipLibCheck: true,
  target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext,
  moduleResolution: ts.ModuleResolutionKind.Bundler, allowImportingTsExtensions: true,
};
const host = ts.createCompilerHost(options);
const getSourceFile = host.getSourceFile.bind(host);
host.getSourceFile = (file, ...args) => path.resolve(file) === virtualFile
  ? ts.createSourceFile(file, source, options.target, true) : getSourceFile(file, ...args);
const program = ts.createProgram([virtualFile], options, host);
const errors = ts.getPreEmitDiagnostics(program);
assert.equal(errors.length, 0, ts.formatDiagnosticsWithColorAndContext(errors, host));
console.log(`Validated ${fixtures.length} real API responses against frontend TypeScript contracts.`);
