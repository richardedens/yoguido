"""
Database manager for YoGuido framework
Provides connection pooling and database access methods
"""

import os
import threading
import queue
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from contextlib import contextmanager

# Database imports - we'll support both PostgreSQL and MySQL
# Note: Users need to install these packages:
# pip install psycopg2-binary mysqlclient

class Connection:
    """Wrapper for database connection with session context"""
    
    def __init__(self, conn, db_type, session_id=None):
        self.conn = conn
        self.session_id = session_id
        self._cursor = None
        self.db_type = db_type  # Store db_type to handle differences
    
    def cursor(self):
        """Get a cursor with session tracking"""
        self._cursor = self.conn.cursor()
        return self._cursor
    
    def commit(self):
        """Commit the transaction"""
        return self.conn.commit()
        
    def rollback(self):
        """Rollback the transaction"""
        return self.conn.rollback()
        
    def close(self):
        """Close cursor if open, then close connection"""
        if self._cursor:
            self._cursor.close()
        return self.conn.close()
        
class DatabaseManager:
    """Session-aware database connection manager with connection pooling"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self._local = threading.local()
        self.pool = queue.Queue(maxsize=10)  # Connection pool with max 10 connections
        
        # Database configuration
        self.db_type = self.config.get('type', 'mysql')  # Default to MySQL
        
        # Connection parameters
        self.db_host = self.config.get('host', 'localhost')
        self.db_port = self.config.get('port', 3306 if self.db_type == 'mysql' else 5432)
        self.db_name = self.config.get('database', 'yoguido')
        self.db_user = self.config.get('user', 'root')
        self.db_password = self.config.get('password', '')
        
        # Initialize database
        self._initialize_db()
        
    def _initialize_db(self):
        """Initialize database and create tables if needed"""
        # Fill the connection pool with initial connections
        for _ in range(5):  # Start with 5 connections
            conn = self._create_new_connection()
            if conn:
                self.pool.put(conn)
        
        # Create required tables if they don't exist
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Different SQL syntax based on database type
            if self.db_type == 'mysql':
                # Users table for MySQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        username VARCHAR(255) PRIMARY KEY,
                        full_name VARCHAR(255),
                        email VARCHAR(255),
                        hashed_password VARCHAR(255),
                        disabled TINYINT DEFAULT 0,
                        created_at DATETIME,
                        last_login DATETIME
                    )
                ''')
                
                # User permissions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_permissions (
                        username VARCHAR(255),
                        permission VARCHAR(255),
                        PRIMARY KEY (username, permission),
                        FOREIGN KEY (username) REFERENCES users(username)
                    )
                ''')
                
                # Sessions table for persistence
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        username VARCHAR(255),
                        created_at DATETIME,
                        expires_at DATETIME,
                        data TEXT,
                        FOREIGN KEY (username) REFERENCES users(username)
                    )
                ''')
                
            elif self.db_type == 'postgres':
                # Users table for PostgreSQL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        username VARCHAR(255) PRIMARY KEY,
                        full_name VARCHAR(255),
                        email VARCHAR(255),
                        hashed_password VARCHAR(255),
                        disabled SMALLINT DEFAULT 0,
                        created_at TIMESTAMP,
                        last_login TIMESTAMP
                    )
                ''')
                
                # User permissions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_permissions (
                        username VARCHAR(255),
                        permission VARCHAR(255),
                        PRIMARY KEY (username, permission),
                        FOREIGN KEY (username) REFERENCES users(username)
                    )
                ''')
                
                # Sessions table for persistence
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        username VARCHAR(255),
                        created_at TIMESTAMP,
                        expires_at TIMESTAMP,
                        data TEXT,
                        FOREIGN KEY (username) REFERENCES users(username)
                    )
                ''')
            
            # Check if admin user exists, create it if not
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            if cursor.fetchone()[0] == 0:
                # Create default admin user (password: admin123)
                import hashlib
                hashed_pwd = hashlib.sha256("admin123".encode()).hexdigest()
                
                now = datetime.utcnow()
                
                if self.db_type == 'mysql':
                    cursor.execute('''
                        INSERT INTO users (username, full_name, email, hashed_password, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', ('admin', 'Administrator', 'admin@example.com', hashed_pwd, now))
                else:  # postgres
                    cursor.execute('''
                        INSERT INTO users (username, full_name, email, hashed_password, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', ('admin', 'Administrator', 'admin@example.com', hashed_pwd, now))
                
                # Give admin all permissions
                permissions = ['admin', 'users.view', 'users.edit', 'users.create', 'users.delete']
                for perm in permissions:
                    if self.db_type == 'mysql':
                        cursor.execute('''
                            INSERT INTO user_permissions (username, permission) VALUES (%s, %s)
                        ''', ('admin', perm))
                    else:  # postgres
                        cursor.execute('''
                            INSERT INTO user_permissions (username, permission) VALUES (%s, %s)
                        ''', ('admin', perm))
            
            conn.commit()
    
    def _create_new_connection(self):
        """Create a new database connection"""
        try:
            if self.db_type == 'mysql':
                try:
                    import mysql.connector
                    conn = mysql.connector.connect(
                        host=self.db_host,
                        port=self.db_port,
                        database=self.db_name,
                        user=self.db_user,
                        password=self.db_password
                    )
                    return conn
                except ImportError:
                    print("❌ MySQL connector not installed. Run: pip install mysql-connector-python")
                    raise
                
            elif self.db_type == 'postgres':
                try:
                    import psycopg2
                    import psycopg2.extras
                    conn = psycopg2.connect(
                        host=self.db_host,
                        port=self.db_port,
                        dbname=self.db_name,
                        user=self.db_user,
                        password=self.db_password
                    )
                    return conn
                except ImportError:
                    print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
                    raise
                    
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            return None
    
    @contextmanager
    def get_connection(self, session_id=None) -> Connection:
        """Get a database connection from the pool with session context"""
        from ..core.state import get_current_session_id
        
        # Use session_id from current thread if not specified
        if not session_id:
            session_id = get_current_session_id()
            
        conn = None
        try:
            # Get connection from pool or create new if pool is empty
            try:
                conn = self.pool.get(block=False)
                print("🔄 Reusing database connection from pool")
            except queue.Empty:
                conn = self._create_new_connection()
                print("🆕 Created new database connection")
            
            # Wrap connection with session context
            wrapped_conn = Connection(conn, self.db_type, session_id)
            yield wrapped_conn
            
            # Commit any changes
            wrapped_conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            if conn:
                # Return connection to pool
                try:
                    self.pool.put(conn, block=False)
                except queue.Full:
                    # If pool is full, close the connection
                    conn.close()
    
    # Utility methods for common operations
    
    def query(self, sql: str, params: Tuple = (), session_id: str = None) -> List[Dict]:
        """Execute a query and return rows as dictionaries"""
        with self.get_connection(session_id) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            # Convert cursor results to dictionaries
            columns = [col[0] for col in cursor.description] if cursor.description else []
            results = []
            
            for row in cursor.fetchall():
                # Handle different result formats between MySQL and PostgreSQL
                if isinstance(row, tuple):
                    # Convert tuple to dict
                    results.append(dict(zip(columns, row)))
                elif hasattr(row, 'keys'):  
                    # Some drivers already return dict-like objects
                    results.append({key: row[key] for key in row.keys()})
                else:
                    # Fallback for other formats
                    results.append(dict(zip(columns, row)))
            
            return results
    
    def execute(self, sql: str, params: Tuple = (), session_id: str = None) -> int:
        """Execute a statement and return affected row count"""
        with self.get_connection(session_id) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.rowcount
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        placeholder = '%s'  # Both MySQL and PostgreSQL use %s
            
        users = self.query(
            f"SELECT * FROM users WHERE username = {placeholder}", 
            (username,)
        )
        return users[0] if users else None
    
    def get_user_permissions(self, username: str) -> List[str]:
        """Get permissions for a user"""
        placeholder = '%s'  # Both MySQL and PostgreSQL use %s
            
        permissions = self.query(
            f"SELECT permission FROM user_permissions WHERE username = {placeholder}",
            (username,)
        )
        return [p['permission'] for p in permissions]
    
    def save_session(self, session_id: str, username: str, expires_at: datetime, data: Dict) -> bool:
        """Save session data to database for persistence"""
        try:
            now = datetime.utcnow()
            placeholder = '%s'  # Both MySQL and PostgreSQL use %s
                
            if self.db_type == 'mysql':
                self.execute(
                    f"""
                    INSERT INTO sessions 
                    (session_id, username, created_at, expires_at, data) 
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ON DUPLICATE KEY UPDATE 
                    username = VALUES(username), expires_at = VALUES(expires_at), data = VALUES(data)
                    """,
                    (session_id, username, now, expires_at, json.dumps(data))
                )
            else:  # postgres
                self.execute(
                    f"""
                    INSERT INTO sessions 
                    (session_id, username, created_at, expires_at, data) 
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                    ON CONFLICT (session_id) DO UPDATE SET
                    username = EXCLUDED.username, expires_at = EXCLUDED.expires_at, data = EXCLUDED.data
                    """,
                    (session_id, username, now, expires_at, json.dumps(data))
                )
                
            return True
        except Exception as e:
            print(f"❌ Failed to save session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load session data from database"""
        now = datetime.utcnow()
        placeholder = '%s'  # Both MySQL and PostgreSQL use %s
            
        sessions = self.query(
            f"SELECT * FROM sessions WHERE session_id = {placeholder} AND expires_at > {placeholder}",
            (session_id, now)
        )
        
        if not sessions:
            return None
            
        session = sessions[0]
        try:
            session_data = json.loads(session['data'])
            return {
                'session_id': session['session_id'],
                'username': session['username'],
                'created_at': session['created_at'],
                'expires_at': session['expires_at'],
                'data': session_data
            }
        except json.JSONDecodeError:
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session data from database"""
        try:
            placeholder = '%s'  # Both MySQL and PostgreSQL use %s
            self.execute(
                f"DELETE FROM sessions WHERE session_id = {placeholder}",
                (session_id,)
            )
            return True
        except Exception:
            return False