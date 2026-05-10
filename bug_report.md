# Frontend Bug Report

## HIGH Severity Bugs

### F-006: Silent Error Swallowing in all hooks
**Status:** Fixed

**Description:** All hooks were catching errors but not re-throwing them or returning error information to callers. This made it impossible for callers to handle errors programmatically.

**Fix Applied:**
- Added `createError()` helper function that creates proper Error objects with cause information
- Modified all hooks to re-throw errors after setting local error state
- `refetch()` functions now properly throw errors that callers can catch
- `updateStatus`, `markRead`, and other mutation functions now properly propagate errors

**Files Modified:**
- `hooks/useAnomalies.ts`
- `hooks/useAuth.ts`
- `hooks/useDatasets.ts`
- `hooks/useForecast.ts`
- `hooks/useNotifications.ts`
- `hooks/useQueryHistory.ts`
- `hooks/useScheduledReports.ts`

---

### F-007: Empty Dependency Arrays in all hooks
**Status:** Fixed

**Description:** Callbacks like `refetch` had stale closures due to empty dependency arrays, causing them to use outdated parameter values.

**Fix Applied:**
- Added ref tracking for all parameters: `datasetIdRef`, `statusRef`, `severityRef`, `pageRef`, `limitRef`, etc.
- Created synchronization effect that keeps refs fresh whenever parameters change
- Changed callback dependency arrays to empty `[]` since they now use refs
- useEffect hooks now use refs instead of direct values to avoid stale closures

**Files Modified:**
- `hooks/useAnomalies.ts`
- `hooks/useDatasets.ts`
- `hooks/useForecast.ts`
- `hooks/useNotifications.ts`
- `hooks/useQueryHistory.ts`
- `hooks/useScheduledReports.ts`

---

### F-008: Memory Leak in WebSocket in hooks/useAnomalyWebSocket.ts (lines 105-113)
**Status:** Fixed

**Description:** The WebSocket cleanup in the reconnect timeout callback was setting state after component unmount, and reconnection could occur after unmount.

**Fix Applied:**
- Added `mountedRef` to track component mount state
- Added connection guard at the start of `connect()` function to exit early if not mounted
- All state updates and WebSocket operations now check `mountedRef.current` before proceeding
- Reconnect logic now checks both `mountedRef.current` and `enabled` before attempting reconnect

**Files Modified:**
- `hooks/useAnomalyWebSocket.ts`

---

### F-009: Missing AbortController in all hooks
**Status:** Fixed

**Description:** No request cancellation mechanism existed, leaving in-flight requests active even after component unmount or when new requests were initiated.

**Fix Applied:**
- Added `abortControllerRef` to track current AbortController in all hooks
- Modified all fetch calls to accept and pass `signal` parameter
- Created cancellation logic that aborts previous request before starting new one
- Added AbortController timeout support to API functions
- Handle `AbortError` gracefully without setting error state

**Files Modified:**
- `hooks/useAnomalies.ts`
- `hooks/useDatasets.ts`
- `hooks/useForecast.ts`
- `hooks/useNotifications.ts`
- `hooks/useQueryHistory.ts`
- `hooks/useScheduledReports.ts`
- `services/api.ts` - Added `signal?: AbortSignal` parameter to: `listAnomalies`, `listDatasets`, `getForecast`, `getAnomalyNotifications`, `getQueryHistory`, `listScheduledReports`

---

### F-010: Unsafe Type Assertions in multiple files
**Status:** Fixed

**Description:** Direct type assertions using `as` keyword without proper type guards could cause runtime errors.

**Fix Applied:**
- Added `isValidPayload()` type guard in `useAuth.ts` to properly validate JWT payload structure
- Added `getStringField()` and `getOptionalStringField()` helpers for safe field extraction
- Added `isValidChartType()` and `isNonEmptyArray()` type guards in `QueryResultDisplay.tsx`
- Added proper null/undefined checks before accessing result properties

**Files Modified:**
- `hooks/useAuth.ts`
- `components/charts/QueryResultDisplay.tsx`

---

### F-011: Hardcoded Data Source ID in pages/QueryPage.tsx (line 35)
**Status:** Fixed

**Description:** The data_source_id was hardcoded to "default", preventing users from selecting which dataset to query.

**Fix Applied:**
- Added state for `datasets`, `selectedDataSourceId`
- Added `useEffect` to fetch available CSV datasets on mount
- Added Select dropdown component to choose data source
- Query submission now uses `selectedDataSourceId` instead of hardcoded value

**Files Modified:**
- `pages/QueryPage.tsx`

---

### F-012: No Retry Logic in services/api.ts
**Status:** Fixed

**Description:** API requests failed permanently on 5xx errors or network issues without any retry mechanism.

**Fix Applied:**
- Added `fetchWithRetry()` helper function with configurable retry logic
- Implements exponential backoff (1s, 2s, 4s delays)
- Retries on 5xx errors and 429 (rate limit) responses
- Configurable timeout (default 30 seconds) to prevent hanging requests
- Handles both network errors and HTTP errors appropriately

**Files Modified:**
- `services/api.ts`

---

## MEDIUM Severity Bugs

### F-013: XHR Upload Error Handling in services/api.ts (lines 107-109)
**Status:** Fixed

**Description:** The XHR error handler assumed all responses were JSON, causing parse errors when server returned non-JSON error responses.

**Fix Applied:**
- Wrapped JSON.parse in try-catch to handle non-JSON responses
- Added fallback error messages for different HTTP status codes
- For 4xx errors, includes specific status in message
- For 5xx errors, indicates server error occurred
- Provides user-friendly error messages instead of "Failed to parse JSON"

**Files Modified:**
- `services/api.ts`

---

### F-014: Inconsistent Error Handling - standardize on Error objects
**Status:** Fixed

**Description:** Some places used string error messages, others used Error objects with inconsistent property names.

**Fix Applied:**
- Standardized on using proper Error objects with message and cause properties
- Added `createError()` helper in all hooks to create consistent errors
- Errors now include `cause` property for debugging
- Error messages are consistent across all hooks

**Files Modified:**
- All hook files

---

### F-015: ECharts Re-imported in components/charts/Chart.tsx (lines 74-93)
**Status:** Fixed

**Description:** ECharts was imported dynamically on every effect execution, causing unnecessary module loading and potential performance issues.

**Fix Applied:**
- Created module-level cache for echarts import (`echartsModule` variable)
- Created `getEcharts()` function that returns cached module or initiates import
- Promise-based caching prevents duplicate import attempts
- Chart instance properly stored in ref and cleaned up on unmount

**Files Modified:**
- `components/charts/Chart.tsx`

---

### F-016: Inefficient Dataset Search in pages/DatasetsList.tsx (line 75)
**Status:** Fixed

**Description:** The search filter was computed on every render without memoization, causing unnecessary computation for large datasets.

**Fix Applied:**
- Imported `useMemo` from React
- Wrapped `filteredDatasets` computation in `useMemo` with proper dependency array
- Filter now only recomputes when `datasets` or `search` actually change

**Files Modified:**
- `pages/DatasetsList.tsx`

---

### F-018: Missing Request Timeout in services/api.ts
**Status:** Fixed

**Description:** Requests could hang indefinitely without timeout, causing poor user experience on slow/unreliable networks.

**Fix Applied:**
- Added `DEFAULT_TIMEOUT` constant (30 seconds)
- `fetchWithRetry` now creates AbortController with timeout
- All API functions that use fetch benefit from automatic timeout
- Requests that exceed timeout are properly aborted and throw AbortError

**Files Modified:**
- `services/api.ts`

---

### F-019: Sequential Notification Mark-Read in components/NotificationBell.tsx (lines 48-53)
**Status:** Fixed

**Description:** Notifications were marked as read one at a time sequentially, causing slow UI updates when many notifications existed.

**Fix Applied:**
- Changed from sequential `for...await` loop to parallel `Promise.all`
- All mark-read requests now fire simultaneously
- Added error handling per notification to prevent one failure from affecting others
- Uses `.catch()` on individual promises to log failures without blocking others

**Files Modified:**
- `components/NotificationBell.tsx`

---

### F-020: Fixed Skeleton Item Counts in pages/DatasetsList.tsx
**Status:** Fixed

**Description:** The skeleton loading placeholder used a hardcoded `[...Array(3)]`, making it difficult to adjust the number of skeleton items dynamically.

**Fix Applied:**
- Added `SKELETON_COUNT` constant (set to 3) at the top of the component
- Replaced hardcoded `3` with the `SKELETON_COUNT` constant
- Now the skeleton count can be easily adjusted by changing the constant value

**Files Modified:**
- `pages/DatasetsList.tsx`

---

### F-021: AnomalyTable Missing Loading State in components/dashboard/AnomalyTable.tsx
**Status:** Fixed

**Description:** The AnomalyTable component had no loading state, causing inconsistency with other components that show skeleton loaders.

**Fix Applied:**
- Added `loading` prop (defaults to `false`) to AnomalyTableProps interface
- Added loading state that displays skeleton rows (5 rows) when `loading={true}`
- Updated Dashboard.tsx to pass `loading={anomaliesLoading}` to AnomalyTable

**Files Modified:**
- `components/dashboard/AnomalyTable.tsx`
- `pages/Dashboard.tsx`

---

### F-022: Missing Type Annotations
**Status:** Fixed

**Description:** Some places lacked explicit type annotations, relying on implicit any or inferred types.

**Fix Applied:**
- All hook interfaces have explicit type annotations for props and return values
- Component props interfaces are fully typed
- Function parameters and return types are explicitly annotated where needed

**Files Modified:**
- All hook files have proper interface definitions
- All component files have typed props interfaces

---

## Summary

| Bug ID | Title | Severity | Status |
|--------|-------|----------|--------|
| F-006 | Silent Error Swallowing in all hooks | HIGH | Fixed |
| F-007 | Empty Dependency Arrays in all hooks | HIGH | Fixed |
| F-008 | Memory Leak in WebSocket | HIGH | Fixed |
| F-009 | Missing AbortController in all hooks | HIGH | Fixed |
| F-010 | Unsafe Type Assertions | HIGH | Fixed |
| F-011 | Hardcoded Data Source ID | HIGH | Fixed |
| F-012 | No Retry Logic in services/api.ts | HIGH | Fixed |
| F-013 | XHR Upload Error Handling | MEDIUM | Fixed |
| F-014 | Inconsistent Error Handling | MEDIUM | Fixed |
| F-015 | ECharts Re-imported | MEDIUM | Fixed |
| F-016 | Inefficient Dataset Search | MEDIUM | Fixed |
| F-018 | Missing Request Timeout | MEDIUM | Fixed |
| F-019 | Sequential Notification Mark-Read | MEDIUM | Fixed |
| F-020 | Fixed Skeleton Item Counts | LOW | Fixed |
| F-021 | AnomalyTable Missing Loading State | LOW | Fixed |
| F-022 | Missing Type Annotations | LOW | Fixed |

All 16 bugs have been fixed.