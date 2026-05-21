const SHEET_NAME = "Base_Lancamentos";
const DEFAULT_TOKEN = "Click123";

const HEADERS = [
  "ID","Cliente","Data","Tipo","Solicitada por","Técnico",
  "Descrição da intervenção","Horas Pack","Horas Usadas",
  "Saldo Automático","Estado","Saldo Original","Origem",
  "Registado por","Data de registo"
];

function token_() {
  return PropertiesService.getScriptProperties().getProperty("APP_TOKEN") || DEFAULT_TOKEN;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME);

  if (sh.getLastRow() === 0 || sh.getLastColumn() === 0) {
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  } else {
    const current = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), HEADERS.length)).getValues()[0];
    const existing = {};
    current.forEach(h => { if (h) existing[h] = true; });
    HEADERS.forEach(h => {
      if (!existing[h]) sh.getRange(1, sh.getLastColumn() + 1).setValue(h);
    });
  }
  return sh;
}

function read_() {
  const sh = sheet_();
  const values = sh.getDataRange().getValues();
  if (values.length <= 1) return [];

  const headers = values[0];
  const rows = [];

  for (let i = 1; i < values.length; i++) {
    const o = {};
    headers.forEach((h, j) => {
      if (!h) return;
      let v = values[i][j];
      if (v instanceof Date) v = Utilities.formatDate(v, Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
      o[h] = v;
    });
    if (o["Cliente"] && String(o["Cliente"]).trim() !== "") rows.push(o);
  }
  return rows;
}

function append_(rowObj) {
  const sh = sheet_();
  const row = HEADERS.map(h => {
    let v = rowObj[h];
    if (v === null || v === undefined) return "";
    if (["Horas Pack","Horas Usadas","Saldo Automático","Saldo Original"].includes(h)) {
      const n = Number(String(v).replace(",", "."));
      return isNaN(n) ? "" : n;
    }
    return v;
  });
  sh.appendRow(row);
}

function replaceAll_(rows) {
  const sh = sheet_();
  sh.clearContents();
  sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  if (!rows || rows.length === 0) return;
  const values = rows.map(r => HEADERS.map(h => r[h] === null || r[h] === undefined ? "" : r[h]));
  sh.getRange(2, 1, values.length, HEADERS.length).setValues(values);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const body = JSON.parse(e.postData.contents || "{}");
    if (body.token !== token_()) return out_({ok:false, error:"Token inválido"});

    if (body.action === "read") return out_({ok:true, rows: read_()});
    if (body.action === "append") { append_(body.row || {}); return out_({ok:true}); }
    if (body.action === "replace_all") { replaceAll_(body.rows || []); return out_({ok:true}); }

    return out_({ok:false, error:"Ação desconhecida"});
  } catch (err) {
    return out_({ok:false, error:String(err)});
  } finally {
    lock.releaseLock();
  }
}
