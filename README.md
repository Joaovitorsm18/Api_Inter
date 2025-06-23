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
