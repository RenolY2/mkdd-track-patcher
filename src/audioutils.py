"""
A module that includes functionality for audio processing.
"""
import shutil
import warnings
import wave

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import audioop  # Deprecated in Python 3.11.


def conform_audio_wave(
    src_filepath: str,
    dst_filepath: str,
    max_sample_rate: int,
    max_sample_count: int,
) -> list[str]:
    with wave.open(src_filepath, 'rb') as f:
        bit_depth = f.getsampwidth() * 8
        if bit_depth not in (16, ):
            raise RuntimeError(f'Input file "{src_filepath}" has an unsupported bit depth '
                               f'({bit_depth}).')

        channel_count = f.getnchannels()
        if channel_count not in (1, 2, 4):
            raise RuntimeError(f'Input file "{src_filepath}" has an unsupported number of channels '
                               f'({channel_count}).')

        sample_rate = f.getframerate()
        sample_count = f.getnframes()

        max_duration = max_sample_count / max_sample_rate
        duration = sample_count / sample_rate

        needs_mixing = channel_count > 1
        needs_downsampling = sample_rate > max_sample_rate
        needs_truncating = duration > max_duration

        if not needs_mixing and not needs_downsampling and not needs_truncating:
            shutil.copy2(src_filepath, dst_filepath)
            return []

        data = f.readframes(sample_count)

    errors = []

    if needs_mixing:
        errors.append(f'{channel_count} channels mixed into mono')

        if channel_count == 4:
            data = audioop.tomono(data, bit_depth // 8, 1.0, 1.0)
            channel_count = 2
        if channel_count == 2:
            data = audioop.tomono(data, bit_depth // 8, 1.0, 1.0)
            channel_count = 1

    if needs_downsampling:
        errors.append(f'Audio downsampled from {sample_rate} Hz to {max_sample_rate} Hz')

        data, _state = audioop.ratecv(data, bit_depth // 8, channel_count, sample_rate,
                                      max_sample_rate, None)
        sample_rate = max_sample_rate

    if needs_truncating:
        errors.append(f'Duration truncated from {duration} seconds to {max_duration} seconds')

        max_byte_count = round(max_duration * sample_rate * (bit_depth // 8))
        data = data[:max_byte_count]

    with wave.open(dst_filepath, 'wb') as f:
        f: wave.Wave_write
        f.setsampwidth(bit_depth // 8)
        f.setnchannels(channel_count)
        f.setframerate(sample_rate)
        f.writeframes(data)

    return errors
