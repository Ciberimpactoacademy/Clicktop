# App Packs de Horas — sem JSON

Esta versão usa Google Apps Script em vez de Service Account.

## Passos

1. Substituir os ficheiros no GitHub por estes.
2. Abrir a Google Sheet.
3. Ir a Extensões > Apps Script.
4. Colar o conteúdo de `AppsScript.gs`.
5. Guardar.
6. Implementar > Nova implementação > Aplicação Web.
7. Executar como: Eu.
8. Quem tem acesso: Qualquer pessoa.
9. Copiar o URL da aplicação Web.
10. No Streamlit > Settings > Secrets, colocar:

```toml
APP_PASSWORD = "Click123"
APPS_SCRIPT_WEBAPP_URL = "COLE_AQUI_O_URL"
APPS_SCRIPT_TOKEN = "Click123"
```

11. Fazer Reboot app.
12. Na app, ir a 📥 Importar e importar o Excel inicial.
