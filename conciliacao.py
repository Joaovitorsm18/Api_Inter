import os
from datetime import datetime, timedelta
from main import build_ofx, get_mes_atual_datas
from dotenv import dotenv_values, load_dotenv
import requests
import time
from collections import defaultdict
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import argparse
import tempfile

BASE_PATH = './CONDOMÍNIOS'

load_dotenv()


def enviar_email_resumo(assunto, corpo):
    remetente_email = os.getenv("EMAIL_REMETENTE")
    remetente_nome = "Relatório de Conciliação Diária"
    senha = os.getenv("EMAIL_SENHA")  
    email_destinatario = os.getenv("EMAIL_DESTINATARIO")

    msg = EmailMessage()
    msg.set_content(corpo)
    msg["Subject"] = assunto
    msg["From"] = formataddr((remetente_nome, remetente_email))
    msg["To"] = email_destinatario

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(remetente_email, senha)
            smtp.send_message(msg)
        print("📨 E-mail enviado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao enviar e-mail: {e}")

def get_id_contabanco(id_condominio):
    headers = {
        'app_token': os.getenv('APP_TOKEN'),
        'access_token': os.getenv('ACCESS_TOKEN')
    }

    params = {
        'exibirDadosAgencia': 0,
        'exibirContasFechadas': 0,
        'exibirDadosBanco': 0,
        'exibirContasAtivas': 0,
        'idCondominio': id_condominio,
    }

    response = requests.get('https://api.superlogica.net/v2/condor/contabancos/index',
        headers=headers,
        params=params
    )
    response.raise_for_status()
    return response.json()[0].get('id_contabanco_cb')

def conciliar_super(local_arquivo, id_contabanco):
    headers = {
        'app_token': os.getenv('APP_TOKEN'),
        'access_token': os.getenv('ACCESS_TOKEN')
    }

    data = {
        'ID_CONTABANCO_CB': id_contabanco,
    }
    try:
        datas = get_mes_atual_datas()
   
        params = {
            'dtInicio': datas[0],
            'dtFim': datas[1],
            'idConta': id_contabanco
        }
        # remove o arquivo anterior primeiro
        response = requests.post('https://api.superlogica.net/v2/condor/conciliacao/delete',
             headers=headers,
             params=params
        )
        response.raise_for_status()
        print(f'✅ Arquivo excluído')
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro ao excluir extrato no Super: {e}")
        return          

    # Abre o arquivo OFX no modo binário
    with open(local_arquivo, 'rb') as f:
        files = {
            'ARQUIVO': (local_arquivo, f, 'application/octet-stream')
        }
        response_conciliacao = requests.post("https://api.superlogica.net/v2/condor/conciliacao/put",
            headers=headers,
            data=data,
            files=files
        )
        try:
            response_conciliacao.raise_for_status()
            print(f'✅ Arquivo enviado')
        except requests.exceptions.HTTPError as e:
            print(f"❌ Erro ao subir arquivio de conciliação: {e}")
            return
        
def get_conciliacao_atual(id_contabanco, id_condominio):
    datas = get_mes_atual_datas()
    data_inicio = datetime.strptime(datas[0], "%Y-%m-%d").strftime("%m/%d/%Y")
    data_fim = datetime.strptime(datas[1], "%Y-%m-%d").strftime("%m/%d/%Y")

    headers = {
        'app_token': os.getenv('APP_TOKEN'),
        'access_token': os.getenv('ACCESS_TOKEN')
    }

    params = {
        'dtInicio': data_inicio,
        'dtFim': data_fim,
        'idConta': id_contabanco,
        'idCondominio': id_condominio,
    }

    response = requests.get('https://api.superlogica.net/v2/condor/conciliacao',
        headers=headers,
        params=params
    )
    try:
        response.raise_for_status()      
        res_json = response.json()
        #print(res_json)
        if isinstance(res_json, list):
            return res_json
        elif isinstance(res_json, dict):
            return res_json.get('itens', [])
        else:
            return []
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erro ao pegar conciliação atual: {e}")
        return
    
def analisar_conciliacao(itens):
    # Agrupar por data
    totais_software = defaultdict(float)
    totais_banco = defaultdict(float)
    detalhes_por_data = defaultdict(lambda: {'software': [], 'banco': []})
    
    for item in itens:
        # Parse valores corretamente
        valor_banco = float(item.get("valor_banco", "0").replace(",", "."))
        valor_software = float(item.get("valor_software", "0").replace(",", "."))
        
        # Pega data (de preferência a data explícita, senão a geral)
        data_banco = item.get("data_banco") or item.get("data")
        data_software = item.get("data_software") or item.get("data")

        if item.get("valor_banco"):
            totais_banco[data_banco] += valor_banco
            detalhes_por_data[data_banco]['banco'].append({
                'valor': valor_banco,
                'descricao': item.get("descricao_banco")
            })

        if item.get("valor_software"):
            totais_software[data_software] += valor_software
            detalhes_por_data[data_software]['software'].append({
                'valor': valor_software,
                'descricao': item.get("descricao_software")
            })

    # Conciliar por data
    todas_datas = set(totais_banco.keys()) | set(totais_software.keys())
    diferencas = []
    conciliado = True

    for data in sorted(todas_datas):
        valor_banco = round(totais_banco.get(data, 0.0), 2)
        valor_software = round(totais_software.get(data, 0.0), 2)

        # Converte a data da diferença para datetime
        try:
            data_dt = datetime.strptime(data, "%m/%d/%Y")
        except ValueError:
            data_dt = None  # Se não conseguir converter, considera como erro

        # Só adiciona ao relatório se for até o dia atual
        if abs(valor_banco - valor_software) > 0.01 and (data_dt is None or data_dt.date() <= datetime.today().date()):
            conciliado = False
            diferencas.append({
                'data': data,
                'valor_banco': valor_banco,
                'valor_software': valor_software,
                'detalhes_banco': detalhes_por_data[data]['banco'],
                'detalhes_software': detalhes_por_data[data]['software'],
            })

    total_banco = round(sum(totais_banco.values()), 2)
    total_software = round(sum(totais_software.values()), 2)

    return {
        'conciliado': conciliado,
        'diferencas': diferencas,
        'total_banco': total_banco,
        'total_software': total_software
    }

def exibir_resultado_conciliacao(analise):
    if analise.get("conciliado", False):
        return "✅ Conciliado"
    
    datas_nao_conciliadas = []

    for dif in analise.get("diferencas", []):
        data_str = dif.get("data")
        if data_str:
            try:
                data_formatada = datetime.strptime(data_str, "%m/%d/%Y").strftime("%d/%m/%Y")
                datas_nao_conciliadas.append(data_formatada)
            except ValueError:
                datas_nao_conciliadas.append(data_str)  # Se falhar, mantém a original

    if datas_nao_conciliadas:
        return "❌ Não conciliado nas datas:\n" + "\n".join(f"- {data}" for data in datas_nao_conciliadas)
    else:
        return "⚠️ Diferenças encontradas, mas sem datas específicas."
   
def processar_condominio(nome_condominio, data_inicio, data_fim, resultados_conciliacao):
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
    caminho_teste = tempfile.gettempdir() 
    
    os.makedirs(caminho_teste, exist_ok=True)
    caminho_com_nome = f'{caminho_teste}/{nome_condominio}.ofx'
    with open(caminho_com_nome, "w", encoding="utf-8") as f:
        f.write(ofx_data)
    print(f'✅ OFX salvo como {nome_condominio}.ofx')

    id_condominio = config.get('idCondominio')
    if not id_condominio:
        print(f"❌ id_condominio faltando em {nome_condominio}")
        return
    
    id_contabanco = get_id_contabanco(id_condominio)
    conciliar_super(caminho_com_nome ,id_contabanco)
    os.remove(caminho_com_nome)
    
    concilidacao_atual = get_conciliacao_atual(id_contabanco, id_condominio)
    conciliacao_analisada = analisar_conciliacao(concilidacao_atual)
    resultado = exibir_resultado_conciliacao(conciliacao_analisada)
    resultados_conciliacao[nome_condominio] = resultado
    print(resultado)


def main(enviar_email=False): 
    resultados_conciliacao = {}
    hoje = datetime.today()
    data_inicio = hoje.replace(day=1).strftime("%Y-%m-%d")
    data_fim = hoje.strftime("%Y-%m-%d")
    for nome_condominio in os.listdir(BASE_PATH):
        caminho_completo = os.path.join(BASE_PATH, nome_condominio)
        if os.path.isdir(caminho_completo):
            try:
                print(f"\n⏳ Processando {nome_condominio}...")
                processar_condominio(nome_condominio, data_inicio, data_fim, resultados_conciliacao)
                print(f"✅ {nome_condominio} concluído com sucesso")
            except Exception as e:
                print(f"❌ Erro ao processar {nome_condominio}: {str(e)}")
                with open("log_erros.txt", "a") as log:
                    log.write(f"[{datetime.now()}] {nome_condominio}: {str(e)}\n")
            time.sleep(2) # Adiciona um atraso de 1 segundo entre cada condomínio
    # Filtra apenas os que não foram conciliados
    if enviar_email:
        nao_conciliados = {
            nome: resultado for nome, resultado in resultados_conciliacao.items()
            if resultado.startswith("❌")
        }

        if nao_conciliados:
            corpo_email = "Condomínios com conciliação não finalizada:\n\n"
            for nome, resultado in nao_conciliados.items():
                corpo_email += f"- {nome}:\n{resultado}\n\n"
            
            enviar_email_resumo("Relatório de Conciliação - Erros Encontrados", corpo_email)
        else:
            print("📬 Todos os condomínios foram conciliados com sucesso.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--enviar-email", action="store_true", help="Enviar e-mail com o relatório de conciliação")
    args = parser.parse_args()
    
    main(enviar_email=args.enviar_email)
