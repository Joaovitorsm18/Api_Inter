import os
from dotenv import dotenv_values
from datetime import datetime, timedelta
import requests
import base64
import re
import time

BASE_PATH = '../CONDOMÍNIOS'

# --- Funções de Data ---
def get_mes_atual_datas():
    """Retorna o primeiro e último dia do mês atual no formato YYYY-MM-DD."""
    hoje = datetime.today()
    data_inicio = hoje.replace(day=1)
    # Para obter o último dia do mês:
    # Avança para o primeiro dia do mês seguinte e subtrai 1 dia
    proximo_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1)
    data_fim = proximo_mes - timedelta(days=1)
    return data_inicio.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d")

def get_mes_anterior_datas():
    """Retorna o primeiro e último dia do mês anterior no formato YYYY-MM-DD."""
    hoje = datetime.today()
    # Último dia do mês anterior
    data_fim = hoje.replace(day=1) - timedelta(days=1)
    data_inicio = data_fim.replace(day=1)
    return data_inicio.strftime("%Y-%m-%d"), data_fim.strftime("%Y-%m-%d")

# Extrair sigla
def extract_sigla(nome_condominio):
    """
    Extrai a sigla entre parênteses do nome do condomínio.
    Ex: "Jatobá 1 (JT)" -> "JT"
    """
    match = re.search(r'\((.*?)\)', nome_condominio)
    if match:
        return match.group(1) # Retorna o conteúdo dentro dos parênteses
    return None # Retorna None se não encontrar

# Transforma json em ofx
def build_ofx(transacoes, saldo_final, dt_start_filter, dt_end_filter):
    """
    Converte a lista de transações do Banco Inter para formato OFX
    
    Args:
        transacoes (list): Lista de transações no formato JSON
        saldo_final (float): Saldo final da conta (opcional)
        
    Returns:
        str: String no formato OFX
    """
    # Informações da conta (fixas para Banco Inter)
    account_info = {
        "bank_org": "Banco Intermedium S/A",
        "bank_id": "077",
        "branch_id": "0001-9",
        "account_id": "",  # Substitua pelo número real da conta
    }
    
    # Usar as datas de início e fim do filtro
    start_date_ofx = datetime.strptime(dt_start_filter, "%Y-%m-%d").strftime("%Y%m%d")
    end_date_ofx = datetime.strptime(dt_end_filter, "%Y-%m-%d").strftime("%Y%m%d")

    # Cabeçalho OFX
    ofx = f"""OFXHEADER:100

DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<DTSERVER>{datetime.now().strftime("%Y%m%d")}</DTSERVER>
<LANGUAGE>POR</LANGUAGE>
<FI>
<ORG>{account_info['bank_org']}</ORG>
<FID>{account_info['bank_id']}</FID>
</FI>
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001</TRNUID>
<STATUS>
<CODE>0</CODE>
<SEVERITY>INFO</SEVERITY>
</STATUS>
<STMTRS>
<CURDEF>BRL</CURDEF>
<BANKACCTFROM>
<BANKID>{account_info['bank_id']}</BANKID>
<BRANCHID>{account_info['branch_id']}</BRANCHID>
<ACCTID>{account_info['account_id']}</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE>
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>{start_date_ofx}</DTSTART>
<DTEND>{end_date_ofx}</DTEND>
"""

    # Mapeamento de tipos de transação para TRNTYPE
    trn_type_map = {
        "DEBITO_AUTOMATICO": "PAYMENT",
        "PIX": "PAYMENT",  # Será ajustado abaixo baseado no tipoOperacao
        "PAGAMENTO": "PAYMENT",
        "COMPRA_DEBITO": "PAYMENT",
        "OUTROS": "PAYMENT",
        "DARF": "PAYMENT"
    }

    # Contador para gerar FITIDs sequenciais por dia
    fitid_counters = {}

    # Processar cada transação
    for trn in transacoes:
        # Determinar o tipo de transação
        trn_type = trn_type_map.get(trn["tipoTransacao"], "OTHER")
        
        # Ajustar para crédito/débito
        if trn["tipoTransacao"] == "PIX":
            trn_type = "CREDIT" if trn["tipoOperacao"] == "C" else "PAYMENT"
        
        # Formatar valor (negativo para débitos)
        amount = float(trn["valor"])
        if trn["tipoOperacao"] == "D":
            amount = -amount
        
        # Formatar data no formato YYYYMMDD
        dt_posted = datetime.strptime(trn["dataTransacao"], "%Y-%m-%d").strftime("%Y%m%d")
        
        # Gerar FITID no padrão do Banco Inter (YYYYMMDD + 077 + sequencial)
        if dt_posted not in fitid_counters:
            fitid_counters[dt_posted] = 1
        else:
            fitid_counters[dt_posted] += 1
        
        fit_id = f"{dt_posted}{account_info['bank_id']}{fitid_counters[dt_posted]:03d}"
        
        memo = ""
        if trn["tipoTransacao"] == "DEBITO_AUTOMATICO":
            memo = f'Debito automatico: "{trn.get("descricao", "")}"'
        elif trn["tipoTransacao"] == "PIX":
            end_to_end = trn.get("detalhes", {}).get("endToEndId", "")
            # Extrai apenas a parte do código antes do ano (ex: E00416968202505202050bX9x5sS8lY9 -> 00416968)
            pix_id = end_to_end[1:9] if end_to_end and len(end_to_end) > 9 else ""
            
            if trn["tipoOperacao"] == "C":
                memo = f'Pix recebido: "Cp :{pix_id}-{trn.get("descricao", "")}"'
            else:
                memo = f'Pix enviado: "Cp :{pix_id}-{trn.get("descricao", "")}"'
        elif trn["tipoTransacao"] == "COMPRA_DEBITO":
            memo = f'Compra no debito: "No estabelecimento {trn.get("descricao", "").strip()}"'
        elif trn["tipoTransacao"] == "PAGAMENTO":
            memo = f'Pagamento efetuado: "{trn.get("descricao", "")}"'
        elif "DARF" in trn.get("titulo", "").upper():
            memo = "DARF NUMERADO"
        else:
            memo = f'{trn.get("titulo", "")}: {trn.get("descricao", "")}'

        # Adicionar transação ao OFX
        ofx += f"""<STMTTRN>
<TRNTYPE>{trn_type}</TRNTYPE>
<DTPOSTED>{dt_posted}</DTPOSTED>
<TRNAMT>{amount:.2f}</TRNAMT>
<FITID>{fit_id}</FITID>
<CHECKNUM>{account_info['bank_id']}</CHECKNUM>
<REFNUM>{account_info['bank_id']}</REFNUM>
<MEMO>{memo}</MEMO>
</STMTTRN>
"""

    # Rodapé OFX com saldo
    saldo = saldo_final if saldo_final is not None else 0.00
    ofx += f"""</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>{saldo:.2f}</BALAMT>
<DTASOF>{datetime.now().strftime("%Y%m%d")}</DTASOF>
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""

    return ofx


def processar_condominio(nome_condominio, data_inicio, data_fim):
    pasta_condominio = os.path.join(BASE_PATH, nome_condominio)
    caminho_env = os.path.join(pasta_condominio, '.env')

    if not os.path.exists(caminho_env):
        print(f"⚠️  .env não encontrado para {nome_condominio}, pulando.")
        return
    
    # Carrega o .env daquele condomínio
    config = dotenv_values(caminho_env)

    client_id = config.get('ClientID')
    client_secret = config.get('ClientSecret')

    if not client_id or not client_secret:
        print(f"❌ CLIENT_ID ou CLIENT_SECRET faltando em {nome_condominio}")
        return
    
    # Monta caminhos absolutos dos certificados
    cert_path = os.path.join(pasta_condominio, 'Inter API_Certificado.crt')
    key_path = os.path.join(pasta_condominio, 'Inter API_Chave.key')

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print(f"❌ Certificado ou chave não encontrados para {nome_condominio}")
        return
    

    #capturando token
    request_body = f'client_id={client_id}&client_secret={client_secret}&scope=extrato.read&grant_type=client_credentials'
    
    response = requests.post("https://cdpj.partners.bancointer.com.br/oauth/v2/token", 
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    cert=(cert_path, key_path),
    data=request_body)

    response.raise_for_status()

    token=response.json().get("access_token") #token capturado
   
    opFiltros={"dataInicio": data_inicio, "dataFim": data_fim}
    cabecalhos={"Authorization": "Bearer " + token, "Content-Type": "Application/json"}

    #Caminho teste
    #caminho_teste = f'C:/Users/User/Downloads/teste/{nome_condominio}' 

    #Caminho para salvar dentro do Drive
    caminho_drive = f'G:/Meu Drive/CONDOMÍNIOS/{nome_condominio}/FINANCEIRO/BANCO/INTER'

    #Converte a string 'data_inicio' para um objeto datetime
    data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%d")
    # Extrai o ano do objeto datetime
    ano = data_inicio_obj.year
    mes = data_inicio_obj.strftime("%m")
    sigla = extract_sigla(nome_condominio)
    nome_arquivo_final = f'{ano}-{mes} EXTRATO {sigla}'

    # Salva PDF
    response_pdf = requests.get("https://cdpj.partners.bancointer.com.br/banking/v2/extrato/exportar",
        params=opFiltros,
        headers=cabecalhos,
        cert=(cert_path, key_path),
    )
    try:
        response_pdf.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro ao baixar PDF do condomínio {nome_condominio}: {e}")
        return
    
    pdf_base64 = response_pdf.json().get("pdf")
    caminho_pdf = f'{caminho_drive}/EXTRATOS PDF/{ano}'
    #caminho_pdf_teste = f'{caminho_teste}/EXTRATOS PDF/{ano}'
    os.makedirs(caminho_pdf, exist_ok=True)
    with open(f'{caminho_pdf}/{nome_arquivo_final}.pdf', "wb") as f:
        f.write(base64.b64decode(pdf_base64))
    print(f'✅ PDF salvo como {nome_arquivo_final}.pdf')

    # Saldo
    opFiltros_saldo={"dataSaldo": data_fim}
    response_saldo = requests.get("https://cdpj.partners.bancointer.com.br/banking/v2/saldo",
        params=opFiltros_saldo,
        headers=cabecalhos,
        cert=(cert_path, key_path),
    )
    response_saldo.raise_for_status()
    saldo = response_saldo.json().get("disponivel")

    # Extrato enriquecido
    response_ofx = requests.get("https://cdpj.partners.bancointer.com.br/banking/v2/extrato/completo",
        params=opFiltros,
        headers=cabecalhos,
         cert=(cert_path, key_path),
    )
    try:
        response_ofx.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro ao baixar OFX do condomínio {nome_condominio}: {e}")
        return
    
    transacoes = response_ofx.json().get("transacoes", [])
    ofx_data = build_ofx(transacoes, saldo, data_inicio, data_fim)
    caminho_ofx = f'{caminho_drive}/EXTRATOS OFX/{ano}'
    #caminho_ofx_teste = f'{caminho_teste}/EXTRATOS OFX/{ano}'

    os.makedirs(caminho_ofx, exist_ok=True)
    with open(f'{caminho_ofx}/{nome_arquivo_final}.ofx', "w", encoding="utf-8") as f:
        f.write(ofx_data)
    print(f'✅ OFX salvo como {nome_arquivo_final}.ofx')

def processar_condominio_com_retry(nome_condominio, data_inicio, data_fim):
    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            processar_condominio(nome_condominio, data_inicio, data_fim)
            return  # Sucesso - sai da função
        except (requests.exceptions.RequestException, ConnectionError) as e:
            if tentativa == tentativas:
                raise  # Última tentativa - re-lança a exceção
                
            espera = 2 ** tentativa  # Espera exponencial
            print(f"⚠️ Tentativa {tentativa} falhou para {nome_condominio}. Tentando novamente em {espera}s...")
            time.sleep(espera)
        except Exception as e:
            raise  # Outros erros não tentamos novamente


def main():
     # Seleção de mês no início do programa
    texto_opcoes = """
Selecione o período para os extratos:
1 - Mês atual
2 - Mês anterior
"""
    opcao = input(texto_opcoes).strip()

    data_inicio_selecionada = None
    data_fim_selecionada = None

    if opcao == "1":
        print("Mês atual selecionado.")
        data_inicio_selecionada, data_fim_selecionada = get_mes_atual_datas()
    elif opcao == "2":
        print("Mês anterior selecionado.")
        data_inicio_selecionada, data_fim_selecionada = get_mes_anterior_datas()
    else:
        print("❌ Opção inválida. Por favor, digite '1' ou '2'.")
        return # Sai do programa se a opção for inválida

    print(f"Datas de Extrato: {data_inicio_selecionada} a {data_fim_selecionada}")

    for nome_condominio in os.listdir(BASE_PATH):
        caminho_completo = os.path.join(BASE_PATH, nome_condominio)
        if os.path.isdir(caminho_completo):
            try:
                print(f"\n⏳ Processando {nome_condominio}...")
                processar_condominio_com_retry(nome_condominio, data_inicio_selecionada, data_fim_selecionada)
                print(f"✅ {nome_condominio} concluído com sucesso")
            except Exception as e:
                print(f"❌ Erro ao processar {nome_condominio}: {str(e)}")
                with open("log_erros.txt", "a") as log:
                    log.write(f"[{datetime.now()}] {nome_condominio}: {str(e)}\n")
            time.sleep(2) # Adiciona um atraso de 1 segundo entre cada condomínio

if __name__ == "__main__":
    main()

    
    