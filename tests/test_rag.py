"""RAG local: PDF → chunks → recuperação por similaridade, sem rede."""

from datetime import datetime, timezone

from app.rag.ingest import extract_text, ingest_bytes
from app.rag.retriever import build_context, retrieve
from db.client import Database, migrate

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def tiny_pdf(text: str) -> bytes:
    """PDF de uma página com um único operador Tj, suficiente para os dois leitores."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT\n/F1 11 Tf\n72 720 Td\n({safe}) Tj\nET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        output += f"{offset:010d} 00000 n \n".encode()
    output += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return output


class TestRag:
    def test_pdf_to_search(self, tmp_path):
        db = Database(str(tmp_path / "rag.db"))
        migrate(db)
        pdf = tiny_pdf("Manual PETR4: hedge com borboleta de call protege a posição contra queda moderada.")

        assert "PETR4" in extract_text(pdf, "manual.pdf")
        first = ingest_bytes(db, "manual.pdf", pdf, NOW, source="teste")
        assert first.pages == 1 and first.chunks >= 1 and first.updated is True

        again = ingest_bytes(db, "manual.pdf", pdf, NOW)
        assert again.document_id == first.document_id and again.updated is False

        found = retrieve(db, "hedge PETR4 borboleta")
        assert found and "PETR4" in found[0].content
        context = build_context(db, "proteção com borboleta")
        assert "manual.pdf" in context and "pág. 1" in context

    def test_query_without_terms_returns_nothing(self, tmp_path):
        db = Database(str(tmp_path / "empty.db"))
        migrate(db)
        assert retrieve(db, "e de os") == []
        assert build_context(db, "xyz") == ""

    def test_tables_absent_degrades_gracefully(self, tmp_path):
        from db.client import Database as PlainDatabase

        db = PlainDatabase(str(tmp_path / "no-schema.db"))
        assert retrieve(db, "PETR4") == []
