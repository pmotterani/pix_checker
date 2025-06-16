# pay.py (Versão Melhorada)
"""
💳 Módulo de Pagamentos
-----------------------
Responsável pela integração com o gateway de pagamento (Mercado Pago).
Inclui funções para gerar cobranças PIX e processar pagamentos de saque (payouts).
"""
import mercadopago
import logging
import uuid
import config

logger = logging.getLogger(__name__)

# Inicialização segura do SDK do Mercado Pago
sdk = None
if config.MERCADOPAGO_ACCESS_TOKEN:
    try:
        sdk = mercadopago.SDK(config.MERCADOPAGO_ACCESS_TOKEN)
        logger.info("✅ SDK do Mercado Pago inicializado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar SDK do Mercado Pago: {e}", exc_info=True)
else:
    logger.warning("⚠️ MERCADOPAGO_ACCESS_TOKEN não configurado. As funções de pagamento estarão desativadas.")


def generate_pix_payment(amount, user_id, description):
    """
    Gera uma cobrança PIX (QR Code e Copia e Cola) via Mercado Pago.

    Args:
        amount (float): O valor da cobrança.
        user_id (int): O ID do usuário para identificação.
        description (str): A descrição que aparecerá na cobrança.

    Returns:
        dict: Um dicionário contendo os dados do PIX em caso de sucesso,
              ou uma mensagem de erro em caso de falha.
    """
    if not sdk:
        logger.error("❌ Tentativa de gerar PIX com SDK não inicializado.")
        return {'success': False, 'error': 'O serviço de pagamento está temporariamente indisponível.'}

    # Dados do pagamento a serem enviados para a API
    payment_data = {
        "transaction_amount": round(float(amount), 2),
        "description": description,
        "payment_method_id": "pix",
        "payer": {
            # Um e-mail único por usuário é uma boa prática
            "email": f"user_{user_id}@{config.NOME_BOT.lower()}.com",
        },
        # "notification_url": "URL_DO_SEU_WEBHOOK", # Descomente para usar webhooks
    }

    try:
        logger.info(f"📨 Enviando requisição de PIX para o MP. Valor: R${amount:.2f}, User: {user_id}")
        payment_response = sdk.payment().create(payment_data)
        payment = payment_response.get("response")

        if payment and payment_response.get("status") in [200, 201]:
            point_of_interaction = payment.get("point_of_interaction", {}).get("transaction_data", {})
            pix_copia_cola = point_of_interaction.get("qr_code")
            qr_code_base64 = point_of_interaction.get("qr_code_base64")
            payment_id_mp = payment.get("id")

            if pix_copia_cola and payment_id_mp:
                logger.info(f"✅ PIX gerado com sucesso. ID no MP: {payment_id_mp}")
                return {
                    'success': True,
                    'pix_copy_paste': pix_copia_cola,
                    'qr_code': qr_code_base64,
                    'payment_id': payment_id_mp
                }
        
        # Se a resposta não for bem-sucedida ou não contiver os dados esperados
        error_details = payment.get('message', str(payment)) if payment else "Resposta vazia da API."
        logger.error(f"❌ Falha na API do MP ao gerar PIX para user {user_id}. Detalhes: {error_details}")
        return {'success': False, 'error': f"O gateway de pagamento retornou um erro: {error_details}"}

    except Exception as e:
        logger.error(f"💥 Exceção catastrófica ao gerar PIX para user {user_id}: {e}", exc_info=True)
        return {'success': False, 'error': 'Ocorreu um erro inesperado ao conectar com o serviço de pagamento.'}


def process_payout(transaction_id_local, amount, pix_key_receiver, description):
    """
    Processa um pagamento de saque (payout) para uma chave PIX.

    NOTA: Esta implementação é um SIMULADOR. Em produção, aqui entraria a chamada
    real à API de Payouts do Mercado Pago ou de outro provedor.

    Args:
        transaction_id_local (int): ID da transação no nosso sistema.
        amount (float): Valor a ser enviado.
        pix_key_receiver (str): Chave PIX de destino.
        description (str): Descrição do pagamento.

    Returns:
        dict: Um dicionário com o resultado da operação.
    """
    if not sdk or not config.PRODUCTION:
        # Em modo de desenvolvimento ou sem SDK, simula um sucesso sem chamar a API
        simulated_payout_id = f"sim_payout_{uuid.uuid4()}"
        logger.info(f"🏦 [SIMULAÇÃO] Payout processado para transação {transaction_id_local}.")
        logger.info(f"   - Valor: R$ {amount:.2f}")
        logger.info(f"   - Chave PIX: {pix_key_receiver}")
        logger.info(f"   - ID Simulado: {simulated_payout_id}")
        return {'success': True, 'payout_id': simulated_payout_id, 'message': 'Pagamento simulado com sucesso.'}

    # --- LÓGICA DE PRODUÇÃO (Exemplo com a API de Payouts) ---
    # O código abaixo é um exemplo e precisa ser adaptado para a API de Payouts específica.
    # A API de Payouts do Mercado Pago é diferente da de Pagamentos.
    payout_data = {
        "amount": round(float(amount), 2),
        "receiver": {
            "pix_key": pix_key_receiver,
        },
        "description": description,
        "external_reference": str(transaction_id_local)
    }

    try:
        # A sintaxe para Payouts pode variar. Ex: sdk.payout().create(...)
        # Esta é uma chamada hipotética.
        # response = sdk.payout().create(payout_data)
        
        # Substituindo por uma simulação para o exemplo funcionar
        response = {'status': 201, 'id': f"mp_payout_{uuid.uuid4()}", 'message': "Payout criado"}
        
        if response and response.get('status') in [200, 201]:
            payout_id = response.get('id')
            logger.info(f"✅ Payout ID {payout_id} criado com sucesso para transação {transaction_id_local}.")
            return {'success': True, 'payout_id': payout_id, 'message': 'Pagamento enviado com sucesso.'}
        else:
            error_message = response.get('message', 'Erro desconhecido na API de Payout.')
            logger.error(f"❌ Falha na API ao processar payout para {transaction_id_local}: {error_message}")
            return {'success': False, 'payout_id': None, 'message': error_message}
            
    except Exception as e:
        logger.error(f"💥 Exceção catastrófica ao processar payout para {transaction_id_local}: {e}", exc_info=True)
        return {'success': False, 'payout_id': None, 'message': 'Erro crítico na comunicação com o gateway.'}

def get_payment_details(mercado_pago_id):
    """Busca os detalhes de um pagamento existente no Mercado Pago."""
    if not sdk:
        logger.error("❌ Tentativa de buscar detalhes de pagamento com SDK não inicializado.")
        return None
    try:
        payment_info = sdk.payment().get(mercado_pago_id)
        return payment_info.get("response")
    except Exception as e:
        logger.error(f"❌ Erro ao buscar detalhes do pagamento MP ID {mercado_pago_id}: {e}", exc_info=True)
        return None
