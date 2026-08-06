"""
AudioClip — representa un clip de audio posicionado en el timeline.
"""
import os
import numpy as np


class AudioClip:
    def __init__(self, file_path: str, start_frame: int = 0):
        self.file_path:   str   = file_path
        self.start_frame: int   = start_frame   # frame donde empieza
        self.trim_start:  float = 0.0           # segundos recortados al inicio
        self.trim_end:    float = 0.0           # segundos recortados al final
        self.volume:      float = 1.0
        self.name:        str   = os.path.basename(file_path)

        # Waveform cacheada (lista de amplitudes normalizadas 0-1)
        self._waveform: list[float] | None = None
        self._duration: float | None = None     # duración total del archivo

    # ── Duración ──────────────────────────────────────────────────────

    def get_file_duration(self) -> float:
        """Duración total del archivo de audio en segundos."""
        if self._duration is not None:
            return self._duration
        try:
            import wave, contextlib
            with contextlib.closing(wave.open(self.file_path, 'r')) as f:
                frames = f.getnframes()
                rate   = f.getframerate()
                self._duration = frames / float(rate)
                return self._duration
        except Exception:
            pass
        # Fallback con mutagen si está disponible
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(self.file_path)
            if audio is not None:
                self._duration = float(audio.info.length)
                return self._duration
        except Exception:
            pass
        self._duration = 0.0
        return 0.0

    def get_play_duration(self) -> float:
        """Duración efectiva del clip (después de recortes)."""
        total = self.get_file_duration()
        return max(0.0, total - self.trim_start - self.trim_end)

    def get_end_frame(self, fps: int) -> int:
        """Frame donde termina el clip."""
        return self.start_frame + int(self.get_play_duration() * fps)

    # ── Waveform ──────────────────────────────────────────────────────

    def get_waveform(self, samples: int = 200) -> list[float]:
        """
        Devuelve lista de `samples` amplitudes normalizadas [0, 1].
        Se cachea tras el primer cálculo.
        """
        if self._waveform is not None and len(self._waveform) == samples:
            return self._waveform

        try:
            import wave, struct, contextlib
            with contextlib.closing(wave.open(self.file_path, 'r')) as f:
                n_channels = f.getnchannels()
                sampwidth  = f.getsampwidth()
                n_frames   = f.getnframes()
                raw        = f.readframes(n_frames)

            fmt = {1: 'b', 2: 'h', 4: 'i'}.get(sampwidth, 'h')
            data = np.frombuffer(raw, dtype=np.dtype(fmt))
            if n_channels > 1:
                data = data[::n_channels]   # mono

            # Normalizar
            max_val = max(abs(data.max()), abs(data.min()), 1)
            data    = data.astype(np.float32) / max_val

            # Reducir a `samples` puntos
            chunk = max(1, len(data) // samples)
            waveform = []
            for i in range(samples):
                segment = data[i*chunk:(i+1)*chunk]
                waveform.append(float(np.abs(segment).mean()) if len(segment) else 0.0)

            self._waveform = waveform
            return waveform

        except Exception:
            self._waveform = [0.0] * samples
            return self._waveform

    # ── Serialización ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "file_path":   self.file_path,
            "start_frame": self.start_frame,
            "trim_start":  self.trim_start,
            "trim_end":    self.trim_end,
            "volume":      self.volume,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AudioClip":
        clip = cls(d["file_path"], d.get("start_frame", 0))
        clip.trim_start = d.get("trim_start", 0.0)
        clip.trim_end   = d.get("trim_end",   0.0)
        clip.volume     = d.get("volume",     1.0)
        return clip