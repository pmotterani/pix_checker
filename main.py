# main.py (Versão com Verificador Periódico e sem Webhook)
"""
🌐 FlexiPay Bot
---------------
Sistema completo de movimentação financeira via Telegram com foco em
privacidade, automação e facilidade de uso.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
from logging.handlers import RotatingFileHandler
import threading
import time

# Módulos internos do projeto
import config
import database
import pay
import adm

# =============================================
# 📜 CONFIGURAÇÃO DE LOGGING
# =============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler("flexypay.log", maxBytes=5*1024*1024, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# 🚀 INICIALIZAÇÃO DO BOT
# =============================================
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
adm.register_admin_handlers(bot)

logger.info(f"✅ Iniciando {config.NOME_BOT}...")
logger.info(f"   - Modo: {'PRODUÇÃO' if config.PRODUCTION else 'DESENVOLVIMENTO'}")
logger.info(f"   - Admins Configurados: {len(config.ADMIN_TELEGRAM_IDS)}")

# =============================================
# 🎬 FUNÇÃO PARA CRIAR O MENU PRINCIPAL
# =============================================
# (A função criar_menu_principal() permanece exatamente igual)
def criar_menu_principal():
    """Cria e retorna o teclado do menu principal com botões interativos."""
    markup = InlineKeyboardMarkup(row_width=2)
    
    btn_depositar = InlineKeyboardButton("📥 Depositar (PIX)", callback_data="menu_depositar")
    btn_sacar = InlineKeyboardButton("📤 Sacar", callback_data="menu_sacar")
    btn_carteira = InlineKeyboardButton("💼 Minha Carteira", callback_data="menu_carteira")
    btn_taxas = InlineKeyboardButton("💰 Taxas", callback_data="menu_taxas")
    btn_suporte = InlineKeyboardButton("🛎️ Suporte", callback_data="menu_suporte")
    btn_canal = InlineKeyboardButton("📢 Canal", callback_data="menu_canal")

    markup.add(btn_depositar, btn_sacar, btn_carteira, btn_taxas, btn_suporte, btn_canal)
    # Adicionando o botão de verificação ao menu
    btn_verificar = InlineKeyboardButton("🔄 Verificar PIX", callback_data="menu_verificar")
    markup.add(btn_verificar)
    return markup

# =============================================
# 🛠️ FUNÇÃO AUXILIAR PARA PROCESSAR PAGAMENTOS
# =============================================
def processar_pagamento_aprovado(transaction):
    """
    Função centralizada que processa um pagamento de depósito aprovado.
    Atualiza saldo, registra taxas e notifica o usuário.
    Retorna True se o processamento foi bem-sucedido.
    """
    if not transaction or transaction['status'] != config.STATUS_DEPOSITO_PENDENTE:
        return False

    user_id = transaction['user_telegram_id']
    valor_deposito = transaction['amount']
    transaction_id = transaction['id']

    # Lógica de taxa de depósito
    taxa_deposito = valor_deposito * config.TAXA_DEPOSITO_PERCENTUAL
    valor_liquido = valor_deposito - taxa_deposito

    # Operação atômica para garantir consistência
    conn_atomic = database.get_db_connection()
    try:
        # Credita o valor líquido na carteira do usuário
        database.update_balance(user_id, valor_liquido, conn_ext=conn_atomic)
        
        # Registra a taxa para cálculo de lucro
        database.record_transaction(
            user_telegram_id=user_id, type="FEE", amount=taxa_deposito,
            status=config.STATUS_CONCLUIDO,
            admin_notes=f"Taxa de depósito referente à transação ID {transaction_id}",
            conn_ext=conn_atomic
        )
        
        # Atualiza o status da transação de depósito original para PAGO
        database.update_transaction_status(transaction_id, config.STATUS_DEPOSITO_PAGO, conn_ext=conn_atomic)
        
        conn_atomic.commit()
        logger.info(f"✅ Depósito ID {transaction_id} para user {user_id} APROVADO. Valor creditado: R${valor_liquido:.2f}")

        # Notifica o usuário
        bot.send_message(user_id, f"✅ Seu depósito de R$ {valor_deposito:.2f} foi confirmado com sucesso!\n\n+ *R$ {valor_liquido:.2f}* foram adicionados à sua carteira.\nID da Transação: `{transaction_id}`")
        return True

    except Exception as e:
        if conn_atomic: conn_atomic.rollback()
        logger.critical(f"🆘 FALHA CRÍTICA ao processar depósito para ID {transaction_id}: {e}")
        return False
    finally:
        if conn_atomic: conn_atomic.close()

# =============================================
# 🤖 LÓGICA DO VERIFICADOR AUTOMÁTICO
# =============================================
def verificador_pix_periodico():
    """
    Esta função roda em uma thread separada, verificando PIX pendentes
    periodicamente.
    """
    logger.info("🤖 Verificador periódico de PIX iniciado.")
    while True:
        try:
            pending_transactions = database.get_pending_pix_transactions(hours=2)
            if pending_transactions:
                logger.info(f"Verificando {len(pending_transactions)} transações PIX pendentes...")
                for trans in pending_transactions:
                    payment_details = pay.get_payment_details(trans['mercado_pago_id'])
                    if payment_details and payment_details.get("status") == "approved":
                        logger.info(f"Transação pendente {trans['id']} foi paga. Processando...")
                        processar_pagamento_aprovado(trans)
        except Exception as e:
            logger.error(f"💥 Erro no laço do verificador periódico de PIX: {e}", exc_info=True)
        
        # Aguarda 20 segundos para a próxima verificação
        time.sleep(20)

# =============================================
# 🏷️ HANDLERS DE COMANDOS DO USUÁRIO
# =============================================

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    user = message.from_user
    logger.info(f"👋 Usuário {user.id} ('{user.first_name}') iniciou o bot.")
    database.create_user_if_not_exists(user.id, user.username, user.first_name)
    saldo = database.get_balance(user.id)
    welcome_text = (
        f"Olá, *{user.first_name}*!\n"
        f"Seu saldo atual é de *R$ {saldo:.2f}*.\n\n"
        f"👇 Escolha uma opção abaixo para começar:"
    )
    bot.reply_to(message, welcome_text, reply_markup=criar_menu_principal())

# <<< NOVO COMANDO >>>
@bot.message_handler(commands=['verificar'])
def handle_verificar_command(message):
    user_id = message.from_user.id
    parts = message.text.split()

    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Uso incorreto!\nPor favor, envie o comando no formato:\n`/verificar <ID da Transação>`")
        return

    try:
        transaction_id = int(parts[1])
    except (ValueError, IndexError):
        bot.reply_to(message, "❌ ID inválido. O ID da transação deve ser um número.")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    
    transaction = database.get_transaction_by_id_and_user(transaction_id, user_id)

    if not transaction:
        bot.reply_to(message, f"❌ Transação com ID `{transaction_id}` não encontrada ou não pertence a você.")
        return

    if transaction['status'] == config.STATUS_DEPOSITO_PAGO:
        bot.reply_to(message, f"✅ A transação `{transaction_id}` já foi confirmada e o valor creditado.")
        return
        
    if transaction['status'] != config.STATUS_DEPOSITO_PENDENTE:
        bot.reply_to(message, f"ℹ️ A transação `{transaction_id}` não está pendente de pagamento (Status: {transaction['status']}).")
        return

    # Se a transação está pendente, verifica no gateway
    payment_details = pay.get_payment_details(transaction['mercado_pago_id'])
    
    if payment_details and payment_details.get("status") == "approved":
        logger.info(f"Verificação manual para transação {transaction_id} foi bem-sucedida. Processando...")
        if processar_pagamento_aprovado(transaction):
            bot.reply_to(message, f"Ótima notícia! Verificamos e confirmamos seu pagamento para a transação `{transaction_id}`.")
        else:
            bot.reply_to(message, f"🆘 Encontramos o pagamento para a transação `{transaction_id}`, mas ocorreu um erro crítico ao creditar o valor. Contate o suporte.")
    else:
        status_gateway = payment_details.get("status", "desconhecido") if payment_details else "não encontrado"
        bot.reply_to(message, f"⌛ A transação `{transaction_id}` ainda está aguardando pagamento no gateway (Status: {status_gateway}). Tente novamente em alguns instantes.")


# =============================================
# 📞 HANDLER PARA CALLBACKS DOS BOTÕES
# =============================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
def handle_menu_callbacks(call):
    action = call.data.split('_')[1]
    message = call.message
    bot.answer_callback_query(call.id)

    if action == "depositar":
        handle_pix_deposit(message, from_button=True)
    elif action == "sacar":
        bot.send_message(message.chat.id, "💸 Para sacar, use o comando no formato:\n`/sacar <sua_chave_pix> <valor_total_a_debitar>`\n\n*Exemplo:*\n`/sacar cpf:123.456.789-00 100`")
    elif action == "carteira":
        handle_carteira(message, from_button=True)
    elif action == "taxas":
        handle_taxa(message, from_button=True)
    elif action == "suporte":
        handle_suporte(message, from_button=True)
    elif action == "canal":
        handle_canal(message, from_button=True)
    elif action == "verificar":
        bot.send_message(message.chat.id, "🔄 Para verificar manualmente um PIX pendente, use o comando:\n`/verificar <ID da Transação>`")


# (As funções handle_carteira, handle_pix_deposit, handle_saque, etc. permanecem iguais)
@bot.message_handler(commands=['carteira'])
def handle_carteira(message, from_button=False):
    """Exibe o saldo atual e informações da carteira do usuário."""
    user = message.from_user
    if not from_button: logger.info(f"👤 Usuário {user.id} consultou a carteira via comando.")
    
    database.create_user_if_not_exists(user.id, user.username, user.first_name)
    saldo = database.get_balance(user.id)
    last_update = database.get_last_transaction_date(user.id)
    
    response = (
        f"💼 *Sua Carteira {config.NOME_BOT}*\n\n"
        f"👤 Titular: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n\n"
        f"💰 *Saldo Disponível:*\n"
        f"   *R$ {saldo:.2f}*\n\n"
        f"📅 Última movimentação: {last_update}"
    )
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['pix'])
def handle_pix_deposit(message, from_button=False):
    """
    Gera uma cobrança PIX para o usuário com uma imagem fixa personalizada.
    Se o 'from_button' for True, apenas exibe as instruções de uso.
    """
    user = message.from_user
    # Loga a ação apenas se for iniciada por um comando de texto
    if not from_button:
        logger.info(f"💰 Usuário {user.id} solicitou um depósito PIX via comando.")
    
    parts = message.text.split()
    
    # Se o comando foi acionado por um botão do menu, dê as instruções
    if from_button:
        bot.send_message(message.chat.id, "📥 Para depositar, use o comando no formato:\n`/pix <valor>`\n\n*Exemplo:*\n`/pix 75.50`")
        return

    # Validação para o comando via texto
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Formato incorreto!\nUso: `/pix <valor>`\nExemplo: `/pix 50`")
        return

    try:
        # Tenta converter o valor para um número
        valor = float(parts[1].replace(',', '.'))
        
        # Valida se o valor está dentro dos limites definidos em config.py
        if not (config.LIMITE_MINIMO_DEPOSITO <= valor <= config.LIMITE_MAXIMO_DEPOSITO):
            msg = f"⚠️ *Valor fora dos limites!*\nO depósito deve ser entre *R$ {config.LIMITE_MINIMO_DEPOSITO:.2f}* e *R$ {config.LIMITE_MAXIMO_DEPOSITO:.2f}*."
            bot.reply_to(message, msg)
            return

        bot.send_chat_action(message.chat.id, 'typing')
        
        # Chama a função para gerar o pagamento no gateway
        pix_data = pay.generate_pix_payment(valor, user.id, f"Depósito {config.NOME_BOT} ID {user.id}")

        # Verifica se o gateway retornou um erro
        if not pix_data.get('success'):
            bot.reply_to(message, f"❌ *Falha ao gerar PIX.*\nMotivo: {pix_data.get('error', 'Erro desconhecido.')}")
            return

        # Grava a transação no banco de dados com status pendente
        transaction_id = database.record_transaction(
            user_telegram_id=user.id, type="DEPOSIT", amount=valor,
            status=config.STATUS_DEPOSITO_PENDENTE,
            mercado_pago_id=str(pix_data['payment_id'])
        )

        # Prepara o texto completo que irá na legenda da imagem
        msg_pix_caption = (
            f"✅ *PIX Gerado com Sucesso!*\n\n"
            f"Valor a pagar: *R$ {valor:.2f}*\n"
            f"ID da Transação: `{transaction_id}`\n\n"
            f"👇 *Copie o código abaixo e pague no seu app do banco:*\n"
            f"`{pix_data['pix_copy_paste']}`\n\n"
            f"🔄 _Após o pagamento, seu saldo será atualizado automaticamente. Se preferir, use /verificar `{transaction_id}` para confirmar manualmente._"
        )
        
        # Lógica de envio da imagem (se houver)
        try:
            with open('pix.jpg', 'rb') as foto_fixa:
                bot.send_photo(message.chat.id, photo=foto_fixa, caption=msg_pix_caption)
        except FileNotFoundError:
            logger.warning("Imagem 'pix.jpg' não encontrada. Enviando PIX como texto.")
            bot.send_message(message.chat.id, msg_pix_caption)

    except ValueError:
        bot.reply_to(message, "❌ Valor inválido. Use apenas números. Ex: `/pix 50.75`")
    except Exception as e:
        logger.error(f"💥 Erro inesperado em /pix para {user.id}: {e}", exc_info=True)
        bot.reply_to(message, "❌ Ocorreu um erro crítico. Tente novamente mais tarde.")

@bot.message_handler(commands=['sacar'])
def handle_saque(message):
    """Processa uma solicitação de saque."""
    user = message.from_user
    logger.info(f"💸 Usuário {user.id} iniciou uma solicitação de saque.")
    database.create_user_if_not_exists(user.id, user.username, user.first_name)

    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ *Uso incorreto!*\n`/sacar <sua_chave_pix> <valor_total_a_debitar>`\n\n*Exemplo:*\n`/sacar cpf:12345678900 100`")
        return

    chave_pix = parts[1]
    
    try:
        valor_total_debito = float(parts[2].replace(',', '.'))
        if valor_total_debito <= config.TAXA_SAQUE_FIXA:
            bot.reply_to(message, f"❌ O valor a debitar deve ser maior que a taxa fixa de R$ {config.TAXA_SAQUE_FIXA:.2f}.")
            return

        valor_a_receber = round((valor_total_debito - config.TAXA_SAQUE_FIXA) / (1 + config.TAXA_SAQUE_PERCENTUAL), 2)
        
        # <<< NEW: Minimum withdrawal validation >>>
        if valor_a_receber < config.LIMITE_MINIMO_SAQUE:
            bot.reply_to(message, f"❌ *Valor Mínimo Não Atingido!*\nO valor líquido a receber deve ser de pelo menos *R$ {config.LIMITE_MINIMO_SAQUE:.2f}*.")
            return
        
        taxa_final = round(valor_total_debito - valor_a_receber, 2)
        saldo_atual = database.get_balance(user.id)

        if saldo_atual < valor_total_debito:
            bot.reply_to(message, f"❌ *Saldo insuficiente.*\nSeu saldo: *R$ {saldo_atual:.2f}* | Necessário: *R$ {valor_total_debito:.2f}*")
            return

        conn = database.get_db_connection()
        try:
            # The transaction starts automatically with this first database call
            if not database.update_balance(user.id, -valor_total_debito, conn_ext=conn):
                 # This handles the case where the balance would go negative, which should be caught earlier, but is a good safeguard.
                 raise Exception("Falha ao atualizar o saldo, possivelmente resultando em saldo negativo.")

            transaction_id = database.record_transaction(
                conn_ext=conn, user_telegram_id=user.id, type="WITHDRAWAL",
                amount=valor_a_receber, status=config.STATUS_EM_ANALISE, pix_key=chave_pix
            )
            database.record_transaction(
                conn_ext=conn, user_telegram_id=user.id, type="FEE",
                amount=taxa_final, status=config.STATUS_CONCLUIDO,
                admin_notes=f"Taxa referente ao saque ID {transaction_id}"
            )
            
            conn.commit()
            
            adm.notify_admin_of_withdrawal_request(transaction_id, user.id, user.first_name, valor_a_receber, chave_pix)
            bot.reply_to(message,
                         f"✅ *Solicitação de saque enviada!*\n\n"
                         f"➖ Débito total: *R$ {valor_total_debito:.2f}*\n"
                         f"💸 Você receberá: *R$ {valor_a_receber:.2f}*\n"
                         f"📋 Taxa: R$ {taxa_final:.2f}\n\n"
                         f"🔑 Chave PIX: `{chave_pix}`\n"
                         f"🆔 ID: `{transaction_id}`")
        except Exception as e_atomic:
            if conn: conn.rollback()
            logger.critical(f"💥 Erro atômico no /sacar para {user.id}: {e_atomic}", exc_info=True)
            bot.reply_to(message, "❌ Erro crítico ao registrar sua solicitação. Nenhum valor foi debitado.")
        finally:
            if conn: conn.close()
            
    except ValueError:
        bot.reply_to(message, "❌ Valor inválido. Ex: `/sacar chave@pix.com 100`")
    except Exception as e:
        logger.error(f"💥 Erro inesperado no /sacar para {user.id}: {e}", exc_info=True)
        bot.reply_to(message, "❌ Ocorreu um erro inesperado.")
        
@bot.message_handler(commands=['taxa'])
def handle_taxa(message, from_button=False):
    """Exibe as taxas de operação de forma clara para o usuário."""
    if not from_button: logger.info(f"💰 Usuário {message.from_user.id} consultou as taxas.")
    texto_taxas = (
        "💰 *Taxas de Operação*\n\n"
        "📥 *DEPÓSITO:*\n"
        f"• *{config.TAXA_DEPOSITO_PERCENTUAL * 100:.1f}%* sobre o valor depositado.\n"
        "_Ex: Ao depositar R$100, você recebe R$89 em saldo._\n\n"
        "📤 *SAQUE:*\n"
        f"• *{config.TAXA_SAQUE_PERCENTUAL * 100:.1f}%* sobre o valor a receber\n"
        f"• *+ R$ {config.TAXA_SAQUE_FIXA:.2f}* fixos por transação."
    )
    bot.send_message(message.chat.id, texto_taxas)

@bot.message_handler(commands=['suporte'])
def handle_suporte(message, from_button=False):
    """Fornece os canais de suporte ao usuário."""
    if not from_button: logger.info(f"🆘 Usuário {message.from_user.id} solicitou suporte.")
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton(text="🤖 Falar com o Suporte", url=config.BOT_SUPORTE))
    support_msg = (
        f"🛎️ *Suporte {config.NOME_BOT}*\n\n"
        f"Clique no botão para falar com nossa equipe.\n"
        f"Seu ID de usuário: `{message.from_user.id}`"
    )
    bot.send_message(message.chat.id, support_msg, reply_markup=markup, disable_web_page_preview=True)

@bot.message_handler(commands=['canal'])
def handle_canal(message, from_button=False):
    """Envia o link do canal oficial."""
    if not from_button: logger.info(f"📢 Usuário {message.from_user.id} pediu o link do canal.")
    channel_msg = f"📢 *Canal Oficial {config.NOME_BOT}*\n\nAcesse e fique por dentro de todas as novidades:\n{config.CANAL_OFICIAL}"
    bot.send_message(message.chat.id, channel_msg, disable_web_page_preview=True)

# =============================================
# ▶️ INICIAR O BOT E O VERIFICADOR
# =============================================
if __name__ == '__main__':
    # Inicia o verificador periódico em uma thread separada
    checker_thread = threading.Thread(target=verificador_pix_periodico, daemon=True)
    checker_thread.start()
    
    logger.info("--- BOT INICIADO E PRONTO PARA RECEBER COMANDOS ---")
    try:
        # Inicia o polling do bot
        bot.infinity_polling(timeout=30, long_polling_timeout=5)
    except Exception as e:
        logger.critical(f"🆘 O BOT PAROU DE FUNCIONAR! Erro fatal no polling: {e}", exc_info=True)
