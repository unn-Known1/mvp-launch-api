"""
Storage abstraction layer for MVP Launch API.

Provides abstract base class for storage backends (S3, GCS, local, etc.)
to allow flexible storage implementation without tight coupling to AWS S3.
"""

from abc import ABC, abstractmethod
from typing import Optional
import os


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    Implement this class to add support for different storage providers
    (S3, GCS, Azure Blob, local filesystem, etc.)
    """

    @abstractmethod
    def upload(self, file_path: str, destination: str) -> str:
        """
        Upload a file to storage.

        Args:
            file_path: Path to the local file to upload
            destination: Destination path in storage

        Returns:
            URL or path to the uploaded file
        """
        pass

    @abstractmethod
    def download(self, source: str, destination: str) -> bool:
        """
        Download a file from storage.

        Args:
            source: Source path in storage
            destination: Destination path for local file

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            path: Path to the file to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    def get_url(self, path: str, expiration_seconds: int = 3600) -> str:
        """
        Get a temporary or signed URL for accessing a file.

        Args:
            path: Path to the file
            expiration_seconds: How long the URL should be valid

        Returns:
            URL string for accessing the file
        """
        pass

    @abstractmethod
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in storage with optional prefix filter.

        Args:
            prefix: Filter files by prefix path

        Returns:
            List of file paths
        """
        pass


class S3Storage(StorageBackend):
    """
    AWS S3 storage backend implementation.
    """

    def __init__(self, bucket: str = None, region: str = None):
        self.bucket = bucket or os.getenv("S3_BUCKET", "")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None

    @property
    def client(self):
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("s3", region_name=self.region)
            except ImportError:
                raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        return self._client

    def upload(self, file_path: str, destination: str) -> str:
        """Upload file to S3."""
        try:
            self.client.upload_file(file_path, self.bucket, destination)
            return f"s3://{self.bucket}/{destination}"
        except Exception as e:
            raise RuntimeError(f"Failed to upload to S3: {e}")

    def download(self, source: str, destination: str) -> bool:
        """Download file from S3."""
        try:
            # Extract bucket and key from s3:// URI
            parts = source.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            self.client.download_file(bucket, key, destination)
            return True
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        """Delete file from S3."""
        try:
            parts = path.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            self.client.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def exists(self, path: str) -> bool:
        """Check if file exists in S3."""
        try:
            parts = path.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def get_url(self, path: str, expiration_seconds: int = 3600) -> str:
        """Get signed URL for S3 object."""
        try:
            parts = path.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiration_seconds,
            )
            return url
        except Exception as e:
            raise RuntimeError(f"Failed to generate S3 URL: {e}")

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in S3 bucket with prefix."""
        try:
            # If prefix doesn't start with bucket, add it
            if not prefix.startswith(self.bucket):
                prefix = f"{self.bucket}/{prefix}" if prefix else self.bucket

            response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            files = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    files.append(f"s3://{self.bucket}/{obj['Key']}")
            return files
        except Exception:
            return []


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend for development/testing.
    """

    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.getenv("LOCAL_STORAGE_PATH", "/tmp/mvp-storage")
        os.makedirs(self.base_path, exist_ok=True)

    def _resolve_path(self, path: str) -> str:
        """Resolve relative path to absolute path within base_path."""
        if path.startswith("/"):
            return os.path.join(self.base_path, path.lstrip("/"))
        return os.path.join(self.base_path, path)

    def upload(self, file_path: str, destination: str) -> str:
        """Upload file to local storage (copy)."""
        import shutil
        dest_path = self._resolve_path(destination)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(file_path, dest_path)
        return f"file://{dest_path}"

    def download(self, source: str, destination: str) -> bool:
        """Download file from local storage."""
        import shutil
        try:
            src_path = self._resolve_path(source)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(src_path, destination)
            return True
        except Exception:
            return False

    def delete(self, path: str) -> bool:
        """Delete file from local storage."""
        try:
            file_path = self._resolve_path(path)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception:
            return False

    def exists(self, path: str) -> bool:
        """Check if file exists in local storage."""
        return os.path.exists(self._resolve_path(path))

    def get_url(self, path: str, expiration_seconds: int = 3600) -> str:
        """Get file:// URL for local file (no expiration)."""
        return f"file://{self._resolve_path(path)}"

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in local storage."""
        import glob
        search_path = self._resolve_path(prefix)
        if not prefix:
            search_path = os.path.join(search_path, "**", "*")
        else:
            search_path = os.path.join(search_path, "*")

        files = glob.glob(search_path, recursive=True)
        return [f"file://{f}" for f in files if os.path.isfile(f)]


def get_storage_backend() -> StorageBackend:
    """
    Factory function to get the configured storage backend.

    Returns:
        StorageBackend implementation based on environment configuration
    """
    storage_type = os.getenv("STORAGE_TYPE", "local").lower()

    if storage_type == "s3":
        return S3Storage(
            bucket=os.getenv("S3_BUCKET"),
            region=os.getenv("AWS_REGION", "us-east-1"),
        )
    elif storage_type == "local":
        return LocalStorage(base_path=os.getenv("LOCAL_STORAGE_PATH"))
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


# Default export
default_storage = get_storage_backend()