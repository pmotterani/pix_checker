# config.py
"""
⚙️ Arquivo de Configuração Central
------------------------------------
Este arquivo contém todas as variáveis, chaves de API, textos e parâmetros
que controlam o comportamento do bot. Mantenha as chaves secretas no arquivo .env.
"""
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# =============================================
# 🔑 CHAVES DE API E CONFIGURAÇÕES CRÍTICAS
# =============================================
# Token do seu bot, obtido com o @BotFather no Telegram.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Access Token da sua conta do Mercado Pago para processar pagamentos.
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")

# <<< ALTERAÇÃO: De DB_NAME para DATABASE_URL >>>
# URL de conexão do banco de dados PostgreSQL, fornecida pela Railway.
DATABASE_URL = os.getenv("DATABASE_URL")

# Define se o bot está em modo de produção. Afeta logs e avisos.
# Defina como "true" no seu ambiente de produção.
PRODUCTION = os.getenv("PRODUCTION", "False").lower() == "true"


# =============================================
# 👑 ADMINISTRADORES DO BOT
# =============================================
# Lista de IDs de usuários do Telegram que terão acesso aos comandos administrativos.
ADMIN_TELEGRAM_IDS = []
admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") # Ex: "123456,789012"
if admin_ids_str:
    try:
        # Converte a string de IDs separados por vírgula em uma lista de inteiros
        ADMIN_TELEGRAM_IDS = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',')]
    except ValueError:
        print("⚠️ ERRO: ADMIN_TELEGRAM_IDS no arquivo .env contém um valor inválido. Use números inteiros separados por vírgula.")


# =============================================
# 📊 CONFIGURAÇÕES FINANCEIRAS
# =============================================
# Taxa percentual cobrada sobre o valor do DEPÓSITO. (Ex: 0.10 para 10%)
TAXA_DEPOSITO_PERCENTUAL = 0.11

# Taxa percentual cobrada para SAQUES. (Ex: 0.05 para 5%)
TAXA_SAQUE_PERCENTUAL = 0.025

# Taxa fixa em R$ cobrada em CADA SAQUE, somada à percentual.
TAXA_SAQUE_FIXA = 3.50

# Limites para a criação de cobranças PIX.
LIMITE_MINIMO_DEPOSITO = 7.50
LIMITE_MAXIMO_DEPOSITO = 1000.00

LIMITE_MINIMO_SAQUE = 10.00 # <<< NEW SETTING


# =============================================
# 🏷️ STATUS DE TRANSAÇÕES (Uso interno)
# =============================================
STATUS_EM_ANALISE = "EM ANÁLISE"
STATUS_EM_ANDAMENTO = "EM ANDAMENTO"
STATUS_CONCLUIDO = "CONCLUÍDO"
STATUS_RECUSADO = "RECUSADO"
STATUS_FALHA_PAGAMENTO = "FALHA NO PAGAMENTO"
STATUS_DEPOSITO_PENDENTE = "AGUARDANDO PAGAMENTO"
STATUS_DEPOSITO_PAGO = "PAGO"
STATUS_AJUSTE_MANUAL = "AJUSTE MANUAL"


# =============================================
# 🤖 INFORMAÇÕES DO BOT E SUPORTE
# =============================================
NOME_BOT = "FlexiPay"
CANAL_OFICIAL = os.getenv("CANAL_OFICIAL", "@FlexiPayChannel")
BOT_SUPORTE = os.getenv("BOT_SUPORTE", "https://t.me/FlexiPaySuporteBot")
EMAIL_SUPORTE = "flexipaysuporte@gmail.com"
HORARIO_SUPORTE = "08:00 às 20:00 (GMT-3)"


# =============================================
# 📜 MENSAGENS PADRÃO (COPY)
# =============================================
# (O restante do arquivo permanece igual)
COPY_INTRO = (
    f"🌐 *Bem-vindo(a) ao {NOME_BOT}: o BOT do PIX SEM RASTRO!*"
)
MSG_BOAS_VINDAS = (
    "🚀 Faça depósitos, saques e transferências anonimamente, direto pelo Telegram.\n"
    "*Nada de CPF, nada de banco, nada de rastro.*\n\n"
    "💼 Esquece burocracia, esquece regra — aqui você tem *liberdade total* pra movimentar sua grana como quiser."
)
MSG_DIFERENCIAIS = (
    "\nNossos Diferenciais:\n"
    "✅ *Operações 100% Automatizadas*\n"
    "🛡️ *Sistema Blindado, Privado e Discreto*\n"
    "💸 *Saques Rápidos e Anônimos*\n"
    "👨‍💻 *Suporte Especializado*\n"
)
MSG_COMANDOS_BASE = (
    "\n\n📋 *Comandos Disponíveis:*\n"
    "`/pix <valor>` - Gerar QR Code para depósito.\n"
    "`/sacar <chave> <total>` - Sacar (débito total).\n"
    "`/carteira` - Consultar seu saldo.\n"
    "`/taxa` - Ver as taxas de operação.\n"
    "`/suporte` - Falar com o suporte.\n"
    "`/canal` - Entrar no nosso canal."
)


# =============================================
# ❗️ VALIDAÇÕES FINAIS (Garante que o bot possa iniciar)
# =============================================
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("FATAL: Token do Telegram não configurado. Defina a variável TELEGRAM_BOT_TOKEN no seu arquivo .env")

# <<< ALTERAÇÃO: Verifica a DATABASE_URL em produção >>>
if not DATABASE_URL and PRODUCTION:
    raise ValueError("FATAL: DATABASE_URL não configurada no ambiente de produção.")
elif not DATABASE_URL:
    print("AVISO: DATABASE_URL não configurada. O bot não conseguirá se conectar ao banco de dados.")

if not MERCADOPAGO_ACCESS_TOKEN and PRODUCTION:
    print("AVISO: Token do Mercado Pago não configurado. Funcionalidades de pagamento estarão desativadas.")

if not ADMIN_TELEGRAM_IDS:
    print("AVISO: Nenhum ADMIN_TELEGRAM_ID configurado. Funcionalidades administrativas não funcionarão.")
