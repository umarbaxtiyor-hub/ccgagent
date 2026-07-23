import type { PendingTransaction, Project } from "./db.ts";

export function confirmKeyboard(pendingId: string) {
  return {
    inline_keyboard: [
      [
        { text: "Tasdiqlash", callback_data: `tx_confirm:${pendingId}` },
        { text: "Kategoriya", callback_data: `tx_category:${pendingId}` },
      ],
      [{ text: "Bekor qilish", callback_data: `tx_cancel:${pendingId}` }],
    ],
  };
}

export function categoryChoiceKeyboard(pendingId: string, categories: string[]) {
  const rows = [];
  for (let i = 0; i < categories.length; i += 2) {
    const chunk = categories.slice(i, i + 2);
    rows.push(
      chunk.map((name, j) => ({
        text: name,
        callback_data: `tx_setcat:${pendingId}:${i + j}`,
      })),
    );
  }
  rows.push([{ text: "Orqaga", callback_data: `tx_back:${pendingId}` }]);
  return { inline_keyboard: rows };
}

export function bankImportKeyboard(pendingId: string) {
  return {
    inline_keyboard: [
      [
        { text: "Barchasini saqlash", callback_data: `bank_confirm:${pendingId}` },
        { text: "Bekor qilish", callback_data: `bank_cancel:${pendingId}` },
      ],
    ],
  };
}

export function projectListKeyboard(projects: Project[]) {
  const rows = [];
  for (let i = 0; i < projects.length; i += 2) {
    const chunk = projects.slice(i, i + 2);
    rows.push(chunk.map((p) => ({ text: p.name, callback_data: `proj_select:${p.id}` })));
  }
  return { inline_keyboard: rows };
}

export function reportPeriodKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "Bugun", callback_data: "report:today" },
        { text: "Shu hafta", callback_data: "report:week" },
        { text: "Shu oy", callback_data: "report:month" },
      ],
    ],
  };
}

export function formatPending(p: Pick<PendingTransaction,
  "type" | "amount" | "category" | "occurred_on" | "description" | "counterparty" | "project_name">): string {
  const typeLabel = p.type === "income" ? "Kirim" : "Chiqim";
  const amountText = Math.round(p.amount).toLocaleString("uz-UZ").replace(/,/g, " ");
  const lines = [
    `<b>${typeLabel}</b>: ${amountText} so'm`,
    `Loyiha: ${p.project_name ?? "-"}`,
    `Kategoriya: ${p.category}`,
    `Sana: ${p.occurred_on}`,
    `Tavsif: ${p.description || "-"}`,
  ];
  if (p.counterparty) {
    lines.push(`Kontragent: ${p.counterparty}`);
  }
  lines.push("", "Tasdiqlaysizmi?");
  return lines.join("\n");
}
