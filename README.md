# Conciliação Bancária Automática (Banco Inter)

Automatiza o download de extratos (PDF e OFX) do Banco Inter para múltiplos condomínios, gerando arquivos organizados por data e nome de condomínio. Ideal para integrar com ERP ou para upload manual otimizado.

---

## 🗂️ Estrutura de diretórios

```
.
├── CONDOMÍNIOS/
│   ├── Jatobá 1 (JT)/
│   │   ├── .env
│   │   ├── Inter API_Certificado.crt
│   │   └── Inter API_Chave.key
│   ├── Pedro I (PE)/
│   │   └── …
│   └── …
├── main.py
├── requirements.txt
└── README.md
```

- **CONDOMÍNIOS/**  
  Cada subpasta corresponde a um condomínio e deve conter:
  - `.env` com as variáveis `ClientID` e `ClientSecret`
  - `Inter API_Certificado.crt` e `Inter API_Chave.key`
- **main.py**  
  Script principal que itera por todas as pastas de condomínio, baixa PDF/OFX e salva em Drive local.
- **requirements.txt**  
  Lista de dependências Python.

---

## 🚀 Instalação

1. Clone este repositório:
   ```bash
   git clone https://github.com/Joaovitorsm18/Api_Inter.git
   ```

2. Crie e ative um virtualenv:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux / macOS
   venv\Scripts\activate      # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuração

Para cada condomínio, na pasta `CONDOMÍNIOS/Nome do Condomínio/`:

1. Crie um arquivo `.env` contendo:
   ```dotenv
   ClientID=seu_client_id
   ClientSecret=seu_client_secret
   ```
2. Coloque os arquivos de certificado:
   - `Inter API_Certificado.crt`
   - `Inter API_Chave.key`

---

## 📋 Uso

Execute o `main.py` e escolha entre mês atual ou anterior:

```bash
python main.py
```

Você verá um prompt:
```
Selecione o período para os extratos:
1 - Mês atual
2 - Mês anterior
```

- Digite `1` para extrair do primeiro ao último dia do mês atual.  
- Digite `2` para extrair do mês anterior.

Os arquivos serão salvos em:
```
G:/Meu Drive/CONDOMÍNIOS/<Nome>/FINANCEIRO/BANCO/INTER/
 ├─ EXTRATOS PDF/<ANO>/<ANO-MM EXTRATO SIGLA>.pdf
 └─ EXTRATOS OFX/<ANO>/<ANO-MM EXTRATO SIGLA>.ofx
```

---

## 🛠️ Como funciona

1. **Carrega credenciais** de cada condomínio via `.env` e certificado mTLS.  
2. **Autentica** na API do Inter (`/oauth/v2/token`).  
3. **Baixa PDF** (`/extrato/exportar`) e salva decodificando Base64.  
4. **Consulta saldo** (`/saldo`).  
5. **Baixa extrato enriquecido** (`/extrato/completo`), gera OFX com `build_ofx()` e salva.  
6. Faz **retry** em até 3 tentativas se ocorrerem falhas de rede/API.  
7. **Log de erros** em `log_erros.txt` sem interromper o processamento dos demais.

---

## 📦 Dependências

- `python-dotenv`  
- `requests`

Conteúdo de `requirements.txt`:

```
python-dotenv==1.1.0
requests==2.32.3
```

---

## 🆕 Novidades e Melhorias (Atualização - Conciliacao.py)

### Conciliação automática e integração com Superlógica

- Novo script `conciliacao.py` para automatizar a conciliação bancária dos condomínios.
- Baixa extratos OFX diretamente da API Banco Inter.
- Integra com a API Superlógica para:
  - Obter `id_contabanco` de cada condomínio.
  - Apagar conciliações anteriores.
  - Enviar o arquivo OFX para conciliação automática.
  - Consultar status da conciliação.
- Analisa divergências entre valores do banco e sistema, agrupando por data.

### Envio de e-mail automático

- Envio de relatório diário por e-mail com o resumo das conciliações pendentes.
- Configuração via variáveis de ambiente:
  - `EMAIL_REMETENTE`, `EMAIL_SENHA`, `EMAIL_DESTINATARIO`
- Ativação via linha de comando com a flag `--enviar-email`.

### Execução agendada recomendada

- Pode ser rodado automaticamente a cada 30 minutos para manter dados atualizados.
- Envio de e-mail configurado para rodar uma vez por dia, via flag.

---

## ⚙️ Como usar o novo script `conciliacao.py`

1. Configure as variáveis de ambiente no arquivo `.env` na raiz do projeto:

```dotenv
EMAIL_REMETENTE=seu_email@gmail.com
EMAIL_SENHA=sua_senha_app
EMAIL_DESTINATARIO=destinatario@exemplo.com

APP_TOKEN=seu_app_token_superlogica
ACCESS_TOKEN=seu_access_token_superlogica
````

2. Rodar conciliação normalmente (sem envio de e-mail):

```bash
python conciliacao.py
```

3. Rodar e enviar relatório por e-mail (geralmente 1x por dia):

```bash
python conciliacao.py --enviar-email
```

---

## 📑 Como funciona internamente

* Para cada condomínio:

  * Carrega credenciais e certificados Banco Inter.
  * Busca extrato OFX e saldo via API Banco Inter.
  * Salva OFX temporariamente.
  * Consulta `id_contabanco` na API Superlógica.
  * Exclui conciliações antigas do mês.
  * Envia o arquivo OFX para conciliação.
  * Consulta e analisa resultados, detectando diferenças.
  * Remove arquivo temporário.
* Gera relatório final e envia por e-mail, se solicitado.

---

