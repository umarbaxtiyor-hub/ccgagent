import postgres from "npm:postgres@3.4.5";

let _sql: ReturnType<typeof postgres> | null = null;

export function getSql() {
  if (!_sql) {
    _sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, {
      prepare: false,
      ssl: "require",
    });
  }
  return _sql;
}

export interface BotConfig {
  bot_token: string;
  anthropic_api_key: string;
  anthropic_model: string;
  allowed_user_ids: string;
  webhook_secret: string;
  [key: string]: string;
}

export async function loadConfig(): Promise<BotConfig> {
  const sql = getSql();
  const rows = await sql<{ key: string; value: string }[]>`
    select key, value from app_private.bot_config
  `;
  const config: Record<string, string> = {};
  for (const row of rows) config[row.key] = row.value;
  return config as unknown as BotConfig;
}

export function isAllowedUser(config: BotConfig, telegramId: number): boolean {
  const raw = config.allowed_user_ids?.trim() ?? "";
  if (!raw) return true;
  const ids = raw.split(",").map((s) => s.trim()).filter(Boolean);
  return ids.includes(String(telegramId));
}

export interface UserRecord {
  id: number;
  current_project_id: number | null;
  current_project_name: string | null;
}

export async function getOrCreateUser(
  telegramId: number,
  fullName: string,
  username: string,
): Promise<UserRecord> {
  const sql = getSql();
  const existing = await sql<UserRecord[]>`
    select u.id, u.current_project_id,
           p.name as current_project_name
    from users u
    left join projects p on p.id = u.current_project_id
    where u.telegram_id = ${telegramId}
  `;
  if (existing.length) return existing[0];
  const inserted = await sql<{ id: number }[]>`
    insert into users (telegram_id, full_name, username)
    values (${telegramId}, ${fullName}, ${username})
    returning id
  `;
  return { id: inserted[0].id, current_project_id: null, current_project_name: null };
}

export interface Project {
  id: number;
  name: string;
}

export async function listProjects(): Promise<Project[]> {
  const sql = getSql();
  return await sql<Project[]>`select id, name from projects order by name`;
}

export async function createProject(name: string): Promise<Project> {
  const sql = getSql();
  const existing = await sql<Project[]>`select id, name from projects where name = ${name}`;
  if (existing.length) return existing[0];
  const [row] = await sql<Project[]>`
    insert into projects (name) values (${name}) returning id, name
  `;
  return row;
}

export async function setUserCurrentProject(userDbId: number, projectId: number): Promise<void> {
  const sql = getSql();
  await sql`update users set current_project_id = ${projectId} where id = ${userDbId}`;
}

export async function categoryNames(type: "income" | "expense"): Promise<string[]> {
  const sql = getSql();
  const rows = await sql<{ name: string }[]>`
    select name from categories where type = ${type} order by id
  `;
  return rows.map((r) => r.name);
}

export async function getOrCreateCategory(
  name: string,
  type: "income" | "expense",
): Promise<number> {
  const sql = getSql();
  const existing = await sql<{ id: number }[]>`
    select id from categories where name = ${name}
  `;
  if (existing.length) return existing[0].id;
  const inserted = await sql<{ id: number }[]>`
    insert into categories (name, type) values (${name}, ${type})
    returning id
  `;
  return inserted[0].id;
}

export interface PendingTransaction {
  id: string;
  telegram_id: number;
  user_db_id: number;
  type: "income" | "expense";
  amount: number;
  category: string;
  description: string;
  counterparty: string;
  occurred_on: string;
  source: "manual_text" | "receipt_photo" | "bank_statement" | "voice_message";
  project_id: number | null;
  project_name: string | null;
}

export async function addPendingTx(
  data: Omit<PendingTransaction, "id">,
): Promise<string> {
  const sql = getSql();
  const [row] = await sql<{ id: string }[]>`
    insert into pending_transactions
      (telegram_id, user_db_id, type, amount, category, description, counterparty, occurred_on,
       source, project_id, project_name)
    values
      (${data.telegram_id}, ${data.user_db_id}, ${data.type}, ${data.amount}, ${data.category},
       ${data.description}, ${data.counterparty}, ${data.occurred_on}, ${data.source},
       ${data.project_id}, ${data.project_name})
    returning id
  `;
  return row.id;
}

export async function getPendingTx(id: string): Promise<PendingTransaction | null> {
  const sql = getSql();
  const rows = await sql<PendingTransaction[]>`
    select id, telegram_id, user_db_id, type, amount::float8 as amount, category,
           description, counterparty, occurred_on::text as occurred_on, source,
           project_id, project_name
    from pending_transactions where id = ${id}
  `;
  return rows[0] ?? null;
}

export async function setPendingTxCategory(id: string, category: string): Promise<void> {
  const sql = getSql();
  await sql`update pending_transactions set category = ${category} where id = ${id}`;
}

export async function popPendingTx(id: string): Promise<PendingTransaction | null> {
  const sql = getSql();
  const rows = await sql<PendingTransaction[]>`
    delete from pending_transactions
    where id = ${id}
    returning id, telegram_id, user_db_id, type, amount::float8 as amount, category,
              description, counterparty, occurred_on::text as occurred_on, source,
              project_id, project_name
  `;
  return rows[0] ?? null;
}

export interface PendingBankRow {
  occurred_on: string;
  amount: number;
  type: "income" | "expense";
  category: string;
  description: string;
}

export async function addPendingBankImport(
  telegramId: number,
  userDbId: number,
  projectId: number | null,
  rows: PendingBankRow[],
): Promise<string> {
  const sql = getSql();
  const [row] = await sql<{ id: string }[]>`
    insert into pending_bank_imports (telegram_id, user_db_id, project_id, rows)
    values (${telegramId}, ${userDbId}, ${projectId}, ${sql.json(rows)})
    returning id
  `;
  return row.id;
}

export async function popPendingBankImport(
  id: string,
): Promise<{ user_db_id: number; project_id: number | null; rows: PendingBankRow[] } | null> {
  const sql = getSql();
  const rows = await sql<{ user_db_id: number; project_id: number | null; rows: PendingBankRow[] }[]>`
    delete from pending_bank_imports where id = ${id}
    returning user_db_id, project_id, rows
  `;
  return rows[0] ?? null;
}

export async function insertTransaction(params: {
  type: "income" | "expense";
  source: "manual_text" | "receipt_photo" | "bank_statement" | "voice_message";
  amount: number;
  description: string;
  counterparty: string;
  occurred_on: string;
  category_id: number;
  created_by_id: number;
  project_id: number | null;
}): Promise<void> {
  const sql = getSql();
  await sql`
    insert into transactions
      (type, source, amount, description, counterparty, occurred_on, category_id, created_by_id, project_id)
    values
      (${params.type}, ${params.source}, ${params.amount}, ${params.description},
       ${params.counterparty}, ${params.occurred_on}, ${params.category_id}, ${params.created_by_id},
       ${params.project_id})
  `;
}

export interface ReportRow {
  occurred_on: string;
  type: "income" | "expense";
  category: string;
  amount: number;
  description: string;
  counterparty: string;
  full_name: string;
  project_name: string | null;
}

export async function fetchReportRows(start: string, end: string): Promise<ReportRow[]> {
  const sql = getSql();
  const rows = await sql<ReportRow[]>`
    select
      t.occurred_on::text as occurred_on,
      t.type,
      c.name as category,
      t.amount::float8 as amount,
      t.description,
      t.counterparty,
      u.full_name,
      p.name as project_name
    from transactions t
    join categories c on c.id = t.category_id
    join users u on u.id = t.created_by_id
    left join projects p on p.id = t.project_id
    where t.occurred_on >= ${start} and t.occurred_on <= ${end}
    order by t.occurred_on, t.id
  `;
  return rows;
}
