# App colaborativa — Gestão de Packs de Horas

Esta versão permite que vários colaboradores registem movimentos numa base partilhada.

A app usa:

- **Streamlit** para a interface;
- **Google Sheets** como base de dados colaborativa;
- **Excel** para exportação e backup.

## Funcionalidades

- Adicionar novos clientes;
- Registar compra de pack de horas;
- Registar horas utilizadas numa intervenção;
- Ver saldo automático por cliente;
- Ver alertas de saldo baixo, crítico e esgotado;
- Identificar quem registou cada movimento;
- Exportar Excel atualizado;
- Importar os dados iniciais do Excel para Google Sheets.

## Ficheiros incluídos

- `app.py`
- `requirements.txt`
- `README.md`
- `.streamlit/config.toml`
- `PACKS_DE_HORAS_AUTOMATIZADO.xlsx`

## Como colocar no GitHub

1. Abrir o repositório no GitHub.
2. Clicar em **Add file > Upload files**.
3. Carregar todos os ficheiros desta pasta.
4. Clicar em **Commit changes**.

## Como publicar no Streamlit

1. Entrar em https://share.streamlit.io
2. Clicar em **New app**.
3. Escolher o repositório.
4. Em **Main file path**, colocar:

```bash
app.py
```

5. Clicar em **Deploy**.

## Como ligar ao Google Sheets

### 1. Criar uma Google Sheet

Crie uma folha Google Sheets nova com o nome, por exemplo:

```text
Base Packs de Horas
```

Copie o ID da folha.  
O ID está no link, entre `/d/` e `/edit`.

Exemplo:

```text
https://docs.google.com/spreadsheets/d/ESTE_E_O_ID_DA_FOLHA/edit
```

### 2. Criar Service Account no Google Cloud

1. Entrar em Google Cloud Console.
2. Criar ou escolher um projeto.
3. Ativar a API **Google Sheets API**.
4. Ativar também a API **Google Drive API**.
5. Criar uma **Service Account**.
6. Criar uma chave JSON.
7. Guardar o ficheiro JSON em local seguro.

### 3. Partilhar a Google Sheet com a Service Account

No ficheiro JSON existe um campo chamado:

```text
client_email
```

Copie esse email e partilhe a Google Sheet com esse email com permissão de **Editor**.

### 4. Colocar os Secrets no Streamlit

No Streamlit Cloud:

```text
App > Settings > Secrets
```

Cole os dados neste formato:

```toml
GOOGLE_SHEET_ID = "COLE_AQUI_O_ID_DA_SUA_GOOGLE_SHEET"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

Depois guarde e faça **Reboot app**.

## Primeira utilização

Depois de configurar o Google Sheets:

1. Abrir a app.
2. Ir ao separador **Importar**.
3. Confirmar que quer importar o Excel inicial.
4. Clicar em **Importar Excel para Google Sheets**.

A partir daí, todos os movimentos ficam gravados no Google Sheets e são visíveis para todos os colaboradores.

## Nota de segurança

Recomenda-se:

- Manter o repositório GitHub como **Private**;
- Partilhar a app só com colaboradores autorizados;
- Não colocar a chave JSON diretamente no código;
- Usar sempre os **Secrets** do Streamlit.


## Acesso sem conta Streamlit

Esta versão permite partilhar a app com colaboradores sem eles terem de entrar no Streamlit.

A app deve ficar **pública no Streamlit**, mas protegida por uma palavra-passe interna.

### Como configurar a palavra-passe

No Streamlit Cloud:

```text
App > Settings > Secrets
```

Adicione esta linha aos Secrets:

```toml
APP_PASSWORD = "EscolhaUmaPalavraPasseForte"
```

Depois faça **Save** e, se necessário, **Reboot app** uma vez.

### Como os colaboradores entram

Os colaboradores só precisam de:

1. Abrir o link da app;
2. Introduzir a palavra-passe;
3. Escrever o nome na barra lateral;
4. Registar clientes, packs ou horas utilizadas.

Não precisam de conta Streamlit, GitHub ou Google Cloud.

### Nota de segurança

Esta é uma proteção simples por palavra-passe partilhada.  
Se um colaborador sair da empresa, altere a palavra-passe nos Secrets.
