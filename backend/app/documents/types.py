from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class NormalizedPage:
    number: int
    text: str
    extraction_method: str
    visual_context: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TextChunk:
    ordinal: int
    page_start: int
    page_end: int
    text: str
    section: str | None = None
