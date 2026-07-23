import {
  addPendingBankImport,
  addPendingTx,
  categoryNames,
  fetchReportRows,
  getOrCreateCategory,
  getOrCreateUser,
  getPendingTx,
  insertTransaction,
  isAllowedUser,
  loadConfig,
  popPendingBankImport,
  popPendingTx,
  setPendingTxCategory,
  type BotConfig,
} from "./lib/db.ts";
import {
  answerCallbackQuery,
  downloadFile,
  editMessageReplyMarkup,
  editMessageText,
  getFilePath,
  sendDocument,
  sendMessage,
} from "./lib/telegram.ts";
import { categorizeBankRows, parseExpenseText, parseReceiptImage } from "./lib/ai.ts";
import { BankImportError, buildReportWorkbook, parseBankStatement } from "./lib/excel.ts";
import {
  bankImportKeyboard,
  categoryChoiceKeyboard,
  confirmKeyboard,
  formatPending,
  reportPeriodKeyboard,
} from "./lib/keyboards.ts";

const WELCOME_TEXT =
  "Assalomu alaykum! Men qurilish kompaniyasi uchun xarajat/daromad hisobchi botman.\n\n" +
  "Nima qila olaman:\n" +
  "- Erkin matn yozing (masalan: \"Sement uchun 500000 so'm to'ladim\") - men summani, " +
  "kategoriyani va turini o'zim aniqlayman.\n" +
  "- Chek yoki kvitansiya rasmini yuboring - undan ma'lumotni o'zim o'qib olaman.\n" +
  "- Bank ko'chirmasi faylini (.xlsx yoki .csv) yuboring - barcha tranzaksiyalarni avtomatik " +
  "kategoriyalarga bo'lib qo'shaman.\n" +
  "- /report - kunlik/haftalik/oylik hisobotni Excel faylda olish.\n\n" +
  "Har bir yozuvni saqlashdan oldin tasdiqlashingizni so'rayman.";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function periodRange(period: string): [string, string] {
  const now = new Date();
  const end = todayStr();
  if (period === "today") return [end, end];
  if (period === "week") {
    const day = (now.getUTCDay() + 6) % 7; // Monday = 0
    const monday = new Date(now);
    monday.setUTCDate(now.getUTCDate() - day);
    return [monday.toISOString().slice(0, 10), end];
  }
  if (period === "month") {
    const first = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    return [first.toISOString().slice(0, 10), end];
  }
  return [end, end];
}

const PERIOD_LABELS: Record<string, string> = {
  today: "Bugungi",
  week: "Shu haftalik",
  month: "Shu oylik",
};

// deno-lint-ignore no-explicit-any
async function handleTextEntry(config: BotConfig, message: any) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const userDbId = await getOrCreateUser(
    telegramId,
    [message.from.first_name, message.from.last_name].filter(Boolean).join(" "),
    message.from.username ?? "",
  );

  const [expenseCats, incomeCats] = await Promise.all([
    categoryNames("expense"),
    categoryNames("income"),
  ]);

  let parsed;
  try {
    parsed = await parseExpenseText(
      config.anthropic_api_key,
      config.anthropic_model,
      message.text,
      expenseCats,
      incomeCats,
      todayStr(),
    );
  } catch (e) {
    console.error("parseExpenseText failed", e);
    await sendMessage(
      config.bot_token,
      chatId,
      "Kechirasiz, xabaringizni tahlil qila olmadim. Iltimos, summani va nima uchunligini aniqroq yozing.",
    );
    return;
  }

  if (parsed.confidence === "low") {
    await sendMessage(
      config.bot_token,
      chatId,
      "Xabaringizdan summa yoki tafsilotlarni aniq ajrata olmadim. Iltimos, masalan shu ko'rinishda " +
        "qayta yozing: \"Sement uchun 500000 so'm to'ladim\".",
    );
    return;
  }

  const pendingId = await addPendingTx({
    telegram_id: telegramId,
    user_db_id: userDbId,
    type: parsed.type,
    amount: parsed.amount,
    category: parsed.category,
    description: parsed.description ?? "",
    counterparty: parsed.counterparty ?? "",
    occurred_on: parsed.occurred_on,
    source: "manual_text",
  });

  await sendMessage(config.bot_token, chatId, formatPending({ ...parsed, counterparty: parsed.counterparty ?? "" }), confirmKeyboard(pendingId));
}

// deno-lint-ignore no-explicit-any
async function handlePhoto(config: BotConfig, message: any) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const userDbId = await getOrCreateUser(
    telegramId,
    [message.from.first_name, message.from.last_name].filter(Boolean).join(" "),
    message.from.username ?? "",
  );

  const [expenseCats, incomeCats] = await Promise.all([
    categoryNames("expense"),
    categoryNames("income"),
  ]);

  const statusMsg = await sendMessage(config.bot_token, chatId, "Chekni o'qiyapman...");
  const statusMessageId = statusMsg.result.message_id;

  const photo = message.photo[message.photo.length - 1];
  const filePath = await getFilePath(config.bot_token, photo.file_id);
  const imageBytes = await downloadFile(config.bot_token, filePath);

  let parsed;
  try {
    parsed = await parseReceiptImage(
      config.anthropic_api_key,
      config.anthropic_model,
      imageBytes,
      "image/jpeg",
      expenseCats,
      incomeCats,
      todayStr(),
    );
  } catch (e) {
    console.error("parseReceiptImage failed", e);
    await editMessageText(
      config.bot_token,
      chatId,
      statusMessageId,
      "Kechirasiz, chekni o'qiy olmadim. Iltimos, aniqroq rasm yuboring.",
    );
    return;
  }

  if (parsed.confidence === "low") {
    await editMessageText(
      config.bot_token,
      chatId,
      statusMessageId,
      "Chekdagi ma'lumotlarni aniq o'qiy olmadim. Iltimos, yaqinroq/tiniqroq rasm yuboring yoki " +
        "matn ko'rinishida yozing.",
    );
    return;
  }

  const pendingId = await addPendingTx({
    telegram_id: telegramId,
    user_db_id: userDbId,
    type: parsed.type,
    amount: parsed.amount,
    category: parsed.category,
    description: parsed.description ?? "",
    counterparty: parsed.counterparty ?? "",
    occurred_on: parsed.occurred_on,
    source: "receipt_photo",
  });

  await editMessageText(
    config.bot_token,
    chatId,
    statusMessageId,
    formatPending({ ...parsed, counterparty: parsed.counterparty ?? "" }),
    confirmKeyboard(pendingId),
  );
}

// deno-lint-ignore no-explicit-any
async function handleDocument(config: BotConfig, message: any) {
  const chatId = message.chat.id;
  const telegramId = message.from.id;
  const filename: string = message.document.file_name ?? "";

  if (!/\.(xlsx|xls|csv)$/i.test(filename)) {
    await sendMessage(
      config.bot_token,
      chatId,
      "Faqat .xlsx yoki .csv formatidagi bank ko'chirmasi fayllarini qabul qilaman.",
    );
    return;
  }

  const userDbId = await getOrCreateUser(
    telegramId,
    [message.from.first_name, message.from.last_name].filter(Boolean).join(" "),
    message.from.username ?? "",
  );
  const [expenseCats, incomeCats] = await Promise.all([
    categoryNames("expense"),
    categoryNames("income"),
  ]);

  const statusMsg = await sendMessage(config.bot_token, chatId, "Fayl tahlil qilinmoqda...");
  const statusMessageId = statusMsg.result.message_id;

  const filePath = await getFilePath(config.bot_token, message.document.file_id);
  const fileBytes = await downloadFile(config.bot_token, filePath);

  let rows;
  try {
    rows = parseBankStatement(fileBytes, filename);
  } catch (e) {
    const text = e instanceof BankImportError
      ? e.message
      : "Faylni o'qishda xatolik yuz berdi. Fayl formatini tekshiring.";
    await editMessageText(config.bot_token, chatId, statusMessageId, text);
    return;
  }

  if (rows.length > 300) {
    await editMessageText(
      config.bot_token,
      chatId,
      statusMessageId,
      `Faylda ${rows.length} ta qator topildi, bu bir martada qayta ishlash uchun juda ko'p. ` +
        "Iltimos, faylni qismlarga bo'lib yuboring (masalan, oylik).",
    );
    return;
  }

  const aiInput = rows.map((r, i) => ({
    row_index: i,
    type: r.type,
    amount: r.amount,
    raw_description: r.raw_description,
  }));

  let categorized;
  try {
    categorized = await categorizeBankRows(
      config.anthropic_api_key,
      config.anthropic_model,
      aiInput,
      expenseCats,
      incomeCats,
    );
  } catch (e) {
    console.error("categorizeBankRows failed", e);
    await editMessageText(
      config.bot_token,
      chatId,
      statusMessageId,
      "Tranzaksiyalarni kategoriyalashda xatolik yuz berdi. Qayta urinib ko'ring.",
    );
    return;
  }

  let totalIncome = 0;
  let totalExpense = 0;
  const enrichedRows = rows.map((r, i) => {
    if (r.type === "income") totalIncome += r.amount;
    else totalExpense += r.amount;
    const info = categorized.get(i);
    return {
      occurred_on: r.occurred_on,
      amount: r.amount,
      type: r.type,
      category: info?.category ?? "Boshqa xarajat",
      description: info?.description ?? r.raw_description,
    };
  });

  const pendingId = await addPendingBankImport(telegramId, userDbId, enrichedRows);

  const fmt = (n: number) => Math.round(n).toLocaleString("uz-UZ").replace(/,/g, " ");
  const summary =
    `Faylda ${rows.length} ta tranzaksiya topildi:\n` +
    `Jami kirim: ${fmt(totalIncome)} so'm\n` +
    `Jami chiqim: ${fmt(totalExpense)} so'm\n\n` +
    "Barchasini saqlaymizmi?";
  await editMessageText(config.bot_token, chatId, statusMessageId, summary, bankImportKeyboard(pendingId));
}

async function handleReportCallback(config: BotConfig, chatId: number, period: string) {
  const [start, end] = periodRange(period);
  const rows = await fetchReportRows(start, end);
  const buffer = buildReportWorkbook(rows);
  const filename = `hisobot_${start}_${end}.xlsx`;
  await sendDocument(
    config.bot_token,
    chatId,
    filename,
    buffer,
    `${PERIOD_LABELS[period] ?? ""} hisobot (${start} - ${end})`,
  );
}

// deno-lint-ignore no-explicit-any
async function handleCallbackQuery(config: BotConfig, cq: any) {
  const data: string = cq.data ?? "";
  const chatId = cq.message.chat.id;
  const messageId = cq.message.message_id;

  if (data.startsWith("tx_confirm:")) {
    const id = data.split(":")[1];
    const pending = await popPendingTx(id);
    if (!pending) {
      await answerCallbackQuery(config.bot_token, cq.id, "Bu yozuv muddati o'tgan.", true);
      return;
    }
    const categoryId = await getOrCreateCategory(pending.category, pending.type);
    await insertTransaction({
      type: pending.type,
      source: pending.source,
      amount: pending.amount,
      description: pending.description,
      counterparty: pending.counterparty,
      occurred_on: pending.occurred_on,
      category_id: categoryId,
      created_by_id: pending.user_db_id,
    });
    await editMessageText(
      config.bot_token,
      chatId,
      messageId,
      formatPending(pending) + "\n\n✅ Saqlandi.",
    );
    await answerCallbackQuery(config.bot_token, cq.id, "Saqlandi");
    return;
  }

  if (data.startsWith("tx_cancel:")) {
    const id = data.split(":")[1];
    await popPendingTx(id);
    await editMessageText(config.bot_token, chatId, messageId, "❌ Bekor qilindi.");
    await answerCallbackQuery(config.bot_token, cq.id, "Bekor qilindi");
    return;
  }

  if (data.startsWith("tx_category:")) {
    const id = data.split(":")[1];
    const pending = await getPendingTx(id);
    if (!pending) {
      await answerCallbackQuery(config.bot_token, cq.id, "Bu yozuv muddati o'tgan.", true);
      return;
    }
    const cats = await categoryNames(pending.type);
    await editMessageReplyMarkup(config.bot_token, chatId, messageId, categoryChoiceKeyboard(id, cats));
    await answerCallbackQuery(config.bot_token, cq.id);
    return;
  }

  if (data.startsWith("tx_setcat:")) {
    const [, id, idxStr] = data.split(":");
    const pending = await getPendingTx(id);
    if (!pending) {
      await answerCallbackQuery(config.bot_token, cq.id, "Bu yozuv muddati o'tgan.", true);
      return;
    }
    const cats = await categoryNames(pending.type);
    const idx = parseInt(idxStr, 10);
    if (idx >= 0 && idx < cats.length) {
      await setPendingTxCategory(id, cats[idx]);
      pending.category = cats[idx];
    }
    await editMessageText(config.bot_token, chatId, messageId, formatPending(pending), confirmKeyboard(id));
    await answerCallbackQuery(config.bot_token, cq.id);
    return;
  }

  if (data.startsWith("tx_back:")) {
    const id = data.split(":")[1];
    const pending = await getPendingTx(id);
    if (!pending) {
      await answerCallbackQuery(config.bot_token, cq.id, "Bu yozuv muddati o'tgan.", true);
      return;
    }
    await editMessageText(config.bot_token, chatId, messageId, formatPending(pending), confirmKeyboard(id));
    await answerCallbackQuery(config.bot_token, cq.id);
    return;
  }

  if (data.startsWith("bank_confirm:")) {
    const id = data.split(":")[1];
    const pending = await popPendingBankImport(id);
    if (!pending) {
      await answerCallbackQuery(config.bot_token, cq.id, "Bu import muddati o'tgan.", true);
      return;
    }
    for (const row of pending.rows) {
      const categoryId = await getOrCreateCategory(row.category, row.type);
      await insertTransaction({
        type: row.type,
        source: "bank_statement",
        amount: row.amount,
        description: row.description,
        counterparty: "",
        occurred_on: row.occurred_on,
        category_id: categoryId,
        created_by_id: pending.user_db_id,
      });
    }
    await editMessageText(config.bot_token, chatId, messageId, `✅ ${pending.rows.length} ta tranzaksiya saqlandi.`);
    await answerCallbackQuery(config.bot_token, cq.id, "Saqlandi");
    return;
  }

  if (data.startsWith("bank_cancel:")) {
    const id = data.split(":")[1];
    await popPendingBankImport(id);
    await editMessageText(config.bot_token, chatId, messageId, "❌ Import bekor qilindi.");
    await answerCallbackQuery(config.bot_token, cq.id, "Bekor qilindi");
    return;
  }

  if (data.startsWith("report:")) {
    const period = data.split(":")[1];
    await handleReportCallback(config, chatId, period);
    await answerCallbackQuery(config.bot_token, cq.id);
    return;
  }
}

// deno-lint-ignore no-explicit-any
async function handleUpdate(config: BotConfig, update: any) {
  if (update.callback_query) {
    const telegramId = update.callback_query.from.id;
    if (!isAllowedUser(config, telegramId)) {
      await answerCallbackQuery(config.bot_token, update.callback_query.id, "Ruxsat yo'q.", true);
      return;
    }
    await handleCallbackQuery(config, update.callback_query);
    return;
  }

  const message = update.message;
  if (!message) return;

  const telegramId = message.from?.id;
  const chatId = message.chat.id;

  if (!telegramId || !isAllowedUser(config, telegramId)) {
    await sendMessage(config.bot_token, chatId, "Kechirasiz, sizda bu botdan foydalanish uchun ruxsat yo'q.");
    return;
  }

  const text: string | undefined = message.text;

  if (text === "/start" || text === "/help") {
    await getOrCreateUser(
      telegramId,
      [message.from.first_name, message.from.last_name].filter(Boolean).join(" "),
      message.from.username ?? "",
    );
    await sendMessage(config.bot_token, chatId, WELCOME_TEXT);
    return;
  }

  if (text === "/report") {
    await sendMessage(config.bot_token, chatId, "Qaysi davr uchun hisobot kerak?", reportPeriodKeyboard());
    return;
  }

  if (message.photo) {
    await handlePhoto(config, message);
    return;
  }

  if (message.document) {
    await handleDocument(config, message);
    return;
  }

  if (text && !text.startsWith("/")) {
    await handleTextEntry(config, message);
    return;
  }
}

Deno.serve(async (req: Request) => {
  try {
    const config = await loadConfig();

    const secretHeader = req.headers.get("x-telegram-bot-api-secret-token");
    if (secretHeader !== config.webhook_secret) {
      return new Response("forbidden", { status: 403 });
    }

    const update = await req.json();
    await handleUpdate(config, update);
    return new Response("ok", { status: 200 });
  } catch (e) {
    console.error("Unhandled error", e);
    // Always 200 so Telegram doesn't retry-storm on transient errors; the
    // failure is visible in Supabase edge-function logs instead.
    return new Response("ok", { status: 200 });
  }
});
