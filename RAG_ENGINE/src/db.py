
import psycopg2
from config.settings import POSTGRES_CONN

def get_connection():
    return psycopg2.connect(POSTGRES_CONN)
