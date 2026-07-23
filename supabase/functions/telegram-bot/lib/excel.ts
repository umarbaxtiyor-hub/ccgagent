import * as XLSX from "npm:xlsx@0.18.5";
import type { ReportRow } from "./db.ts";

const DATE_COLS = ["sana", "date", "sanasi", "operatsiya sanasi"];
const AMOUNT_COLS = ["summa", "summasi", "amount", "miqdor", "sum"];
const DEBIT_COLS = ["chiqim", "debit", "xarajat", "debet"];
const CREDIT_COLS = ["kirim", "credit", "kredit", "daromad"];
const DESC_COLS = ["tavsif", "description", "izoh", "maqsad", "detail"];

export class BankImportError extends Error {}

export interface BankStatementRow {
  occurred_on: string;
  amount: number;
  type: "income" | "expense";
  raw_description: string;
}

function findColumn(headers: string[], candidates: string[]): number {
  const lowered = headers.map((h) => (h ?? "").toString().trim().toLowerCase());
  for (let i = 0; i < lowered.length; i++) {
    for (const cand of candidates) {
      if (lowered[i].includes(cand)) return i;
    }
  }
  return -1;
}

function excelSerialToDate(serial: number): Date {
  const utcDays = Math.floor(serial - 25569);
  return new Date(utcDays * 86400 * 1000);
}

function toDateString(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === "number") {
    return excelSerialToDate(value).toISOString().slice(0, 10);
  }
  const text = String(value).trim();
  const patterns: Array<[RegExp, (m: RegExpMatchArray) => string]> = [
    [/^(\d{2})\.(\d{2})\.(\d{4})/, (m) => `${m[3]}-${m[2]}-${m[1]}`],
    [/^(\d{4})-(\d{2})-(\d{2})/, (m) => `${m[1]}-${m[2]}-${m[3]}`],
    [/^(\d{2})\/(\d{2})\/(\d{4})/, (m) => `${m[3]}-${m[2]}-${m[1]}`],
  ];
  for (const [re, fmt] of patterns) {
    const m = text.match(re);
    if (m) return fmt(m);
  }
  const parsed = new Date(text);
  if (!isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return null;
}

function toFloat(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number") return value;
  const text = String(value).trim().replace(/\s/g, "").replace(",", ".");
  if (!text) return null;
  const num = parseFloat(text);
  return isNaN(num) ? null : num;
}

export function parseBankStatement(bytes: Uint8Array, filename: string): BankStatementRow[] {
  const isCsv = filename.toLowerCase().endsWith(".csv");
  const workbook = isCsv
    ? XLSX.read(new TextDecoder("utf-8").decode(bytes), { type: "string" })
    : XLSX.read(bytes, { type: "array" });

  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const grid: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: true });
  if (grid.length < 2) {
    throw new BankImportError("Faylda tranzaksiya qatorlari topilmadi.");
  }

  const headers = (grid[0] as unknown[]).map((h) => String(h ?? ""));
  const dateCol = findColumn(headers, DATE_COLS);
  const descCol = findColumn(headers, DESC_COLS);
  const debitCol = findColumn(headers, DEBIT_COLS);
  const creditCol = findColumn(headers, CREDIT_COLS);
  const amountCol = debitCol >= 0 && creditCol >= 0 ? -1 : findColumn(headers, AMOUNT_COLS);

  if (dateCol < 0) {
    throw new BankImportError(
      "Fayldan sana ustunini aniqlab bo'lmadi. Ustun nomlari orasida 'Sana'/'Date' bo'lishi kerak.",
    );
  }
  if (!(debitCol >= 0 && creditCol >= 0) && amountCol < 0) {
    throw new BankImportError(
      "Fayldan summa ustunlarini aniqlab bo'lmadi. 'Kirim'/'Chiqim' yoki 'Summa' ustuni kerak.",
    );
  }

  const rows: BankStatementRow[] = [];
  for (let i = 1; i < grid.length; i++) {
    const row = grid[i] as unknown[];
    if (!row || row.length === 0) continue;

    const occurredOn = toDateString(row[dateCol]);
    if (!occurredOn) continue;

    const description = descCol >= 0 ? String(row[descCol] ?? "").trim() : "";

    let amount: number;
    let type: "income" | "expense";
    if (debitCol >= 0 && creditCol >= 0) {
      const debitVal = toFloat(row[debitCol]);
      const creditVal = toFloat(row[creditCol]);
      if (debitVal) {
        amount = Math.abs(debitVal);
        type = "expense";
      } else if (creditVal) {
        amount = Math.abs(creditVal);
        type = "income";
      } else {
        continue;
      }
    } else {
      const value = toFloat(row[amountCol]);
      if (value === null || value === 0) continue;
      amount = Math.abs(value);
      type = value < 0 ? "expense" : "income";
    }

    rows.push({ occurred_on: occurredOn, amount, type, raw_description: description });
  }

  if (rows.length === 0) {
    throw new BankImportError("Faylda tranzaksiya qatorlari topilmadi.");
  }
  return rows;
}

interface CategoryTotal {
  projectName: string;
  typeLabel: string;
  category: string;
  total: number;
}

export function buildReportWorkbook(rows: ReportRow[]): Uint8Array {
  const wb = XLSX.utils.book_new();

  const sheetData: (string | number)[][] = [
    ["Sana", "Loyiha", "Turi", "Kategoriya", "Summasi", "Tavsif", "Kontragent", "Kim kiritdi"],
  ];
  let totalIncome = 0;
  let totalExpense = 0;
  const totalsByCategory = new Map<string, CategoryTotal>();

  for (const r of rows) {
    const typeLabel = r.type === "income" ? "Kirim" : "Chiqim";
    const projectName = r.project_name ?? "-";
    if (r.type === "income") {
      totalIncome += r.amount;
    } else {
      totalExpense += r.amount;
    }
    sheetData.push([
      r.occurred_on,
      projectName,
      typeLabel,
      r.category,
      r.amount,
      r.description,
      r.counterparty,
      r.full_name,
    ]);

    const key = projectName + "::" + typeLabel + "::" + r.category;
    const existing = totalsByCategory.get(key);
    if (existing) {
      existing.total += r.amount;
    } else {
      totalsByCategory.set(key, { projectName, typeLabel, category: r.category, total: r.amount });
    }
  }

  sheetData.push([]);
  sheetData.push(["", "", "", "Jami kirim", totalIncome]);
  sheetData.push(["", "", "", "Jami chiqim", totalExpense]);
  sheetData.push(["", "", "", "Balans", totalIncome - totalExpense]);

  const ws = XLSX.utils.aoa_to_sheet(sheetData);
  XLSX.utils.book_append_sheet(wb, ws, "Tranzaksiyalar");

  const summaryData: (string | number)[][] = [["Loyiha", "Turi", "Kategoriya", "Jami summa"]];
  const sortedEntries = [...totalsByCategory.values()].sort((a, b) =>
    (a.projectName + a.typeLabel + a.category).localeCompare(b.projectName + b.typeLabel + b.category)
  );
  for (const entry of sortedEntries) {
    summaryData.push([entry.projectName, entry.typeLabel, entry.category, entry.total]);
  }
  const summaryWs = XLSX.utils.aoa_to_sheet(summaryData);
  XLSX.utils.book_append_sheet(wb, summaryWs, "Kategoriyalar bo'yicha");

  const out = XLSX.write(wb, { type: "array", bookType: "xlsx" });
  return new Uint8Array(out);
}
