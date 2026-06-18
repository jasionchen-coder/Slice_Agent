from app.schemas.transcript_schema import TranscriptSegment


class TranscriptService:
    filler_words = {"嗯", "啊", "额", "呃"}

    def clean_segments(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        cleaned: list[TranscriptSegment] = []
        for segment in segments:
            text = self.clean_text(segment.text)
            if not text:
                continue
            cleaned.append(
                TranscriptSegment(
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    speaker=segment.speaker,
                    text=text,
                )
            )
        return self.merge_short_segments(cleaned)

    def clean_text(self, text: str) -> str:
        normalized = " ".join(text.split())
        for word in self.filler_words:
            normalized = normalized.replace(f"{word}{word}", word)
        return normalized.strip()

    def merge_short_segments(
        self, segments: list[TranscriptSegment], *, min_chars: int = 8
    ) -> list[TranscriptSegment]:
        if not segments:
            return []
        merged: list[TranscriptSegment] = []
        buffer = segments[0]
        for segment in segments[1:]:
            if len(buffer.text) < min_chars and segment.speaker == buffer.speaker:
                buffer = TranscriptSegment(
                    start_time=buffer.start_time,
                    end_time=segment.end_time,
                    speaker=buffer.speaker,
                    text=f"{buffer.text}{segment.text}",
                )
            else:
                merged.append(buffer)
                buffer = segment
        merged.append(buffer)
        return merged

    def offset_segments(
        self, segments: list[TranscriptSegment], *, offset_seconds: float
    ) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                start_time=segment.start_time + offset_seconds,
                end_time=segment.end_time + offset_seconds,
                speaker=segment.speaker,
                text=segment.text,
            )
            for segment in segments
        ]

    def merge_chunk_segments(
        self, chunks: list[list[TranscriptSegment]], *, overlap_tolerance: float = 1.0
    ) -> list[TranscriptSegment]:
        flattened = [segment for chunk in chunks for segment in chunk]
        flattened.sort(key=lambda segment: (segment.start_time, segment.end_time))
        merged: list[TranscriptSegment] = []
        for segment in flattened:
            if not merged:
                merged.append(segment)
                continue
            last = merged[-1]
            same_text = segment.text.strip() == last.text.strip()
            overlaps = segment.start_time <= last.end_time + overlap_tolerance
            if same_text and overlaps:
                merged[-1] = TranscriptSegment(
                    start_time=min(last.start_time, segment.start_time),
                    end_time=max(last.end_time, segment.end_time),
                    speaker=last.speaker or segment.speaker,
                    text=last.text,
                )
                continue
            if segment.end_time <= last.end_time and overlaps:
                continue
            merged.append(segment)
        return merged
