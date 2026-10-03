"""Local spectral input axes for observer selection; no scientific fit."""
from pathlib import Path
from vsora_formats.spectral import load_spectral


def spectral_input(workspace,value):
    path=Path(value);path=path if path.is_absolute() else Path(workspace)/path
    if path.suffix.lower()!='.npz' or not path.is_file():
        raise ValueError('指定したWSL側の相関NPZが見つかりません。')
    return path.resolve()


def input_axes(workspace,value):
    path=spectral_input(workspace,value);before=path.stat();data=load_spectral(path);after=path.stat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('入力が読込中に変更されました。保存済みのファイルを選んでください。')
    metadata=data.get('metadata',{})
    if not isinstance(metadata,dict):raise ValueError('spectral metadata must be a mapping')
    return {'times_s':data['times_s'].tolist(),'frequencies_hz':data['frequencies_hz'].tolist(),
            'time_origin_utc':metadata.get('time_origin_utc'),
            'visibility_unit':metadata.get('visibility_unit'),
            'diagnostic_pair_counts_available':'valid_fft_count' in data}
