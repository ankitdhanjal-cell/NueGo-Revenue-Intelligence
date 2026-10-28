import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { reset } from './handlers';
import { server } from './server';

// jsdom has no ResizeObserver, which the charts use to size themselves.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Node's fetch cannot resolve relative URLs the way a browser does.
const nodeFetch = globalThis.fetch;
globalThis.fetch = (input, init) =>
  nodeFetch(
    typeof input === 'string' && input.startsWith('/') ? `http://localhost:3000${input}` : input,
    init,
  );

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  reset();
});
afterAll(() => server.close());
