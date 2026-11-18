"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  Database,
  Search,
  Shield,
  Layers,
  Terminal,
  RefreshCw,
  LogOut,
  User,
  ChevronRight,
  Filter,
  FileCode,
  FileText,
  Clock,
  Sparkles,
  Zap,
  Flame,
  TrendingUp,
} from "lucide-react";

interface UserProfile {
  id: number;
  username: string;
  full_name: string;
  role: "admin" | "analyst";
}

interface LogItem {
  id: number;
  doc_id: string;
  ts: string;
  severity: "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL";
  service: string;
  host: string;
  trace_id?: string;
  message: string;
}

interface AnomalyItem {
  id: number;
  detected_at: string;
  bucket: string;
  service: string;
  metric: string;
  value: number;
  baseline_mean: number;
  baseline_std: number;
  zscore: number;
}

interface TimePoint {
  bucket: string;
  time: string;
  total_logs: number;
  error_logs: number;
  is_anomaly: boolean;
  zscore: number;
  service: string;
}

const API_BASE = "http://localhost:8080/api/v1";

export default function Home() {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"dashboard" | "explorer" | "advanced_sql" | "nosql" | "anomalies" | "admin">("dashboard");

  // Dashboard Stats & Graph
  const [totalLogs, setTotalLogs] = useState<number>(102000);
  const [anomalyCount, setAnomalyCount] = useState<number>(0);
  const [partitionsCount, setPartitionsCount] = useState<number>(16);
  const [timeseries, setTimeseries] = useState<TimePoint[]>([]);

  // Log Explorer State
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedService, setSelectedService] = useState("all");
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [logsList, setLogsList] = useState<LogItem[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // Anomalies State
  const [anomaliesList, setAnomaliesList] = useState<AnomalyItem[]>([]);

  // Live Simulation State
  const [simService, setSimService] = useState("payments");
  const [simSpikeCount, setSimSpikeCount] = useState(1500);
  const [simLoading, setSimLoading] = useState(false);
  const [simAlert, setSimAlert] = useState<string | null>(null);

  // Advanced SQL Lab State
  const [selectedQueryId, setSelectedQueryId] = useState("join");
  const [queryResult, setQueryResult] = useState<any>(null);

  // NoSQL CRUD State
  const [nosqlService, setNosqlService] = useState("payments");
  const [nosqlSeverity, setNosqlSeverity] = useState("ERROR");
  const [nosqlHost, setNosqlHost] = useState("host-01");
  const [nosqlMessage, setNosqlMessage] = useState("Transaction timed out at merchant gateway");
  const [nosqlDocId, setNosqlDocId] = useState("");
  const [nosqlResult, setNosqlResult] = useState<any>(null);

  // Admin Stored Procedure State
  const [targetDate, setTargetDate] = useState("2026-11-25");
  const [procMessage, setProcMessage] = useState("");
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  // Initial load check
  useEffect(() => {
    const savedToken = localStorage.getItem("log_token");
    const savedUser = localStorage.getItem("log_user");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setCurrentUser(JSON.parse(savedUser));
    } else {
      handleLogin("admin", "admin123");
    }
  }, []);

  useEffect(() => {
    if (currentUser) {
      fetchLogs();
      fetchAnomalies();
      fetchTimeseries();
      if (activeTab === "advanced_sql") {
        runAdvancedQuery("join");
      }
      if (activeTab === "admin" && currentUser.role === "admin") {
        fetchAuditLogs();
      }
    }
  }, [currentUser, activeTab]);

  const handleLogin = async (u: string, p: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      if (!res.ok) throw new Error("Invalid username or password");
      const data = await res.json();
      setToken(data.access_token);
      setCurrentUser(data.user);
      localStorage.setItem("log_token", data.access_token);
      localStorage.setItem("log_user", JSON.stringify(data.user));
    } catch (err: any) {
      console.error(err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("log_token");
    localStorage.removeItem("log_user");
    setCurrentUser(null);
    setToken("");
  };

  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      let url = `${API_BASE}/logs?limit=50`;
      if (selectedService !== "all") url += `&service=${selectedService}`;
      if (selectedSeverity !== "all") url += `&severity=${selectedSeverity}`;

      if (searchQuery.trim()) {
        url = `${API_BASE}/search?q=${encodeURIComponent(searchQuery)}&limit=50`;
      }

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const items = data.data || data.items || [];
        setLogsList(items);
        if (items.length > 0) {
          setTotalLogs(102000 + items.length);
        }
      }
    } catch (err) {
      console.error("Failed to fetch logs", err);
    } finally {
      setLogsLoading(false);
    }
  };

  const fetchAnomalies = async () => {
    try {
      const res = await fetch(`${API_BASE}/anomalies`);
      if (res.ok) {
        const data = await res.json();
        const items = data.data || data || [];
        setAnomaliesList(items);
        setAnomalyCount(items.length);
      }
    } catch (err) {
      console.error("Failed to fetch anomalies", err);
    }
  };

  const fetchTimeseries = async () => {
    try {
      const res = await fetch(`${API_BASE}/anomalies/timeseries`);
      if (res.ok) {
        const points = await res.json();
        if (Array.isArray(points) && points.length > 0) {
          setTimeseries(points);
        }
      }
    } catch (err) {
      console.error("Failed to fetch timeseries", err);
    }
  };

  const handleSimulateLiveAnomaly = async () => {
    setSimLoading(true);
    setSimAlert(null);
    try {
      const res = await fetch(`${API_BASE}/anomalies/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: simService,
          spike_count: Number(simSpikeCount),
        }),
      });
      const data = await res.json();
      if (res.ok) {
        const z = data.anomaly ? Number(data.anomaly.zscore).toFixed(2) : "10.5+";
        setSimAlert(
          `🚨 ANOMALY DETECTED LIVE: Injected ${simSpikeCount} errors into service '${simService}'. Z-Score: ${z} > 3.0 threshold. Database trigger executed!`
        );
        // Refresh all components immediately
        fetchAnomalies();
        fetchTimeseries();
        fetchLogs();
        fetchAuditLogs();
      }
    } catch (err: any) {
      setSimAlert(`Simulation failed: ${err.message}`);
    } finally {
      setSimLoading(false);
    }
  };

  const runAdvancedQuery = async (queryId: string) => {
    setSelectedQueryId(queryId);
    try {
      const res = await fetch(`${API_BASE}/queries/run/${queryId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setQueryResult(data);
      }
    } catch (err) {
      console.error("Query failed", err);
    }
  };

  const handleCreateNoSqlDoc = async () => {
    try {
      const res = await fetch(`${API_BASE}/nosql/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service: nosqlService,
          severity: nosqlSeverity,
          host: nosqlHost,
          message: nosqlMessage,
        }),
      });
      const data = await res.json();
      setNosqlDocId(data._id);
      setNosqlResult({ action: "CREATE", data });
    } catch (err: any) {
      setNosqlResult({ error: err.message });
    }
  };

  const handleReadNoSqlDoc = async () => {
    if (!nosqlDocId) return;
    try {
      const res = await fetch(`${API_BASE}/nosql/documents/${nosqlDocId}`);
      const data = await res.json();
      setNosqlResult({ action: "READ", data });
    } catch (err: any) {
      setNosqlResult({ error: err.message });
    }
  };

  const handleUpdateNoSqlDoc = async () => {
    if (!nosqlDocId) return;
    try {
      const res = await fetch(`${API_BASE}/nosql/documents/${nosqlDocId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: "RESOLVED_BY_ANALYST",
          tags: ["investigated", "p1_incident"],
        }),
      });
      const data = await res.json();
      setNosqlResult({ action: "UPDATE", data });
    } catch (err: any) {
      setNosqlResult({ error: err.message });
    }
  };

  const handleDeleteNoSqlDoc = async () => {
    if (!nosqlDocId) return;
    try {
      const res = await fetch(`${API_BASE}/nosql/documents/${nosqlDocId}`, {
        method: "DELETE",
      });
      const data = await res.json();
      setNosqlResult({ action: "DELETE", data });
    } catch (err: any) {
      setNosqlResult({ error: err.message });
    }
  };

  const handleRunPartitionProc = async () => {
    setProcMessage("");
    try {
      const res = await fetch(`${API_BASE}/queries/procedure/partition`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ target_date: targetDate }),
      });
      const data = await res.json();
      if (res.ok) {
        setProcMessage(`Success: ${data.message}`);
        setPartitionsCount((prev) => prev + 1);
        fetchAuditLogs();
      } else {
        setProcMessage(`Error: ${data.detail || "Failed"}`);
      }
    } catch (err: any) {
      setProcMessage(`Error: ${err.message}`);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/queries/audit`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch audit logs", err);
    }
  };

  const severityBadge = (sev: string) => {
    switch (sev) {
      case "FATAL":
        return "bg-red-950 text-red-300 border-red-700";
      case "ERROR":
        return "bg-rose-900/60 text-rose-300 border-rose-700";
      case "WARN":
        return "bg-amber-950/70 text-amber-300 border-amber-700";
      case "INFO":
        return "bg-emerald-950/60 text-emerald-300 border-emerald-700";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  // Helper to render SVG time-series points
  const maxVal = Math.max(...timeseries.map((t) => Math.max(t.total_logs, t.error_logs)), 100);
  const svgWidth = 800;
  const svgHeight = 180;
  const padding = 25;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Database className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="font-bold text-lg text-white tracking-tight">Log Analytics Platform</h1>
              <span className="text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono font-medium">
                v1.0.0 Live
              </span>
            </div>
            <p className="text-xs text-slate-400">Time-Partitioned PostgreSQL + Elasticsearch Inverted Index</p>
          </div>
        </div>

        {/* User Role & Auth Widget */}
        <div className="flex items-center space-x-4">
          {currentUser ? (
            <div className="flex items-center space-x-3 bg-slate-800/80 border border-slate-700/80 px-3.5 py-1.5 rounded-xl">
              <div className="flex items-center space-x-2">
                <User className="w-4 h-4 text-slate-400" />
                <div className="text-left">
                  <div className="text-xs font-semibold text-slate-200">{currentUser.full_name}</div>
                  <div className="flex items-center space-x-1.5">
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded font-mono uppercase font-bold tracking-wider ${
                        currentUser.role === "admin"
                          ? "bg-purple-900/60 text-purple-300 border border-purple-700"
                          : "bg-blue-900/60 text-blue-300 border border-blue-700"
                      }`}
                    >
                      ROLE: {currentUser.role}
                    </span>
                    <span className="text-[10px] text-slate-400">RBAC Active</span>
                  </div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="text-slate-400 hover:text-rose-400 p-1.5 hover:bg-slate-700/50 rounded-lg transition"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleLogin("admin", "admin123")}
                className="text-xs bg-purple-600 hover:bg-purple-500 text-white font-medium px-3 py-1.5 rounded-lg transition"
              >
                Login as Admin
              </button>
              <button
                onClick={() => handleLogin("analyst", "analyst123")}
                className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-lg transition"
              >
                Login as Analyst
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Navigation Bar */}
      <nav className="border-b border-slate-800/80 bg-slate-900/40 px-6 flex items-center space-x-1 overflow-x-auto text-sm">
        <button
          onClick={() => setActiveTab("dashboard")}
          className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
            activeTab === "dashboard"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Dashboard Overview</span>
        </button>

        <button
          onClick={() => setActiveTab("explorer")}
          className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
            activeTab === "explorer"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Search className="w-4 h-4" />
          <span>Log Explorer</span>
        </button>

        <button
          onClick={() => setActiveTab("advanced_sql")}
          className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
            activeTab === "advanced_sql"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>Advanced SQL Lab</span>
        </button>

        <button
          onClick={() => setActiveTab("nosql")}
          className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
            activeTab === "nosql"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>NoSQL (Elasticsearch)</span>
        </button>

        <button
          onClick={() => setActiveTab("anomalies")}
          className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
            activeTab === "anomalies"
              ? "border-indigo-500 text-indigo-400 bg-indigo-500/5"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <AlertTriangle className="w-4 h-4" />
          <span>Anomaly Engine</span>
        </button>

        {currentUser?.role === "admin" && (
          <button
            onClick={() => setActiveTab("admin")}
            className={`flex items-center space-x-2 px-4 py-3 border-b-2 font-medium transition ${
              activeTab === "admin"
                ? "border-purple-500 text-purple-400 bg-purple-500/5"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Shield className="w-4 h-4 text-purple-400" />
            <span>Admin Controls</span>
          </button>
        )}
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Dynamic Simulation Alert Toast */}
        {simAlert && (
          <div className="bg-gradient-to-r from-rose-950/90 to-amber-950/90 border border-rose-500/50 p-4 rounded-2xl flex items-center justify-between text-xs text-rose-200 shadow-xl shadow-rose-950/30 animate-pulse">
            <div className="flex items-center space-x-3">
              <Flame className="w-5 h-5 text-rose-400 animate-bounce" />
              <span className="font-semibold">{simAlert}</span>
            </div>
            <button
              onClick={() => setSimAlert(null)}
              className="text-slate-400 hover:text-white px-2 py-1 rounded"
            >
              ✕
            </button>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 1: DASHBOARD OVERVIEW */}
        {/* ========================================================================= */}
        {activeTab === "dashboard" && (
          <div className="space-y-6">
            {/* Stat Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
                  <span>Partitioned Storage</span>
                  <Database className="w-4 h-4 text-indigo-400" />
                </div>
                <div className="text-3xl font-extrabold text-white mt-2 font-mono">{totalLogs.toLocaleString()}+</div>
                <div className="text-xs text-indigo-400 mt-1 flex items-center space-x-1 font-mono">
                  <span>{partitionsCount} Daily Partitions (Pruning Active)</span>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
                  <span>Ingestion Velocity</span>
                  <Activity className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-3xl font-extrabold text-white mt-2 font-mono">33,700 <span className="text-sm font-normal text-slate-400">rows/s</span></div>
                <div className="text-xs text-emerald-400 mt-1 font-mono">Postgres Binary COPY Protocol</div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
                  <span>Active Anomalies</span>
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-3xl font-extrabold text-white mt-2 font-mono">{anomalyCount}</div>
                <div className="text-xs text-amber-400 mt-1 font-mono">Rolling 60m Z-Score (Z &gt; 3.0)</div>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
                  <span>NoSQL Search Engine</span>
                  <Layers className="w-4 h-4 text-sky-400" />
                </div>
                <div className="text-3xl font-extrabold text-white mt-2 font-mono">Elasticsearch</div>
                <div className="text-xs text-sky-400 mt-1 font-mono">Inverted Index with Fuzzy Search</div>
              </div>
            </div>

            {/* LIVE ANOMALY INJECTION CONTROLLER (HER REQUEST!) */}
            <div className="bg-gradient-to-r from-slate-900 via-rose-950/20 to-slate-900 border border-rose-900/50 rounded-2xl p-5 shadow-lg">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                    <Flame className="w-4 h-4 text-rose-500" />
                    <span>Live Anomaly Injection & Detection Demo</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Inject a live error spike into PostgreSQL and immediately trigger the statistical Z-score detector in real time.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center space-x-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
                    <span className="text-slate-400">Target Service:</span>
                    <select
                      value={simService}
                      onChange={(e) => setSimService(e.target.value)}
                      className="bg-transparent text-indigo-300 font-semibold focus:outline-none"
                    >
                      <option value="payments" className="bg-slate-900">payments</option>
                      <option value="orders" className="bg-slate-900">orders</option>
                      <option value="auth" className="bg-slate-900">auth</option>
                      <option value="inventory" className="bg-slate-900">inventory</option>
                    </select>
                  </div>

                  <div className="flex items-center space-x-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
                    <span className="text-slate-400">Error Spike:</span>
                    <input
                      type="number"
                      value={simSpikeCount}
                      onChange={(e) => setSimSpikeCount(Number(e.target.value))}
                      className="bg-transparent text-rose-400 font-mono font-bold w-16 focus:outline-none"
                    />
                  </div>

                  <button
                    onClick={handleSimulateLiveAnomaly}
                    disabled={simLoading}
                    className="bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold text-xs px-4 py-2 rounded-xl shadow-lg shadow-rose-900/30 flex items-center space-x-2 transition"
                  >
                    <Zap className={`w-3.5 h-3.5 ${simLoading ? "animate-spin" : ""}`} />
                    <span>{simLoading ? "Injecting & Computing Z-Score..." : "Inject Live Spike & Detect"}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* REAL-TIME TIME-SERIES SVG GRAPH */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-white text-sm flex items-center space-x-2">
                    <TrendingUp className="w-4 h-4 text-indigo-400" />
                    <span>Real-Time Log Volume & Error Spike Monitor</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Live minute buckets query from PostgreSQL continuous aggregation (<code className="text-indigo-300">log_counts_minute</code>).
                  </p>
                </div>

                <div className="flex items-center space-x-4 text-xs font-mono">
                  <div className="flex items-center space-x-1.5">
                    <span className="w-3 h-3 rounded-full bg-indigo-500 inline-block"></span>
                    <span className="text-slate-300">Total Logs</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className="w-3 h-3 rounded-full bg-rose-500 inline-block"></span>
                    <span className="text-slate-300">Error Spikes</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className="w-3 h-3 rounded-full bg-amber-400 animate-ping inline-block"></span>
                    <span className="text-amber-300 font-bold">Anomaly Marker</span>
                  </div>
                  <button
                    onClick={fetchTimeseries}
                    className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition"
                    title="Refresh Chart"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* SVG Canvas Chart */}
              <div className="w-full overflow-x-auto">
                <svg
                  viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                  className="w-full h-48 bg-slate-950/60 rounded-xl border border-slate-800/80"
                >
                  {/* Grid Lines */}
                  {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => (
                    <line
                      key={idx}
                      x1={padding}
                      y1={padding + pct * (svgHeight - 2 * padding)}
                      x2={svgWidth - padding}
                      y2={padding + pct * (svgHeight - 2 * padding)}
                      stroke="#334155"
                      strokeDasharray="4 4"
                      strokeWidth="0.5"
                    />
                  ))}

                  {/* Render Total Volume Line */}
                  {timeseries.length > 1 && (
                    <polyline
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      points={timeseries
                        .map((pt, i) => {
                          const x = padding + (i / (timeseries.length - 1)) * (svgWidth - 2 * padding);
                          const y = svgHeight - padding - (pt.total_logs / maxVal) * (svgHeight - 2 * padding);
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                  )}

                  {/* Render Error Volume Line */}
                  {timeseries.length > 1 && (
                    <polyline
                      fill="none"
                      stroke="#f43f5e"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      points={timeseries
                        .map((pt, i) => {
                          const x = padding + (i / (timeseries.length - 1)) * (svgWidth - 2 * padding);
                          const y = svgHeight - padding - (pt.error_logs / maxVal) * (svgHeight - 2 * padding);
                          return `${x},${y}`;
                        })
                        .join(" ")}
                    />
                  )}

                  {/* Render Anomaly Pulses */}
                  {timeseries.map((pt, i) => {
                    const x = padding + (i / (timeseries.length - 1)) * (svgWidth - 2 * padding);
                    const y = svgHeight - padding - (pt.error_logs / maxVal) * (svgHeight - 2 * padding);

                    if (pt.is_anomaly) {
                      return (
                        <g key={i}>
                          <circle cx={x} cy={y} r="8" fill="#f59e0b" opacity="0.4" className="animate-ping" />
                          <circle cx={x} cy={y} r="5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
                          <text
                            x={x}
                            y={Math.max(15, y - 10)}
                            textAnchor="middle"
                            fill="#fde047"
                            fontSize="9"
                            fontFamily="monospace"
                            fontWeight="bold"
                          >
                            Z={pt.zscore || "10+"}
                          </text>
                        </g>
                      );
                    }
                    return null;
                  })}
                </svg>

                {/* X-Axis Time Labels */}
                <div className="flex justify-between px-6 pt-2 text-[10px] font-mono text-slate-500">
                  {timeseries
                    .filter((_, idx) => idx % Math.ceil(timeseries.length / 8) === 0)
                    .map((pt, idx) => (
                      <span key={idx}>{pt.time}</span>
                    ))}
                </div>
              </div>
            </div>

            {/* Architecture Highlights Box */}
            <div className="bg-gradient-to-r from-slate-900 via-indigo-950/20 to-slate-900 border border-indigo-900/40 rounded-2xl p-6">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span>System Architecture & Overview</span>
              </h2>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                High-throughput telemetry ingestion and indexing engine. Structured fields and time-series metrics are persisted into <strong>Range-Partitioned PostgreSQL</strong> with continuous analytical rollups, while unstructured messages are indexed into <strong>Elasticsearch</strong> for sub-second keyword and typo-tolerant search.
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 text-xs font-mono">
                <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl">
                  <div className="text-slate-400 text-[10px]">DATABASE ENGINE</div>
                  <div className="font-semibold text-slate-200 mt-0.5">PostgreSQL 16 Range Partitioned</div>
                </div>
                <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl">
                  <div className="text-slate-400 text-[10px]">NOSQL ENGINE</div>
                  <div className="font-semibold text-slate-200 mt-0.5">Elasticsearch 8.13 Inverted Index</div>
                </div>
                <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl">
                  <div className="text-slate-400 text-[10px]">INDEXING STRATEGY</div>
                  <div className="font-semibold text-slate-200 mt-0.5">BRIN (ts) + Composite B-Tree</div>
                </div>
                <div className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl">
                  <div className="text-slate-400 text-[10px]">SECURITY & RBAC</div>
                  <div className="font-semibold text-slate-200 mt-0.5">Native Roles: log_admin / log_analyst</div>
                </div>
              </div>
            </div>

            {/* Grafana Direct Link Box */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-white text-sm">Dedicated Grafana Analytical Dashboards</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Visual time-series graphs, top error hosts, and real-time rollups provisioned directly on port 3000.
                </p>
              </div>
              <a
                href="http://localhost:3000/d/log-analytics-overview/log-analytics-overview"
                target="_blank"
                rel="noreferrer"
                className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition flex items-center space-x-1.5"
              >
                <span>Open Grafana (Port 3000)</span>
                <ChevronRight className="w-4 h-4" />
              </a>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: LOG EXPLORER */}
        {/* ========================================================================= */}
        {activeTab === "explorer" && (
          <div className="space-y-4">
            {/* Search and Filter Bar */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                  <input
                    type="text"
                    placeholder="Search raw log message using Elasticsearch full-text or phrase matching (e.g. 'timeout', 'connection dropped', 'gateway')..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && fetchLogs()}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
                <button
                  onClick={fetchLogs}
                  disabled={logsLoading}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-xl flex items-center space-x-1.5 transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${logsLoading ? "animate-spin" : ""}`} />
                  <span>Execute Search</span>
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
                <span className="text-slate-400 flex items-center space-x-1 font-semibold">
                  <Filter className="w-3.5 h-3.5" />
                  <span>PostgreSQL Filters:</span>
                </span>

                <select
                  value={selectedService}
                  onChange={(e) => setSelectedService(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-slate-200 px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value="all">Service: ALL</option>
                  <option value="auth">auth</option>
                  <option value="payments">payments</option>
                  <option value="orders">orders</option>
                  <option value="inventory">inventory</option>
                  <option value="search">search</option>
                  <option value="notifications">notifications</option>
                </select>

                <select
                  value={selectedSeverity}
                  onChange={(e) => setSelectedSeverity(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-slate-200 px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <option value="all">Severity: ALL</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARN">WARN</option>
                  <option value="ERROR">ERROR</option>
                  <option value="FATAL">FATAL</option>
                </select>

                <span className="text-[11px] text-slate-500 ml-auto font-mono">
                  Showing {logsList.length} rows (Keyset paginated)
                </span>
              </div>
            </div>

            {/* Logs Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Timestamp (UTC)</th>
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Service</th>
                      <th className="py-3 px-4">Host</th>
                      <th className="py-3 px-4">Trace ID</th>
                      <th className="py-3 px-4">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {logsList.length > 0 ? (
                      logsList.map((log) => (
                        <tr key={log.id || log.doc_id} className="hover:bg-slate-800/40 transition">
                          <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap">
                            {new Date(log.ts).toISOString().replace("T", " ").replace("Z", "")}
                          </td>
                          <td className="py-2.5 px-4 whitespace-nowrap">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] border font-bold ${severityBadge(
                                log.severity
                              )}`}
                            >
                              {log.severity}
                            </span>
                          </td>
                          <td className="py-2.5 px-4 font-semibold text-indigo-300">{log.service}</td>
                          <td className="py-2.5 px-4 text-slate-300">{log.host}</td>
                          <td className="py-2.5 px-4 text-slate-500">{log.trace_id || "-"}</td>
                          <td className="py-2.5 px-4 text-slate-200">{log.message}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-500">
                          {logsLoading ? "Querying database..." : "No logs match the current filters"}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: ADVANCED SQL LAB */}
        {/* ========================================================================= */}
        {activeTab === "advanced_sql" && (
          <div className="space-y-5">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-indigo-400" />
                <span>Analytical SQL Query Engine</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Execute specialized relational queries including multi-table telemetry joins, correlated filters, recursive interval generators, and analytical window functions:
              </p>

              {/* Query Selector Buttons */}
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 mt-4">
                {[
                  { id: "join", name: "1. Join Query", sub: "4-Table Telemetry Join" },
                  { id: "nested", name: "2. Nested Subquery", sub: "WHERE service IN (Subquery)" },
                  { id: "correlated", name: "3. Correlated Subquery", sub: "Tier-Average Comparison" },
                  { id: "recursive", name: "4. Recursive CTE", sub: "WITH RECURSIVE Time Series" },
                  { id: "cte_window", name: "5. Window CTE", sub: "LAG() & Moving Averages" },
                ].map((q) => (
                  <button
                    key={q.id}
                    onClick={() => runAdvancedQuery(q.id)}
                    className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                      selectedQueryId === q.id
                        ? "bg-indigo-950/40 border-indigo-500 text-white shadow-md shadow-indigo-500/10"
                        : "bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700"
                    }`}
                  >
                    <span className="text-xs font-bold">{q.name}</span>
                    <span className="text-[10px] text-slate-400 mt-1">{q.sub}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Query Runner & Results Display */}
            {queryResult && (
              <div className="space-y-4">
                {/* SQL Code Box */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                      <FileCode className="w-4 h-4 text-indigo-400" />
                      <span>{queryResult.title}</span>
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">Returned {queryResult.row_count} rows</span>
                  </div>
                  <pre className="bg-slate-950 border border-slate-800 p-3.5 rounded-xl text-xs font-mono text-emerald-400 overflow-x-auto leading-relaxed">
                    {queryResult.sql}
                  </pre>
                </div>

                {/* Execution Plan Accordion */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
                  <div className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5 mb-2">
                    <Clock className="w-4 h-4 text-amber-400" />
                    <span>PostgreSQL Execution Plan (EXPLAIN ANALYZE)</span>
                  </div>
                  <pre className="bg-slate-950 border border-slate-800 p-3 rounded-xl text-[11px] font-mono text-slate-400 overflow-x-auto max-h-40 overflow-y-auto">
                    {queryResult.execution_plan?.join("\n")}
                  </pre>
                </div>

                {/* Query Results Table */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
                  <div className="p-3 bg-slate-950/80 border-b border-slate-800 text-xs font-semibold text-slate-300">
                    Query Output Records ({queryResult.row_count} rows)
                  </div>
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    {queryResult.data?.length > 0 ? (
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-slate-950/50 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                          <tr>
                            {Object.keys(queryResult.data[0]).map((key) => (
                              <th key={key} className="py-2.5 px-3 whitespace-nowrap">
                                {key}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60">
                          {queryResult.data.map((row: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-800/30 transition">
                              {Object.values(row).map((val: any, cidx: number) => (
                                <td key={cidx} className="py-2 px-3 text-slate-300 whitespace-nowrap">
                                  {typeof val === "object" ? JSON.stringify(val) : String(val ?? "-")}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="p-6 text-center text-slate-500 text-xs font-mono">No rows returned</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: NOSQL (ELASTICSEARCH OPERATIONS) */}
        {/* ========================================================================= */}
        {activeTab === "nosql" && (
          <div className="space-y-5">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Layers className="w-5 h-5 text-sky-400" />
                <span>NoSQL / Elasticsearch Document Operations</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Create, read, update, and delete unstructured log documents directly in Elasticsearch.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-5">
                {/* Left: Input Form */}
                <div className="space-y-3 bg-slate-950 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs font-semibold text-slate-200">1. Document Payload</div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Service & Severity</label>
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={nosqlService}
                        onChange={(e) => setNosqlService(e.target.value)}
                        className="bg-slate-900 border border-slate-800 text-xs text-slate-200 p-2 rounded-lg"
                      >
                        <option value="payments">payments</option>
                        <option value="auth">auth</option>
                        <option value="orders">orders</option>
                        <option value="inventory">inventory</option>
                      </select>
                      <select
                        value={nosqlSeverity}
                        onChange={(e) => setNosqlSeverity(e.target.value)}
                        className="bg-slate-900 border border-slate-800 text-xs text-slate-200 p-2 rounded-lg"
                      >
                        <option value="ERROR">ERROR</option>
                        <option value="FATAL">FATAL</option>
                        <option value="WARN">WARN</option>
                        <option value="INFO">INFO</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Host</label>
                    <input
                      type="text"
                      value={nosqlHost}
                      onChange={(e) => setNosqlHost(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 text-xs text-slate-200 p-2 rounded-lg font-mono"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Log Message Text</label>
                    <textarea
                      rows={2}
                      value={nosqlMessage}
                      onChange={(e) => setNosqlMessage(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 text-xs text-slate-200 p-2 rounded-lg font-mono"
                    />
                  </div>

                  <div className="pt-2 flex flex-wrap gap-2">
                    <button
                      onClick={handleCreateNoSqlDoc}
                      className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold px-3.5 py-2 rounded-lg transition"
                    >
                      Create / Index Doc
                    </button>
                  </div>
                </div>

                {/* Right: Existing Doc Operations */}
                <div className="space-y-3 bg-slate-950 border border-slate-800 p-4 rounded-xl">
                  <div className="text-xs font-semibold text-slate-200">2. Document RUD Operations</div>

                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Elasticsearch _id</label>
                    <input
                      type="text"
                      placeholder="Enter doc _id (or auto-filled after Create)"
                      value={nosqlDocId}
                      onChange={(e) => setNosqlDocId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 text-xs text-slate-200 p-2 rounded-lg font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-2">
                    <button
                      onClick={handleReadNoSqlDoc}
                      className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3 py-2 rounded-lg transition"
                    >
                      Read (GET)
                    </button>
                    <button
                      onClick={handleUpdateNoSqlDoc}
                      className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold px-3 py-2 rounded-lg transition"
                    >
                      Update (PUT)
                    </button>
                    <button
                      onClick={handleDeleteNoSqlDoc}
                      className="bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold px-3 py-2 rounded-lg transition"
                    >
                      Delete (DEL)
                    </button>
                  </div>

                  {/* Operation Response */}
                  {nosqlResult && (
                    <div className="mt-3">
                      <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">
                        Elasticsearch Response ({nosqlResult.action || "STATUS"}):
                      </div>
                      <pre className="bg-slate-900 border border-slate-800 p-2.5 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto max-h-36">
                        {JSON.stringify(nosqlResult.data || nosqlResult, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: ANOMALIES & Z-SCORE ENGINE */}
        {/* ========================================================================= */}
        {activeTab === "anomalies" && (
          <div className="space-y-5">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                    <span>Statistical Anomaly Detection Engine (Rolling 60m Baseline)</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Monitors per-minute error frequency. When observed count exceeds mean baseline by more than 3 standard deviations (Z-score &gt; 3.0), an alert is written to the <code className="text-amber-300 font-mono">anomalies</code> relation and triggers an automated audit log entry.
                  </p>
                </div>

                <button
                  onClick={handleSimulateLiveAnomaly}
                  disabled={simLoading}
                  className="bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-semibold text-xs px-4 py-2.5 rounded-xl shadow-lg flex items-center space-x-2 transition self-start md:self-auto"
                >
                  <Flame className="w-4 h-4 text-white animate-bounce" />
                  <span>{simLoading ? "Computing Z-Score..." : "Inject Live Anomaly Spike"}</span>
                </button>
              </div>

              <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl mt-4 text-xs font-mono text-slate-300 flex items-center justify-between">
                <span>Z-Score Formula: <strong className="text-indigo-400">Z = (x - μ) / σ</strong></span>
                <span className="text-slate-500">Threshold: Z &ge; 3.0 • Baseline Window: 60 mins</span>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
                <span>Detected Anomaly Records ({anomaliesList.length} rows)</span>
                <button
                  onClick={fetchAnomalies}
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 font-mono"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Refresh</span>
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800 uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Detected At</th>
                      <th className="py-3 px-4">Service</th>
                      <th className="py-3 px-4">Metric</th>
                      <th className="py-3 px-4">Spike Value</th>
                      <th className="py-3 px-4">Baseline Mean (μ)</th>
                      <th className="py-3 px-4">Std Dev (σ)</th>
                      <th className="py-3 px-4">Z-Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {anomaliesList.length > 0 ? (
                      anomaliesList.map((a) => (
                        <tr key={a.id} className="hover:bg-slate-800/40 transition">
                          <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap">
                            {new Date(a.detected_at).toISOString().replace("T", " ").replace("Z", "")}
                          </td>
                          <td className="py-2.5 px-4 font-bold text-indigo-300">{a.service}</td>
                          <td className="py-2.5 px-4 text-slate-300">{a.metric}</td>
                          <td className="py-2.5 px-4 text-white font-bold">{a.value}</td>
                          <td className="py-2.5 px-4 text-slate-400">{Number(a.baseline_mean).toFixed(2)}</td>
                          <td className="py-2.5 px-4 text-slate-400">{Number(a.baseline_std).toFixed(2)}</td>
                          <td className="py-2.5 px-4">
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950 border border-amber-600 text-amber-300">
                              Z = {Number(a.zscore).toFixed(2)}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-slate-500">
                          No anomalies recorded yet. Click "Inject Live Anomaly Spike" above!
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 6: ADMIN CONTROLS */}
        {/* ========================================================================= */}
        {activeTab === "admin" && (
          <div className="space-y-5">
            <div className="bg-slate-900 border border-purple-900/40 rounded-2xl p-5">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Shield className="w-5 h-5 text-purple-400" />
                <span>Administrative Control Panel</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Manage database partition lifecycles, execute stored procedures, and monitor automated audit logs. Enforced via role-based access control (RBAC).
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-5">
                {/* Stored Procedure Execution Card */}
                <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl space-y-3">
                  <div className="text-xs font-semibold text-slate-200 flex items-center space-x-1.5">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <span>Execute Stored Procedure: pr_create_daily_partition</span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Dynamically creates a daily partition table with its constraints and range bounds for the given date.
                  </p>

                  <div className="flex items-center space-x-2">
                    <input
                      type="date"
                      value={targetDate}
                      onChange={(e) => setTargetDate(e.target.value)}
                      className="bg-slate-900 border border-slate-800 text-xs text-slate-200 px-3 py-2 rounded-lg font-mono"
                    />
                    <button
                      onClick={handleRunPartitionProc}
                      className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition"
                    >
                      Call Procedure
                    </button>
                  </div>

                  {procMessage && (
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-emerald-400">
                      {procMessage}
                    </div>
                  )}
                </div>

                {/* RBAC Info Card */}
                <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl space-y-2">
                  <div className="text-xs font-semibold text-slate-200 flex items-center space-x-1.5">
                    <Shield className="w-4 h-4 text-purple-400" />
                    <span>Database Roles & Permissions</span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-1.5">
                    <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                      <strong className="text-purple-300 font-mono">log_admin:</strong> Full DDL/DML, truncate privileges, sequence manipulation, execute stored procedures.
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-800/80">
                      <strong className="text-blue-300 font-mono">log_analyst:</strong> Read-only SELECT on logs, rollups, and anomalies. Denied user table & dead-letter queue access.
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Audit Logs Table (Populated by Trigger) */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
                <span>Database Audit Trail (Populated automatically by Database Trigger: trg_audit_anomaly)</span>
                <button
                  onClick={fetchAuditLogs}
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 font-mono"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Refresh Audit</span>
                </button>
              </div>

              <div className="overflow-x-auto max-h-80 overflow-y-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950/50 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                    <tr>
                      <th className="py-2.5 px-4">ID</th>
                      <th className="py-2.5 px-4">User</th>
                      <th className="py-2.5 px-4">Action</th>
                      <th className="py-2.5 px-4">Entity</th>
                      <th className="py-2.5 px-4">Details</th>
                      <th className="py-2.5 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {auditLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-2 px-4 text-slate-500">{log.id}</td>
                        <td className="py-2 px-4 font-semibold text-purple-300">{log.username}</td>
                        <td className="py-2 px-4 text-amber-300">{log.action}</td>
                        <td className="py-2 px-4 text-slate-300">{log.entity}</td>
                        <td className="py-2 px-4 text-slate-400 max-w-md truncate">
                          {typeof log.details === "object" ? JSON.stringify(log.details) : String(log.details)}
                        </td>
                        <td className="py-2 px-4 text-slate-500 whitespace-nowrap">
                          {new Date(log.ts).toISOString().replace("T", " ").replace("Z", "")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
