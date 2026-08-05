"""add document versions and content hashes"""

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20260805_04"
down_revision = "20260804_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("index_error", sa.String(length=500), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_sha256", "document_versions", ["sha256"])

    connection = op.get_bind()
    uploads = Path(__file__).resolve().parents[2] / "data" / "uploads"
    documents = connection.execute(
        sa.text(
            "SELECT id, original_name, stored_name, media_type, size_bytes, status, "
            "index_error, indexed_at, chunk_count, created_at FROM documents"
        )
    ).mappings()
    version_table = sa.table(
        "document_versions",
        sa.column("id", sa.Uuid()),
        sa.column("document_id", sa.Uuid()),
        sa.column("version", sa.Integer()),
        sa.column("original_name", sa.String()),
        sa.column("stored_name", sa.String()),
        sa.column("media_type", sa.String()),
        sa.column("size_bytes", sa.Integer()),
        sa.column("sha256", sa.String()),
        sa.column("status", sa.String()),
        sa.column("index_error", sa.String()),
        sa.column("indexed_at", sa.DateTime(timezone=True)),
        sa.column("chunk_count", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for document in documents:
        document_id = document["id"]
        if not isinstance(document_id, uuid.UUID):
            document_id = uuid.UUID(str(document_id))
        path = uploads / document["stored_name"]
        digest = hashlib.sha256(
            path.read_bytes() if path.is_file() else document["stored_name"].encode()
        ).hexdigest()
        indexed_at = document["indexed_at"]
        created_at = document["created_at"]
        if isinstance(indexed_at, str):
            indexed_at = datetime.fromisoformat(indexed_at)
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        connection.execute(
            version_table.insert().values(
                id=document_id,
                document_id=document_id,
                version=1,
                original_name=document["original_name"],
                stored_name=document["stored_name"],
                media_type=document["media_type"],
                size_bytes=document["size_bytes"],
                sha256=digest,
                status=document["status"],
                index_error=document["index_error"],
                indexed_at=indexed_at,
                chunk_count=document["chunk_count"],
                created_at=created_at,
            )
        )

    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("active_version_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE documents SET active_version_id = id")
    with op.batch_alter_table("documents") as batch:
        batch.create_foreign_key(
            "fk_documents_active_version_id",
            "document_versions",
            ["active_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "document_chunks_new",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "position"),
    )
    op.execute(
        "INSERT INTO document_chunks_new (id, version_id, position, page_number, content) "
        "SELECT id, document_id, position, page_number, content FROM document_chunks"
    )
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.rename_table("document_chunks_new", "document_chunks")
    op.create_index("ix_document_chunks_version_id", "document_chunks", ["version_id"])

    with op.batch_alter_table("documents") as batch:
        batch.drop_column("stored_name")
        batch.drop_column("media_type")
        batch.drop_column("size_bytes")
        batch.drop_column("status")
        batch.drop_column("index_error")
        batch.drop_column("indexed_at")
        batch.drop_column("chunk_count")


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("stored_name", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("media_type", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("index_error", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("chunk_count", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE documents SET "
        "stored_name = (SELECT stored_name FROM document_versions WHERE id = active_version_id), "
        "media_type = (SELECT media_type FROM document_versions WHERE id = active_version_id), "
        "size_bytes = (SELECT size_bytes FROM document_versions WHERE id = active_version_id), "
        "status = (SELECT status FROM document_versions WHERE id = active_version_id), "
        "index_error = (SELECT index_error FROM document_versions WHERE id = active_version_id), "
        "indexed_at = (SELECT indexed_at FROM document_versions WHERE id = active_version_id), "
        "chunk_count = (SELECT chunk_count FROM document_versions WHERE id = active_version_id)"
    )
    with op.batch_alter_table("documents") as batch:
        batch.alter_column("stored_name", nullable=False)
        batch.alter_column("media_type", nullable=False)
        batch.alter_column("size_bytes", nullable=False)
        batch.alter_column("status", nullable=False)
        batch.alter_column("chunk_count", nullable=False)
        batch.create_unique_constraint("uq_documents_stored_name", ["stored_name"])

    op.create_table(
        "document_chunks_old",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "position"),
    )
    op.execute(
        "INSERT INTO document_chunks_old (id, document_id, position, page_number, content) "
        "SELECT document_chunks.id, document_versions.document_id, document_chunks.position, "
        "document_chunks.page_number, document_chunks.content FROM document_chunks "
        "JOIN document_versions ON document_versions.id = document_chunks.version_id "
        "JOIN documents ON documents.active_version_id = document_versions.id"
    )
    op.drop_index("ix_document_chunks_version_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.rename_table("document_chunks_old", "document_chunks")
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_active_version_id", type_="foreignkey")
        batch.drop_column("active_version_id")
    op.drop_index("ix_document_versions_sha256", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
