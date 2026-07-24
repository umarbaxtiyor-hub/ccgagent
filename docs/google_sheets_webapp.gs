/**
 * Paste this into Extensions > Apps Script from inside your Google Sheet
 * ("Qurilish xarajatlari"), replace SECRET below with a long random value,
 * then deploy it as a Web App (Deploy > New deployment > type: Web app,
 * "Execute as": Me, "Who has access": Anyone). Copy the resulting URL into
 * the bot's SHEETS_WEBHOOK_URL env var, and the SECRET into
 * SHEETS_WEBHOOK_SECRET.
 *
 * The sheet tab receiving rows must be named exactly as SHEET_NAME below and
 * already have the header row:
 * Sana | Nomi / material | Miqdor | Birlik | Birim narx | Umumiy summa |
 * Kategoriya | Kim yozdi | Loyiha | To'lov turi | Asl xabar | Izoh
 */

var SECRET = "REPLACE_WITH_A_LONG_RANDOM_SECRET";
var SHEET_NAME = "Xarajatlar";

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    if (data.secret !== SECRET) {
      return jsonResponse({ ok: false, error: "unauthorized" });
    }

    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
    if (!sheet) {
      return jsonResponse({ ok: false, error: "sheet not found: " + SHEET_NAME });
    }

    sheet.appendRow([
      data.sana || "",
      data.nomi || "",
      data.miqdor || "",
      data.birlik || "",
      data.birim_narx || "",
      data.umumiy_summa || "",
      data.kategoriya || "",
      data.kim_yozdi || "",
      data.loyiha || "",
      data.tolov_turi || "",
      data.asl_xabar || "",
      data.izoh || "",
    ]);

    return jsonResponse({ ok: true });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err) });
  }
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
