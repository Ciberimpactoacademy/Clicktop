# App — Controlo de Packs de Horas

Esta app transforma o ficheiro Excel de packs de horas numa aplicação simples, com:

- Dashboard por cliente;
- Alertas de saldo baixo, crítico e esgotado;
- Pesquisa e filtro por cliente/estado;
- Ficha individual de cliente;
- Registo de novas compras de packs e intervenções;
- Exportação de Excel atualizado.

## 1. Como correr no computador

1. Instalar Python 3.10 ou superior.
2. Abrir a pasta deste projeto no terminal.
3. Instalar dependências:

```bash
pip install -r requirements.txt
```

4. Correr a app:

```bash
streamlit run app.py
```

5. Abrir o link apresentado no terminal.

## 2. Como usar

- A app já inclui o ficheiro `PACKS_DE_HORAS_AUTOMATIZADO.xlsx`.
- Também pode carregar outro Excel na barra lateral.
- Para novos registos, usar o separador **Novo lançamento**.
- No final, usar o separador **Exportar** para descarregar o Excel atualizado.

## 3. Como publicar online

Pode publicar no Streamlit Community Cloud, Replit, Render ou outro serviço compatível com Python.

Ficheiros necessários:

- `app.py`
- `requirements.txt`
- `PACKS_DE_HORAS_AUTOMATIZADO.xlsx`

Comando de arranque:

```bash
streamlit run app.py
```

## 4. Nota importante

Esta versão não altera diretamente o ficheiro original no servidor.
Os lançamentos feitos na app ficam ativos durante a sessão e devem ser exportados para Excel no final.
