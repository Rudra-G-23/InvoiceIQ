/// <reference types="vite/client" />

import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { ClipboardList, FileUp, LayoutDashboard, ReceiptText, RefreshCw, Search, ShieldCheck, Store } from "lucide-react";
import "./styles.css";
import "./preview.css";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const STAGES = ["RECEIVED", "CLASSIFY_DOCUMENT", "TEXT_EXTRACTION", "AI_FIELD_EXTRACTION", "SCHEMA_VALIDATION", "VENDOR_MATCH", "PO_RECONCILIATION", "RULE_VALIDATION", "DECISION", "COMPLETED"];
const ACTIVE_RUN_STATUSES = new Set(["QUEUED", "RUNNING"]);

type Check = { code: string; status: string; explanation: string };
type Run = { id: string; status: string; stage: string; error?: string; events: { stage: string; status: string; occurred_at: string; detail?: string }[] };
type Document = { id: string; original_filename: string; mime_type: string; document_type: string; uploaded_at: string; decision_outcome?: string; run_id?: string; run_status?: string; run_stage?: string; stage_event_count?: number; extraction?: Record<string, unknown>; decision?: { outcome: string; reason_codes: string[]; explanation: string; checks: Check[] }; runs?: Run[] };

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Request failed");
  return response.json();
}

function Badge({ value }: { value?: string }) { return <span className={`badge ${value?.toLowerCase().replaceAll("_", "-") ?? "pending"}`}>{value?.replaceAll("_", " ") ?? "Processing"}</span>; }

function ProcessingRail() {
  const [active, setActive] = useState<Document>();
  useEffect(() => {
    let mounted = true;
    const refresh = async () => {
      try {
        const documents = await get<Document[]>("/documents");
        if (mounted) setActive(documents.find((document) => ACTIVE_RUN_STATUSES.has(document.run_status ?? "")));
      } catch { if (mounted) setActive(undefined); }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 1000);
    return () => { mounted = false; window.clearInterval(interval); };
  }, []);
  const stageIndex = active?.run_stage ? Math.max(STAGES.indexOf(active.run_stage), 0) : 0;
  const percent = active ? Math.round(((stageIndex + 1) / STAGES.length) * 100) : 0;
  return <section className={`processing-rail ${active ? "processing-rail-active" : ""}`} aria-live="polite"><p>LIVE PROCESSING</p><strong>{active ? active.original_filename : "Waiting for an upload"}</strong><span>{active ? active.run_stage?.replaceAll("_", " ") : "Idle"}</span><div className="processing-track"><i style={{ width: `${percent}%` }} /></div></section>;
}

function Shell({ children }: { children: React.ReactNode }) {
  const links = [["/", LayoutDashboard, "Dashboard"], ["/invoices", ReceiptText, "Invoices"], ["/reviews", ShieldCheck, "Review queue"], ["/vendors", Store, "Vendors"], ["/purchase-orders", ClipboardList, "Purchase orders"]] as const;
  return <div className="app-shell"><aside><Link className="brand" to="/"><span>IQ</span>InvoiceIQ</Link><p className="eyebrow">AP OPERATIONS</p><nav>{links.map(([to, Icon, label]) => <NavLink key={to} to={to} end={to === "/"}><Icon />{label}</NavLink>)}</nav><ProcessingRail /><div className="sidebar-note">Local single-user demo<br />No payment action is initiated.</div></aside><main><header><div><p className="eyebrow">DOCUMENT INTELLIGENCE</p><h1>Invoice operations</h1></div></header>{children}</main></div>;
}

function Dashboard() {
  const [data, setData] = useState<{ counts: Record<string, number>; recent: Document[] }>(); const [error, setError] = useState("");
  useEffect(() => { void get<typeof data>("/dashboard/summary").then(setData).catch((item: Error) => setError(item.message)); }, []);
  if (error) return <AppError message={error} />;
  const counts = data?.counts;
  return <><section className="metric-grid">{[["Processed", counts?.processed], ["Approved", counts?.approved], ["Needs review", counts?.needs_review], ["Blocked", counts?.blocked]].map(([label, value]) => <article className="metric" key={String(label)}><p>{label}</p><strong>{value ?? "-"}</strong></article>)}</section><section className="panel"><div className="section-heading"><div><p className="eyebrow">LIVE HISTORY</p><h2>Recent documents</h2></div><Link to="/invoices">View all</Link></div>{data?.recent.length ? <DocumentTable documents={data.recent} /> : <Empty text="No documents have been processed yet. Upload a PDF or image to begin." />}</section></>;
}

function DocumentTable({ documents }: { documents: Document[] }) { return <div className="table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Uploaded</th><th>Decision</th></tr></thead><tbody>{documents.map((document) => <tr key={document.id}><td><Link className="doc-link" to={`/invoices/${document.id}`}>{document.original_filename}</Link></td><td>{document.document_type.replaceAll("_", " ")}</td><td>{new Date(document.uploaded_at).toLocaleString()}</td><td><Badge value={document.decision_outcome ?? document.decision?.outcome} /></td></tr>)}</tbody></table></div>; }

function Invoices() {
  const navigate = useNavigate(); const [documents, setDocuments] = useState<Document[]>([]); const [message, setMessage] = useState(""); const [uploading, setUploading] = useState(false);
  const refresh = () => get<Document[]>("/documents").then(setDocuments).catch((error: Error) => setMessage(error.message));
  useEffect(() => { void refresh(); }, []);
  async function upload(file?: File) {
    if (!file) return;
    setUploading(true); setMessage("");
    const form = new FormData(); form.append("file", file);
    try {
      const response = await fetch(`${API}/documents`, { method: "POST", body: form });
      const body: { document_id: string } = await response.json();
      if (!response.ok) throw new Error("Upload failed");
      navigate(`/invoices/${body.document_id}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Upload failed"); }
    finally { setUploading(false); }
  }
  return <><section className="upload-card"><FileUp /><div><h2>Upload an invoice or receipt</h2><p>PDF, JPG, and PNG up to 10 MB. Uploading opens its live processing workspace.</p></div><label className="button primary"><input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => upload(event.target.files?.[0])} />{uploading ? "Uploading..." : "Choose file"}</label></section>{message && <p className="notice">{message}</p>}<section className="panel"><div className="section-heading"><div><p className="eyebrow">INBOX</p><h2>All documents</h2></div><button className="button secondary" onClick={() => void refresh()}><RefreshCw />Refresh</button></div>{documents.length ? <DocumentTable documents={documents} /> : <Empty text="Your inbox is empty." />}</section></>;
}

function Detail() {
  const { id } = useParams(); const [document, setDocument] = useState<Document>(); const [error, setError] = useState("");
  useEffect(() => {
    let mounted = true; let timer: number | undefined;
    const refresh = async () => {
      try {
        const next = await get<Document>(`/documents/${id}`);
        if (!mounted) return;
        setDocument(next); setError("");
        if (ACTIVE_RUN_STATUSES.has(next.runs?.[0]?.status ?? "")) timer = window.setTimeout(() => void refresh(), 1000);
      } catch (item) { if (mounted) setError(item instanceof Error ? item.message : "Request failed"); }
    };
    if (id) void refresh();
    return () => { mounted = false; if (timer) window.clearTimeout(timer); };
  }, [id]);
  if (error) return <AppError message={error} />;
  if (!document) return <p className="loading">Opening processing workspace...</p>;
  const extraction = document.extraction ?? {}; const run = document.runs?.[0]; const previewUrl = `${API}/documents/${document.id}/file`;
  return <div className="workspace"><section className="panel preview"><div className="section-heading"><h2>{document.original_filename}</h2><Badge value={document.decision?.outcome ?? run?.stage} /></div>{document.mime_type.startsWith("image/") ? <img src={previewUrl} alt={`Original ${document.original_filename}`} /> : <iframe title="Original document preview" src={previewUrl} />}<a className="text-link" href={previewUrl} target="_blank" rel="noreferrer">Open original document</a></section><section className="panel"><p className="eyebrow">NORMALIZED FIELDS</p><h2>Extracted invoice</h2><dl>{["vendor_raw_name", "invoice_number", "invoice_date", "po_reference", "currency", "grand_total", "cash_tendered", "change", "extraction_method"].map((key) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(extraction[key] ?? "Processing")}</dd></div>)}</dl><p className="eyebrow">DECISION</p><p>{document.decision?.explanation ?? "The document is processing. Fields and rule checks update from persisted workflow events."}</p>{document.decision?.reason_codes.map((reason) => <Badge key={reason} value={reason} />)}</section><section className="panel"><p className="eyebrow">PERSISTED TIMELINE</p><h2>{run?.stage?.replaceAll("_", " ") ?? "Queued"}</h2><ol className="timeline">{run?.events.map((event, index) => <li key={`${event.stage}-${index}`}><strong>{event.stage.replaceAll("_", " ")}</strong><span>{event.status} {event.detail ? `- ${event.detail}` : ""}</span></li>)}</ol><p className="eyebrow">RULE CHECKS</p>{document.decision?.checks.map((check) => <div className="check" key={check.code}><Badge value={check.status} /><div><strong>{check.code.replaceAll("_", " ")}</strong><p>{check.explanation}</p></div></div>)}</section></div>;
}

function Ledger({ path, title, columns }: { path: string; title: string; columns: string[] }) { const [rows, setRows] = useState<Record<string, string>[]>([]); const [error, setError] = useState(""); useEffect(() => { void get<Record<string, string>[]>(path).then(setRows).catch((item: Error) => setError(item.message)); }, [path]); if (error) return <AppError message={error} />; return <section className="panel"><p className="eyebrow">REFERENCE LEDGER</p><h2>{title}</h2>{rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map((column) => <td key={column}>{String(row[column] ?? "-")}</td>)}</tr>)}</tbody></table></div> : <Empty text="No ledger records available." />}</section>; }
function Reviews() { const [rows, setRows] = useState<Document[]>([]); const [error, setError] = useState(""); useEffect(() => { void get<Document[]>("/reviews").then(setRows).catch((item: Error) => setError(item.message)); }, []); if (error) return <AppError message={error} />; return <section className="panel"><p className="eyebrow">HUMAN REVIEW</p><h2>Cases requiring action</h2>{rows.length ? <DocumentTable documents={rows} /> : <Empty text="No review cases are currently open." />}</section>; }
function Empty({ text }: { text: string }) { return <div className="empty"><Search /><p>{text}</p></div>; }
function AppError({ message }: { message: string }) { return <section className="panel error"><h2>Could not reach InvoiceIQ</h2><p>{message}</p><p>Start the local backend at <code>127.0.0.1:8000</code> and refresh this view.</p></section>; }
function App() { return <BrowserRouter><Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/invoices" element={<Invoices />} /><Route path="/invoices/:id" element={<Detail />} /><Route path="/reviews" element={<Reviews />} /><Route path="/vendors" element={<Ledger path="/vendors" title="Vendors" columns={["id", "legal_name", "status", "currency"]} />} /><Route path="/purchase-orders" element={<Ledger path="/purchase-orders" title="Purchase orders" columns={["id", "vendor_id", "currency", "authorized_total", "approved_consumed", "remaining_balance", "status"]} />} /></Routes></Shell></BrowserRouter>; }

createRoot(document.getElementById("root")!).render(<App />);
