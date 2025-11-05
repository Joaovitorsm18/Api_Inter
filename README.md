# Conciliação Bancária Automática (Banco Inter)

Sistema completo de automação financeira para condomínios que integra Banco Inter e Superlógica. Inclui download de extratos, conciliação automática e liquidação de despesas.

---

## 📁 Estrutura do Projeto

```
INTER/
│
├── CONDOMÍNIOS/                 # Credenciais e certificados por condomínio
│   ├── Jatobá 1 (JT)/
│   │   ├── .env
│   │   ├── Inter API_Certificado.crt
│   │   └── Inter API_Chave.key
│   ├── Pedro I (PE)/
│   │   └── …
│   └── …
├── CONDOMÍNIOS ANTIGOS/         # Condomínios desativados
├── SCRIPTS/                     # Scripts de automação
│   ├── extrato_mensal.py
│   ├── conciliacao.py
│   ├── liquidacao_despesas.py
│   ├── main.py
│   ├── utils/                   # Funções auxiliares
│   └── config/                  # Configurações
├── requirements.txt
└── README.md
```

---

## 🚀 Scripts e Funcionalidades

### 📄 `extrato_mensal.py` (main.py)
- **Execução**: Início de cada mês
- **Função**: Baixa extratos PDF e OFX do Banco Inter
- **Saída**: Salva no Google Drive organizado por condomínio/ano/mês

### 🔄 `conciliacao.py`
- **Execução**: 
  - A cada **30 minutos** (conciliação rápida)
  - **1x por dia** com `--enviar-email` (relatório completo)
- **Função**: 
  - Baixa extrato OFX da API Banco Inter
  - Integra com Superlógica para conciliação automática
  - Envia relatório por e-mail das pendências

### 💰 `liquidacao_despesas.py`
- **Execução**: Diariamente
- **Função**: 
  - Verifica despesas pendentes no Superlógica
  - Confirma liquidação no Banco Inter
  - Liquida automaticamente no sistema
  - Ideal para débitos automáticos (CEMIG, COPASA)

---

## ⚙️ Instalação e Configuração

### 1. Clone e ambiente virtual
```bash
git clone https://github.com/Joaovitorsm18/Api_Inter.git
cd Api_Inter

python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Configuração por Condomínio

Cada pasta em `CONDOMÍNIOS/` deve conter:

**`.env`**
```dotenv
ClientID=seu_client_id
ClientSecret=seu_client_secret
idCondominio=id_do_condominio_superlogica
```

**Certificados:**
- `Inter API_Certificado.crt`
- `Inter API_Chave.key`

### 3. Configuração Global (Raiz do Projeto)

**`.env`** (para conciliação e e-mails)
```dotenv
# Email (Gmail)
EMAIL_REMETENTE=seu_email@gmail.com
EMAIL_SENHA=sua_senha_app
EMAIL_DESTINATARIO=destinatario@exemplo.com

# Superlógica
APP_TOKEN=seu_app_token_superlogica
ACCESS_TOKEN=seu_access_token_superlogica
```

---

## 📋 Uso dos Scripts

### Extrato Mensal
```bash
python scripts/extrato_mensal.py
# ou
python main.py
```
Escolha entre mês atual ou anterior. Arquivos salvos em:
```
G:/Meu Drive/CONDOMÍNIOS/<Nome>/FINANCEIRO/BANCO/INTER/
 ├─ EXTRATOS PDF/<ANO>/<ANO-MM EXTRATO SIGLA>.pdf
 └─ EXTRATOS OFX/<ANO>/<ANO-MM EXTRATO SIGLA>.ofx
```

### Conciliação Automática
```bash
# Conciliação normal (a cada 30min)
python scripts/conciliacao.py

# Conciliação com relatório por e-mail (1x por dia)
python scripts/conciliacao.py --enviar-email
```

### Liquidação de Despesas
```bash
python scripts/liquidacao_despesas.py
```

---

## 🛠️ Funcionamento Interno

### Conciliação (`conciliacao.py`)
1. **Autenticação** via OAuth2 + mTLS no Banco Inter
2. **Download** do extrato OFX
3. **Integração Superlógica**:
   - Obtém `id_contabanco` do condomínio
   - Remove conciliações anteriores do mês
   - Envia arquivo OFX para conciliação
4. **Análise** de divergências entre banco e sistema
5. **Relatório** por e-mail das pendências

### Liquidação (`liquidacao_despesas.py`)
1. Busca **despesas pendentes** no Superlógica
2. Consulta **extrato Banco Inter** por pagamentos
3. **Concilia automaticamente** quando encontra match
4. **Liquida no Superlógica** com data correta
5. Envia **relatório** das liquidações realizadas

---

## 📦 Dependências

**`requirements.txt`**
```
python-dotenv==1.1.0
requests==2.32.3
```

---

## 🔄 Agendamento Recomendado

| Script | Frequência | Parâmetros |
|--------|------------|------------|
| `extrato_mensal.py` | 1x/mês (início) | - |
| `conciliacao.py` | A cada 30min | - |
| `conciliacao.py` | 1x/dia | `--enviar-email` |
| `liquidacao_despesas.py` | 1x/dia | - |

---

## 📊 Saídas e Relatórios

### E-mail de Conciliação
- Lista condomínios com pendências
- Detalha datas não conciliadas
- Mostra diferenças entre valores

### E-mail de Liquidação
- Confirma despesas liquidadas
- Detalha valores e datas
- Inclui IDs para auditoria

### Logs de Erro
- `log_erros.txt` com falhas por condomínio
- Continua processamento mesmo com erros individuais

---

## 🚨 Observações Importantes

- **Estrutura de pastas** é crítica - não altere sem revisar scripts
- **Certificados** devem estar atualizados para autenticação mTLS
- **Credenciais** são carregadas dinamicamente por condomínio
- **Retry automático** em caso de falhas de rede/API
- **Futuras melhorias**: Dockerização e agendamento em servidor

---

## 📞 Suporte

Em caso de problemas:
1. Verifique logs em `log_erros.txt`
2. Confirme estrutura de pastas e certificados
3. Valide credenciais no `.env` de cada condomínio