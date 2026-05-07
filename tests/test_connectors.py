"""
Tests for database connectors.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.base import DataSourceConfig  # noqa: E402
from connectors.encryption import decrypt_value, encrypt_value  # noqa: E402
from connectors.mysql import MySQLConnector  # noqa: E402
from connectors.postgres import PostgreSQLConnector  # noqa: E402
from connectors.store import DataSourceStore  # noqa: E402


class TestEncryption(unittest.TestCase):
    """Test credential encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "super_secret_password_123"
        encrypted = encrypt_value(plaintext)
        self.assertNotEqual(plaintext, encrypted)
        decrypted = decrypt_value(encrypted)
        self.assertEqual(plaintext, decrypted)

    def test_encrypted_values_differ(self):
        """Each encryption should produce different ciphertext (Fernet includes timestamp)."""
        plaintext = "same_password"
        enc1 = encrypt_value(plaintext)
        enc2 = encrypt_value(plaintext)
        self.assertNotEqual(enc1, enc2)
        self.assertEqual(decrypt_value(enc1), decrypt_value(enc2))


class TestDataSourceConfig(unittest.TestCase):
    """Test DataSourceConfig model."""

    def test_password_encryption_on_set(self):
        config = DataSourceConfig(
            name="test-db",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="mydb",
            username="admin",
        )
        config.password = "secret123"
        self.assertNotEqual("secret123", config.password_encrypted)
        self.assertEqual("secret123", config.password)

    def test_connection_url_postgresql(self):
        config = DataSourceConfig(
            db_type="postgresql",
            host="db.example.com",
            port=5432,
            database="production",
            username="admin",
        )
        config.password = "pass"
        url = config.to_connection_url()
        self.assertTrue(url.startswith("postgresql+psycopg2://"))
        self.assertIn("db.example.com:5432/production", url)

    def test_connection_url_mysql(self):
        config = DataSourceConfig(
            db_type="mysql",
            host="db.example.com",
            port=3306,
            database="production",
            username="root",
        )
        config.password = "pass"
        url = config.to_connection_url()
        self.assertTrue(url.startswith("mysql+pymysql://"))
        self.assertIn("db.example.com:3306/production", url)

    def test_connection_url_ssl_postgresql(self):
        config = DataSourceConfig(
            db_type="postgresql",
            host="db.example.com",
            port=5432,
            database="production",
            username="admin",
            ssl_enabled=True,
        )
        config.password = "pass"
        url = config.to_connection_url()
        self.assertIn("sslmode=require", url)


class TestDataSourceStore(unittest.TestCase):
    """Test CRUD operations for data source configurations."""

    def setUp(self):
        self.store = DataSourceStore()

    def test_create(self):
        config = DataSourceConfig(
            name="pg-test",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "secret"
        created = self.store.create(config)
        self.assertIsNotNone(created.id)
        self.assertIsNotNone(created.created_at)
        self.assertIsNotNone(created.updated_at)

    def test_get(self):
        config = DataSourceConfig(
            name="pg-test",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "secret"
        created = self.store.create(config)
        retrieved = self.store.get(created.id)
        self.assertEqual(created.id, retrieved.id)
        self.assertEqual("secret", retrieved.password)

    def test_get_not_found(self):
        self.assertIsNone(self.store.get("nonexistent-id"))

    def test_list_all(self):
        for i in range(3):
            config = DataSourceConfig(
                name=f"db-{i}",
                db_type="postgresql",
                host="localhost",
                port=5432,
                database=f"db{i}",
                username="admin",
            )
            config.password = f"secret{i}"
            self.store.create(config)
        results = self.store.list_all()
        self.assertEqual(3, len(results))

    def test_update(self):
        config = DataSourceConfig(
            name="pg-test",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "secret"
        created = self.store.create(config)
        updated = self.store.update(created.id, {"host": "newhost", "port": 3306})
        self.assertEqual("newhost", updated.host)
        self.assertEqual(3306, updated.port)

    def test_update_password(self):
        config = DataSourceConfig(
            name="pg-test",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "old_secret"
        created = self.store.create(config)
        self.store.update(created.id, {"password": "new_secret"})
        retrieved = self.store.get(created.id)
        self.assertEqual("new_secret", retrieved.password)

    def test_update_not_found(self):
        self.assertIsNone(self.store.update("nonexistent", {"host": "x"}))

    def test_delete(self):
        config = DataSourceConfig(
            name="pg-test",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "secret"
        created = self.store.create(config)
        self.assertTrue(self.store.delete(created.id))
        self.assertIsNone(self.store.get(created.id))

    def test_delete_not_found(self):
        self.assertFalse(self.store.delete("nonexistent"))


class TestConnectorFactory(unittest.TestCase):
    """Test connector creation factory."""

    def test_create_postgresql_connector(self):
        from connectors import create_connector

        config = DataSourceConfig(
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        config.password = "secret"
        connector = create_connector(config)
        self.assertIsInstance(connector, PostgreSQLConnector)
        connector.close()

    def test_create_mysql_connector(self):
        from connectors import create_connector

        config = DataSourceConfig(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
        )
        config.password = "secret"
        connector = create_connector(config)
        self.assertIsInstance(connector, MySQLConnector)
        connector.close()

    def test_create_unsupported_connector(self):
        from connectors import create_connector

        config = DataSourceConfig(
            db_type="sqlite",
            host="localhost",
            port=0,
            database="testdb",
            username="admin",
        )
        with self.assertRaises(ValueError):
            create_connector(config)


class TestPostgreSQLConnectorMocked(unittest.TestCase):
    """Test PostgreSQL connector with mocked database."""

    def setUp(self):
        self.config = DataSourceConfig(
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="admin",
        )
        self.config.password = "secret"
        self.connector = PostgreSQLConnector(self.config)

    def tearDown(self):
        self.connector.close()

    @patch.object(PostgreSQLConnector, "get_connection")
    def test_test_connection_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("PostgreSQL 15.0",)
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = self.connector.test_connection()
        self.assertTrue(result.success)
        self.assertIn("PostgreSQL 15.0", result.server_version)

    @patch.object(PostgreSQLConnector, "get_connection")
    def test_test_connection_failure(self, mock_get_conn):
        mock_get_conn.side_effect = Exception("Connection refused")
        result = self.connector.test_connection()
        self.assertFalse(result.success)
        self.assertIn("Connection refused", result.message)


class TestMySQLConnectorMocked(unittest.TestCase):
    """Test MySQL connector with mocked database."""

    def setUp(self):
        self.config = DataSourceConfig(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="testdb",
            username="root",
        )
        self.config.password = "secret"
        self.connector = MySQLConnector(self.config)

    def tearDown(self):
        self.connector.close()

    @patch.object(MySQLConnector, "get_connection")
    def test_test_connection_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("8.0.35",)
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = self.connector.test_connection()
        self.assertTrue(result.success)
        self.assertEqual("8.0.35", result.server_version)


if __name__ == "__main__":
    unittest.main()
