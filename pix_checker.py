# pix_checker.py
"""
🤖 Verificador de PIX Standalone
---------------------------------
Este script executa em um loop contínuo para verificar transações de depósito
com status 'AGUARDANDO PAGAMENTO'.

Se um pagamento for confirmado no gateway, ele atualiza o saldo do usuário,
registra as taxas e notifica o usuário sobre o crédito.

Este arquivo é projetado para ser o único ponto de entrada da aplicação
em um ambiente como o Railway, focado apenas na tarefa de verificação.
"""
import telebot
import logging
from logging.handlers import RotatingFileHandler
import time
import decimal
import sys

# Módulos internos do projeto
import config
import database
import pay

# =============================================
# 📜 CONFIGURAÇÃO DE LOGGING
# =============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler("pix_checker.log", maxBytes=5*1024*1024, backupCount=2),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# 🚀 INICIALIZAÇÃO
# =============================================
try:
    logger.info("🗃️  Inicializando o banco de dados...")
    database.init_db() #
    logger.info("✅ Banco de dados pronto.")
except Exception as e:
    logger.critical(f"🆘 FATAL: Não foi possível conectar ou inicializar o banco de dados: {e}", exc_info=True)
    sys.exit("Erro crítico de banco de dados. Encerrando.")

# Inicializa o bot do Telegram apenas para enviar mensagens, sem polling.
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN) #
logger.info("✅ Objeto do Bot Telegram inicializado para envio de notificações.")


# =============================================
# 🛠️ FUNÇÃO DE PROCESSAMENTO DE PAGAMENTO
# =============================================
def processar_pagamento_aprovado(transaction):
    """
    Processa um depósito que foi confirmado como 'approved' no gateway.
    Atualiza o saldo, registra a taxa e notifica o usuário.
    """
    if not transaction or transaction['status'] != config.STATUS_DEPOSITO_PENDENTE: #
        logger.warning(f"Tentativa de processar transação {transaction['id']} com status inválido: {transaction['status']}.")
        return False

    user_id = transaction['user_telegram_id']
    transaction_id = transaction['id']
    # O valor vem do banco como um objeto Decimal
    valor_deposito = transaction['amount']

    # Usa Decimal para precisão monetária
    taxa_percentual = decimal.Decimal(str(config.TAXA_DEPOSITO_PERCENTUAL)) #
    taxa_deposito = valor_deposito * taxa_percentual
    valor_liquido = valor_deposito - taxa_deposito

    conn_atomic = None
    try:
        conn_atomic = database.get_db_connection() #
        
        # 1. Credita o valor líquido na carteira do usuário
        database.update_balance(user_id, float(valor_liquido), conn_ext=conn_atomic) #
        
        # 2. Registra a transação da taxa para o cálculo de lucros
        database.record_transaction( #
            user_telegram_id=user_id, type="FEE", amount=float(taxa_deposito),
            status=config.STATUS_CONCLUIDO, #
            admin_notes=f"Taxa de depósito referente à transação ID {transaction_id}",
            conn_ext=conn_atomic
        )
        
        # 3. Atualiza o status da transação de depósito para PAGO
        database.update_transaction_status(transaction_id, config.STATUS_DEPOSITO_PAGO, conn_ext=conn_atomic) #
        
        conn_atomic.commit()
        logger.info(f"✅ SUCESSO: Depósito {transaction_id} (Usuário: {user_id}) processado. Creditado: R$ {valor_liquido:.2f}")

        # 4. Notifica o usuário sobre o sucesso
        bot.send_message(user_id, f"✅ Seu depósito de R$ {valor_deposito:.2f} foi confirmado com sucesso!\n\n+ *R$ {valor_liquido:.2f}* foram adicionados à sua carteira.\nID da Transação: `{transaction_id}`", parse_mode="Markdown")
        return True

    except Exception as e:
        if conn_atomic:
            conn_atomic.rollback()
        logger.critical(f"🆘 FALHA CRÍTICA ao processar depósito {transaction_id} para usuário {user_id}: {e}", exc_info=True)
        return False
    finally:
        if conn_atomic:
            conn_atomic.close()

# =============================================
# 🤖 LÓGICA DO VERIFICADOR
# =============================================
def iniciar_verificador():
    """
    Função principal que roda em loop para buscar e processar transações.
    """
    logger.info("--- 🤖 VERIFICADOR DE PIX INICIADO ---")
    while True:
        try:
            # Busca transações pendentes das últimas 2 horas
            pending_transactions = database.get_pending_pix_transactions(hours=2) #
            
            if not pending_transactions:
                logger.info("Nenhuma transação pendente encontrada. Aguardando...")
            else:
                logger.info(f"Encontradas {len(pending_transactions)} transações pendentes. Verificando status...")
                for trans in pending_transactions:
                    logger.info(f"Verificando transação ID {trans['id']} (MP ID: {trans['mercado_pago_id']})...")
                    payment_details = pay.get_payment_details(trans['mercado_pago_id']) #
                    
                    if payment_details and payment_details.get("status") == "approved":
                        logger.info(f"➡️ Transação {trans['id']} foi PAGA. Processando crédito...")
                        processar_pagamento_aprovado(trans)
                    else:
                        status = "não encontrado"
                        if payment_details:
                           status = payment_details.get("status", "desconhecido")
                        logger.info(f"⬅️ Transação {trans['id']} ainda com status '{status}' no gateway.")

        except Exception as e:
            logger.error(f"💥 Erro inesperado no loop principal do verificador: {e}", exc_info=True)
        
        # Aguarda 30 segundos antes da próxima rodada de verificações
        time.sleep(30)

# =============================================
# ▶️ PONTO DE ENTRADA
# =============================================
if __name__ == '__main__':
    iniciar_verificador()
