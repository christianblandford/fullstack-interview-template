# Frontend Performance Guidelines

**Last updated:** 2025-11-01  
**Owner:** Frontend Team  
**Status:** Current

## Overview

The Acme Platform frontend is a React SPA served via CloudFront. Performance is critical — our customers use the platform throughout the workday, and slow interactions directly impact their productivity and our NPS scores.

## Performance Budgets

| Metric | Budget | Current | Status |
| ------ | ------ | ------- | ------ |
| Largest Contentful Paint (LCP) | < 2.5s | 1.8s | OK |
| First Input Delay (FID) | < 100ms | 45ms | OK |
| Cumulative Layout Shift (CLS) | < 0.1 | 0.04 | OK |
| Time to Interactive (TTI) | < 3.5s | 2.9s | OK |
| Total JS bundle (gzipped) | < 350 KB | 312 KB | Warning |
| Initial CSS (gzipped) | < 50 KB | 38 KB | OK |

Budgets are enforced in CI — builds that exceed any budget by more than 10% are blocked.

## Code Splitting Strategy

### Route-Based Splitting

Every top-level route is lazy-loaded:

```tsx
const Workflows = lazy(() => import('./features/workflows'));
const Analytics = lazy(() => import('./features/analytics'));
const Settings = lazy(() => import('./features/settings'));
```

This keeps the initial bundle to ~120 KB (gzipped) — just the shell, auth, and navigation.

### Component-Level Splitting

Heavy components are split even within routes:
- **Rich text editor** (Tiptap) — loaded only when editing a document (~85 KB)
- **Chart library** (Recharts) — loaded only on analytics pages (~65 KB)
- **PDF viewer** — loaded only when viewing a document (~40 KB)
- **Date picker** (with locale data) — loaded on first interaction (~15 KB)

### Prefetching

We prefetch likely next routes on hover:

```tsx
<Link to="/workflows" onMouseEnter={() => prefetchRoute('workflows')}>
```

This gives a ~200ms head start on navigation, making most transitions feel instant.

## Data Fetching Patterns

### React Query Configuration

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,        // Data is fresh for 1 minute
      gcTime: 300_000,          // Cache kept for 5 minutes after unmount
      retry: 2,                  // Retry failed requests twice
      refetchOnWindowFocus: true, // Refresh when user returns to tab
    },
  },
});
```

### Optimistic Updates

All mutations that affect the current view use optimistic updates:

1. Immediately update the React Query cache with the expected result
2. Send the mutation to the server
3. On success: invalidate related queries to get the canonical server state
4. On error: roll back the optimistic update and show an error toast

This makes the UI feel instant even on slow connections.

### Pagination

All list endpoints use cursor-based pagination:
- Page size: 25 items (configurable up to 100)
- Prefetch the next page when the user scrolls to 80% of the current page
- Keep the previous 3 pages in cache for instant back-navigation

### WebSocket Updates

The `realtime` service pushes updates via WebSocket for:
- Workflow status changes (so the list view updates without polling)
- New comments on workflows the user is viewing
- System notifications (maintenance windows, new features)

WebSocket messages trigger React Query cache invalidation for the affected queries, so the UI stays in sync without polling.

## Image & Asset Optimization

- All images are served via CloudFront with automatic WebP/AVIF conversion
- SVG icons use a sprite sheet (single HTTP request for all icons)
- Fonts are self-hosted (Inter Variable) with `font-display: swap`
- Critical CSS is inlined in the HTML shell; the rest is loaded async

## Monitoring

- **Real User Monitoring (RUM):** Datadog RUM tracks Core Web Vitals for every page load
- **Synthetic monitoring:** Datadog Synthetics runs a login → create workflow → view analytics flow every 5 minutes from 3 regions
- **Bundle analysis:** `vite-bundle-visualizer` runs in CI and posts a comment on PRs that change bundle size by > 5%
- **Error tracking:** Sentry captures frontend exceptions with full replay context

## Common Performance Pitfalls

### 1. Unnecessary Re-renders

Use `React.memo` for list items and `useMemo`/`useCallback` for expensive computations. The React DevTools Profiler should show < 5ms per render for any component.

### 2. Large List Rendering

Any list that could exceed 100 items must use virtualization (`@tanstack/react-virtual`). The workflow list, audit log, and document list all use this.

### 3. Unoptimized Images

Never use raw uploaded images in the UI. Always go through the CloudFront image transformation pipeline: `https://cdn.acmecorp.com/images/{id}?w=400&h=300&fit=cover&format=auto`

### 4. Blocking the Main Thread

Long-running computations (CSV parsing, data transformation) must run in a Web Worker. The `useWorker` hook wraps this pattern:

```tsx
const { result, isProcessing } = useWorker(
  () => parseCSV(rawData),
  [rawData]
);
```

### 5. Memory Leaks

Common sources:
- WebSocket subscriptions not cleaned up on unmount
- `setInterval` without cleanup in `useEffect`
- Large datasets held in component state after navigation

Use the React DevTools Memory tab and Chrome DevTools heap snapshots to diagnose. Any component that grows memory by > 1 MB per minute of usage is a bug.

## Performance Review Process

Every PR that touches the frontend goes through:

1. **Automated checks:** Bundle size, Lighthouse CI score, TypeScript strict mode
2. **Visual review:** Storybook screenshots compared via Chromatic
3. **Manual check (for large PRs):** Run the app locally and check React DevTools Profiler

Quarterly, the frontend team runs a full performance audit using WebPageTest and publishes results to the engineering blog.
