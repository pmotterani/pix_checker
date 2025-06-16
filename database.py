# database.py (Versão para PostgreSQL com novas funções de verificação)
"""
🗃️ Módulo de Banco de Dados
---------------------------
Responsável por todas as interações com o banco de dados PostgreSQL.
Inclui criação de tabelas, CRUD de usuários e transações.
"""
import psycopg2
from psycopg2.extras import DictCursor
import logging
from datetime import datetime, timedelta # <<< Adicionado timedelta
import config
import decimal # <<< 1. IMPORT ADDED

logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Cria e retorna uma nova conexão com o banco de dados PostgreSQL.
    Configura o DictCursor para permitir acesso às colunas por nome.
    """
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        logger.critical(f"FATAL: Não foi possível conectar ao banco de dados PostgreSQL: {e}", exc_info=True)
        raise

# Em database.py

def init_db():
    """
    Inicializa o banco de dados, criando as tabelas se não existirem.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Tabela de Usuários
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance NUMERIC(15, 2) DEFAULT 0.00,  -- <<< ALTERADO DE REAL PARA NUMERIC
                    created_at TIMESTAMPTZ NOT NULL
                )
            ''')
            # Tabela de Transações
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id BIGINT NOT NULL,
                    type TEXT NOT NULL,
                    amount NUMERIC(15, 2) NOT NULL,        -- <<< ALTERADO DE REAL PARA NUMERIC
                    status TEXT NOT NULL,
                    pix_key TEXT,
                    mercado_pago_id TEXT,
                    admin_notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY (user_telegram_id) REFERENCES users (telegram_id)
                )
            ''')
        conn.commit()
    logger.info("✅ Banco de dados PostgreSQL inicializado e verificado com sucesso.")

# <<< NOVA FUNÇÃO >>>
def get_pending_pix_transactions(hours=2):
    """Busca transações PIX pendentes das últimas 'hours' horas."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                time_threshold = datetime.now() - timedelta(hours=hours)
                sql = """
                    SELECT * FROM transactions
                    WHERE type = 'DEPOSIT' AND status = %s AND created_at >= %s
                """
                cursor.execute(sql, (config.STATUS_DEPOSITO_PENDENTE, time_threshold))
                return cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar PIX pendentes: {e}", exc_info=True)
                return []

# <<< NOVA FUNÇÃO >>>
def get_transaction_by_id_and_user(transaction_id, user_telegram_id):
    """Busca uma transação pelo ID, garantindo que pertence ao usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM transactions WHERE id = %s AND user_telegram_id = %s", (transaction_id, user_telegram_id))
                return cursor.fetchone()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar transação {transaction_id} para usuário {user_telegram_id}: {e}", exc_info=True)
                return None

# (O restante do arquivo database.py, com as outras funções, continua aqui sem alterações...)
# (admin_set_balance, get_users_with_balance, create_user_if_not_exists, etc...)
def admin_set_balance(user_telegram_id, new_balance):
    """[ADMIN] Define um novo saldo para um usuário."""
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET balance = %s WHERE telegram_id = %s",
                    (new_balance, user_telegram_id)
                )
                if cursor.rowcount > 0:
                    record_transaction(
                        user_telegram_id=user_telegram_id, type='AJUSTE_MANUAL',
                        amount=new_balance, status='CONCLUIDO',
                        admin_notes=f"Saldo definido para R${new_balance:.2f} por um admin."
                    )
                    conn.commit()
                    return True
                return False
        except psycopg2.Error as e:
            logger.error(f"❌ Erro no DB ao setar saldo para {user_telegram_id}: {e}", exc_info=True)
            conn.rollback()
            return False

def get_users_with_balance():
    """[ADMIN] Retorna todos os usuários com saldo maior que zero."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT telegram_id, first_name, username, balance FROM users WHERE balance > 0 ORDER BY balance DESC")
                return cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar usuários com saldo: {e}", exc_info=True)
                return []

def create_user_if_not_exists(telegram_id, username, first_name):
    """Cria um novo usuário se ele não existir."""
    now = datetime.now()
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO users (telegram_id, username, first_name, balance, created_at)
                    VALUES (%s, %s, %s, 0.00, %s)
                    ON CONFLICT (telegram_id) DO NOTHING;
                """
                cursor.execute(sql, (telegram_id, username, first_name, now))
                if cursor.rowcount > 0:
                    logger.info(f"👤 Novo usuário criado: ID={telegram_id}, Nome='{first_name}'.")
            conn.commit()
        except psycopg2.Error as e:
            logger.error(f"❌ Erro ao tentar criar usuário {telegram_id}: {e}", exc_info=True)
            conn.rollback()

def get_balance(telegram_id):
    """Busca e retorna o saldo de um usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT balance FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                return result['balance'] if result else 0.00
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar saldo para {telegram_id}: {e}", exc_info=True)
                return 0.00

def update_balance(telegram_id, amount_change, conn_ext=None):
    """Atualiza o saldo de um usuário."""
    conn = conn_ext or get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT balance FROM users WHERE telegram_id = %s FOR UPDATE", (telegram_id,))
            result = cursor.fetchone()
            
            # <<< 2. MODIFIED BLOCK START >>>
            current_balance = result['balance'] if result else decimal.Decimal('0.00')
            
            # Convert float to Decimal for safe addition/subtraction
            decimal_amount_change = decimal.Decimal(str(amount_change))
            new_balance = current_balance + decimal_amount_change
            
            if new_balance < 0:
                logger.warning(f"⚠️ Tentativa de deixar saldo negativo para {telegram_id}.")
                # Do not rollback here, just signal failure
                return False
            # <<< MODIFIED BLOCK END >>>

            cursor.execute("UPDATE users SET balance = %s WHERE telegram_id = %s", (new_balance, telegram_id))
            if not conn_ext: conn.commit()
            logger.info(f"💰 Saldo de {telegram_id} atualizado. De R${current_balance:.2f} para R${new_balance:.2f} (Mudança: {amount_change:+.2f}).")
            return True
    except psycopg2.Error as e:
        logger.error(f"❌ Erro ao atualizar saldo para {telegram_id}: {e}", exc_info=True)
        if conn_ext is None and conn: conn.rollback()
        return False
    finally:
        if conn_ext is None and conn: conn.close()

def update_transaction_status(transaction_id, new_status, **kwargs):
    """Atualiza o status e outros campos de uma transação."""
    # <<< 1. FIX: Apply the same logic here.
    is_external_conn = 'conn_ext' in kwargs
    conn = kwargs.pop('conn_ext') if is_external_conn else get_db_connection()

    fields_to_update = ["status = %s", "updated_at = %s"]
    values = [new_status, datetime.now()]
    if 'mp_id' in kwargs:
        fields_to_update.append("mercado_pago_id = %s")
        values.append(kwargs['mp_id'])
    if 'admin_notes' in kwargs:
        fields_to_update.append("admin_notes = %s")
        values.append(kwargs['admin_notes'])
    values.append(transaction_id)
    try:
        with conn.cursor() as cursor:
            sql = f"UPDATE transactions SET {', '.join(fields_to_update)} WHERE id = %s"
            cursor.execute(sql, tuple(values))
            
            # <<< 2. FIX: Use the boolean flag here as well.
            if not is_external_conn:
                conn.commit()
                
        logger.info(f"🔄 Status da transação {transaction_id} atualizado para '{new_status}'.")
        return True
    except psycopg2.Error as e:
        logger.error(f"❌ Erro ao atualizar status da transação {transaction_id}: {e}", exc_info=True)
        if not is_external_conn and conn:
            conn.rollback()
        return False
    finally:
        if not is_external_conn and conn:
            conn.close()

def record_transaction(**kwargs):
    """Registra uma nova transação no banco de dados."""
    # <<< 1. FIX: Check for the external connection BEFORE removing it from kwargs.
    is_external_conn = 'conn_ext' in kwargs
    conn = kwargs.pop('conn_ext') if is_external_conn else get_db_connection()
    
    now = datetime.now()
    kwargs.setdefault('pix_key', None); kwargs.setdefault('mercado_pago_id', None); kwargs.setdefault('admin_notes', None)
    kwargs['created_at'] = now; kwargs['updated_at'] = now
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            columns = ', '.join(kwargs.keys())
            placeholders = ', '.join(['%s'] * len(kwargs))
            sql = f"INSERT INTO transactions ({columns}) VALUES ({placeholders}) RETURNING id"
            cursor.execute(sql, tuple(kwargs.values()))
            transaction_id = cursor.fetchone()['id']
            
            # <<< 2. FIX: Use the boolean flag to decide whether to commit.
            if not is_external_conn:
                conn.commit()
                
            logger.info(f"📄 Transação {transaction_id} (Tipo: {kwargs['type']}) registrada para usuário {kwargs['user_telegram_id']}.")
            return transaction_id
    except psycopg2.Error as e:
        logger.error(f"❌ Erro ao registrar transação para {kwargs.get('user_telegram_id')}: {e}", exc_info=True)
        if not is_external_conn and conn:
            conn.rollback()
        return None
    finally:
        if not is_external_conn and conn:
            conn.close()

def get_transaction_details(transaction_id):
    """Busca todos os detalhes de uma transação pelo seu ID."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
                return cursor.fetchone()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar detalhes da transação {transaction_id}: {e}", exc_info=True)
                return None

def get_pending_withdrawals():
    """Retorna todas as transações de saque com status 'EM ANÁLISE'."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM transactions WHERE type = 'WITHDRAWAL' AND status = %s", (config.STATUS_EM_ANALISE,))
                return cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar saques pendentes: {e}", exc_info=True)
                return []

def calculate_profits():
    """
    Calcula o lucro total somando as taxas de transações CONCLUÍDAS.
    - Taxas de depósito são contadas diretamente.
    - Taxas de saque são contadas apenas se o saque correspondente foi concluído.
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                # Esta consulta SQL usa uma subconsulta para garantir que apenas as taxas
                # de saques bem-sucedidos sejam incluídas no cálculo do lucro.
                # É específica para PostgreSQL devido ao uso de SUBSTRING com expressão regular.
                sql_query = """
                    SELECT COALESCE(SUM(T1.amount), 0.00)
                    FROM transactions T1
                    WHERE T1.type = 'FEE' AND T1.status = %s AND (
                        -- Sempre conta as taxas de depósito, pois são criadas no sucesso.
                        T1.admin_notes LIKE 'Taxa de depósito%%'
                        OR
                        -- Só conta taxas de saque se o saque correspondente foi CONCLUÍDO.
                        (
                            T1.admin_notes LIKE 'Taxa referente ao saque ID %%'
                            AND
                            EXISTS (
                                SELECT 1
                                FROM transactions T2
                                WHERE T2.type = 'WITHDRAWAL'
                                  AND T2.status = %s
                                  -- Extrai o ID da nota e converte para integer para a correspondência.
                                  AND T2.id = CAST(substring(T1.admin_notes from '(\\d+)$') AS INTEGER)
                            )
                        )
                    )
                """
                cursor.execute(sql_query, (config.STATUS_CONCLUIDO, config.STATUS_CONCLUIDO))
                result = cursor.fetchone()
                # Retorna o resultado da soma. Se não houver, retorna 0.00.
                return result[0] if result and result[0] is not None else 0.00
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao calcular lucro: {e}", exc_info=True)
                return 0.00

def get_fee_for_withdrawal(withdrawal_transaction_id):
    """Busca o valor da taxa associada a uma transação de saque."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                note = f"Taxa referente ao saque ID {withdrawal_transaction_id}"
                cursor.execute("SELECT amount FROM transactions WHERE type = 'FEE' AND admin_notes = %s", (note,))
                result = cursor.fetchone()
                return result['amount'] if result else 0.00
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar taxa para o saque {withdrawal_transaction_id}: {e}", exc_info=True)
                return 0.00

def get_user_info(telegram_id):
    """Busca informações básicas de um usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return cursor.fetchone()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar info do usuário {telegram_id}: {e}", exc_info=True)
                return None

def get_last_transaction_date(telegram_id):
    """Busca a data da última transação atualizada de um usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT updated_at FROM transactions WHERE user_telegram_id = %s ORDER BY updated_at DESC LIMIT 1", (telegram_id,))
                result = cursor.fetchone()
                if result:
                    return result['updated_at'].strftime('%d/%m/%Y %H:%M')
                return "Nenhuma transação"
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar última data de transação para {telegram_id}: {e}", exc_info=True)
                return "Erro ao consultar"
