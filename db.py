import sqlite3
from typing import Optional, Tuple, Union
import logging

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        credits INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول المستخدمين المسموح لهم
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS allowed_users (
        user_id INTEGER PRIMARY KEY,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول أكواد الشحن (هذا هو الجدول المطلوب)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY,
        credits INTEGER NOT NULL,
        used BOOLEAN DEFAULT FALSE,
        used_by INTEGER,
        used_at TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("تم تهيئة قاعدة البيانات بنجاح")


# الاتصال بقاعدة البيانات (تأكد من المسار الصحيح)
conn = sqlite3.connect('data/database.db', check_same_thread=False)
cursor = conn.cursor()

def get_all_users():
    """
    تُرجع قائمة من جميع المستخدمين تحتوي على (user_id, credit) فقط.
    """
    cursor.execute("SELECT user_id, credit FROM users")
    return cursor.fetchall()

def update_credits(user_id: int, new_credits: int) -> bool:
    """
    تحديث رصيد المستخدم مباشرة بقيمة جديدة
    :param user_id: ID المستخدم
    :param new_credits: الرصيد الجديد
    :return: True إذا تم التحديث بنجاح
    """
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('''
        UPDATE users 
        SET credits = ?
        WHERE user_id = ?
        ''', (new_credits, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"خطأ في تحديث الرصيد: {e}")
        return False
    finally:
        conn.close()

# وظائف المستخدمين
def add_user(user_id: int):
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في إضافة المستخدم: {e}")
    finally:
        conn.close()

def remove_user(user_id: int):
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في حذف المستخدم: {e}")
    finally:
        conn.close()

# وظائف الصلاحيات
def is_allowed(user_id: int) -> bool:
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT 1 FROM allowed_users WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"خطأ في التحقق من الصلاحية: {e}")
        return False
    finally:
        conn.close()

def add_allowed_user(user_id: int, added_by: Optional[int] = None):
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT OR IGNORE INTO allowed_users (user_id, added_by) 
        VALUES (?, ?)
        ''', (user_id, added_by))
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في إضافة مستخدم مسموح: {e}")
    finally:
        conn.close()

# وظائف الرصيد
def get_credits(user_id: int) -> int:
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"خطأ في جلب الرصيد: {e}")
        return 0
    finally:
        conn.close()

def has_credit(user_id: int, amount: int = 1) -> bool:
    return get_credits(user_id) >= amount

def deduct_credit(user_id: int, amount: int = 1):
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('''
        UPDATE users 
        SET credits = credits - ? 
        WHERE user_id = ? AND credits >= ?
        ''', (amount, user_id, amount))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"خطأ في خصم الرصيد: {e}")
        return False
    finally:
        conn.close()

# وظائف أكواد الشحن
def redeem_code(code: str, user_id: int) -> Tuple[bool, Union[int, str]]:
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        # التحقق من صحة الكود
        cursor.execute('''
        SELECT credits FROM redeem_codes 
        WHERE code = ? AND used = FALSE
        ''', (code,))
        result = cursor.fetchone()
        
        if not result:
            return False, "كود غير صالح أو مستخدم مسبقًا"
        
        credits = result[0]
        
        # تحديث حالة الكود
        cursor.execute('''
        UPDATE redeem_codes 
        SET used = TRUE, used_by = ?, used_at = CURRENT_TIMESTAMP 
        WHERE code = ?
        ''', (user_id, code))
        
        # إضافة الرصيد للمستخدم
        cursor.execute('''
        UPDATE users 
        SET credits = credits + ? 
        WHERE user_id = ?
        ''', (credits, user_id))
        
        conn.commit()
        return True, credits
    except Exception as e:
        conn.rollback()
        logger.error(f"خطأ في استرداد الكود: {e}")
        return False, "حدث خطأ أثناء معالجة الكود"
    finally:
        conn.close()

# وظائف إضافية للإدارة
def add_redeem_code(code: str, credits: int) -> bool:
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO redeem_codes (code, credits) 
        VALUES (?, ?)
        ''', (code, credits))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        logger.error(f"خطأ في إضافة كود شحن: {e}")
        return False
    finally:
        conn.close()

def get_user(user_id: int) -> Optional[dict]:
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        cursor.execute('''
        SELECT u.user_id, u.credits, u.created_at, 
               CASE WHEN a.user_id IS NOT NULL THEN 1 ELSE 0 END as is_allowed
        FROM users u
        LEFT JOIN allowed_users a ON u.user_id = a.user_id
        WHERE u.user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        if result:
            return {
                'user_id': result[0],
                'credits': result[1],
                'created_at': result[2],
                'is_allowed': bool(result[3])
            }
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات المستخدم: {e}")
        return None
    finally:
        conn.close()

def list_users(all_users: bool = False) -> list:
    """الحصول على قائمة بالمستخدمين"""
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    try:
        if all_users:
            cursor.execute('''
            SELECT u.user_id, u.credits, u.created_at, 
                   CASE WHEN a.user_id IS NOT NULL THEN 1 ELSE 0 END as is_allowed
            FROM users u
            LEFT JOIN allowed_users a ON u.user_id = a.user_id
            ''')
        else:
            cursor.execute('''
            SELECT user_id, credits, created_at 
            FROM users
            ''')
        
        users = []
        for row in cursor.fetchall():
            if all_users:
                users.append({
                    'user_id': row[0],
                    'credits': row[1],
                    'created_at': row[2],
                    'is_allowed': bool(row[3])
                })
            else:
                users.append({
                    'user_id': row[0],
                    'credits': row[1],
                    'created_at': row[2]
                })
        return users
    except Exception as e:
        logger.error(f"خطأ في جلب قائمة المستخدمين: {e}")
        return []
    finally:
        conn.close()
        
def create_codes(count: int, credits: int) -> list:
    """
    إنشاء أكواد شحن جديدة
    :param count: عدد الأكواد المراد إنشاؤها
    :param credits: عدد النقاط لكل كود
    :return: قائمة بالأكواد المنشأة
    """
    import random
    import string
    
    conn = sqlite3.connect('bot_db.sqlite')
    cursor = conn.cursor()
    codes = []
    
    try:
        for _ in range(count):
            # إنشاء كود عشوائي مكون من 10 حروف/أرقام
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            
            cursor.execute('''
            INSERT INTO redeem_codes (code, credits)
            VALUES (?, ?)
            ''', (code, credits))
            
            codes.append(code)
        
        conn.commit()
        return codes
    
    except Exception as e:
        conn.rollback()
        logger.error(f"خطأ في إنشاء الأكواد: {e}")
        return []
    
    finally:
        conn.close()



# تهيئة قاعدة البيانات عند الاستيراد
init_db()