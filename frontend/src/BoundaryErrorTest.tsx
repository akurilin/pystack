// Throwaway verification route at /boundary-error-test. This throws during
// render, which is the failure mode AppErrorBoundary is designed to catch.
export function BoundaryErrorTest(): never {
  throw new Error("Boundary error test: render failed intentionally.");
}
