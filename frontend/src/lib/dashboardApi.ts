/**
 * Dashboard API - Fetch scan results and artifacts for dashboard display
 */

export interface ScanSummary {
  timestamp: string;
  total_symbols: number;
  actionable: number;
  watch: number;
  risk: number;
  skipped: number;
  failed: number;
  health_status: "PASS" | "WARN" | "FAIL";
}

export interface ScanHistoryItem {
  id: string;
  timestamp: string;
  health_status: "PASS" | "WARN" | "FAIL";
  total_symbols: number;
  actionable: number;
  watch: number;
  risk: number;
}

export interface DataHealthInfo {
  status: "PASS" | "WARN" | "FAIL";
  stale_symbols: string[];
  last_updated: string;
  message?: string;
}

export interface DashboardData {
  summary: ScanSummary | null;
  history: ScanHistoryItem[];
  health: DataHealthInfo | null;
}

/**
 * Parse scan results from artifact files
 * In production, these would be fetched from the backend API
 * For now, we read from the scan artifact directory
 */
export async function fetchLatestScanResults(): Promise<ScanSummary | null> {
  try {
    // Try to find the latest scan directory
    const scanDir = await findLatestScanDirectory();
    if (!scanDir) {
      return null;
    }

    // Read scan results
    const resultsPath = `${scanDir}/scan_results.json`;
    const response = await fetch(resultsPath);
    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    return parseScanResults(data);
  } catch {
    return null;
  }
}

/**
 * Parse scan results into summary format
 */
function parseScanResults(data: Record<string, unknown>): ScanSummary {
  const results = (data.results as Array<{ symbol: string; bucket: string }>) || [];
  const manifest = data.manifest as { timestamp?: string } | undefined;

  const counts = {
    actionable: results.filter((r) => r.bucket === "actionable").length,
    watch: results.filter((r) => r.bucket === "watch").length,
    risk: results.filter((r) => r.bucket === "risk" || r.bucket === "excluded").length,
    skipped: results.filter((r) => r.bucket === "skipped").length,
    failed: results.filter((r) => r.bucket === "failed").length,
  };

  return {
    timestamp: manifest?.timestamp || new Date().toISOString(),
    total_symbols: results.length,
    health_status: "PASS",
    ...counts,
  };
}

/**
 * Find the latest scan directory
 */
async function findLatestScanDirectory(): Promise<string | null> {
  // In production, this would be an API call
  // For now, return null to indicate no data
  return null;
}

/**
 * Fetch scan history
 */
export async function fetchScanHistory(limit = 10): Promise<ScanHistoryItem[]> {
  try {
    // In production, this would fetch from API
    // For now, return mock data
    return generateMockHistory(limit);
  } catch {
    return [];
  }
}

/**
 * Generate mock history for development
 */
function generateMockHistory(count: number): ScanHistoryItem[] {
  const history: ScanHistoryItem[] = [];
  const now = new Date();

  for (let i = 0; i < count; i++) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    history.push({
      id: `scan-${i}`,
      timestamp: date.toISOString(),
      health_status: i % 5 === 0 ? "WARN" : "PASS",
      total_symbols: 20 + Math.floor(Math.random() * 10),
      actionable: Math.floor(Math.random() * 5),
      watch: Math.floor(Math.random() * 8),
      risk: Math.floor(Math.random() * 3),
    });
  }

  return history;
}

/**
 * Fetch data health status
 */
export async function fetchDataHealth(): Promise<DataHealthInfo | null> {
  try {
    // In production, this would fetch from API
    return {
      status: "PASS",
      stale_symbols: [],
      last_updated: new Date().toISOString(),
      message: "All data is fresh",
    };
  } catch {
    return null;
  }
}

/**
 * Get full dashboard data
 */
export async function getDashboardData(): Promise<DashboardData> {
  const [summary, history, health] = await Promise.all([
    fetchLatestScanResults(),
    fetchScanHistory(),
    fetchDataHealth(),
  ]);

  return { summary, history, health };
}
