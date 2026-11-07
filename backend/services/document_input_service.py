import csv
import io
import json
from pathlib import Path
import zipfile
import yaml
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError
from pypdf.errors import PdfReadError

from fastapi import HTTPException
from pydantic import ValidationError

from schemas.inputs import InputBundle


class DocumentInputService:
    @staticmethod
    def expand(bundle: InputBundle) -> InputBundle:
        if not bundle.documents:
            return bundle
        from services.input_analysis_service import InputAnalysisService
        texts = [bundle.text] if bundle.text else []
        scenes = list(bundle.scenes)
        characters = list(bundle.characters)
        total = 0
        for document in bundle.documents:
            data = InputAnalysisService.decode(document)
            total += len(data)
            if total > 40_000_000:
                raise HTTPException(status_code=422, detail="Combined documents exceed 40 MB.")
            suffix = Path(document.name).suffix.lower()
            structured = None
            try:
                if suffix in {".txt", ".md"}:
                    text = data.decode("utf-8-sig")
                elif suffix == ".docx":
                    from docx import Document
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        if len(archive.infolist()) > 2000 or sum(item.file_size for item in archive.infolist()) > 40_000_000:
                            raise ValueError("DOCX archive expands beyond safe limits.")
                    document_data = Document(io.BytesIO(data))
                    text = "\n".join(
                        [paragraph.text for paragraph in document_data.paragraphs] +
                        ["\t".join(cell.text for cell in row.cells) for table in document_data.tables for row in table.rows]
                    )
                elif suffix == ".pdf":
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(data))
                    if reader.is_encrypted or len(reader.pages) > 100:
                        raise ValueError("PDF must be unencrypted and have at most 100 pages.")
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    if not text.strip():
                        raise ValueError("PDF has no extractable text. Scanned PDFs require OCR outside this import.")
                elif suffix in {".json", ".yaml", ".yml", ".csv"}:
                    if len(data) > 1_000_000:
                        raise ValueError("Structured documents must be at most 1 MB.")
                    decoded = data.decode("utf-8-sig")
                    if suffix == ".json":
                        structured = json.loads(decoded)
                    elif suffix in {".yaml", ".yml"}:
                        if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
                               for token in yaml.scan(decoded)):
                            raise ValueError("YAML anchors/aliases are not supported.")
                        structured = yaml.safe_load(decoded)
                    else:
                        rows = list(csv.DictReader(io.StringIO(decoded)))
                        if not rows or len(rows) > 12:
                            raise ValueError("CSV must contain 1-12 rows with headers.")
                        if "name" in rows[0]:
                            structured = {"characters": [{
                                "name": row["name"], "role": row.get("role", ""),
                                "appearance": row.get("appearance", ""), "personality": row.get("personality", ""),
                                "motivations": row.get("motivations", ""), "relationships": row.get("relationships", ""),
                                "portrait_prompt": row.get("portrait_prompt") or row.get("appearance") or row["name"],
                            } for row in rows]}
                        elif {"title", "description"} <= rows[0].keys():
                            structured = {"scenes": rows}
                        else:
                            raise ValueError("CSV requires name (characters), or title and description (scenes).")
                    if not isinstance(structured, dict) or set(structured) - {"text", "text_kind", "scenes", "characters", "title"}:
                        raise ValueError("JSON/YAML must contain text/text_kind, scenes and/or characters using the input schema.")
                    parsed = InputBundle.model_validate(structured)
                    scenes.extend(parsed.scenes)
                    characters.extend(parsed.characters)
                    text = parsed.text
                    if parsed.text_kind != "auto" and bundle.text_kind == "auto":
                        bundle = bundle.model_copy(update={"text_kind": parsed.text_kind})
                else:
                    raise ValueError("Supported documents: TXT, MD, DOCX, PDF, JSON, YAML and CSV.")
            except (ValueError, UnicodeError, zipfile.BadZipFile, ValidationError, KeyError,
                    yaml.YAMLError, PdfReadError, PackageNotFoundError, XMLSyntaxError) as error:
                raise HTTPException(status_code=422, detail=f"Invalid document {document.name}: {error}") from error
            if text:
                texts.append(text)
        try:
            return InputBundle.model_validate({
                **bundle.model_dump(), "text": "\n\n".join(texts), "scenes": scenes, "characters": characters,
            })
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=f"Combined document content exceeds input limits: {error}") from error
