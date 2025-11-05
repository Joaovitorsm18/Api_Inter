from datetime import datetime, timedelta
import time
import requests
import os
from dotenv import dotenv_values
from conciliacao import enviar_email_resumo
hoje = datetime.today()
data_inicio = hoje.replace(day=1)
proximo_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1)
data_fim = (proximo_mes - timedelta(days=1))


BASE_PATH = '../CONDOMÍNIOS'


def tratar_despesas_superlogica(dados_brutos):
    despesas_tratadas  = []

    for item in dados_brutos:
        apropriacoes_contas = []
            
        apropiacoes = item.get('apropriacao', [])
        

        for apropiacao_item in apropiacoes:
            conta = apropiacao_item.get('st_conta_cont')
            if conta:
                apropriacoes_contas.append(conta) 

        despesa = {
            'ID_DESPESA_DES' : item.get('id_despesa_des'),
            'ID_PARCELA_PDES' : item.get('id_parcela_pdes'),
            'ID_CONTATO_CON' : item.get('id_contato_con'),
            'ST_NOME_CON' : item.get('st_nome_con'),
            'DT_VENCIMENTO_PDES' : item.get('dt_vencimento_pdes'),
            'ID_FORMA_PAG' : item.get('id_forma_pag'),
            'ID_CONTABANCO_CB' : item.get('id_contabanco_cb'),
            'VL_VALOR_PDES' : item.get('vl_valor_pdes'),
            'ID_CONDOMINIO_COND' : item.get('id_condominio_cond'),
            'ID_CONTA_CATEGORIA': apropriacoes_contas,
        }
        despesas_tratadas.append(despesa)
    return despesas_tratadas

def get_despesas_pendentes_superlogica(id_condominio):  
    url = 'https://api.superlogica.net/v2/condor/despesas/index'
    
    params = {
        'comStatus': 'pendentes',
        'dtInicio': data_inicio.strftime('%m/%d/%Y'),   
        'dtFim': data_fim.strftime('%m/%d/%Y'),
        'filtrarpor': 'vencimento',
        'idCondominio': id_condominio,
        'CONTAS[0]': '2.2.2', # Conta categoria de água
        'CONTAS[1]': '2.2.1' # Conta categoria de luz
    }

    headers = {
        'Content-Type': 'application/json',
        'app_token': os.getenv('APP_TOKEN'),
        'access_token': os.getenv('ACCESS_TOKEN')
    }


    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() # Levanta HTTPError para 4xx/5xx
        dados_brutos = response.json()
        print(f"  Superlógica: {len(dados_brutos)} despesa(s) bruta(s) encontrada(s)")
        return tratar_despesas_superlogica(dados_brutos)
    except requests.exceptions.RequestException as e:
        print(f"  Erro ao buscar despesas na Superlógica (Condomínio {id_condominio})): {e}")
        return []

def get_extrato_inter(pasta_condominio ,client_id, client_secret):
        # Monta caminhos absolutos dos certificados
        cert_path = os.path.join(pasta_condominio, 'Inter API_Certificado.crt')
        key_path = os.path.join(pasta_condominio, 'Inter API_Chave.key')

        if not (os.path.exists(cert_path) and os.path.exists(key_path)):
            print(f"  Erro: Certificados Inter não encontrados em {pasta_condominio}. Verifique 'Inter API_Certificado.crt' e 'Inter API_Chave.key'.")
            return None

        request_body = f'client_id={client_id}&client_secret={client_secret}&scope=extrato.read&grant_type=client_credentials'

        response = requests.post("https://cdpj.partners.bancointer.com.br/oauth/v2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        cert=(cert_path, key_path),
        data=request_body)

        response.raise_for_status()

        token=response.json().get("access_token")

        opFiltros={"dataInicio": data_inicio.strftime("%Y-%m-%d"), "dataFim": data_fim.strftime("%Y-%m-%d")}
        cabecalhos={"Authorization": "Bearer " + token, "Content-Type": "Application/json"}

        try:
            extrato_response = requests.get("https://cdpj.partners.bancointer.com.br/banking/v2/extrato",
                params=opFiltros,
                headers=cabecalhos,
                cert=(cert_path, key_path)
            )
            extrato_response.raise_for_status()
            return extrato_response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Erro ao buscar extrato do Banco Inter: {e}")
        return None

def localizar_pagamentos_concessionarias(extrato_data):
    pagamentos_encontrados = {
        'CEMIG': [],
        'COPASA': []
    }

    if not extrato_data or 'transacoes' not in extrato_data:
        print("Erro: O extrato não contém a chave 'transacoes'.")
        return pagamentos_encontrados

    for transacao in extrato_data['transacoes']:
        # Verifica se é uma transação de débito (saída de dinheiro)
        if transacao.get('tipoOperacao') == 'D':
            descricao = transacao.get('descricao', '').upper()
            titulo = transacao.get('titulo', '').upper()

            # Procura por CEMIG
            if 'CEMIG' in descricao or 'CEMIG' in titulo:
                pagamentos_encontrados['CEMIG'].append(transacao)
            
            # Procura por COPASA
            if 'COPASA' in descricao or 'COPASA' in titulo:
                pagamentos_encontrados['COPASA'].append(transacao)
                
    return pagamentos_encontrados

def datas_compativeis(data_vencimento, data_pagamento, tolerancia_dias=5):
    """Retorna True se o pagamento for >= vencimento e <= vencimento + tolerância"""
    # tenta converter data no formato esperado
    formatos = ["%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]
    def parse_data(data_str):
        for f in formatos:
            try:
                return datetime.strptime(data_str, f)
            except ValueError:
                continue
        raise ValueError(f"Formato de data inválido: {data_str}")
    
    dt_venc = parse_data(data_vencimento)
    dt_pag = parse_data(data_pagamento)
    
    return dt_venc <= dt_pag <= (dt_venc + timedelta(days=tolerancia_dias))

def conciliar_e_liquidar(despesas, pagamentos):
    liquidadas = []

    for despesa in despesas:
        valor = float(despesa['VL_VALOR_PDES'])

        if '2.2.1' in despesa['ID_CONTA_CATEGORIA']:  # CEMIG
            for pagamento in pagamentos['CEMIG']:
                if (
                    abs(float(pagamento['valor']) - valor) < 0.01 
                    and datas_compativeis(despesa['DT_VENCIMENTO_PDES'], pagamento['dataEntrada'])
                ):
                    data_pagamento = pagamento['dataEntrada']
                    print(f"  🔄 Conciliando e liquidando despesa CEMIG ID {despesa['ID_DESPESA_DES']}")
                    liquidar_despesa(despesa, data_pagamento)

                    liquidadas.append({
                        'nome': 'CEMIG',
                        'id_despesa': despesa['ID_DESPESA_DES'],
                        'valor': valor,
                        'data_pagamento': data_pagamento
                    })

                    break

        elif '2.2.2' in despesa['ID_CONTA_CATEGORIA']:  # COPASA
            for pagamento in pagamentos['COPASA']:
                if (
                    abs(float(pagamento['valor']) - valor) < 0.01 
                    and datas_compativeis(despesa['DT_VENCIMENTO_PDES'], pagamento['dataEntrada'])
                ):
                    data_pagamento = pagamento['dataEntrada']
                    print(f"  🔄 Conciliando e liquidando despesa COPASA ID {despesa['ID_DESPESA_DES']}")
                    liquidar_despesa(despesa, data_pagamento)

                    liquidadas.append({
                        'nome': 'COPASA',
                        'id_despesa': despesa['ID_DESPESA_DES'],
                        'valor': valor,
                        'data_pagamento': data_pagamento
                    })

                    break
        
    return liquidadas

def processar_condominio(nome_condominio, resultado_liquidacao):
    pasta_condominio = os.path.join(BASE_PATH, nome_condominio)
    caminho_env = os.path.join(pasta_condominio, '.env')
    

    if not os.path.exists(caminho_env):
        print(f"⚠️  .env não encontrado para {nome_condominio}, pulando.")
        return
    
    config = dotenv_values(caminho_env)
    
    idCondominio = config.get('idCondominio')

    if not idCondominio:
        print(f"❌ idCondominio faltando em {nome_condominio}")
        return
    
    client_id = config.get('ClientID')
    client_secret = config.get('ClientSecret')

    # Caminhos absolutos para os certificados devem estar DENTRO da pasta do condomínio
    inter_cert_path = os.path.join(pasta_condominio, 'Inter API_Certificado.crt')
    inter_key_path = os.path.join(pasta_condominio, 'Inter API_Chave.key')

    if not all([client_id, client_secret, os.path.exists(inter_cert_path), os.path.exists(inter_key_path)]):
        print(f"  ❌ Credenciais ou certificados do Banco Inter ausentes ou inválidos para {nome_condominio}. Verifique o .env e os arquivos de certificado/chave.")
        return
    
    # 1. Buscar todas as despesas pendentes na Superlógica (em um período maior)
    print(f"  Buscando despesas pendentes na Superlógica para {nome_condominio}...")
    todas_despesas_superlogica = get_despesas_pendentes_superlogica(idCondominio)
    if not todas_despesas_superlogica:
        print(f"  Nenhuma despesa pendente encontrada na Superlógica para {nome_condominio}. Nenhuma conciliação necessária.")
        return
    else:
        #print(todas_despesas_superlogica)
        print(f"  Buscando extrato do Banco Inter para {nome_condominio}...")
        extrato_banco_raw = get_extrato_inter(pasta_condominio, client_id, client_secret)

        if not extrato_banco_raw:
            print(f"  Não foi possível obter o extrato para {nome_condominio}. Continuando...")
            return
    
        print(f"  Localizando pagamentos de concessionárias no extrato...")
        pagamentos_concessionarias_extrato = localizar_pagamentos_concessionarias(extrato_banco_raw)
        resultado = conciliar_e_liquidar(todas_despesas_superlogica, pagamentos_concessionarias_extrato)
        resultado_liquidacao[nome_condominio] = resultado
        print(f"🔍 Resultado da liquidação para {nome_condominio}: {resultado}")
        

def liquidar_despesa(dados_liquid, data_pagamento):

    if data_pagamento:
        # Converte de string para datetime
        try:
            data_pagamento_dt = datetime.strptime(data_pagamento, '%Y-%m-%d')
            data_liquidacao = data_pagamento_dt.strftime('%m/%d/%Y')
        except ValueError:
            print(f"⚠️  Formato de data inválido: {data_pagamento}. Usando data de hoje.")
            data_liquidacao = datetime.now().strftime('%m/%d/%Y')
    else:
        data_liquidacao = datetime.now().strftime('%m/%d/%Y')

    url = 'https://api.superlogica.net/v2/condor/despesas/liquidar'

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'app_token': os.getenv('APP_TOKEN'),
        'access_token': os.getenv('ACCESS_TOKEN')
    }   

    payload = {
        'ID_DESPESA_DES':        dados_liquid['ID_DESPESA_DES'],
        'ID_PARCELA_PDES':       dados_liquid['ID_PARCELA_PDES'],
        'ID_CONTATO_CON':        dados_liquid['ID_CONTATO_CON'],
        'ST_NOME_CON':           dados_liquid['ST_NOME_CON'],
        'DT_LIQUIDACAO_PDES':    data_liquidacao,  
        'ID_FORMA_PAG':          dados_liquid['ID_FORMA_PAG'],
        'ID_CONTABANCO_CB':      dados_liquid['ID_CONTABANCO_CB'],
        'NM_NUMERO_CH':          '',
        'VL_VALOR_PDES':         dados_liquid['VL_VALOR_PDES'],
        'CHECK_LIQUIDAR_TODOS_CH': 0,
        'EMITIR_RECIBO':         0,
        'VL_DESCONTO_PDES':      0,
        'VL_MULTA_PDES':         0,
        'VL_JUROS_PDES':         0,
        'VL_PAGO':               dados_liquid['VL_VALOR_PDES'],
        'ID_CONDOMINIO_COND':    dados_liquid['ID_CONDOMINIO_COND'],
        # Remova ou comente esta parte se não estiver anexando um NOVO arquivo:
        # 'ARQUIVOS[]': dados_liquid.get('ARQUIVOS_IDS', [])
    }
  
    response = requests.put(url, headers=headers, data=payload)
    response.raise_for_status()
    
     # Acesse o conteúdo JSON da resposta
    response_json = response.json()

    # Verifique se a resposta tem o formato esperado (lista com dicionário)
    if response_json and isinstance(response_json, list) and len(response_json) > 0:
        primeiro_item = response_json[0]
        status = primeiro_item.get('status')
        mensagem = primeiro_item.get('msg')
        print(f"Liquidação: Status: {status} - Mensagem: {mensagem}")
    else:
        print(f"Liquidação: Resposta inesperada da API: {response.text}")

def main():
    resultado_liquidacao = {}
    for nome_condominio in os.listdir(BASE_PATH):
        caminho_completo = os.path.join(BASE_PATH, nome_condominio)
        if os.path.isdir(caminho_completo):
            try:
                print(f"\n⏳ Processando {nome_condominio}...")
                processar_condominio(nome_condominio, resultado_liquidacao)
                print(f"✅ {nome_condominio} concluído com sucesso")
            except Exception as e:
                print(f"❌ Erro ao processar {nome_condominio}: {str(e)}")
                with open("log_erros.txt", "a") as log:
                    log.write(f"[{datetime.now()}] {nome_condominio}: {str(e)}\n")
            time.sleep(2) # Adiciona um atraso de 1 segundo entre cada condomínio
    
    liquidados = {
        nome: resultado for nome, resultado in resultado_liquidacao.items()
        if resultado is not None and len(resultado) > 0
    }
    if liquidados:
        corpo_email = "Condomínios com liquidações realizadas:\n\n"

        for nome, despesas in liquidados.items():
            corpo_email += f"🏢 {nome}:\n"
            for d in despesas:
                corpo_email += f"   ✅ {d['nome']}: R${d['valor']:.2f} em {d['data_pagamento']} (ID {d['id_despesa']})\n"
            corpo_email += "\n"
        enviar_email_resumo("✅ Relatório de Liquidações Realizadas", corpo_email, "Relatório de Liquidações Automáticas Diárias")

    else:
        print("📬 Nenhuma liquidação realizada.")
    

if __name__ == "__main__":
    main()