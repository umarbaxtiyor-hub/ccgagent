function apiUrl(token: string, method: string): string {
  return `https://api.telegram.org/bot${token}/${method}`;
}

export async function callTelegram(
  token: string,
  method: string,
  // deno-lint-ignore no-explicit-any
  payload: Record<string, any>,
  // deno-lint-ignore no-explicit-any
): Promise<any> {
  const res = await fetch(apiUrl(token, method), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) {
    console.error("Telegram API error", method, JSON.stringify(data));
  }
  return data;
}

export function sendMessage(
  token: string,
  chatId: number,
  text: string,
  // deno-lint-ignore no-explicit-any
  replyMarkup?: any,
) {
  return callTelegram(token, "sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    reply_markup: replyMarkup,
  });
}

export function editMessageText(
  token: string,
  chatId: number,
  messageId: number,
  text: string,
  // deno-lint-ignore no-explicit-any
  replyMarkup?: any,
) {
  return callTelegram(token, "editMessageText", {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: "HTML",
    reply_markup: replyMarkup,
  });
}

export function editMessageReplyMarkup(
  token: string,
  chatId: number,
  messageId: number,
  // deno-lint-ignore no-explicit-any
  replyMarkup?: any,
) {
  return callTelegram(token, "editMessageReplyMarkup", {
    chat_id: chatId,
    message_id: messageId,
    reply_markup: replyMarkup,
  });
}

export function answerCallbackQuery(
  token: string,
  callbackId: string,
  text?: string,
  showAlert = false,
) {
  return callTelegram(token, "answerCallbackQuery", {
    callback_query_id: callbackId,
    text,
    show_alert: showAlert,
  });
}

export async function getFilePath(token: string, fileId: string): Promise<string> {
  const data = await callTelegram(token, "getFile", { file_id: fileId });
  return data.result.file_path as string;
}

export async function downloadFile(token: string, filePath: string): Promise<Uint8Array> {
  const url = `https://api.telegram.org/file/bot${token}/${filePath}`;
  const res = await fetch(url);
  return new Uint8Array(await res.arrayBuffer());
}

export async function sendDocument(
  token: string,
  chatId: number,
  filename: string,
  bytes: Uint8Array,
  caption?: string,
  // deno-lint-ignore no-explicit-any
): Promise<any> {
  const form = new FormData();
  form.append("chat_id", String(chatId));
  if (caption) form.append("caption", caption);
  form.append("document", new Blob([bytes]), filename);
  const res = await fetch(apiUrl(token, "sendDocument"), { method: "POST", body: form });
  return res.json();
}
