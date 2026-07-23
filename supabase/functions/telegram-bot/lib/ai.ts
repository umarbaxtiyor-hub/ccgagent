import { encodeBase64 } from "jsr:@std/encoding@1/base64";

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";

async function callClaude(
  apiKey: string,
  model: string,
  // deno-lint-ignore no-explicit-any
  body: Record<string, any>,
  // deno-lint-ignore no-explicit-any
): Promise<any> {
  const res = await fetch(ANTHROPIC_API_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({ model, ...body }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Anthropic API error ${res.status}: ${text}`);
  }
  return res.json();
}

// deno-lint-ignore no-explicit-any
function extractToolInput(message: any): any {
  for (const block of message.content) {
    if (block.type === "tool_use") return block.input;
  }
  throw new Error("No tool_use block in Anthropic response");
}

const TRANSACTION_TOOL = {
  name: "record_transaction",
  description:
    "Qurilish kompaniyasi uchun kirim yoki chiqim tranzaksiyasini tuzilgan ko'rinishda qaytaradi.",
  input_schema: {
    type: "object",
    properties: {
      type: {
        type: "string",
        enum: ["income", "expense"],
        description: "income = kirim (pul kelishi), expense = chiqim (xarajat)",
      },
      amount: {
        type: "number",
        description: "Summasi (faqat raqam, valyuta belgisisiz), so'mda",
      },
      category: {
        type: "string",
        description:
          "Berilgan kategoriyalar ro'yxatidan eng mos kelgani, aks holda 'Boshqa xarajat' yoki 'Boshqa daromad'",
      },
      description: {
        type: "string",
        description: "Qisqa tavsif (nima uchun to'lov/kirim)",
      },
      counterparty: {
        type: "string",
        description:
          "To'lov qilingan/qabul qilingan tomon (agar mavjud bo'lsa), aks holda bo'sh qatr",
      },
      occurred_on: {
        type: "string",
        description:
          "Sana YYYY-MM-DD formatida. Agar matnda sana ko'rsatilmagan bo'lsa, berilgan bugungi sanani ishlating.",
      },
      confidence: {
        type: "string",
        enum: ["high", "low"],
        description: "Agar matn tushunarsiz yoki summa aniq bo'lmasa 'low', aks holda 'high'",
      },
    },
    required: ["type", "amount", "category", "description", "occurred_on", "confidence"],
  },
};

export interface ParsedTransaction {
  type: "income" | "expense";
  amount: number;
  category: string;
  description: string;
  counterparty?: string;
  occurred_on: string;
  confidence: "high" | "low";
}

export async function parseExpenseText(
  apiKey: string,
  model: string,
  text: string,
  expenseCategories: string[],
  incomeCategories: string[],
  today: string,
): Promise<ParsedTransaction> {
  const prompt =
    `Bugungi sana: ${today}\n` +
    `Chiqim kategoriyalari: ${expenseCategories.join(", ")}\n` +
    `Kirim kategoriyalari: ${incomeCategories.join(", ")}\n\n` +
    `Quyidagi xabarni tahlil qil va record_transaction tool orqali natijani qaytar:\n"${text}"`;

  const message = await callClaude(apiKey, model, {
    max_tokens: 1024,
    tools: [TRANSACTION_TOOL],
    tool_choice: { type: "tool", name: "record_transaction" },
    messages: [{ role: "user", content: prompt }],
  });
  return extractToolInput(message);
}

export async function parseReceiptImage(
  apiKey: string,
  model: string,
  imageBytes: Uint8Array,
  mediaType: string,
  expenseCategories: string[],
  incomeCategories: string[],
  today: string,
): Promise<ParsedTransaction> {
  const b64Image = encodeBase64(imageBytes);
  const prompt =
    `Bugungi sana: ${today}\n` +
    `Chiqim kategoriyalari: ${expenseCategories.join(", ")}\n` +
    `Kirim kategoriyalari: ${incomeCategories.join(", ")}\n\n` +
    "Bu rasm - chek yoki to'lov kvitansiyasi. Undan summani, sanani va nimaga sarflanganini " +
    "aniqlab, record_transaction tool orqali natijani qaytar. Agar chekdagi sana o'qib bo'lmasa, " +
    "bugungi sanani ishlat.";

  const message = await callClaude(apiKey, model, {
    max_tokens: 1024,
    tools: [TRANSACTION_TOOL],
    tool_choice: { type: "tool", name: "record_transaction" },
    messages: [
      {
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: mediaType, data: b64Image } },
          { type: "text", text: prompt },
        ],
      },
    ],
  });
  return extractToolInput(message);
}

const BANK_ROW_TOOL = {
  name: "categorize_bank_rows",
  description: "Bank ko'chirmasidagi har bir qatorga kirim/chiqim kategoriyasini biriktiradi.",
  input_schema: {
    type: "object",
    properties: {
      results: {
        type: "array",
        items: {
          type: "object",
          properties: {
            row_index: { type: "integer" },
            category: { type: "string" },
            description: { type: "string" },
          },
          required: ["row_index", "category", "description"],
        },
      },
    },
    required: ["results"],
  },
};

export interface BankRowInput {
  row_index: number;
  type: "income" | "expense";
  amount: number;
  raw_description: string;
}

export async function categorizeBankRows(
  apiKey: string,
  model: string,
  rows: BankRowInput[],
  expenseCategories: string[],
  incomeCategories: string[],
): Promise<Map<number, { category: string; description: string }>> {
  const prompt =
    `Chiqim kategoriyalari: ${expenseCategories.join(", ")}\n` +
    `Kirim kategoriyalari: ${incomeCategories.join(", ")}\n\n` +
    "Quyidagi bank tranzaksiyalari ro'yxati berilgan (JSON). Har biriga eng mos kategoriyani " +
    "va qisqa tushunarli tavsifni tanla, keyin categorize_bank_rows tool orqali natijani qaytar:\n\n" +
    JSON.stringify(rows);

  const message = await callClaude(apiKey, model, {
    max_tokens: 4096,
    tools: [BANK_ROW_TOOL],
    tool_choice: { type: "tool", name: "categorize_bank_rows" },
    messages: [{ role: "user", content: prompt }],
  });
  const parsed = extractToolInput(message);
  const map = new Map<number, { category: string; description: string }>();
  for (const item of parsed.results) {
    map.set(item.row_index, { category: item.category, description: item.description });
  }
  return map;
}
