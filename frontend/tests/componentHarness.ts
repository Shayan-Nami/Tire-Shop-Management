import { readFileSync } from 'node:fs';

import { setImmediate } from 'node:timers/promises';
import React from 'react';
import ts from 'typescript';


/** Compile TSX with the already-installed TypeScript; no browser/test dependencies. */
export function loadComponent(path: string, mocks: Record<string, unknown>) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
  });
  const module = { exports: {} as Record<string, any> };
  const mockedRequire = (id: string) => {
    if (id in mocks) return mocks[id];
    if (id === 'react') return React;
    if (id === 'lucide-react') return new Proxy({}, { get: (_target, name) => String(name) });
    throw new Error(`Unmocked component dependency: ${id}`);
  };
  const evaluate = new Function('require', 'module', 'exports', outputText);
  evaluate(mockedRequire, module, module.exports);
  return module.exports;
}

type Effect = { deps?: unknown[]; cleanup?: () => void };

/**
 * A small hook-level harness: executes real component handlers/effects with controlled
 * transport promises. It deliberately does not simulate DOM layout, focus, or React scheduling.
 */
export function mountComponent(path: string, exportName: string, mocks: Record<string, unknown>, props: Record<string, unknown> = {}) {
  const state: any[] = [];
  const effects: Effect[] = [];
  let cursor = 0;
  let dirty = false;
  let unmounted = false;
  let tree: any;
  let pending: Array<() => void> = [];
  const sameDeps = (a?: unknown[], b?: unknown[]) => a && b && a.length === b.length && a.every((value, index) => Object.is(value, b[index]));
  const react = {
    ...React,
    useState(initial: unknown) {
      const index = cursor++;
      if (!(index in state)) state[index] = typeof initial === 'function' ? initial() : initial;
      return [state[index], (next: any) => {
        if (unmounted) throw new Error('State update after unmount');
        state[index] = typeof next === 'function' ? next(state[index]) : next;
        dirty = true;
      }];
    },
    useRef(initial: unknown) {
      const index = cursor++;
      if (!(index in state)) state[index] = { current: initial };
      return state[index];
    },
    useCallback(callback: unknown, deps: unknown[]) {
      const index = cursor++;
      if (!state[index] || !sameDeps(state[index].deps, deps)) state[index] = { callback, deps };
      return state[index].callback;
    },
    useEffect(callback: () => void | (() => void), deps?: unknown[]) {
      const index = cursor++;
      if (effects[index] && sameDeps(effects[index].deps, deps)) return;
      pending.push(() => {
        effects[index]?.cleanup?.();
        effects[index] = { deps, cleanup: callback() || undefined };
      });
    },
  };
  const Component = loadComponent(path, { ...mocks, react })[exportName];
  function render() {
    cursor = 0;
    dirty = false;
    pending = [];
    tree = Component(props);
    const scheduled = pending;
    pending = [];
    for (const effect of scheduled) effect();
    return tree;
  }
  render();
  return {
    render,
    get tree() { return tree; },
    async flush() {
      await setImmediate();
      for (let iteration = 0; dirty && iteration < 20; iteration++) {
        render();
        await setImmediate();
      }
      if (dirty) throw new Error('Component did not settle');
    },
    unmount() {
      for (const effect of effects) effect?.cleanup?.();
      unmounted = true;
    },
  };
}

export function nodes(tree: any, predicate: (node: any) => boolean): any[] {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap((node) => nodes(node, predicate));
  return [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)];
}

export function text(tree: any): string {
  if (tree == null || typeof tree === 'boolean') return '';
  if (typeof tree === 'string' || typeof tree === 'number') return String(tree);
  if (Array.isArray(tree)) return tree.map(text).join('');
  return text(tree.props?.children);
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

export function page<T>(results: T[], current = 1, total = 1) {
  return { results, count: results.length * total, current_page: current, total_pages: total,
    next: current < total ? `?page=${current + 1}` : null, previous: null };
}

