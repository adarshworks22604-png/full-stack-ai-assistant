import "@testing-library/jest-dom/vitest";

// jsdom lacks ResizeObserver, which Fluent UI's MessageBar uses.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
